from typing import Any, Awaitable, Callable, Dict
import logging
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser, Message, CallbackQuery

import redis.exceptions
import sqlalchemy.exc
import asyncpg.exceptions

from mc_ping_bot.services.maintenance import MaintenanceService
from mc_ping_bot.services.i18n import i18n_service, current_locale
from mc_ping_bot.bot.middlewares.i18n import SUPPORTED_LOCALES, DEFAULT_LOCALE

logger = logging.getLogger(__name__)

class MaintenanceMiddleware(BaseMiddleware):
    def __init__(self, maintenance_service: MaintenanceService):
        self.maintenance = maintenance_service
        # Define connection exceptions we should catch
        self.db_exceptions = (
            redis.exceptions.ConnectionError,
            redis.exceptions.TimeoutError,
            sqlalchemy.exc.OperationalError,
            asyncpg.exceptions.CannotConnectNowError,
            asyncpg.exceptions.ConnectionDoesNotExistError,
        )

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        tg_user: TgUser = data.get("event_from_user")
        
        # If no user, or user is admin, we proceed, but we still catch errors.
        is_admin = tg_user and tg_user.id == self.maintenance.admin_id
        
        if self.maintenance.is_maintenance() and not is_admin:
            if tg_user and self.maintenance.can_notify_user(tg_user.id):
                await self._send_maintenance_message(event, tg_user)
            return  # Stop propagation
            
        try:
            return await handler(event, data)
        except self.db_exceptions as e:
            logger.error(f"MaintenanceMiddleware caught DB error: {type(e).__name__}: {e}")
            await self.maintenance.trigger_auto_maintenance(e)
            
            # Since we just entered maintenance mode due to a crash during handler execution,
            # we should notify the user that their request failed due to maintenance.
            if tg_user and not is_admin and self.maintenance.can_notify_user(tg_user.id):
                await self._send_maintenance_message(event, tg_user)
            
            # Don't re-raise, we handled it gracefully.
            return

    async def _send_maintenance_message(self, event: TelegramObject, tg_user: TgUser):
        """Sends the localized maintenance message without touching the DB."""
        locale = tg_user.language_code
        if locale and locale[:2] in SUPPORTED_LOCALES:
            locale = locale[:2]
        else:
            locale = DEFAULT_LOCALE
            
        # Temporarily set the locale in contextvars
        token = current_locale.set(locale)
        try:
            msg = i18n_service.get("msg-maintenance")
            
            # We need to answer depending on the event type (Message or CallbackQuery)
            if isinstance(event, Message):
                await event.answer(msg)
            elif isinstance(event, CallbackQuery):
                await event.answer(msg, show_alert=True)
            elif hasattr(event, "message") and isinstance(event.message, Message):
                await event.message.answer(msg)
        except Exception as e:
            logger.error(f"Failed to send maintenance message to {tg_user.id}: {e}")
        finally:
            current_locale.reset(token)
