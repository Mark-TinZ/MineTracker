# 05. Сервисы и Фоновые задачи (Background Workers)



Чтобы хендлеры (обработчики Telegram) работали быстро и не блокировали Event Loop (цикл событий), вся тяжелая логика, работа с внешними API (например, `mcstatus`), кэшем и периодическими проверками должна выноситься в директорию `mc_ping_bot/services/`.



---



## 1. Написание сервисов бизнес-логики



Сервисы инкапсулируют сложную логику, делая её переиспользуемой. Например, функция пингования сервера должна не только обращаться к серверу, но и проверять SRV-записи, защищать сервер от SSRF-атак и взаимодействовать с кэшем.



### Пример: `MinecraftService`



Сервис создается один раз при старте бота в `__main__.py` и прокидывается во все хендлеры.



```python

from typing import Any, Dict

import asyncio

from mcstatus import JavaServer



from mc_ping_bot.security.ssrf import resolve_and_validate_ip

from mc_ping_bot.services.cache import RedisCacheManager



class MinecraftService:

    """

    Сервис бизнес-логики. Не знает ничего про интерфейс Telegram.

    """

    def __init__(self, cache_manager: RedisCacheManager) -> None:

        self.cache = cache_manager



    async def get_server_info(self, address: str, port: int = 25565) -> Dict[str, Any]:

        # 1. Проверка кеша (снижает нагрузку на сеть)

        cached_data = await self.cache.get_server_data(address, port)

        if cached_data:

            return cached_data



        try:

            # 2. Резолв SRV записей 

            target = f"{address}:{port}" if port != 25565 else address

            server = await JavaServer.async_lookup(target)

            

            # 3. Инкапсулированная безопасность: защита от SSRF (обращения бота к localhost/LAN)

            safe_ip, safe_port = await resolve_and_validate_ip(

                server.address.host, 

                server.address.port

            )

            

            safe_server = JavaServer(safe_ip, safe_port)

            

            # 4. Ограничиваем ожидание таймаутом

            status = await asyncio.wait_for(safe_server.async_status(), timeout=10.0)

            

            # ... парсинг ответа ...

            data = {"online": True, "latency": status.latency}

            

            # Обновление кеша

            await self.cache.set_server_data(address, port, data)

            return data

            

        except Exception as e:

            return {"online": False, "error": str(e)}

```



**Правило:** Сервисы возвращают чистые данные (словари, датаклассы или Pydantic-модели). Форматированием этих данных в текст (HTML/Markdown) занимается сам хендлер.



---



## 2. Фоновые задачи (Background Workers)



Фоновые воркеры используются для задач, которые должны работать непрерывно и независимо от входящих сообщений. Например, `monitor.py` отвечает за автоматическое обновление статуса серверов в чатах (Heartbeat) и `subscription_downgrade_worker` — за снятие премиум-подписок по истечению их срока.



### Как не потерять задачу (Проблема Garbage Collector)



Если вы запустите задачу с помощью `asyncio.create_task()` и нигде не сохраните ссылку на нее, **сборщик мусора Python (Garbage Collector)** может уничтожить (отменить) её прямо во время выполнения! Это частая ошибка в асинхронном программировании.



Для решения этой проблемы в `__main__.py` создается специальное множество (set) `background_tasks`.



### Пример запуска воркера (`__main__.py`)



```python

import asyncio

from aiogram import Dispatcher



from mc_ping_bot.services.monitor import subscription_downgrade_worker, start_monitoring_loop



# Глобальное хранилище ссылок на таски (чтобы GC их не удалил)

background_tasks = set()



async def on_startup(dispatcher: Dispatcher) -> None:

    """

    Срабатывает один раз при запуске бота. 

    Идеальное место для инициализации воркеров.

    """

    

    # Воркер 1: Даунгрейд премиум-подписок

    task_downgrade = asyncio.create_task(subscription_downgrade_worker(AsyncSessionLocal))

    # 1. Добавляем таску в множество, удерживая строгую ссылку

    background_tasks.add(task_downgrade)

    # 2. Регистрируем коллбек: как только таска завершится, она удалит себя из множества

    task_downgrade.add_done_callback(background_tasks.discard)

    

    # Воркер 2: Мониторинг серверов

    task_monitor = asyncio.create_task(start_monitoring_loop(bot, AsyncSessionLocal, mc_service))

    background_tasks.add(task_monitor)

    task_monitor.add_done_callback(background_tasks.discard)

```



### Graceful Shutdown (Мягкое завершение)



Если остановить скрипт (`Ctrl+C` или остановка Docker контейнера), нужно дать фоновым задачам шанс завершиться корректно и не порвать транзакции базы данных или соединения Redis.



```python

async def on_shutdown(dispatcher: Dispatcher) -> None:

    """

    Срабатывает перед остановкой бота.

    """

    # 1. Отмена (Cancel) всех запущенных фоновых задач

    for task in background_tasks:

        task.cancel()

        

    # 2. Корректное закрытие сессий библиотек

    await bot.session.close()

    await redis_client.close()

    await engine.dispose()

```



При отмене таски с помощью `task.cancel()`, внутри функции-воркера генерируется исключение `asyncio.CancelledError`.



### Пример внутренностей воркера (`monitor.py`)



```python

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker



async def subscription_downgrade_worker(sessionmaker: async_sessionmaker) -> None:

    """

    Раз в час проверяет истекшие премиум-подписки.

    """

    try:

        while True:

            # Обязательно используем собственную сессию, так как мы работаем вне хендлеров

            async with sessionmaker() as session:

                # Логика работы с БД...

                pass

                

            # Засыпаем на 1 час (3600 сек)

            await asyncio.sleep(3600)

            

    except asyncio.CancelledError:

        # Сюда скрипт попадет во время on_shutdown()

        # Здесь можно добавить логику "последнего слова" или корректного закрытия

        print("Worker stopped safely.")

```

