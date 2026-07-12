import asyncio
import sqlite3
from datetime import datetime
import os
import sys

from sqlalchemy import select

# Добавляем корневую директорию проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mc_ping_bot.database.session import get_session_factory, get_engine
from mc_ping_bot.database.models.user import User, UserRole
from mc_ping_bot.database.models.server import Server
from mc_ping_bot.database.models.chat import Chat
from mc_ping_bot.database.models.monitored_server import MonitoredServer
from mc_ping_bot.database.models.ban import Ban
from mc_ping_bot.database.models.base import Base

SQLITE_DB_PATH = "bot_database.db"

async def migrate():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    session_factory = get_session_factory()
    
    try:
        sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
        sqlite_cursor = sqlite_conn.cursor()
    except Exception as e:
        print(f"Ошибка открытия SQLite базы: {e}")
        return

    async with session_factory() as pg_session:
        # 1. Перенос пользователей
        sqlite_cursor.execute("SELECT user_id, username, full_name, first_seen FROM users")
        users = sqlite_cursor.fetchall()
        for u in users:
            created_at = datetime.now()
            if u[3]:
                try: created_at = datetime.strptime(u[3], "%d.%m.%Y")
                except: pass
            
            pg_user = User(
                id=u[0],
                username=u[1],
                full_name=u[2] or "Minecraft User",
                role=UserRole.USER,
                created_at=created_at
            )
            await pg_session.merge(pg_user)
        print(f"✅ Пользователи перенесены: {len(users)}")

        # 2. Перенос серверов и мониторинга
        sqlite_cursor.execute("SELECT chat_id, server_ip, message_id, moderator_id, last_status, notify_down FROM chats")
        chats = sqlite_cursor.fetchall()
        
        for c in chats:
            chat_id, server_ip, message_id, moderator_id, last_status, notify_down = c
            added_by = moderator_id or users[0][0]
            
            # Проверяем, существует ли уже сервер с таким IP
            stmt = select(Server).where(Server.ip_address == server_ip)
            result = await pg_session.execute(stmt)
            existing_server = result.scalar_one_or_none()
            
            if not existing_server:
                # Создаем новый сервер
                new_server = Server(
                    ip_address=server_ip,
                    last_known_status=(last_status == "UP")
                )
                pg_session.add(new_server)
                await pg_session.flush() # Получаем ID нового сервера
                server_id = new_server.id
            else:
                server_id = existing_server.id
            
            # Убеждаемся, что чат существует
            stmt = select(Chat).where(Chat.id == chat_id)
            if not (await pg_session.execute(stmt)).scalar_one_or_none():
                pg_chat = Chat(
                    id=chat_id,
                    title=f"Migrated Chat {chat_id}",
                    added_by_user_id=added_by
                )
                pg_session.add(pg_chat)
                await pg_session.flush()
                
            # Создаем связь в таблице MonitoredServer
            # Проверяем, нет ли уже такой связи (один чат + один и тот же сервер)
            stmt = select(MonitoredServer).where(
                MonitoredServer.chat_id == chat_id,
                MonitoredServer.server_id == server_id
            )
            if not (await pg_session.execute(stmt)).scalar_one_or_none():
                monitored = MonitoredServer(
                    chat_id=chat_id,
                    server_id=server_id,
                    added_by_user_id=added_by,
                    message_id=message_id,
                    notify_down=bool(notify_down),
                    last_status=last_status
                )
                pg_session.add(monitored)
            
        print(f"✅ Чаты (мониторинг) перенесены: {len(chats)}")

        # 3. Перенос банов юзеров
        sqlite_cursor.execute("SELECT user_id, reason, banned_at FROM ban_users")
        bans = sqlite_cursor.fetchall()
        for b in bans:
            stmt = select(Ban).where(Ban.user_id == b[0])
            res = await pg_session.execute(stmt)
            if not res.scalar_one_or_none():
                pg_ban = Ban(
                    user_id=b[0],
                    reason=b[1],
                    is_active=True
                )
                pg_session.add(pg_ban)
        print(f"✅ Баны перенесены: {len(bans)}")

        await pg_session.commit()
        print("🚀 Миграция SQLite -> PostgreSQL успешно завершена!")

if __name__ == "__main__":
    asyncio.run(migrate())
