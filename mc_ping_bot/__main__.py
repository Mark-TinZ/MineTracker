import asyncio
import logging
import sys
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import TelegramObject
from redis.asyncio import Redis

# Импорт конфигурации
from mc_ping_bot.config import config

# Импорт БД
from mc_ping_bot.db.database import AsyncSessionLocal, engine

# Импорт сервисов
from mc_ping_bot.services.cache import RedisCacheManager
from mc_ping_bot.services.minecraft import MinecraftService
from mc_ping_bot.services.monitor import subscription_downgrade_worker

# Импорт хендлеров и миддлварей
from mc_ping_bot.bot.handlers import setup_routers


class DatabaseMiddleware(BaseMiddleware):
    """
    Middleware для внедрения (Dependency Injection) асинхронной сессии БД 
    в хендлеры (позволяет использовать session: AsyncSession в сигнатуре).
    """
    def __init__(self, sessionmaker):
        self.sessionmaker = sessionmaker

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        async with self.sessionmaker() as session:
            data["session"] = session
            return await handler(event, data)


async def main():
    # 1. Настройка базового логирования
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout
    )
    logger = logging.getLogger(__name__)
    logger.info("Starting Minecraft Ping Bot initialization...")

    # 2. Инициализация клиента Redis и Кеш-менеджера
    redis_client = Redis.from_url(config.redis_url, decode_responses=True)
    cache_manager = RedisCacheManager(redis_client)
    
    # 3. Инициализация бизнес-логики (Ядро Minecraft)
    mc_service = MinecraftService(cache_manager)

    # 4. Инициализация Aiogram 3 (Bot и Dispatcher)
    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()

    # 5. Внедрение глобальных зависимостей (Доступно во всех хендлерах)
    dp["mc_service"] = mc_service
    dp["sessionmaker"] = AsyncSessionLocal

    # 6. Регистрация Middleware
    # Outer middleware срабатывает ДО любых фильтров, что идеально для получения БД-сессии
    dp.update.outer_middleware(DatabaseMiddleware(AsyncSessionLocal))
    
    from mc_ping_bot.bot.middlewares.rate_limit import RateLimitMiddleware
    from mc_ping_bot.bot.middlewares.album import AlbumMiddleware

    # Rate Limit применяется к конкретным типам апдейтов
    rate_limit_mdw = RateLimitMiddleware(redis_client, rate_limit=30)
    dp.message.middleware(rate_limit_mdw)
    dp.callback_query.middleware(rate_limit_mdw)
    
    album_mdw = AlbumMiddleware(latency=0.6)
    dp.message.middleware(album_mdw)

    # 7. Подключение роутеров через бота
    setup_routers(dp)

    # 8. Настройка фоновых задач и Graceful Shutdown
    background_tasks = set()

    async def on_startup(dispatcher: Dispatcher):
        logger.info("Bot is starting. Running background workers...")
        
        # Установка глобальных команд
        from mc_ping_bot.bot.commands_setup import set_global_commands
        await set_global_commands(bot)
        logger.info("Global commands mapped successfully.")
        
        # Запуск фонового воркера даунгрейда подписок
        # Обязательно сохраняем ссылку на таску, чтобы сборщик мусора Python (GC) её не убил!
        task = asyncio.create_task(subscription_downgrade_worker(AsyncSessionLocal))
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)
        
        # Запуск основного цикла мониторинга (Background Heartbeat)
        from mc_ping_bot.services.monitor import start_monitoring_loop
        task_loop = asyncio.create_task(start_monitoring_loop(bot, AsyncSessionLocal, mc_service))
        background_tasks.add(task_loop)
        task_loop.add_done_callback(background_tasks.discard)

    async def on_shutdown(dispatcher: Dispatcher):
        logger.warning("Bot is shutting down. Graceful shutdown initiated...")
        
        # 1. Отмена фоновых задач
        for task in background_tasks:
            task.cancel()
        
        # 2. Закрытие сессии бота (чтобы предотвратить TimeoutError при завершении)
        await bot.session.close()
        
        # 3. Закрытие соединения с Redis
        await redis_client.close()
        
        # 4. Закрытие пула соединений PostgreSQL
        await engine.dispose()
        
        logger.info("All connections closed cleanly. Goodbye!")

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # 9. Запуск Polling
    try:
        # Сбрасываем старые апдейты, чтобы бот не спамил при запуске
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        logger.info("Bot polling stopped.")


if __name__ == "__main__":
    try:
        # Для корректной работы с asyncio в Python 3.8+
        asyncio.run(main())
    except KeyboardInterrupt:
        # Игнорируем трейсбек при нажатии Ctrl+C
        pass
