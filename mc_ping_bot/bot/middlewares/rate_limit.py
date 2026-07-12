from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from redis.asyncio import Redis


class RateLimitMiddleware(BaseMiddleware):
    """
    Middleware для ограничения частоты запросов от одного пользователя.
    Защищает бота от спама ресурсоемкими командами и Callback-кнопками.
    """

    def __init__(self, redis: Redis, rate_limit: int = 30):
        self.redis = redis
        self.rate_limit = rate_limit
        # Список команд, на которые распространяется лимит (O(1) поиск через множество)
        self.heavy_commands = {"/info", "/players", "/ping"}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        
        user_id = None
        is_heavy = False

        # Обработка текстовых сообщений
        if isinstance(event, Message):
            if event.text and event.from_user:
                user_id = event.from_user.id
                
                # Разделяем текст по пробелам и берем первое слово
                first_word = event.text.split()[0]
                
                # Отсекаем упоминание бота, например /info@bot_name -> /info
                command_clean = first_word.split("@")[0]
                
                # Строго проверяем точное совпадение
                if command_clean in self.heavy_commands:
                    is_heavy = True

        # Обработка Inline-кнопок (CallbackQuery)
        elif isinstance(event, CallbackQuery):
            if event.data and event.from_user:
                user_id = event.from_user.id
                
                # Проверяем коллбеки на обновление (или другие тяжелые действия)
                if event.data.startswith("refresh_"):
                    is_heavy = True

        # Проверка лимитов для тяжелых действий
        if is_heavy and user_id is not None:
            key = f"rate_limit:{user_id}"
            
            # Атомарная установка: nx=True вернет True, если ключа не было и он установлен
            is_set = await self.redis.set(name=key, value="1", ex=self.rate_limit, nx=True)
            
            if not is_set:
                # Ключ уже существует, значит лимит превышен.
                # Только в этом случае запрашиваем TTL.
                ttl = await self.redis.ttl(key)
                
                # На случай гонки (если ключ истек между set nx и ttl, ttl вернет -2)
                wait_time = ttl if ttl > 0 else 1
                
                msg_text = f"⏳ Пожалуйста, подождите {wait_time} секунд перед следующим запросом."
                
                if isinstance(event, Message):
                    await event.answer(msg_text)
                elif isinstance(event, CallbackQuery):
                    await event.answer(msg_text, show_alert=True)
                    
                # Прерываем обработку (handler не вызывается)
                return

        # Передаем управление дальше
        return await handler(event, data)
