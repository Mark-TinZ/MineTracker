from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, ChatMemberUpdated, BotCommandScopeChat
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, IS_NOT_MEMBER, MEMBER
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mc_ping_bot.db.models import Chat, MonitoredServer, Server
from mc_ping_bot.services.minecraft import MinecraftService
from mc_ping_bot.bot.commands_setup import GROUP_COMMANDS

router = Router()
router.message.filter(F.chat.type.in_({"group", "supergroup"}))


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=IS_NOT_MEMBER >> MEMBER))
async def bot_added_to_group(event: ChatMemberUpdated, bot: Bot):
    if event.chat.type not in ["group", "supergroup"]:
        return
        
    await bot.send_message(
        event.chat.id,
        "👋 Всем привет! Я MineTracker.\n"
        "Чтобы настроить мониторинг сервера в этом чате, администратор должен использовать команду <code>/set_chat_server &lt;ip&gt;</code>",
        parse_mode="HTML"
    )
    
    try:
        await bot.set_my_commands(
            GROUP_COMMANDS,
            scope=BotCommandScopeChat(chat_id=event.chat.id)
        )
    except Exception:
        pass



@router.message(Command("set_chat_server"))
async def cmd_set_chat_server(message: Message, command: CommandObject, session: AsyncSession, mc_service: MinecraftService):
    """
    Создает трекер (MonitoredServer) для конкретного чата.
    Обеспечивает валидацию сервера и создание связанных записей в БД.
    """
    # 1. Проверка типа чата
    if message.chat.type not in ["group", "supergroup"]:
        await message.answer("⚠️ Эта команда предназначена только для групповых чатов.", parse_mode="HTML")
        return

    # 2. Проверка аргументов
    if not command.args:
        await message.answer("⚠️ Укажите IP сервера. Пример: <code>/set_chat_server mc.hypixel.net</code>", parse_mode="HTML")
        return

    address = command.args.strip()
    msg = await message.answer("⏳ <i>Проверка сервера...</i>", parse_mode="HTML")

    # 3. Валидация IP и предотвращение SSRF
    data = await mc_service.get_server_info(address)
    
    if data.get("error") == "invalid_address":
        await msg.edit_text("❌ <b>Ошибка:</b> Введен недопустимый IP-адрес (попытка SSRF или локальный хост).", parse_mode="HTML")
        return
        
    if not data.get("online"):
        status_text = "⚠️ Сервер сейчас оффлайн, но мониторинг настроен."
    else:
        status_text = f"🟢 Онлайн: <b>{data['players_online']}/{data['players_max']}</b>"

    # Извлекаем безопасный IP и порт
    server_ip = data.get("ip", address)
    server_port = data.get("port", 25565)

    # 4. Инициализация в БД
    # 4.1. Чат
    chat = await session.scalar(select(Chat).where(Chat.tg_chat_id == message.chat.id))
    if not chat:
        chat = Chat(tg_chat_id=message.chat.id, type=message.chat.type)
        session.add(chat)
        await session.flush() # Получаем ID

    # 4.2. Физический Сервер
    server_db = await session.scalar(
        select(Server).where(Server.ip_domain == server_ip, Server.port == server_port)
    )
    if not server_db:
        server_db = Server(ip_domain=server_ip, port=server_port)
        session.add(server_db)
        await session.flush() # Получаем ID

    # 4.3. Трекер (MonitoredServer)
    tracker = await session.scalar(
        select(MonitoredServer).where(
            MonitoredServer.chat_id == chat.id,
            MonitoredServer.server_id == server_db.id
        )
    )
    
    if not tracker:
        tracker = MonitoredServer(
            chat_id=chat.id,
            server_id=server_db.id,
            interval_seconds=300,  # Бесплатный тариф по умолчанию
            show_motd=True,
            show_players=True,
            show_tps=False,
            is_paused=False
        )
        session.add(tracker)
    else:
        # Если он уже был, реактивируем его
        tracker.interval_seconds = 300
        tracker.is_paused = False
        
    await session.commit()

    # 5. Формирование закрепляемого сообщения
    text = (
        f"📊 <b>Мониторинг инициализирован!</b>\n\n"
        f"🌍 Сервер: <code>{server_ip}:{server_port}</code>\n"
        f"📡 Статус: {status_text}\n\n"
        f"<i>Это сообщение будет обновляться автоматически. Рекомендуем его закрепить!</i>"
    )
    
    tracker_msg = await message.answer(text, parse_mode="HTML")
    
    # 6. Сохранение message_id для Background Worker'а
    tracker.message_id = tracker_msg.message_id
    await session.commit()
    
    # Удаляем временное сообщение
    await msg.delete()
