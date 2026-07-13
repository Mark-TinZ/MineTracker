# 02. Архитектура и Внедрение зависимостей (Dependency Injection)



Проект **MineTracker** спроектирован по принципам многослойной архитектуры (Layered Architecture) с использованием **Dependency Injection (DI)**. Данный подход гарантирует высокую тестируемость, отсутствие сильного зацепления компонентов (Loose Coupling) и предотвращает типичные проблемы утечек соединений с базой данных.



---



## 🏗 Слоистая архитектура



Кодовая база приложения жестко разделена на независимые слои, каждый из которых выполняет свою специфичную задачу. Запрещается смешивать ответственность слоев!



1. **Слой Telegram (`mc_ping_bot/bot/`)**

   - **Ответственность:** Прием апдейтов (сообщений, коллбеков) от Telegram API, маршрутизация, формирование текста ответов и клавиатур.

   - **Ограничения:** Хендлеры не должны содержать бизнес-логику (например, резолв DNS) или "тяжелые" вычисления. Их единственная задача — принять запрос, вызвать сервис и вернуть результат.



2. **Слой Бизнес-логики (`mc_ping_bot/services/`)**

   - **Ответственность:** Опрос серверов (`MinecraftService`), управление кэшем (`RedisCacheManager`), валидация SSRF-атак, фоновые воркеры (`monitor.py`).

   - **Ограничения:** Сервисы не должны ничего знать об `Aiogram` (кроме фоновых воркеров, рассылающих сообщения). Они получают данные, обрабатывают их и возвращают структурированный результат.



3. **Слой Данных (`mc_ping_bot/db/`)**

   - **Ответственность:** Описание ORM-моделей SQLAlchemy (`models.py`), инициализация пула соединений с PostgreSQL (`database.py`).

   - **Ограничения:** Этот слой не выполняет запросы самостоятельно, он лишь предоставляет структуру данных (модели) и инструмент для работы с ней (`AsyncSessionLocal`).



---



## 🔄 Пайплайн обработки апдейта



Когда пользователь отправляет сообщение боту, апдейт проходит строгий жизненный цикл:



1. **Long Polling / Webhook**: `Aiogram Dispatcher` получает входящий апдейт от Telegram API.

2. **Outer Middlewares**: Апдейт проходит через внешние слои `Middleware` **до** проверки фильтров маршрутизатора. На этом этапе срабатывает `DatabaseMiddleware` — открывается транзакция базы данных.

3. **Routing & Filters**: Диспетчер ищет подходящий `Router` и хендлер, проверяя фильтры (например, `Command("info")`).

4. **Inner Middlewares**: Апдейт проходит внутренние мидлвари (например, `RateLimitMiddleware` проверяет наличие лимитов в Redis).

5. **Handler**: Если все фильтры и мидлвари пройдены, управление передается хендлеру. Хендлер получает готовые зависимости (сессию БД, сервис).

6. **Post-processing**: После завершения работы хендлера (или при возникновении исключения), выполнение возвращается по цепочке мидлварей в обратном порядке. На этапе `DatabaseMiddleware` блок `async with` завершается, и сессия **безопасно закрывается**. Внимание: сессия *не* делает автоматический commit, разработчик обязан вызывать `await session.commit()` вручную для сохранения изменений (INSERT/UPDATE/DELETE).



---



## 💉 Dependency Injection и Middleware



Вам **строго запрещено** создавать сессии с базой данных внутри хендлеров вручную (например, `async with AsyncSessionLocal() as session:`). Это приводит к дублированию кода, сложностям с транзакциями и утечкам соединений.



Вместо этого мы используем механизм **Dependency Injection**, встроенный в Aiogram, через `DatabaseMiddleware`.



### Как работает DatabaseMiddleware



Мидлварь перехватывает каждый входящий апдейт, создает сессию БД и прокидывает ее в словарь `data`, который передается в хендлер.



```python

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware

from aiogram.types import TelegramObject

from sqlalchemy.ext.asyncio import async_sessionmaker



class DatabaseMiddleware(BaseMiddleware):

    """

    Внедряет асинхронную сессию БД во все хендлеры, гарантируя ее безопасное закрытие.

    """

    def __init__(self, sessionmaker: async_sessionmaker) -> None:

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

```



### Проброс сервисов



Помимо сессии БД, при инициализации бота (в `__main__.py`) в глобальный контекст диспетчера прокидываются бизнес-сервисы. Это позволяет иметь один глобальный инстанс сервиса для всего приложения:



```python

# __main__.py

redis_client = Redis.from_url(config.redis_url)

cache_manager = RedisCacheManager(redis_client)

mc_service = MinecraftService(cache_manager)



# Проброс в Dispatcher

dp["mc_service"] = mc_service

```



### Как использовать зависимости в Хендлере



Всё, что было проброшено в `data` (через мидлварь) или в глобальный контекст `dp`, можно получить в хендлере, просто указав аргумент с соответствующим именем. Aiogram автоматически выполнит маппинг.



**Пример правильного использования:**



```python

from aiogram import Router

from aiogram.types import Message

from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select



from mc_ping_bot.db.models import User

from mc_ping_bot.services.minecraft import MinecraftService



router = Router()



@router.message()

async def example_handler(

    message: Message, 

    session: AsyncSession,          # Получаем сессию от DatabaseMiddleware

    mc_service: MinecraftService    # Получаем сервис из глобального словаря dp

) -> None:

    # Мы сразу можем выполнять запросы к БД, не открывая сессию!

    user = await session.scalar(select(User).where(User.tg_id == message.from_user.id))

    

    # Мы можем напрямую использовать методы сервиса

    server_data = await mc_service.get_server_info("mc.hypixel.net")

    

    await message.answer(f"Привет, {user.role}! Статус: {server_data['online']}")

    

    # Внимание: Для INSERT, UPDATE и DELETE запросов вы ОБЯЗАНЫ вызвать:

    # await session.commit()

    # Мидлварь не делает авто-коммит! Но вызывать session.close() не нужно,

    # конструкция async with внутри мидлвари сделает это автоматически.

```



Благодаря этой архитектуре ваши хендлеры становятся "чистыми функциями", а логика получения подключений скрывается на уровне фреймворка.

