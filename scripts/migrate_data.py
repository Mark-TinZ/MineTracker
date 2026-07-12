import asyncio
import logging
import sqlite3
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Подключаем модели новой базы
from mc_ping_bot.core.config import settings
from mc_ping_bot.database.models.user import User, UserRole
from mc_ping_bot.database.models.server import Server
from mc_ping_bot.database.models.chat import Chat
from mc_ping_bot.database.models.ban import Ban

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migration")

LEGACY_DB_PATH = "bot_database.db"
OWNER_ID = getattr(settings, 'owner_id', 0)

async def migrate():
    logger.info("Начинаем миграцию данных...")
    
    # 1. Подключение к старой базе
    try:
        old_db = sqlite3.connect(LEGACY_DB_PATH)
        old_db.row_factory = sqlite3.Row
        old_cursor = old_db.cursor()
    except Exception as e:
        logger.error(f"Не удалось подключиться к старой базе: {e}")
        return

    # 2. Подключение к новой базе
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        # --- МИГРАЦИЯ ПОЛЬЗОВАТЕЛЕЙ ---
        logger.info("Миграция пользователей...")
        try:
            old_cursor.execute("SELECT * FROM users")
            old_users = old_cursor.fetchall()
        except Exception as e:
            logger.warning(f"Ошибка чтения users (возможно база пуста): {e}")
            old_users = []
        
        user_map: Dict[str, int] = {} # username -> user_id (для банов)

        for row in old_users:
            u_id = row["user_id"]
            u_name = row["username"]
            
            if u_name:
                user_map[u_name] = u_id
                
            # Проверяем существует ли
            res = await session.execute(select(User).where(User.id == u_id))
            if res.scalar_one_or_none() is None:
                role = UserRole.OWNER if u_id == OWNER_ID else UserRole.USER
                new_user = User(
                    id=u_id,
                    username=u_name,
                    full_name=row["full_name"] or "Unknown",
                    role=role
                )
                session.add(new_user)
        
        await session.commit()
        logger.info(f"Перенесено/проверено {len(old_users)} пользователей.")

        # --- МИГРАЦИЯ СЕРВЕРОВ И ЧАТОВ ---
        logger.info("Миграция серверов и чатов...")
        try:
            old_cursor.execute("SELECT * FROM chats")
            old_chats = old_cursor.fetchall()
        except Exception as e:
            logger.warning(f"Ошибка чтения chats: {e}")
            old_chats = []

        for row in old_chats:
            ip_address = row["server_ip"]
            chat_id = row["chat_id"]
            mod_id = row["moderator_id"]
            
            if not ip_address:
                continue

            # Ищем или создаем сервер
            res = await session.execute(select(Server).where(Server.ip_address == ip_address))
            server = res.scalar_one_or_none()
            if not server:
                server = Server(ip_address=ip_address, port=25565)
                session.add(server)
                await session.flush() # Получаем ID сервера

            # Проверяем существует ли чат
            res = await session.execute(select(Chat).where(Chat.id == chat_id))
            if res.scalar_one_or_none() is None:
                new_chat = Chat(
                    id=chat_id,
                    title=f"Migrated Chat {chat_id}",
                    server_id=server.id,
                    added_by_user_id=mod_id if mod_id else OWNER_ID,
                    message_id=row["message_id"],
                    notify_down=bool(row["notify_down"]),
                    last_status="ONLINE" if row["last_status"] == "UP" else "OFFLINE"
                )
                session.add(new_chat)
                
        await session.commit()
        logger.info("Чаты и серверы перенесены.")

        # --- МИГРАЦИЯ БАНОВ ---
        logger.info("Миграция банов пользователей...")
        try:
            old_cursor.execute("SELECT * FROM ban_users")
            old_ban_users = old_cursor.fetchall()
        except Exception:
            old_ban_users = []

        for row in old_ban_users:
            banned_user_id = row["user_id"]
            banned_by_str = row["banned_by"]
            reason = row["reason"]
            
            # Fallback для администратора
            admin_id = OWNER_ID
            if banned_by_str and banned_by_str in user_map:
                admin_id = user_map[banned_by_str]
            else:
                logger.warning(f"Fallback: Не удалось найти админа '{banned_by_str}' для бана юзера {banned_user_id}. Назначен OWNER_ID.")

            # Проверяем, существует ли уже такой бан
            res = await session.execute(
                select(Ban).where(Ban.user_id == banned_user_id)
            )
            if res.scalar_one_or_none() is None:
                ban = Ban(
                    user_id=banned_user_id,
                    reason=reason,
                    admin_id=admin_id
                )
                session.add(ban)

        logger.info("Миграция банов IP...")
        try:
            old_cursor.execute("SELECT * FROM ban_ips")
            old_ban_ips = old_cursor.fetchall()
        except Exception:
            old_ban_ips = []

        for row in old_ban_ips:
            ip = row["ip"]
            reason = row["reason"]
            
            # Находим сервер по IP
            res = await session.execute(select(Server).where(Server.ip_address == ip))
            server = res.scalar_one_or_none()
            if not server:
                server = Server(ip_address=ip, port=25565)
                session.add(server)
                await session.flush()
                
            # Проверяем наличие бана
            res = await session.execute(
                select(Ban).where(Ban.server_id == server.id)
            )
            if res.scalar_one_or_none() is None:
                ban = Ban(
                    server_id=server.id,
                    reason=reason,
                    admin_id=OWNER_ID  # В старой БД не было banned_by для IP
                )
                session.add(ban)

        await session.commit()
        logger.info("Миграция банов завершена.")

    old_db.close()
    logger.info("✅ Миграция данных успешно завершена!")

if __name__ == "__main__":
    asyncio.run(migrate())
