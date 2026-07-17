from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from mc_ping_bot.bot.states import TicketStates
from mc_ping_bot.services.i18n import I18n
from mc_ping_bot.db.models import User

router = Router()


def get_help_main_kb(i18n: I18n) -> InlineKeyboardMarkup:
    """Главная клавиатура раздела помощи."""
    builder = InlineKeyboardBuilder()
    builder.button(text=i18n.get("btn-info"), callback_data="bot_info")
    builder.button(text=i18n.get("btn-features"), callback_data="bot_features")
    builder.button(text=i18n.get("btn-instruction"), callback_data="help_instruction")
    builder.button(text=i18n.get("btn-commands"), callback_data="help_commands")
    builder.button(text=i18n.get("btn-support"), callback_data="help_support")
    builder.adjust(2, 1, 2)
    return builder.as_markup()


def get_help_instruction_kb(i18n: I18n) -> InlineKeyboardMarkup:
    """Клавиатура раздела инструкций."""
    builder = InlineKeyboardBuilder()
    builder.button(text=i18n.get("btn-instr-info"), callback_data="help_instr_info")
    builder.button(text=i18n.get("btn-instr-add"), callback_data="help_instr_add")
    builder.button(text=i18n.get("btn-instr-track"), callback_data="help_instr_track")
    builder.button(text=i18n.get("btn-instr-track-multi"), callback_data="help_instr_track_multi")
    builder.button(text=i18n.get("btn-back"), callback_data="help_back")
    builder.adjust(1)
    return builder.as_markup()


def get_help_support_kb(i18n: I18n) -> InlineKeyboardMarkup:
    """Клавиатура раздела частых проблем."""
    builder = InlineKeyboardBuilder()
    builder.button(text=i18n.get("btn-help-info"), callback_data="help_support_info")
    builder.button(text=i18n.get("btn-help-add"), callback_data="help_support_add")
    builder.button(text=i18n.get("btn-help-track"), callback_data="help_support_track")
    builder.button(text=i18n.get("btn-back"), callback_data="help_back")
    builder.adjust(1)
    return builder.as_markup()


def get_help_support_item_kb(i18n: I18n, instr_callback: str = None) -> InlineKeyboardMarkup:
    """Клавиатура для конкретной проблемы с кнопкой перехода на инструкцию."""
    builder = InlineKeyboardBuilder()
    if instr_callback:
        if instr_callback == "help_instr_add":
            btn_text = i18n.get("btn-instr-add")
        elif instr_callback == "help_instr_track":
            btn_text = i18n.get("btn-instr-track")
        elif instr_callback == "help_instr_info":
            btn_text = i18n.get("btn-instr-info")
        else:
            btn_text = i18n.get("btn-instruction")
            
        builder.button(text=btn_text, callback_data=instr_callback)
    
    builder.button(text=i18n.get("btn-ticket"), callback_data="create_ticket")
    builder.button(text=i18n.get("btn-back"), callback_data="help_support")
    builder.adjust(1)
    return builder.as_markup()


def get_back_kb(i18n: I18n, back_to: str = "help_back") -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой назад."""
    builder = InlineKeyboardBuilder()
    builder.button(text=i18n.get("btn-back"), callback_data=back_to)
    return builder.as_markup()


@router.message(Command("help"))
async def cmd_help(message: Message, i18n: I18n):
    """Главное меню помощи."""
    if message.chat.type != "private":
        bot_info = await message.bot.get_me()
        await message.answer(
            i18n.get("msg-help-group", bot_username=bot_info.username), 
            parse_mode="HTML"
        )
        return
        
    await message.answer(i18n.get("msg-help-main"), reply_markup=get_help_main_kb(i18n), parse_mode="HTML")


@router.callback_query(F.data == "help_back")
async def cb_help_back(call: CallbackQuery, i18n: I18n):
    # Если мы возвращаемся из сообщения с картинкой, нужно удалить старое и отправить новое текстовое
    if call.message.photo:
        await call.message.delete()
        await call.message.answer(i18n.get("msg-help-main"), reply_markup=get_help_main_kb(i18n), parse_mode="HTML")
    else:
        await call.message.edit_text(i18n.get("msg-help-main"), reply_markup=get_help_main_kb(i18n), parse_mode="HTML")


@router.callback_query(F.data == "bot_info")
async def cb_bot_info(call: CallbackQuery, i18n: I18n):
    if call.message.photo:
        await call.message.delete()
        await call.message.answer(i18n.get("msg-info"), reply_markup=get_back_kb(i18n), parse_mode="HTML")
    else:
        await call.message.edit_text(i18n.get("msg-info"), reply_markup=get_back_kb(i18n), parse_mode="HTML")


@router.callback_query(F.data == "bot_features")
async def cb_bot_features(call: CallbackQuery, i18n: I18n):
    if call.message.photo:
        await call.message.delete()
        await call.message.answer(i18n.get("msg-features"), reply_markup=get_back_kb(i18n), parse_mode="HTML")
    else:
        await call.message.edit_text(i18n.get("msg-features"), reply_markup=get_back_kb(i18n), parse_mode="HTML")


@router.callback_query(F.data == "help_instruction")
async def cb_help_instruction(call: CallbackQuery, i18n: I18n):
    text = f"📖 <b>{i18n.get('btn-instruction')}</b>"
    if call.message.photo:
        await call.message.delete()
        await call.message.answer(text, reply_markup=get_help_instruction_kb(i18n), parse_mode="HTML")
    else:
        await call.message.edit_text(text, reply_markup=get_help_instruction_kb(i18n), parse_mode="HTML")


@router.callback_query(F.data.startswith("help_instr_"))
async def cb_help_instr_item(call: CallbackQuery, i18n: I18n):
    item = call.data
    text = ""
    
    if item == "help_instr_info":
        text = i18n.get("msg-instr-info-text")
    elif item == "help_instr_add":
        text = i18n.get("msg-instr-add-text")
    elif item == "help_instr_track":
        text = i18n.get("msg-instr-track-text")
    elif item == "help_instr_track_multi":
        text = i18n.get("msg-instr-track-multi-text")
        
    if item in ["help_instr_add", "help_instr_track"]:
        # Для этих пунктов схема требует отправки фото
        await call.message.delete()
        await call.message.answer_photo(
            photo="https://placehold.co/600x400.png?text=Placeholder",
            caption=text,
            reply_markup=get_back_kb(i18n, "help_instruction"),
            parse_mode="HTML"
        )
    else:
        if call.message.photo:
            await call.message.delete()
            await call.message.answer(text, reply_markup=get_back_kb(i18n, "help_instruction"), parse_mode="HTML")
        else:
            await call.message.edit_text(text, reply_markup=get_back_kb(i18n, "help_instruction"), parse_mode="HTML")


@router.callback_query(F.data == "help_support")
async def cb_help_support(call: CallbackQuery, i18n: I18n):
    text = f"🆘 <b>{i18n.get('btn-support')}</b>"
    if call.message.photo:
        await call.message.delete()
        await call.message.answer(text, reply_markup=get_help_support_kb(i18n), parse_mode="HTML")
    else:
        await call.message.edit_text(text, reply_markup=get_help_support_kb(i18n), parse_mode="HTML")


@router.callback_query(F.data.startswith("help_support_"))
async def cb_help_support_item(call: CallbackQuery, i18n: I18n):
    item = call.data
    text = ""
    instr_cb = None
    if item == "help_support_info":
        text = i18n.get("msg-support-info-text")
        instr_cb = "help_instr_info"
    elif item == "help_support_add":
        text = i18n.get("msg-support-add-text")
        instr_cb = "help_instr_add"
    elif item == "help_support_track":
        text = i18n.get("msg-support-track-text")
        instr_cb = "help_instr_track"
        
    if call.message.photo:
        await call.message.delete()
        await call.message.answer(text, reply_markup=get_help_support_item_kb(i18n, instr_cb), parse_mode="HTML")
    else:
        await call.message.edit_text(text, reply_markup=get_help_support_item_kb(i18n, instr_cb), parse_mode="HTML")


@router.callback_query(F.data == "help_commands")
async def cb_help_commands(call: CallbackQuery, i18n: I18n, session: AsyncSession):
    user = await session.scalar(select(User).where(User.tg_id == call.from_user.id))
    role = user.role if user else "user"
    
    text = i18n.get("msg-commands-list")
    if role in ["admin", "moder"]:
        text += "\n" + i18n.get("msg-commands-admin-list")
        
    if call.message.photo:
        await call.message.delete()
        await call.message.answer(text, reply_markup=get_back_kb(i18n), parse_mode="HTML")
    else:
        await call.message.edit_text(text, reply_markup=get_back_kb(i18n), parse_mode="HTML")


@router.callback_query(F.data == "create_ticket")
async def cb_create_ticket(call: CallbackQuery, state: FSMContext, i18n: I18n):
    """Переход в FSM-состояние написания тикета."""
    text = (
        "📝 <b>Создание тикета</b>\n\n"
        "Пожалуйста, подробно опишите вашу проблему в одном сообщении. "
        "При необходимости прикрепите фото или скриншот."
    )
    if call.message.photo:
        await call.message.delete()
        await call.message.answer(text, parse_mode="HTML")
    else:
        await call.message.edit_text(text, parse_mode="HTML")
        
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
