from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mc_ping_bot.db.models import User

router = Router()
router.message.filter(F.chat.type == "private")


def get_start_kb() -> InlineKeyboardMarkup:
    """Клавиатура с выбором языка и меню возможностей."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")
        ],
        [
            InlineKeyboardButton(text="🚀 Возможности", callback_data="bot_features"),
            InlineKeyboardButton(text="ℹ️ О боте", callback_data="bot_info")
        ]
    ])


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession):
    """
    Обработчик команды /start.
    """
    user = await session.scalar(select(User).where(User.tg_id == message.from_user.id))
    
    if not user:
        user = User(tg_id=message.from_user.id, lang="ru")
        session.add(user)
    else:
        user.lang = "ru"
        
    await session.commit()
    
    text = (
        "👋 <b>Добро пожаловать в MineTracker!</b>\n\n"
        "Мощный и быстрый бот для мониторинга Minecraft серверов. "
        "Мы защитим вас от спама, покажем статус онлайна прямо в вашей группе и поможем управлять сервером!\n\n"
        "Выберите язык для продолжения / Choose your language:"
    )
    
    await message.answer(text, reply_markup=get_start_kb(), parse_mode="HTML")


@router.callback_query(F.data.startswith("lang_"))
async def cb_language(call: CallbackQuery, session: AsyncSession):
    """Обработчик выбора языка."""
    lang_code = call.data.split("_")[1]
    
    user = await session.scalar(select(User).where(User.tg_id == call.from_user.id))
    if user:
        user.lang = lang_code
        await session.commit()
    
    text = "✅ Язык установлен на Русский! Используйте /help для вызова меню." if lang_code == "ru" else "✅ Language set to English! Use /help to open menu."
    await call.message.edit_text(text)
    await call.answer()


@router.callback_query(F.data == "bot_features")
async def cb_bot_features(call: CallbackQuery):
    """Отправка текста о возможностях (Бесплатный тариф)."""
    text = (
        "🚀 <b>Возможности (Бесплатный тариф)</b>\n\n"
        "🔹 Пинг сервера раз в <b>300 секунд</b> (5 минут).\n"
        "🔹 Мониторинг <b>1 сервера</b> для одной группы.\n"
        "🔹 Защита от поддельных IP (SSRF) и спама.\n"
        "🔹 Подробная сводка по онлайну и MOTD.\n\n"
        "Чтобы начать, добавьте бота в группу и используйте <code>/set_chat_server &lt;ip&gt;</code>!"
    )
    # Используем answer для нового сообщения, чтобы не перезаписывать приветствие
    await call.message.answer(text, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "bot_info")
async def cb_bot_info(call: CallbackQuery):
    """Отправка информации о боте."""
    text = (
        "ℹ️ <b>О боте MineTracker</b>\n\n"
        "Бот создан для владельцев серверов и игровых комьюнити. "
        "Позволяет следить за статусом сервера в реальном времени, "
        "удерживая активность в чате и объединяя игроков."
    )
    await call.message.answer(text, parse_mode="HTML")
    await call.answer()
