from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mc_ping_bot.db.models import MonitoredServer, User

router = Router()


class AdminFilter:
    """
    Асинхронный фильтр для проверки прав администратора.
    Разрешает прохождение запроса только если role == 'admin'.
    """
    async def __call__(self, message: Message, session: AsyncSession) -> bool:
        user = await session.scalar(select(User).where(User.tg_id == message.from_user.id))
        return user is not None and user.role == "admin"

# Подключаем фильтр ко всем хендлерам внутри роутера
router.message.filter(AdminFilter())


def get_admin_kb() -> InlineKeyboardMarkup:
    """Генерация клавиатуры с тикетами."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎫 Тикеты (Открытые)", callback_data="tickets_open"),
            InlineKeyboardButton(text="🎫 Тикеты (Закрытые)", callback_data="tickets_closed")
        ]
    ])


@router.message(Command("moder"))
async def cmd_moder(message: Message, session: AsyncSession):
    """
    Выводит базовую статистику по системе (агрегация через базу данных).
    """
    # COUNT агрегации по пользователям
    users_count = await session.scalar(select(func.count(User.id)))
    
    # COUNT агрегации по серверам на мониторинге (сущность Трекер / MonitoredServer)
    monitors_count = await session.scalar(select(func.count(MonitoredServer.id)))
    
    text = (
        "👑 <b>Панель Модератора</b>\n\n"
        f"👥 Зарегистрировано пользователей: <code>{users_count}</code>\n"
        f"🖥 Активных мониторингов серверов: <code>{monitors_count}</code>\n"
    )
    
    await message.answer(text, reply_markup=get_admin_kb(), parse_mode="HTML")
