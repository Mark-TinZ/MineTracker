import asyncio
import logging
import time
import socket
import datetime
import yaml
import os
import sys
import html
import re
from typing import Optional, List, Union

from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from aiogram.fsm.storage.memory import MemoryStorage

import aiosqlite
from mcstatus import JavaServer

# --- SETUP LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIG LOADER ---
def load_config():
    if not os.path.exists("config.yaml"):
        # Создаем конфиг по умолчанию, если нет
        default_conf = {
            "bot_token": "YOUR_TOKEN_HERE",
            "owner_id": 0,
            "update_interval": 60,
            "database_file": "bot_database.db"
        }
        with open("config.yaml", "w") as f:
            yaml.dump(default_conf, f)
        logger.warning("config.yaml created! Please fill it.")
        sys.exit(1)
        
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

CONFIG = load_config()
OWNER_ID = int(CONFIG.get("owner_id", 0))
UPDATE_INTERVAL = int(CONFIG.get("update_interval", 60))
DB_FILE = CONFIG.get("database_file", "bot.db")

# --- GLOBAL TIME ---
BOT_START_TIME = time.time()

# --- DATABASE MANAGER ---
class Database:
    def __init__(self, db_path):
        self.db_path = db_path

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            # Users
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    first_seen TEXT
                )
            """)
            # System Stats (Key-Value persistence)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS system_stats (
                    key TEXT PRIMARY KEY,
                    value INTEGER
                )
            """)
            # Initialize request counter if not exists
            await db.execute("INSERT OR IGNORE INTO system_stats (key, value) VALUES ('total_pings', 0)")
            
            # Chats
            await db.execute("""
                CREATE TABLE IF NOT EXISTS chats (
                    chat_id INTEGER PRIMARY KEY,
                    server_ip TEXT,
                    message_id INTEGER,
                    moderator_id INTEGER,
                    notify_down BOOLEAN DEFAULT 0,
                    last_status TEXT
                )
            """)
            # Ban Users
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ban_users (
                    user_id INTEGER PRIMARY KEY,
                    reason TEXT,
                    banned_at TEXT,
                    banned_by TEXT
                )
            """)
            # Ban IPs
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ban_ips (
                    ip TEXT PRIMARY KEY,
                    reason TEXT,
                    banned_at TEXT,
                    domain_hint TEXT
                )
            """)
            await db.commit()

    async def add_user(self, user: types.User):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO users (user_id, username, full_name, first_seen) VALUES (?, ?, ?, COALESCE((SELECT first_seen FROM users WHERE user_id=?), ?))",
                (user.id, user.username, user.full_name, user.id, datetime.datetime.now().strftime("%d.%m.%Y"))
            )
            await db.commit()
    
    async def get_user_info(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT username, full_name FROM users WHERE user_id = ?", (user_id,)) as cur:
                return await cur.fetchone()

    # --- Stats Methods ---
    async def increment_pings(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE system_stats SET value = value + 1 WHERE key = 'total_pings'")
            await db.commit()

    async def get_total_pings(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT value FROM system_stats WHERE key = 'total_pings'") as cur:
                res = await cur.fetchone()
                return res[0] if res else 0

    # --- Chat Methods ---
    async def set_server(self, chat_id, ip, msg_id, mod_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO chats (chat_id, server_ip, message_id, moderator_id, last_status) 
                   VALUES (?, ?, ?, ?, 'UNKNOWN')""",
                (chat_id, ip, msg_id, mod_id)
            )
            await db.commit()

    async def get_chat(self, chat_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT * FROM chats WHERE chat_id = ?", (chat_id,)) as cursor:
                return await cursor.fetchone()

    async def get_all_monitored_chats(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT chat_id, server_ip, message_id, moderator_id, last_status, notify_down FROM chats") as cursor:
                return await cursor.fetchall()

    async def delete_chat(self, chat_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM chats WHERE chat_id = ?", (chat_id,))
            await db.commit()

    async def update_chat_config(self, chat_id, notify_down=None, message_id=None, last_status=None):
        async with aiosqlite.connect(self.db_path) as db:
            query = "UPDATE chats SET "
            params = []
            updates = []
            if notify_down is not None:
                updates.append("notify_down = ?")
                params.append(int(notify_down))
            if message_id is not None:
                updates.append("message_id = ?")
                params.append(message_id)
            if last_status is not None:
                updates.append("last_status = ?")
                params.append(last_status)
            
            if not updates: return
            
            query += ", ".join(updates) + " WHERE chat_id = ?"
            params.append(chat_id)
            await db.execute(query, tuple(params))
            await db.commit()

    # --- Ban Methods ---
    async def ban_user(self, user_id, reason, admin_name):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO ban_users (user_id, reason, banned_at, banned_by) VALUES (?, ?, ?, ?)",
                (user_id, reason, datetime.datetime.now().strftime("%d.%m.%Y"), admin_name)
            )
            await db.commit()

    async def unban_user(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM ban_users WHERE user_id = ?", (user_id,))
            await db.commit()

    async def is_user_banned(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT 1 FROM ban_users WHERE user_id = ?", (user_id,)) as cursor:
                return await cursor.fetchone() is not None

    async def get_banlist_users(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT b.user_id, b.reason, b.banned_at, u.username, u.full_name FROM ban_users b LEFT JOIN users u ON b.user_id = u.user_id") as cursor:
                return await cursor.fetchall()

    async def ban_ip(self, ip, reason, domain=None):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO ban_ips (ip, reason, banned_at, domain_hint) VALUES (?, ?, ?, ?)",
                (ip, reason, datetime.datetime.now().strftime("%d.%m.%Y"), domain)
            )
            await db.commit()

    async def unban_ip(self, ip):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM ban_ips WHERE ip = ?", (ip,))
            await db.commit()
            
    async def get_banlist_ips(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT ip, reason, banned_at, domain_hint FROM ban_ips") as cursor:
                return await cursor.fetchall()
    
    async def check_ip_banned(self, ip_address):
        async with aiosqlite.connect(self.db_path) as db:
             async with db.execute("SELECT 1 FROM ban_ips WHERE ip = ?", (ip_address,)) as cursor:
                return await cursor.fetchone() is not None
                
    async def get_general_stats(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as cur:
                users = (await cur.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM chats") as cur:
                servers = (await cur.fetchone())[0]
            return users, servers

db = Database(DB_FILE)

# --- MINECRAFT UTILS ---
class MCUtils:
    @staticmethod
    def clean_motd(text: Union[str, dict, list]) -> str:
        """Removes Minecraft color codes (§a, §1, etc) and cleans structure."""
        if isinstance(text, dict):
            # Often comes as {'text': '...', 'extra': [...]}
            text = text.get('text', '') + "".join([x.get('text', '') for x in text.get('extra', [])])
        elif isinstance(text, list):
            text = "".join([x.get('text', '') if isinstance(x, dict) else str(x) for x in text])
        
        # Remove Color Codes (§ + char)
        clean_text = re.sub(r'§[0-9a-fk-or]', '', str(text))
        # Remove strict ANSI codes if any
        clean_text = re.sub(r'\x1b\[[0-9;]*m', '', clean_text)
        return clean_text.strip()

    @staticmethod
    def resolve_ip(address: str):
        try:
            host = address.split(':')[0]
            return socket.gethostbyname(host)
        except:
            return None

    @staticmethod
    async def get_server_info(address: str):
        # Stats increment
        await db.increment_pings()
        
        resolved_ip = MCUtils.resolve_ip(address)
        if resolved_ip and await db.check_ip_banned(resolved_ip):
            return {"error": "blocked", "desc": "IP Address is blacklisted by administrator."}
        
        try:
            server = await JavaServer.async_lookup(address)
            # Short timeout to prevent lag
            status = await server.async_status()
            
            player_list = []
            if status.players.sample:
                player_list = [p.name for p in status.players.sample]
            
            motd = MCUtils.clean_motd(status.description)

            return {
                "online": True,
                "ip": address,
                "resolved": resolved_ip,
                "version": status.version.name,
                "latency": round(status.latency),
                "players_online": status.players.online,
                "players_max": status.players.max,
                "player_names": player_list,
                "motd": motd
            }
        except Exception as e:
            return {"online": False, "error": str(e)}

    @staticmethod
    def format_info_text(data: dict):
        if "error" in data and data.get("desc"):
            return f"❌ <b>Ошибка:</b> {html.escape(data['desc'])}"
        
        if not data.get("online"):
            safe_ip = html.escape(data.get('ip', 'Unknown'))
            return f"🔴 <b>Сервер оффлайн</b>\n🌍 <b>IP:</b> <code>{safe_ip}</code>\n❌ Ошибка: Не удалось соединиться."

        # Экранирование данных
        safe_ip = html.escape(data['ip'])
        safe_version = html.escape(data['version'])
        safe_motd = html.escape(data.get('motd', ''))
        ping = data['latency']

        # Логика цвета пинга
        if ping < 100:
            status_icon = "🟢"
        elif ping < 300:
            status_icon = "🟡"
        else:
            status_icon = "🟠"
        
        # Сборка сообщения
        text = f"{status_icon} <b>Server Online</b>\n\n"
        
        if safe_motd:
            text += f"💬 <b>MOTD:</b> <i>{safe_motd}</i>\n"
            
        text += (
            f"🌍 <b>IP:</b> <code>{safe_ip}</code>\n"
            f"🛠 <b>Версия:</b> {safe_version}\n"
            f"📡 <b>Пинг:</b> {ping} ms\n"
            f"👥 <b>Игроки:</b> {data['players_online']} / {data['players_max']}\n"
        )
        
        if data['player_names']:
            safe_players = [html.escape(p) for p in data['player_names']]
            # Объединяем список через запятую
            players_str = ", ".join(safe_players[:10])
            text += f"\n📝 <b>В игре:</b> {players_str}"
            
            if len(data['player_names']) > 10:
                text += f" и еще {data['players_online'] - 10}..."
        
        return text


# --- MIDDLEWARE ---
class StatsAndBanMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: types.Update, data):
        user = None
        if event.message: user = event.message.from_user
        elif event.callback_query: user = event.callback_query.from_user
        
        if user:
            await db.add_user(user)
            if await db.is_user_banned(user.id):
                return
            
        return await handler(event, data)

# --- BOT SETUP ---
bot = Bot(token=CONFIG['bot_token'])
dp = Dispatcher(storage=MemoryStorage())
dp.update.middleware(StatsAndBanMiddleware())

# --- KEYBOARDS ---
def get_refresh_kb(ip):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"refresh_{ip}")]
    ])

def get_monitor_settings_kb(chat_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔔 Уведомления: (Вкл/Выкл)", callback_data=f"conf_notify_{chat_id}")],
        [InlineKeyboardButton(text="🔄 Пересоздать сообщение", callback_data=f"conf_resend_{chat_id}")],
        [InlineKeyboardButton(text="🗑 Удалить сервер", callback_data=f"conf_del_{chat_id}")]
    ])

def get_admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Банлист (Юзеры)", callback_data="adm_banlist_users"),
         InlineKeyboardButton(text="🚫 Банлист (IP)", callback_data="adm_banlist_ips")],
        [InlineKeyboardButton(text="📡 Список серверов", callback_data="adm_monitored_list")],
        [InlineKeyboardButton(text="🔄 Перезагрузка", callback_data="adm_restart"), 
         InlineKeyboardButton(text="✖ Закрыть", callback_data="adm_close")]
    ])

# --- HANDLERS: USER PRIVATE ---
@dp.message(F.chat.type == "private", CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "👋 <b>Привет! Я MCPing Bot.</b>\n\n"
        "Я могу показать статус Minecraft сервера или мониторить его в твоем чате.\n\n"
        "🔹 <b>ЛС Команды:</b>\n"
        "/info &lt;ip&gt; - Статус сервера\n"
        "/players &lt;ip&gt; - Игроки\n\n"
        "🔹 <b>Для Чатов:</b>\n"
        "Добавь меня в группу и используй /server_set.",
        parse_mode="HTML"
    )

@dp.message(F.chat.type == "private", Command("info"))
async def cmd_info(message: Message, command: CommandObject):
    if not command.args:
        return await message.answer("⚠️ Используйте: <code>/info ip</code>", parse_mode="HTML")
    
    msg = await message.answer("🔍 <i>Проверяю сервер...</i>", parse_mode="HTML")
    data = await MCUtils.get_server_info(command.args)
    text = MCUtils.format_info_text(data)
    
    await msg.edit_text(text, parse_mode="HTML", reply_markup=get_refresh_kb(command.args))

@dp.message(F.chat.type == "private", Command("players"))
async def cmd_players(message: Message, command: CommandObject):
    if not command.args:
        return await message.answer("⚠️ Используйте: <code>/players ip</code>", parse_mode="HTML")
    
    data = await MCUtils.get_server_info(command.args)
    if not data.get("online"):
        return await message.answer("🔴 Сервер оффлайн.", parse_mode="HTML")
    
    players = data.get("player_names", [])
    if not players:
        return await message.answer(f"👥 Игроков: {data['players_online']}. Список скрыт.", parse_mode="HTML")
    
    safe_players = [html.escape(p) for p in players]
    await message.answer(f"📜 <b>Игроки на {html.escape(command.args)}:</b>\n" + "\n".join([f"- {p}" for p in safe_players]), parse_mode="HTML")

@dp.callback_query(F.data.startswith("refresh_"))
async def cb_refresh(call: CallbackQuery):
    ip = call.data.split("_")[1]
    data = await MCUtils.get_server_info(ip)
    text = MCUtils.format_info_text(data)
    try:
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=get_refresh_kb(ip))
        await call.answer("✅ Обновлено")
    except:
        await call.answer("Без изменений")

# --- HANDLERS: GROUP ---
async def is_chat_moderator(chat_id: int, user_id: int):
    if user_id == OWNER_ID: return True
    chat_info = await db.get_chat(chat_id)
    if chat_info and chat_info[3] == user_id: return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except: return False

@dp.message(F.chat.type.in_({"group", "supergroup"}), Command("chat"))
async def cmd_group_chat(message: Message):
    if not await is_chat_moderator(message.chat.id, message.from_user.id): return
    await message.answer(f"✅ ID чата: <code>{message.chat.id}</code>", parse_mode="HTML")

@dp.message(F.chat.type.in_({"group", "supergroup"}), Command("server_set"))
async def cmd_server_set(message: Message, command: CommandObject):
    if not await is_chat_moderator(message.chat.id, message.from_user.id): return
    if not command.args: return await message.answer("⚠️ <code>/server_set ip</code>", parse_mode="HTML")
    
    ip = command.args.strip()
    data = await MCUtils.get_server_info(ip)
    text = MCUtils.format_info_text(data) + f"\n\n<i>🔄 Обновление: {UPDATE_INTERVAL}с.</i>"
    
    sent_msg = await message.answer(text, parse_mode="HTML")
    try: await sent_msg.pin()
    except: pass
    
    await db.set_server(message.chat.id, ip, sent_msg.message_id, message.from_user.id)
    await message.answer("✅ Сервер установлен. Настройки: /server_conf")

@dp.message(F.chat.type.in_({"group", "supergroup"}), Command("server_conf"))
async def cmd_server_conf(message: Message):
    if not await is_chat_moderator(message.chat.id, message.from_user.id): return
    if not await db.get_chat(message.chat.id):
        return await message.answer("⚠️ Сначала настройте сервер (/server_set).")
    await message.answer("⚙️ <b>Настройки</b>", parse_mode="HTML", reply_markup=get_monitor_settings_kb(message.chat.id))

@dp.callback_query(F.data.startswith("conf_"))
async def cb_conf(call: CallbackQuery):
    action, chat_id = call.data.split("_")[1], int(call.data.split("_")[2])
    if not await is_chat_moderator(chat_id, call.from_user.id):
        return await call.answer("⛔ Нет прав", show_alert=True)
    
    if action == "del":
        await db.delete_chat(chat_id)
        await call.message.edit_text("🗑 Мониторинг остановлен.")
    elif action == "resend":
        chat_info = await db.get_chat(chat_id)
        if chat_info:
            try: await bot.delete_message(chat_id, chat_info[2])
            except: pass
            data = await MCUtils.get_server_info(chat_info[1])
            text = MCUtils.format_info_text(data) + f"\n\n<i>🔄 Обновление: {UPDATE_INTERVAL}с.</i>"
            new_msg = await bot.send_message(chat_id, text, parse_mode="HTML")
            try: await new_msg.pin()
            except: pass
            await db.update_chat_config(chat_id, message_id=new_msg.message_id)
            await call.answer("✅ Пересоздано")
            await call.message.delete()
    elif action == "notify":
        chat_info = await db.get_chat(chat_id)
        new_state = 0 if chat_info[4] else 1
        await db.update_chat_config(chat_id, notify_down=new_state)
        await call.answer(f"Уведомления: {'ВКЛ' if new_state else 'ВЫКЛ'}")

# --- OWNER / MODERATION ---
@dp.message(F.chat.type == "private", Command("moderation"))
async def cmd_moderation(message: Message):
    if message.from_user.id != OWNER_ID: return
    
    users_count, servers_count = await db.get_general_stats()
    total_pings = await db.get_total_pings()
    uptime = str(datetime.timedelta(seconds=int(time.time() - BOT_START_TIME))).split('.')[0]
    
    text = (
        f"👑 <b>Admin Dashboard</b>\n\n"
        f"⏱ <b>Uptime:</b> {uptime}\n"
        f"📡 <b>Total Requests (Pings):</b> {total_pings}\n"
        f"👤 <b>Total Users:</b> {users_count}\n"
        f"🖥 <b>Monitored Servers:</b> {servers_count}\n"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_admin_kb())

@dp.callback_query(F.data.startswith("adm_"))
async def cb_admin_actions(call: CallbackQuery):
    if call.from_user.id != OWNER_ID: return
    action = call.data
    
    if action == "adm_close":
        await call.message.delete()
        
    elif action == "adm_restart":
        await call.answer("Перезагрузка...")
        sys.exit(0)
        
    elif action == "adm_banlist_users":
        users = await db.get_banlist_users()
        if not users: return await call.answer("Список пуст", show_alert=True)
        
        # Format: n. date, username/link - id: reason
        text = "🚫 <b>Заблокированные пользователи:</b>\n\n"
        for idx, u in enumerate(users, 1):
            uid, reason, date, uname, fullname = u
            display_name = html.escape(uname if uname else (fullname if fullname else "NoName"))
            link = f"<a href='tg://user?id={uid}'>{display_name}</a>"
            text += f"{idx}. {date}, {link} - <code>{uid}</code>: {html.escape(reason)}\n"
            
        # Split text if too long (basic handling)
        if len(text) > 4000: text = text[:4000] + "\n..."
        await call.message.answer(text, parse_mode="HTML")
        await call.answer()
        
    elif action == "adm_banlist_ips":
        ips = await db.get_banlist_ips()
        if not ips: return await call.answer("Список пуст", show_alert=True)
        
        # Format: n. date, domen (ip): reason
        text = "🚫 <b>Заблокированные IP:</b>\n\n"
        for idx, item in enumerate(ips, 1):
            ip_addr, reason, date, domain = item
            entry = f"{domain} ({ip_addr})" if domain else ip_addr
            text += f"{idx}. {date}, <b>{html.escape(entry)}</b>: {html.escape(reason)}\n"
            
        await call.message.answer(text, parse_mode="HTML")
        await call.answer()

    elif action == "adm_monitored_list":
        chats = await db.get_all_monitored_chats()
        if not chats: return await call.answer("Список пуст", show_alert=True)
        
        text = "📡 <b>Мониторинг серверов:</b>\n\n"
        for idx, c in enumerate(chats, 1):
            chat_id, ip, _, _, status, _ = c
            status_icon = "🟢" if status == "UP" else ("🔴" if status == "DOWN" else "⚪️")
            
            # --- НАЧАЛО ИЗМЕНЕНИЙ ---
            try:
                # Получаем информацию о чате от Telegram
                chat_obj = await bot.get_chat(chat_id)
                chat_title = html.escape(chat_obj.title or "Chat")
                
                if chat_obj.username:
                    # Если у чата есть ссылка (публичный)
                    chat_ref = f"<a href='https://t.me/{chat_obj.username}'>{chat_title}</a>"
                else:
                    # Если приватный, оставляем название и ID (ссылку на приватный чат бот может не знать)
                    chat_ref = f"{chat_title} ({chat_id})"
            except Exception:
                # Если бот кикнут или чат удален
                chat_ref = f"Недоступный чат (<code>{chat_id}</code>)"
            
            text += f"{idx}. {status_icon} <code>{html.escape(ip)}</code> — {chat_ref}\n"
            # --- КОНЕЦ ИЗМЕНЕНИЙ ---
            
        await call.message.answer(text[:4000], parse_mode="HTML")
        await call.answer()

@dp.message(Command("ban"), F.from_user.id == OWNER_ID)
async def cmd_ban(message: Message, command: CommandObject):
    target_id = None
    reason = "No reason"
    
    # 1. Check if Reply
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        if command.args:
            reason = command.args
    # 2. Check Arguments
    elif command.args:
        parts = command.args.split(maxsplit=1)
        try:
            target_id = int(parts[0])
            if len(parts) > 1: reason = parts[1]
        except ValueError:
            return await message.answer("❌ ID должен быть числом или используйте Reply.")
            
    if not target_id:
        return await message.answer("ℹ️ <b>Как банить:</b>\n1. Ответьте на сообщение юзера: <code>/ban причина</code>\n2. Или по ID: <code>/ban 12345 причина</code>", parse_mode="HTML")

    if target_id == OWNER_ID:
        return await message.answer("🤡 Себя банить нельзя.")
        
    user_info = await db.get_user_info(target_id)
    admin_name = message.from_user.full_name
    await db.ban_user(target_id, reason, admin_name)
    
    name_display = f"<code>{target_id}</code>"
    if user_info:
        name_display = f"<a href='tg://user?id={target_id}'>{html.escape(user_info[1] or 'User')}</a> (<code>{target_id}</code>)"
        
    await message.answer(f"🚫 Пользователь {name_display} заблокирован.\n📝 Причина: {html.escape(reason)}", parse_mode="HTML")

@dp.message(Command("unban"), F.from_user.id == OWNER_ID)
async def cmd_unban(message: Message, command: CommandObject):
    if not command.args: return
    try:
        uid = int(command.args.split()[0])
        await db.unban_user(uid)
        await message.answer(f"✅ Пользователь <code>{uid}</code> разбанен.", parse_mode="HTML")
    except:
        await message.answer("Ошибка ID.")

@dp.message(Command("banip"), F.from_user.id == OWNER_ID)
async def cmd_banip(message: Message, command: CommandObject):
    if not command.args: return await message.answer("/banip ip/domain reason")
    parts = command.args.split(maxsplit=1)
    addr = parts[0]
    reason = parts[1] if len(parts) > 1 else "No reason"
    
    resolved = MCUtils.resolve_ip(addr)
    target = resolved if resolved else addr
    
    # Сохраняем домен, если мы банили по домену, для красивого вывода
    domain_hint = addr if resolved and addr != resolved else None
    
    await db.ban_ip(target, reason, domain_hint)
    await message.answer(f"🚫 IP <code>{target}</code> заблокирован.\nДомен: {html.escape(str(domain_hint))}", parse_mode="HTML")

@dp.message(Command("unbanip"), F.from_user.id == OWNER_ID)
async def cmd_unbanip(message: Message, command: CommandObject):
    if not command.args:
        return await message.answer("⚠️ Используйте: <code>/unbanip ip</code>", parse_mode="HTML")
    
    target = command.args.strip()
    
    # Пытаемся удалить как есть (если ввели IP)
    await db.unban_ip(target)
    
    # На всякий случай пытаемся разрезолвить, если ввели домен, 
    # так как в базе хранятся именно IP адреса
    resolved = MCUtils.resolve_ip(target)
    if resolved and resolved != target:
        await db.unban_ip(resolved)
        
    await message.answer(f"✅ IP (или домен) <code>{html.escape(target)}</code> удален из черного списка.", parse_mode="HTML")


# --- BACKGROUND MONITORING ---
async def monitoring_loop():
    logger.info("Starting loop...")
    while True:
        try:
            chats = await db.get_all_monitored_chats()
            for chat in chats:
                chat_id, ip, msg_id, _, last_status, notify = chat
                
                data = await MCUtils.get_server_info(ip)
                new_text = MCUtils.format_info_text(data) + f"\n\n<i>🔄 Обновление: {UPDATE_INTERVAL}с.</i>"
                cur_status = "UP" if data.get("online") else "DOWN"
                
                try:
                    await bot.edit_message_text(text=new_text, chat_id=chat_id, message_id=msg_id, parse_mode="HTML")
                except Exception as e:
                    if "chat not found" in str(e) or "kicked" in str(e):
                        await db.delete_chat(chat_id)
                        continue
                
                if notify and last_status != "UNKNOWN" and last_status != cur_status:
                    if cur_status == "DOWN":
                        try: await bot.send_message(chat_id, f"⚠️ <b>ALERT:</b> Сервер {ip} упал!", parse_mode="HTML")
                        except: pass
                
                if last_status != cur_status:
                    await db.update_chat_config(chat_id, last_status=cur_status)
                
                await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Loop err: {e}")
        await asyncio.sleep(UPDATE_INTERVAL)

async def main():
    await db.init_db()
    asyncio.create_task(monitoring_loop())
    logger.info("Bot started!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try: asyncio.run(main())
    except: pass
