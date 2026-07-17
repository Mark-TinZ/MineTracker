import logging
import traceback
from aiogram import Router
from aiogram.types import ErrorEvent
from mc_ping_bot.services.i18n import I18n

logger = logging.getLogger(__name__)
error_router = Router()

@error_router.errors()
async def global_error_handler(event: ErrorEvent, i18n: I18n):
    # 1. Достаем контекст
    update = event.update
    exception = event.exception
    
    # Пытаемся понять, кто вызвал ошибку
    user_id = None
    username = None
    chat_id = None
    action_type = "Unknown"
    action_payload = None

    if update.message:
        user_id = update.message.from_user.id
        username = update.message.from_user.username
        chat_id = update.message.chat.id
        action_type = "Message"
        action_payload = update.message.text
    elif update.callback_query:
        user_id = update.callback_query.from_user.id
        username = update.callback_query.from_user.username
        chat_id = update.callback_query.message.chat.id
        action_type = "CallbackQuery"
        action_payload = update.callback_query.data
        
    # 2. Формируем подробный дебаг-лог
    tb_str = ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))
    
    log_msg = (
        f"🔥 CRITICAL ERROR ENCOUNTERED 🔥\n"
        f"Type: {type(exception).__name__}\n"
        f"Message: {str(exception)}\n"
        f"User ID: {user_id} (@{username})\n"
        f"Chat ID: {chat_id}\n"
        f"Trigger Type: {action_type}\n"
        f"Payload: {action_payload}\n"
        f"Traceback:\n{tb_str}"
    )
    
    logger.error(log_msg)

    # 3. Отправляем юзеру утешительное сообщение
    try:
        error_text = i18n.get("msg-internal-error")
    except Exception:
        error_text = "Oops! Something went wrong on our side. The developers have been notified."

    try:
        if update.message:
            await update.message.answer(error_text)
        elif update.callback_query:
             await update.callback_query.message.answer(error_text)
             await update.callback_query.answer() # Снимаем часики загрузки с кнопки
    except Exception as send_err:
         logger.error(f"Failed to send error notification to user {user_id}: {send_err}")
         
    return True # Говорим Aiogram, что ошибка обработана
