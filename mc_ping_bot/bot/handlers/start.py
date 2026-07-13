from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from mc_ping_bot.db.models import User
from mc_ping_bot.services.i18n import I18n, current_locale
from mc_ping_bot.services.cache import RedisCacheManager

router = Router(name="start_router")
# Обрабатываем команды только в ЛС
router.message.filter(F.chat.type == "private")


def get_lang_kb(i18n: I18n) -> InlineKeyboardMarkup:
    """Клавиатура с выбором языка (динамическая)."""
    builder = InlineKeyboardBuilder()
    builder.button(text=i18n.get("btn-lang-ru"), callback_data="lang_ru")
    builder.button(text=i18n.get("btn-lang-en"), callback_data="lang_en")
    builder.adjust(2)
    return builder.as_markup()

def get_main_menu_kb(i18n: I18n) -> InlineKeyboardMarkup:
    """Главное меню возможностей (динамическая)."""
    builder = InlineKeyboardBuilder()
    builder.button(text=i18n.get("btn-features"), callback_data="bot_features")
    builder.button(text=i18n.get("btn-info"), callback_data="bot_info")
    builder.adjust(2)
    return builder.as_markup()


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, i18n: I18n):
    """Обработчик команды /start."""
    user = await session.scalar(select(User).where(User.tg_id == message.from_user.id))
    
    if user:
        # Пользователь зарегистрирован, выводим сразу сообщение /start
        await message.answer(
            i18n.get("msg-welcome-main"),
            reply_markup=get_main_menu_kb(i18n),
            parse_mode="HTML"
        )
    else:
        # Пользователь НЕ зарегистрирован, выводим сообщение о выборе языка
        await message.answer(
            i18n.get("msg-welcome-new"),
            reply_markup=get_lang_kb(i18n),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("lang_"))
async def cb_language(call: CallbackQuery, session: AsyncSession, i18n: I18n):
    """Обработчик выбора языка (регистрация и смена языка)."""
    lang_code = call.data.split("_")[1]
    
    user = await session.scalar(select(User).where(User.tg_id == call.from_user.id))
    
    if not user:
        # Записываем в БД нового пользователя
        user = User(tg_id=call.from_user.id, lang=lang_code)
        session.add(user)
    else:
        # Смена языка для существующего
        user.lang = lang_code
        
    await session.commit()
    
    # Чтобы язык применился прямо сейчас в рамках этого коллбека, обновляем contextvars
    current_locale.set(lang_code)
    
    # Также желательно обновить Redis-кэш, чтобы следующий запрос не взял старый язык.
    # В идеале прокинуть cache_manager через middleware, но можно и так:
    # TODO: Внедрить cache_manager в хендлеры и вызывать await cache_manager.set_user_lang(call.from_user.id, lang_code)
    
    text = i18n.get("msg-lang-set") + "\n\n" + i18n.get("msg-welcome-main")
    
    await call.message.edit_text(
        text,
        reply_markup=get_main_menu_kb(i18n),
        parse_mode="HTML"
    )
    await call.answer()


@router.message(Command("language"))
async def cmd_language(message: Message, i18n: I18n):
    """Принудительная смена языка."""
    await message.answer(
        i18n.get("msg-welcome-new"),
        reply_markup=get_lang_kb(i18n),
        parse_mode="HTML"
    )
