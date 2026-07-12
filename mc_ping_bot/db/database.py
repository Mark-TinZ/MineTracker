from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mc_ping_bot.config import config
from mc_ping_bot.db.models import Base

# Инициализация асинхронного движка PostgreSQL
engine = create_async_engine(
    config.db_dsn,
    echo=False,  # Выключить логгирование SQL в production для производительности
    pool_size=20,
    max_overflow=10,
    pool_recycle=3600
)

# Фабрика сессий для внедрения зависимостей (Dependency Injection)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

async def get_session():
    """
    Генератор (Dependency) для получения асинхронной сессии БД.
    Используется в Aiogram хендлерах.
    """
    async with AsyncSessionLocal() as session:
        yield session
