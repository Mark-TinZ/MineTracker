from typing import Any, Awaitable, Callable, Dict
import json

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser
from sqlalchemy import select

from mc_ping_bot.db.models import User
from mc_ping_bot.services.cache import RedisCacheManager
from mc_ping_bot.services.i18n import current_locale, i18n_service

SUPPORTED_LOCALES = ["ru", "en"]
DEFAULT_LOCALE = "en"


class LanguageMiddleware(BaseMiddleware):
    """
    Определяет язык пользователя и устанавливает его в contextvars (current_locale).
    Порядок: Redis -> PostgreSQL -> Telegram User -> Fallback (en).
    Работает как Outer Middleware (до фильтров).
    """
    def __init__(self, cache_manager: RedisCacheManager, sessionmaker):
        self.cache_manager = cache_manager
        self.sessionmaker = sessionmaker

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Извлекаем пользователя Telegram из события
        tg_user: TgUser = data.get("event_from_user")
        if not tg_user:
            return await handler(event, data)

        tg_id = tg_user.id
        locale = await self.cache_manager.get_user_lang(tg_id)

        if not locale:
            # Проверяем в БД
            async with self.sessionmaker() as session:
                user = await session.scalar(select(User).where(User.tg_id == tg_id))
                if user and user.lang:
                    locale = user.lang
                else:
                    # Новый пользователь или язык не установлен. Берем из TG, применяем фолбэк.
                    tg_lang = tg_user.language_code
                    if tg_lang and tg_lang[:2] in SUPPORTED_LOCALES:
                        locale = tg_lang[:2]
                    else:
                        locale = DEFAULT_LOCALE
                        
            # Кэшируем результат, даже если юзер не в БД (он скоро зарегистрируется)
            await self.cache_manager.set_user_lang(tg_id, locale)
            
        # Устанавливаем в contextvars для текущей таски
        current_locale.set(locale)
        data["locale"] = locale
        
        return await handler(event, data)


class I18nMiddleware(BaseMiddleware):
    """
    Внедряет инстанс переводчика в хендлеры (как аргумент i18n).
    Работает как Inner Middleware.
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Передаем сам сервис I18n. Метод get() внутри сам посмотрит в current_locale.
        data["i18n"] = i18n_service
        return await handler(event, data)
