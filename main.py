import asyncio
import logging
import sqlite3
import yaml
import sys
import json
import socket
from datetime import datetime

from aiogram import Bot, Dispatcher, F, types, html
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.storage.memory import MemoryStorage
from mcstatus import JavaServer

# --- ЗАГРУЗКА КОНФИГУРАЦИИ ---
try:
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
except FileNotFoundError:
    print("❌ ОШИБКА: Файл config.yaml не найден!")
    sys.exit(1)

BOT_TOKEN = config.get("bot_token")
OWNER_ID = config.get("owner_id")
UPDATE_INTERVAL = config.get("update_interval", 60)
DB_NAME = config.get("db_name", "servers.db")

# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chats (
        chat_id INTEGER PRIMARY KEY,
        server_ip TEXT,
        message_id INTEGER,
        last_players TEXT DEFAULT '[]',
        is_online INTEGER DEFAULT 0,
        notify_join INTEGER DEFAULT 0,
        notify_leave INTEGER DEFAULT 0,
        notify_down_chat INTEGER DEFAULT 0,
        notify_down_pm INTEGER DEFAULT 0
    )
    """)
    conn.commit()
    conn.close()

init_db()

# --- ИНИЦИАЛИЗАЦИЯ БОТА ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

async def get_server_status(ip: str):
    """Асинхронный пинг сервера"""
    try:
        server = await asyncio.to_thread(JavaServer.lookup, ip)
        status = await asyncio.to_thread(server.status)
        return status
    except Exception:
        return None

def get_ip_from_domain(domain: str):
    try:
        host = domain.split(':')[0]
        return socket.gethostbyname(host)
    except Exception:
        return None

def format_server_info(ip: str, status):
    # Экранируем IP чтобы спецсимволы не ломали HTML
    safe_ip = html.quote(ip)
    
    if not status:
        return f"🔴 <b>Сервер Offline</b>\nАдрес: <code>{safe_ip}</code>"
    
    latency_color = "🟢" if status.latency < 50 else "🟡" if status.latency < 150 else "🔴"
    
    # Экранируем имена игроков
    players_list = [html.quote(p.name) for p in status.players.sample] if status.players.sample else []
    
    text = (
        f"🌍 <b>Сервер:</b> <code>{safe_ip}</code>\n"
        f"🛠 <b>Версия:</b> {html.quote(status.version.name)}\n"
        f"📡 <b>Пинг:</b> {latency_color} {int(status.latency)} ms\n"
        f"👥 <b>Игроки:</b> {status.players.online} / {status.players.max}\n"
    )
    
    if players_list:
        # Формируем красивый список, имена в code блоке для безопасности
        clean_players = ", ".join([f"<code>{p}</code>" for p in players_list])
        if len(clean_players) > 2000: # Лимит телеграма ~4096, оставляем запас
             clean_players = clean_players[:2000] + "..."
        text += f"\n📝 <b>В игре:</b> {clean_players}"
    
    return text

# --- DB HELPERS ---
def db_get_chat(chat_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chats WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def db_update_field(chat_id, field, value):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    allowed_fields = ["server_ip", "message_id", "last_players", "is_online", 
                      "notify_join", "notify_leave", "notify_down_chat", "notify_down_pm"]
    if field in allowed_fields:
        cursor.execute(f"UPDATE chats SET {field} = ? WHERE chat_id = ?", (value, chat_id))
    conn.commit()
    conn.close()

# --- HANDLERS: ЛИЧНЫЕ СООБЩЕНИЯ (ДЛЯ ВСЕХ) ---

@dp.message(F.chat.type == "private", CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "👋 <b>Привет! Я MineTracker Bot.</b>\n"
        "Я умею проверять статус серверов Minecraft.\n\n"
        "Используй /help для списка команд."
    , parse_mode="HTML")

@dp.message(F.chat.type == "private", Command("help"))
async def cmd_help(message: Message):
    text = (
        "📌 <b>Доступные команды:</b>\n\n"
        "🔹 <code>/info ip</code> - Полная инфо о сервере\n"
        "🔹 <code>/players ip</code> - Кто играет сейчас\n"
        "🔹 <code>/ip domain</code> - Узнать цифровой IP домена\n\n"
        "🤖 <b>Для владельца:</b>\n"
        "🔸 <code>/chat</code> - Установить текущий чат для мониторинга\n"
        "🔸 <code>/server_set ip</code> - Установить сервер для мониторинга\n"
        "🔸 <code>/server_conf</code> - Настройки уведомлений"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(F.chat.type == "private", Command("info"))
async def cmd_info(message: Message, command: CommandObject):
    if not command.args:
        return await message.answer("⚠️ Используйте: <code>/info ip</code>", parse_mode="HTML")
    
    address = command.args.strip()
    msg = await message.answer("🔄 <i>Подключаюсь к серверу...</i>", parse_mode="HTML")
    
    status = await get_server_status(address)
    response = format_server_info(address, status)
    
    await msg.edit_text(response, parse_mode="HTML")

@dp.message(F.chat.type == "private", Command("players"))
async def cmd_players(message: Message, command: CommandObject):
    if not command.args:
        return await message.answer("⚠️ Используйте: <code>/players ip</code>", parse_mode="HTML")
    
    address = command.args.strip()
    status = await get_server_status(address)
    
    if not status:
        return await message.answer("❌ Сервер недоступен.")
    
    if not status.players.sample:
        return await message.answer("📭 Список игроков скрыт или пуст.")
    
    # Экранируем имена!
    players = [html.quote(p.name) for p in status.players.sample]
    # Сортируем для удобства
    players.sort()
    
    players_str = "\n".join([f"👤 <code>{p}</code>" for p in players])
    
    # Защита от слишком длинных сообщений (лимит 4096 символов)
    if len(players_str) > 3500:
        players_str = players_str[:3500] + "\n\n... список обрезан"

    await message.answer(f"📋 <b>Игроки на {html.quote(address)}:</b>\n\n{players_str}", parse_mode="HTML")

@dp.message(F.chat.type == "private", Command("ip"))
async def cmd_get_ip(message: Message, command: CommandObject):
    if not command.args:
        return await message.answer("⚠️ Используйте: <code>/ip domain</code>", parse_mode="HTML")
    
    domain = command.args.strip()
    resolved_ip = get_ip_from_domain(domain)
    
    if resolved_ip:
        await message.answer(f"🔎 Домен: <code>{html.quote(domain)}</code>\n🔢 IP: <code>{resolved_ip}</code>", parse_mode="HTML")
    else:
        await message.answer("❌ Не удалось узнать IP. Проверьте адрес.", parse_mode="HTML")

# --- HANDLERS: АДМИНИСТРИРОВАНИЕ (ВЛАДЕЛЕЦ) ---

def is_owner(user_id):
    return user_id == OWNER_ID

@dp.message(Command("chat"))
async def cmd_chat_register(message: Message):
    if not is_owner(message.from_user.id):
        return 
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO chats (chat_id) VALUES (?)", (message.chat.id,))
        conn.commit()
        await message.answer("✅ Чат зафиксирован в базе данных.")
    except Exception as e:
        await message.answer(f"❌ Ошибка БД: {e}")
    finally:
        conn.close()

@dp.message(Command("server_set"))
async def cmd_server_set(message: Message, command: CommandObject):
    if not is_owner(message.from_user.id):
        return
    
    if not db_get_chat(message.chat.id):
        return await message.answer("⚠️ Сначала используйте <code>/chat</code> в этом чате.", parse_mode="HTML")

    if not command.args:
        return await message.answer("⚠️ Введите IP: <code>/server_set ip</code>", parse_mode="HTML")
    
    address = command.args.strip()
    
    sent_msg = await message.answer(f"🔄 <b>Инициализация мониторинга для</b> <code>{html.quote(address)}</code>...", parse_mode="HTML")
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE chats SET server_ip = ?, message_id = ?, last_players = '[]' WHERE chat_id = ?", 
                   (address, sent_msg.message_id, message.chat.id))
    conn.commit()
    conn.close()
    
    try:
        await message.delete()
    except:
        pass

@dp.message(Command("server_conf"))
async def cmd_server_conf(message: Message):
    if not is_owner(message.from_user.id):
        return
    
    row = db_get_chat(message.chat.id)
    if not row or not row[1]: 
        return await message.answer("⚠️ Сервер не настроен. Используйте <code>/server_set</code>.", parse_mode="HTML")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{'✅' if row[5] else '❌'} Вход игроков", callback_data="toggle_join")],
        [InlineKeyboardButton(text=f"{'✅' if row[6] else '❌'} Выход игроков", callback_data="toggle_leave")],
        [InlineKeyboardButton(text=f"{'✅' if row[7] else '❌'} Уведомление UP/DOWN (Чат)", callback_data="toggle_down_chat")],
        [InlineKeyboardButton(text=f"{'✅' if row[8] else '❌'} Уведомление UP/DOWN (ЛС)", callback_data="toggle_down_pm")],
        [InlineKeyboardButton(text="🗑 Удалить сервер", callback_data="delete_server")],
        [InlineKeyboardButton(text="Закрыть", callback_data="close_menu")]
    ])
    
    await message.answer("⚙️ <b>Настройки мониторинга:</b>", reply_markup=kb, parse_mode="HTML")

@dp.message(Command("server_info"))
async def cmd_server_info_chat(message: Message):
    if not is_owner(message.from_user.id):
        return
    
    row = db_get_chat(message.chat.id)
    if not row or not row[1]:
         return await message.answer("⚠️ Сервер не установлен.")
    
    status = await get_server_status(row[1])
    await message.answer(format_server_info(row[1], status), parse_mode="HTML")


# --- CALLBACKS ДЛЯ МЕНЮ ---

@dp.callback_query(F.data.startswith("toggle_"))
async def callback_toggle(callback: types.CallbackQuery):
    if not is_owner(callback.from_user.id):
        return await callback.answer("⛔ Доступ запрещен", show_alert=True)
    
    field_map = {
        "toggle_join": "notify_join",
        "toggle_leave": "notify_leave",
        "toggle_down_chat": "notify_down_chat",
        "toggle_down_pm": "notify_down_pm"
    }
    
    action = callback.data
    field = field_map.get(action)
    
    row = db_get_chat(callback.message.chat.id)
    current_val = 0
    if action == "toggle_join": current_val = row[5]
    elif action == "toggle_leave": current_val = row[6]
    elif action == "toggle_down_chat": current_val = row[7]
    elif action == "toggle_down_pm": current_val = row[8]
    
    new_val = 0 if current_val else 1
    db_update_field(callback.message.chat.id, field, new_val)
    
    await callback.message.delete()
    await cmd_server_conf(callback.message)

@dp.callback_query(F.data == "delete_server")
async def callback_delete(callback: types.CallbackQuery):
    if not is_owner(callback.from_user.id):
        return
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE chats SET server_ip = NULL, message_id = NULL, last_players = '[]', 
        is_online = 0 WHERE chat_id = ?
    """, (callback.message.chat.id,))
    conn.commit()
    conn.close()
    
    await callback.message.edit_text("🗑 Сервер удален из базы. Используйте <code>/server_set</code> для новой настройки.", parse_mode="HTML")

@dp.callback_query(F.data == "close_menu")
async def callback_close(callback: types.CallbackQuery):
    await callback.message.delete()

# --- ФОНОВАЯ ЗАДАЧА МОНИТОРИНГА ---

async def monitoring_task():
    while True:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM chats WHERE server_ip IS NOT NULL AND message_id IS NOT NULL")
        chats = cursor.fetchall()
        conn.close()

        for chat in chats:
            chat_id = chat['chat_id']
            ip = chat['server_ip']
            msg_id = chat['message_id']
            
            status = await get_server_status(ip)
            
            is_online_now = 1 if status else 0
            was_online = chat['is_online']
            
            new_text = format_server_info(ip, status)
            try:
                await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=new_text, parse_mode="HTML")
            except Exception:
                pass

            if is_online_now != was_online:
                db_update_field(chat_id, "is_online", is_online_now)
                
                event_text = ""
                if is_online_now == 0:
                    event_text = f"🔴 <b>ВНИМАНИЕ!</b> Сервер <code>{html.quote(ip)}</code> упал!"
                else:
                    event_text = f"🟢 <b>УРА!</b> Сервер <code>{html.quote(ip)}</code> снова доступен!"

                if chat['notify_down_chat']:
                     await bot.send_message(chat_id, event_text, parse_mode="HTML")
                
                if chat['notify_down_pm']:
                     try:
                        await bot.send_message(OWNER_ID, f"🔔 {event_text} (Чат: {chat_id})", parse_mode="HTML")
                     except: pass

            if status and is_online_now:
                current_players = set([p.name for p in status.players.sample]) if status.players.sample else set()
                try:
                    last_players = set(json.loads(chat['last_players']))
                except:
                    last_players = set()
                
                joined = current_players - last_players
                left = last_players - current_players
                
                db_update_field(chat_id, "last_players", json.dumps(list(current_players)))

                if joined and chat['notify_join']:
                    names = ", ".join([f"<code>{html.quote(n)}</code>" for n in joined])
                    await bot.send_message(chat_id, f"➕ Зашел: {names}", parse_mode="HTML")
                
                if left and chat['notify_leave']:
                    names = ", ".join([f"<code>{html.quote(n)}</code>" for n in left])
                    await bot.send_message(chat_id, f"➖ Вышел: {names}", parse_mode="HTML")

        await asyncio.sleep(UPDATE_INTERVAL)

# --- ЗАПУСК ---

async def main():
    asyncio.create_task(monitoring_task())
    print("🤖 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен")
