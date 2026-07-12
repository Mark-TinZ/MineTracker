from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

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
async def process_ticket_message(message: Message, state: FSMContext):
    """Обработчик входящего сообщения для тикета."""
    # В будущем здесь будет логика INSERT INTO tickets 
    # или отправка форварда сообщения в спец. чат администраторов.
    
    await message.answer(
        "✅ <b>Тикет успешно создан!</b>\n\n"
        "Администраторы рассмотрят ваше обращение в ближайшее время.",
        parse_mode="HTML"
    )
    await state.clear()
