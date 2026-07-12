from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mc_ping_bot.db.models import Chat, MonitoredServer

router = Router()


async def is_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Проверка прав администратора в чате."""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ["administrator", "creator"]
    except Exception:
        return False


def get_config_kb(tracker: MonitoredServer) -> InlineKeyboardMarkup:
    """Динамическая клавиатура настроек трекера на основе флагов БД."""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{'✅' if tracker.show_motd else '❌'} Показывать MOTD",
            callback_data=f"cfg_motd_{tracker.id}"
        )],
        [InlineKeyboardButton(
            text=f"{'✅' if tracker.show_players else '❌'} Показывать Игроков",
            callback_data=f"cfg_players_{tracker.id}"
        )],
        [InlineKeyboardButton(
            text=f"{'✅' if tracker.show_tps else '❌'} Показывать TPS",
            callback_data=f"cfg_tps_{tracker.id}"
        )],
        [InlineKeyboardButton(
            text=f"{'▶️ Возобновить мониторинг' if tracker.is_paused else '⏸ Поставить на паузу'}",
            callback_data=f"cfg_pause_{tracker.id}"
        )]
    ])
    return kb


@router.message(Command("configuration"))
async def cmd_configuration(message: Message, session: AsyncSession, bot: Bot):
    """Открывает меню настроек трекера для данного чата."""
    if message.chat.type not in ["group", "supergroup"]:
        await message.answer("⚠️ Команда конфигурации предназначена только для групповых чатов.")
        return
        
    if not await is_admin(bot, message.chat.id, message.from_user.id):
        await message.answer("⚠️ Изменять конфигурацию могут только администраторы чата.")
        return

    chat = await session.scalar(select(Chat).where(Chat.tg_chat_id == message.chat.id))
    if not chat:
        await message.answer("❌ Трекер в этом чате не настроен. Сначала используйте /set_chat_server.")
        return
        
    # Берем первый трекер (в рамках бесплатного тарифа он один на чат)
    trackers = await session.scalars(select(MonitoredServer).where(MonitoredServer.chat_id == chat.id))
    tracker = trackers.first()
    if not tracker:
        await message.answer("❌ В этом чате нет активных серверов на мониторинге.")
        return

    text = "⚙️ <b>Настройки мониторинга</b>\n\nИспользуйте кнопки ниже для переключения флагов отображения в закрепленном сообщении:"
    await message.answer(text, reply_markup=get_config_kb(tracker), parse_mode="HTML")


@router.callback_query(F.data.startswith("cfg_"))
async def cb_configuration(call: CallbackQuery, session: AsyncSession, bot: Bot):
    """Обработчик нажатий на кнопки конфигурации (Toggle)."""
    # Защита от рядовых пользователей
    if not await is_admin(bot, call.message.chat.id, call.from_user.id):
        await call.answer("⚠️ Только администраторы могут менять настройки.", show_alert=True)
        return

    parts = call.data.split("_")
    action = parts[1] # motd, players, tps, pause
    tracker_id = int(parts[2])

    tracker = await session.scalar(select(MonitoredServer).where(MonitoredServer.id == tracker_id))
    if not tracker:
        await call.answer("❌ Трекер не найден или удален.")
        return

    # Toggle логика
    if action == "motd":
        tracker.show_motd = not tracker.show_motd
    elif action == "players":
        tracker.show_players = not tracker.show_players
    elif action == "tps":
        tracker.show_tps = not tracker.show_tps
    elif action == "pause":
        tracker.is_paused = not tracker.is_paused

    await session.commit()
    
    # Мгновенно обновляем UI кнопок
    await call.message.edit_reply_markup(reply_markup=get_config_kb(tracker))
    await call.answer("✅ Настройки обновлены!")
