from aiogram import Router, F
from aiogram.filters import Command, BaseFilter
from aiogram.types import Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mc_ping_bot.db.models import MonitoredServer, User, Ticket
from mc_ping_bot.config import config

router = Router()


class AdminFilter(BaseFilter):
    """
    Асинхронный фильтр для проверки прав администратора.
    Разрешает прохождение запроса только если role == 'admin' или действие происходит в админском чате.
    """
    async def __call__(self, message: Message, session: AsyncSession) -> bool:
        if config.admin_chat_id and message.chat.id == config.admin_chat_id:
            return True
            
        user = await session.scalar(select(User).where(User.tg_id == message.from_user.id))
        return user is not None and user.role == "admin"

# Подключаем фильтр ко всем хендлерам внутри роутера
router.message.filter(AdminFilter())


@router.message(Command("moder"))
async def cmd_moder(message: Message, session: AsyncSession):
    """
    Выводит базовую статистику по системе (агрегация через базу данных).
    """
    # COUNT агрегации по пользователям
    users_count = await session.scalar(select(func.count(User.id)))
    
    # COUNT агрегации по серверам на мониторинге
    monitors_count = await session.scalar(select(func.count(MonitoredServer.id)))
    
    text = (
        "👑 <b>Панель Модератора</b>\n\n"
        f"👥 Зарегистрировано пользователей: <code>{users_count}</code>\n"
        f"🖥 Активных мониторингов серверов: <code>{monitors_count}</code>\n"
        f"<i>(Тикеты обрабатываются в админском чате)</i>"
    )
    
    await message.answer(text, parse_mode="HTML")


@router.message(F.chat.id == config.admin_chat_id, F.reply_to_message)
async def admin_reply_handler(message: Message, session: AsyncSession):
    """
    Обработчик ответов модераторов в админском чате.
    Ищет тикет по ID сообщения (на которое ответили) и пересылает ответ пользователю.
    """
    target_msg_id = message.reply_to_message.message_id
    
    # Ищем тикет, в котором массив admin_message_ids содержит target_msg_id
    ticket = await session.scalar(
        select(Ticket).where(Ticket.admin_message_ids.any(target_msg_id))
    )
    
    if not ticket:
        # Если тикет не найден (возможно, это ответ на другое сообщение), просто игнорируем
        return
        
    try:
        # Отправляем ответ пользователю
        await message.copy_to(ticket.user_id)
        
        # Реакция на сообщение модератора для подтверждения доставки
        await message.react([{"type": "emoji", "emoji": "👍"}])
    except Exception as e:
        await message.reply(f"❌ Ошибка отправки пользователю:\n<code>{e}</code>", parse_mode="HTML")
