from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mc_ping_bot.bot.commands_setup import update_user_commands
from mc_ping_bot.bot.i18n import i18n
from mc_ping_bot.db.models import User
from mc_ping_bot.services.i18n import I18n
from mc_ping_bot.services.minecraft import MinecraftService

router = Router()


def get_refresh_kb(address: str, lang: str) -> InlineKeyboardMarkup:
    """Кнопка для обновления статуса."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.get("update_btn", lang_code=lang), callback_data=f"refresh_info:{address}")]
    ])


def format_server_info(cmd: str, data: dict, lang: str) -> str:
    """Форматирует вывод в зависимости от запрошенной команды."""
    if not data.get("online"):
        err_key = data.get("error", "server_offline")
        return i18n.get(err_key, lang_code=lang, desc=data.get("desc", ""))

    if cmd == "info":
        text = (
            f"🟢 <b>Server Online</b>\n"
            f"🌍 IP: <code>{data['ip']}</code>\n"
            f"🛠 Версия: {data['version']}\n"
            f"📡 Пинг: {data['latency']} ms\n"
            f"👥 Игроки: {data['players_online']} / {data['players_max']}\n"
        )
        if data.get("motd"):
            text += f"💬 MOTD: <i>{data['motd']}</i>\n"
        return text

    elif cmd == "ping":
        return f"📡 Пинг до <code>{data['ip']}</code>: <b>{data['latency']} ms</b>"

    elif cmd == "players":
        text = f"👥 Игроки на <code>{data['ip']}</code>: <b>{data['players_online']} / {data['players_max']}</b>\n\n"
        if data.get("player_names"):
            text += "<b>Отображаемые игроки:</b>\n" + ", ".join(data["player_names"])
        else:
            text += "<i>Список игроков скрыт сервером или пуст.</i>"
        return text

    elif cmd == "motd":
        return f"💬 MOTD сервера <code>{data['ip']}</code>:\n\n<i>{data.get('motd', 'Нет MOTD')}</i>"

    elif cmd == "version":
        return f"🛠 Версия сервера <code>{data['ip']}</code>: <b>{data['version']}</b>"

    elif cmd == "ip":
        return f"🌍 Введенный IP: <code>{data['ip']}</code>\n🔒 Разрешенный IP (Antispam/SSRF): <code>{data['resolved_ip']}</code>"

    return "Неизвестная команда."


@router.message(Command("info", "ping", "players", "motd", "version", "ip"))
async def cmd_server_commands(message: Message, command: CommandObject, session: AsyncSession, mc_service: MinecraftService):
    """
    Универсальный обработчик всех базовых команд для запроса информации о Minecraft сервере.
    Rate Limit проверяется Middleware.
    """
    user = await session.scalar(select(User).where(User.tg_id == message.from_user.id))
    lang = user.lang if user else "ru"
    cmd = command.command

    if not command.args:
        await message.answer(f"⚠️ Укажите IP сервера, например: /{cmd} mc.hypixel.net", parse_mode="HTML")
        return

    address = command.args.strip()
    
    # Визуальный индикатор (Пока работает Pipeline проверки)
    msg = await message.answer("⏳ ...")
    
    # Pipeline: Cache -> Resolve SRV -> Validate SSRF -> Ping
    data = await mc_service.get_server_info(address)
    
    text = format_server_info(cmd, data, lang)

    await msg.edit_text(text, reply_markup=get_refresh_kb(address, lang), parse_mode="HTML")


@router.callback_query(F.data.startswith("refresh_info:"))
async def cb_refresh_info(call: CallbackQuery, session: AsyncSession, mc_service: MinecraftService):
    """
    Обновление информации по кнопке из-под сообщения.
    По умолчанию всегда возвращает полный формат (info).
    """
    user = await session.scalar(select(User).where(User.tg_id == call.from_user.id))
    lang = user.lang if user else "ru"
    address = call.data.split(":", 1)[1]
    
    data = await mc_service.get_server_info(address)
    
    # При обновлении по кнопке "refresh_info", всегда выдаем полную сводку (как /info)
    text = format_server_info("info", data, lang)
            
    try:
        await call.message.edit_text(text, reply_markup=get_refresh_kb(address, lang), parse_mode="HTML")
        await call.answer("✅ Обновлено")
    except Exception:
        # Если текст не изменился (сервер вернул те же самые данные), Aiogram выдаст ошибку
        await call.answer("Изменений нет")


@router.message(Command("commands"))
async def cmd_commands(message: Message, session: AsyncSession, bot: Bot, mc_service: MinecraftService, i18n: I18n):
    """
    Принудительное обновление меню команд пользователя.
    Инвалидирует кеш в Redis и делает вызов к Telegram API.
    """
    if message.chat.type != "private":
        bot_info = await message.bot.get_me()
        await message.answer(
            i18n.get("msg-commands-group", bot_username=bot_info.username), 
            parse_mode="HTML"
        )
        return

    user = await session.scalar(select(User).where(User.tg_id == message.from_user.id))
    role = user.role if user else "user"
    
    cache = mc_service.cache
    
    # Принудительно обновляем (force=True игнорирует Redis)
    await update_user_commands(bot, message.from_user.id, role, cache, force=True)
    
    text = i18n.get("msg-commands-updated") + "\n\n"
    text += i18n.get("msg-commands-list")
    
    if role in ["admin", "moder"]:
        text += "\n" + i18n.get("msg-commands-admin-list")
        
    await message.answer(text, parse_mode="HTML")
