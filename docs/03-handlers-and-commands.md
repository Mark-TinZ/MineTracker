# 03. Создание хендлеров и команд



Добавление нового функционала (команд бота) в **MineTracker** — это структурированный процесс, который требует соблюдения стандартов. Этот документ описывает полный цикл: от написания логики до регистрации новой команды в меню бота.



---



## 1. Создание нового хендлера



В Aiogram 3 для группировки обработчиков используется класс `Router`. Все хендлеры хранятся в директории `mc_ping_bot/bot/handlers/`. Если вы добавляете логику, которая не подходит ни к одному существующему модулю, создайте новый файл (например, `stats.py`).



### Шаг 1. Создание CallbackData класса



Проект использует **строгую типизацию для callback_data**. Запрещено использовать обычные строки в коллбеках кнопок! Сначала объявите класс для ваших кнопок в `mc_ping_bot/bot/keyboards/callback_data.py`:



```python

# mc_ping_bot/bot/keyboards/callback_data.py

from aiogram.filters.callback_data import CallbackData



class StatsCallback(CallbackData, prefix="stats"):

    """Callback для кнопок обновления статистики сервера.

    

    Attributes:

        ip: Строковый IP-адрес сервера.

    """

    ip: str

```



### Шаг 2. Написание логики хендлера (app/bot/handlers/stats.py)



```python

from aiogram import Router

from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from aiogram.filters import Command

from sqlalchemy.ext.asyncio import AsyncSession



# Локальные импорты проекта

from mc_ping_bot.bot.keyboards.callback_data import StatsCallback

from mc_ping_bot.db.models import User

from mc_ping_bot.services.minecraft import MinecraftService



# 1. Создаем инстанс роутера для этого модуля

router = Router()



# 2. Функция для генерации клавиатуры с использованием типизированного CallbackData

def get_stats_keyboard(server_ip: str) -> InlineKeyboardMarkup:

    return InlineKeyboardMarkup(

        inline_keyboard=[

            [

                InlineKeyboardButton(

                    text="🔄 Обновить статистику", 

                    # Формируем строку автоматически через метод .pack()

                    callback_data=StatsCallback(ip=server_ip).pack()

                )

            ]

        ]

    )



# 3. Декоратор регистрации обработчика команды /stats

@router.message(Command("stats"))

async def cmd_stats(message: Message, session: AsyncSession, mc_service: MinecraftService) -> None:

    """

    Обработчик команды /stats.

    Сессия и сервис инжектятся автоматически (см. 02-architecture.md).

    """

    args = message.text.split(maxsplit=1)

    if len(args) < 2:

        await message.answer("⚠️ Использование: /stats <ip>")

        return

        

    server_ip = args[1].strip()

    

    # Взаимодействие с сервисом

    data = await mc_service.get_server_info(server_ip)

    if not data.get("online"):

        await message.answer(f"❌ Сервер {server_ip} недоступен.")

        return



    text = f"📊 Статистика сервера <b>{server_ip}</b>:\nИгроки: {data['players_online']}"

    

    await message.answer(

        text=text, 

        reply_markup=get_stats_keyboard(server_ip),

        parse_mode="HTML"

    )



# 4. Обработчик нажатия на Inline-кнопку через фильтр StatsCallback.filter()

@router.callback_query(StatsCallback.filter())

async def cb_refresh_stats(

    call: CallbackQuery, 

    callback_data: StatsCallback, 

    mc_service: MinecraftService

) -> None:

    """

    Обработка коллбека от кнопки. 

    Аргумент callback_data автоматически парсится Aiogram.

    """

    # Извлекаем IP безопасно как типизированное поле

    server_ip = callback_data.ip

    

    data = await mc_service.get_server_info(server_ip)

    text = f"📊 [Обновлено] Статистика <b>{server_ip}</b>:\nИгроки: {data.get('players_online', 0)}"

    

    try:

        await call.message.edit_text(

            text=text, 

            reply_markup=get_stats_keyboard(server_ip),

            parse_mode="HTML"

        )

        # Обязательно "закрываем" callback, иначе у пользователя будут "часики" на кнопке

        await call.answer("✅ Статистика обновлена")

    except Exception:

        # Если текст не поменялся, API Telegram выбросит исключение MessageNotModified

        await call.answer("Изменений нет", show_alert=False)

```



---



## 2. Регистрация роутера



То, что вы создали `Router` в новом файле, не значит, что бот начнет его использовать. Вы **обязаны** подключить его к главному `Dispatcher`. 



Для этого откройте файл `mc_ping_bot/bot/handlers/__init__.py`:



```python

from aiogram import Dispatcher



# 1. Импортируем ваш новый роутер

from .stats import router as stats_router

# ... другие импорты ...



def setup_routers(dp: Dispatcher) -> None:

    """Регистрирует роутеры в диспетчере."""

    # 2. Подключаем его. 

    # ВАЖНО: Порядок имеет значение! 

    # Более специфичные фильтры должны быть выше, чем общие (например, ловящие любой текст).

    dp.include_router(stats_router)

    

    # ... существующие роутеры ...

```



---



## 3. Добавление команды в меню Telegram



В проекте MineTracker меню команд настраивается динамически для каждого пользователя в зависимости от его роли, и кэшируется в Redis для избежания Rate Limit (ошибка HTTP 429 Too Many Requests от Telegram).



Если вы создали новую команду, которую должны видеть пользователи, отредактируйте файл `mc_ping_bot/bot/commands_setup.py`:



```python

from aiogram.types import BotCommand



# 1. Найдите нужный список команд. Например, USER_PRIVATE_COMMANDS:

USER_PRIVATE_COMMANDS = [

    BotCommand(command="start", description="Запустить бота"),

    BotCommand(command="info", description="Статус сервера"),

    # ... существующие команды ...

    BotCommand(command="stats", description="Подробная статистика сервера"),  # <-- Ваша новая команда!

]

```



### Как применить изменения команд



Поскольку мы кэшируем меню в Redis на 1 час (функция `update_user_commands`), у пользователей новая команда сама не появится сразу. 



Для того чтобы принудительно обновить кэш у всех пользователей при следующем перезапуске, **увеличьте версию конфигурации** в файле переменных окружения `.env` или в `config.py`:



```python

# mc_ping_bot/config.py

class Settings(BaseSettings):

    # Было: commands_version: str = "v1"

    # Стало:

    commands_version: str = "v2"

```



При изменении версии, `check_commands_setup()` в Redis вернет `False`, и бот отправит новый список команд в Telegram API для каждого пользователя, который ему напишет.

