# 04. Работа с машиной состояний (FSM)



Finite State Machine (Машина состояний) в Aiogram 3 используется для пошагового сбора данных от пользователя. Например, при создании тикета, привязке сервера или настройке профиля.



В **MineTracker** все состояния и FSM-данные хранятся в оперативной памяти (через дефолтный `MemoryStorage`, который использует Dispatcher при инициализации). Поэтому **крайне важно** корректно очищать состояния после завершения сценария, иначе оперативная память сервера будет постепенно переполняться "подвисшими" сессиями пользователей.



---



## 1. Регистрация нового состояния



Все классы состояний должны храниться централизованно в файле `mc_ping_bot/bot/states.py`. Это предотвращает циклические импорты.



```python

# mc_ping_bot/bot/states.py

from aiogram.fsm.state import State, StatesGroup



class TicketStates(StatesGroup):

    """FSM состояния для создания тикетов в поддержку."""

    waiting_for_message = State()



class ServerAddStates(StatesGroup):

    """FSM состояния для пошагового добавления сервера."""

    waiting_for_ip = State()

    waiting_for_port = State()

```



---



## 2. Полный цикл работы с FSM



Рассмотрим пример создания пошагового диалога добавления сервера. Мы запрашиваем IP, затем порт, сохраняем в БД и выходим из состояния.



### Шаг 1: Вход в состояние



```python

from aiogram import Router, F

from aiogram.types import Message

from aiogram.filters import Command

from aiogram.fsm.context import FSMContext



from mc_ping_bot.bot.states import ServerAddStates



router = Router()



@router.message(Command("add_server"))

async def cmd_add_server(message: Message, state: FSMContext) -> None:

    """

    Инициализация процесса. Переводим пользователя в состояние ожидания IP.

    """

    # Устанавливаем стейт

    await state.set_state(ServerAddStates.waiting_for_ip)

    

    await message.answer("📝 Введите IP-адрес или домен сервера:")

```



### Шаг 2: Перехват сообщения в стейте и сохранение данных



```python

# Используем фильтр по конкретному состоянию

@router.message(ServerAddStates.waiting_for_ip)

async def process_ip(message: Message, state: FSMContext) -> None:

    """

    Ловим сообщение, когда пользователь находится в State: waiting_for_ip.

    """

    server_ip = message.text.strip()

    

    # Валидация (например, проверка на пустоту)

    if not server_ip:

        await message.answer("❌ IP не может быть пустым. Попробуйте еще раз.")

        # Оставляем пользователя в этом же состоянии

        return

    

    # 1. Сохраняем данные в хранилище FSM (MemoryStorage)

    await state.update_data(ip=server_ip)

    

    # 2. Переводим пользователя на следующий шаг

    await state.set_state(ServerAddStates.waiting_for_port)

    

    await message.answer("📝 Теперь введите порт сервера (например, 25565):")

```



### Шаг 3: Извлечение данных и завершение (Очистка)



```python

from sqlalchemy.ext.asyncio import AsyncSession

from mc_ping_bot.db.models import Server

# предполагается, что модель Server импортирована



@router.message(ServerAddStates.waiting_for_port)

async def process_port(message: Message, state: FSMContext, session: AsyncSession) -> None:

    """

    Последний шаг. Извлекаем ранее сохраненные данные, записываем в БД и чистим FSM.

    """

    port_text = message.text.strip()

    

    if not port_text.isdigit():

        await message.answer("❌ Порт должен быть числом! Введите порт еще раз:")

        return

    

    # 1. Достаем все данные, которые мы сохраняли на предыдущих шагах

    data = await state.get_data()

    saved_ip = data.get("ip")  # "mc.hypixel.net"

    port = int(port_text)

    

    try:

        # 2. Работаем с БД (session автоматически инжектится через DatabaseMiddleware)

        new_server = Server(ip_domain=saved_ip, port=port)

        session.add(new_server)

        

        # ВАЖНО: Для INSERT, UPDATE и DELETE запросов необходимо вручную вызвать commit.

        # DatabaseMiddleware не делает commit автоматически при выходе!

        await session.commit()

        

        await message.answer(f"✅ Сервер {saved_ip}:{port} успешно добавлен!")

        

    except Exception as e:

        await message.answer("❌ Произошла ошибка при сохранении.")

        

    finally:

        # 3. КРИТИЧЕСКИ ВАЖНО: Очистка состояния!

        # Это удалит данные пользователя из памяти, предотвращая утечки (Memory Leak).

        # Обязательно использовать state.clear(), а не state.set_state(None).

        await state.clear()

```



---



## 3. Отмена состояний (Кнопка "Отмена")



Всегда предоставляйте пользователю возможность выйти из процесса. Если он нажмет команду `/cancel` или кнопку отмены, стейт должен очищаться.



```python

@router.message(Command("cancel"))

async def cmd_cancel_fsm(message: Message, state: FSMContext) -> None:

    """

    Универсальный хендлер отмены для любого состояния.

    Важно: этот хендлер должен быть зарегистрирован так, чтобы ловить команду

    НЕЗАВИСИМО от текущего стейта.

    """

    current_state = await state.get_state()

    if current_state is None:

        await message.answer("Отменять нечего.")

        return

        

    await state.clear()

    await message.answer("Действие отменено.")

```

