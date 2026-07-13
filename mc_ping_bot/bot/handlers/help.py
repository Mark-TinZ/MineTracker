from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from mc_ping_bot.bot.states import TicketStates

router = Router()
router.message.filter(F.chat.type == "private")


def get_help_kb() -> InlineKeyboardMarkup:
    """Клавиатура раздела помощи."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛠 Не работает мониторинг", callback_data="help_monitoring")],
        [InlineKeyboardButton(text="🔌 Проблема с добавлением", callback_data="help_adding")],
        [InlineKeyboardButton(text="🎫 Создать тикет", callback_data="create_ticket")]
    ])


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Главное меню помощи."""
    text = (
        "💡 <b>Раздел Помощи</b>\n\n"
        "Если у вас возникли трудности с использованием бота, выберите "
        "категорию проблемы ниже или создайте тикет для обращения к разработчикам."
    )
    await message.answer(text, reply_markup=get_help_kb(), parse_mode="HTML")


@router.callback_query(F.data.in_({"help_monitoring", "help_adding"}))
async def cb_help_articles(call: CallbackQuery):
    """Мини-статьи помощи."""
    if call.data == "help_monitoring":
        await call.answer("Мониторинг может не обновляться, если бот не имеет прав администратора в группе.", show_alert=True)
    else:
        await call.answer("Убедитесь, что IP-адрес введен корректно и сервер отвечает на пинг-запросы (query=true).", show_alert=True)


@router.callback_query(F.data == "create_ticket")
async def cb_create_ticket(call: CallbackQuery, state: FSMContext):
    """Переход в FSM-состояние написания тикета."""
    await call.message.edit_text(
        "📝 <b>Создание тикета</b>\n\n"
        "Пожалуйста, подробно опишите вашу проблему в одном сообщении. "
        "При необходимости прикрепите фото или скриншот.",
        parse_mode="HTML"
    )
    await state.set_state(TicketStates.waiting_for_message)
    await call.answer()


@router.message(TicketStates.waiting_for_message)
async def process_ticket_message(message: Message, state: FSMContext, session: AsyncSession, album: list = None):
    """Обработчик входящего сообщения для тикета."""
    from mc_ping_bot.config import config
    from mc_ping_bot.db.models import Ticket
    
    if not config.admin_chat_id:
        await message.answer("⚠️ Сервис модерации временно недоступен (не настроен admin_chat_id).")
        await state.clear()
        return

    username = message.from_user.username or "Нет юзернейма"
    header_text = (
        f"🎫 <b>Новый тикет</b>\n"
        f"👤 От: @{username} (ID: <code>{message.from_user.id}</code>)\n"
    )
    
    try:
        header_msg = await message.bot.send_message(config.admin_chat_id, header_text, parse_mode="HTML")
        admin_message_ids = [header_msg.message_id]
        
        # Копируем контент
        if album:
            # Используем copy_messages, чтобы телеграм склеил их обратно в альбом
            message_ids = [msg.message_id for msg in album]
            copied_messages = await message.bot.copy_messages(
                chat_id=config.admin_chat_id,
                from_chat_id=message.chat.id,
                message_ids=message_ids
            )
            for m_id in copied_messages:
                admin_message_ids.append(m_id.message_id)
        else:
            copied = await message.copy_to(config.admin_chat_id)
            admin_message_ids.append(copied.message_id)
            
        # Сохраняем в БД
        ticket = Ticket(
            user_id=message.from_user.id,
            admin_message_ids=admin_message_ids,
            status="open"
        )
        session.add(ticket)
        await session.commit()
        
        await message.answer(
            "✅ <b>Тикет успешно создан и передан модераторам!</b>\n\n"
            "Ожидайте ответа, он придет прямо в этот чат.",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer("❌ Произошла ошибка при отправке тикета. Попробуйте позже.")
        print(f"Ticket Error: {e}")
        
    await state.clear()

