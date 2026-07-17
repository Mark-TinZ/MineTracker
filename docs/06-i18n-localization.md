# 🌍 Руководство по Локализации (Enterprise i18n)

Проект использует передовую архитектуру локализации на базе **Mozilla Fluent** (`fluent.runtime`), интегрированную с **PostgreSQL**, **Redis** и **contextvars**. Это позволяет боту "на лету" переводить тексты, корректно обрабатывать склонения, множественные числа (плюрализацию) и сохранять высокую производительность без жестких зависимостей в бизнес-логике.

В этом документе описано, как правильно добавлять новые языки, как работать со строками и каких ошибок следует избегать.

---

## 🏗 Архитектура локализации вкратце

Локализация отделена от хендлеров и бизнес-логики благодаря двум слоям (Middlewares):

1. **`LanguageMiddleware` (Outer)**: 
   Перехватывает каждый запрос пользователя. Определяет его язык, опрашивая (по цепочке): `Redis кэш` -> `PostgreSQL` -> `Язык клиента Telegram (message.from_user.language_code)`. Имеет встроенный fallback: если язык не поддерживается, принудительно переключает на `en`.
   Язык сохраняется глобально для текущей асинхронной задачи через `contextvars`.
   
2. **`I18nMiddleware` (Inner)**: 
   Внедряет объект-переводчик (`i18n`) в параметры хендлера (Dependency Injection).

---

## 📝 Как добавить новый язык?

Предположим, мы хотим добавить поддержку испанского языка (`es`).

### Шаг 1: Добавление файлов переводов
1. Перейдите в папку `mc_ping_bot/locales/`.
2. Создайте новую папку `es` (по коду ISO 639-1).
3. Скопируйте файл `messages.ftl` из английской или русской папки и переведите значения:

**Пример `mc_ping_bot/locales/es/messages.ftl`:**
```ftl
# Кнопки
btn-lang-ru = 🇷🇺 Русский
btn-lang-en = 🇬🇧 English
btn-lang-es = 🇪🇸 Español
btn-features = 🚀 Funciones
btn-info = ℹ️ Sobre el bot

# Сообщения
msg-welcome-main = 👋 <b>¡Bienvenido a MineTracker!</b>

    Un bot rápido y potente...
```

### Шаг 2: Добавление языка в белый список (Whitelist)
Откройте файл `mc_ping_bot/bot/middlewares/i18n.py` и добавьте код языка в `SUPPORTED_LOCALES`:

```python
# Добавляем 'es' в список
SUPPORTED_LOCALES = ["ru", "en", "es"]
DEFAULT_LOCALE = "en"
```

### Шаг 3: Добавление кнопки в меню `/language`
Откройте `mc_ping_bot/bot/handlers/start.py` и обновите генерацию клавиатуры выбора языка `get_lang_kb`, чтобы кнопка с испанским стала доступна пользователям:

```python
def get_lang_kb(i18n: I18n) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=i18n.get("btn-lang-ru"), callback_data="lang_ru")
    builder.button(text=i18n.get("btn-lang-en"), callback_data="lang_en")
    builder.button(text=i18n.get("btn-lang-es"), callback_data="lang_es") # Новая кнопка
    builder.adjust(2)
    return builder.as_markup()
```

Всё! Бот теперь нативно поддерживает испанский язык.

---

## 🛠 Как правильно подтягивать локализацию в коде

### Внутри Aiogram Хендлеров

Благодаря `I18nMiddleware`, инстанс переводчика `i18n: I18n` передается прямо в функцию. Вам остается просто запросить нужный ключ.

```python
from aiogram import Router, types
from mc_ping_bot.services.i18n import I18n

@router.message(Command("status"))
async def status_handler(message: types.Message, i18n: I18n):
    # Вместо: await message.answer("Статус сервера")
    await message.answer(i18n.get("msg-server-status"))
```

### Передача параметров и переменных

Fluent позволяет легко подставлять переменные в текст, не ломая структуру предложений для разных языков.

**В файле `.ftl`:**
```ftl
msg-server-online = 🟢 Сервер <b>{ $ip }</b> сейчас онлайн! Игроков: { $players }.
```

**В Python коде:**
```python
await message.answer(
    i18n.get("msg-server-online", ip="mc.hypixel.net", players=45000),
    parse_mode="HTML"
)
```

### Использование плюрализации (Множественные числа)

Mozilla Fluent решает извечную проблему склонений (1 игрок, 2 игрока, 5 игроков). 

**В файле `.ftl` (русский):**
```ftl
msg-players-count = { $count ->
    [one] 🟢 На сервере играет { $count } игрок.
    [few] 🟢 На сервере играют { $count } игрока.
   *[other] 🟢 На сервере играет { $count } игроков.
}
```

**В файле `.ftl` (английский):**
```ftl
msg-players-count = { $count ->
    [one] 🟢 There is { $count } player online.
   *[other] 🟢 There are { $count } players online.
}
```

В Python коде вы передаете переменную **точно так же**, не задумываясь о языке. Движок сам решит, какую форму выбрать:
```python
await message.answer(i18n.get("msg-players-count", count=server.players_online))
```

---

## 🧱 Использование внутри сервисов (вне хендлеров)

Иногда нужно сформировать текст глубоко в сервисном слое, куда пробрасывать объект `i18n` не с руки. В нашей архитектуре текущая локаль хранится в `contextvars`. Это означает, что вы можете глобально импортировать глобальный `i18n_service` и использовать его:

```python
from mc_ping_bot.services.i18n import i18n_service

async def generate_server_report(ip: str) -> str:
    # Метод get() сам достанет текущий язык (locale) из contextvars
    report_title = i18n_service.get("report-title", ip=ip)
    return report_title
```

> [!WARNING]  
> **Ловушка с `asyncio.create_task()`:**
> В Python 3.7+ функция `asyncio.create_task` **автоматически** копирует `contextvars`. Однако, если вы спавните новую задачу в **пуле потоков** (thread pool) через `run_in_executor` или сторонние библиотеки, вы можете потерять локаль! В таких случаях контекст нужно копировать вручную: `import contextvars; contextvars.copy_context().run(func)`.

---

## 🚫 Правила и Антипаттерны (Как НЕ нужно делать)

### ❌ 1. Хардкодинг строк в коде
Никаких "заглушек" или русских/английских слов в `.py` файлах, предназначенных для пользователя!

* **Плохо:** `await message.answer("Ошибка: Сервер выключен")`
* **Хорошо:** `await message.answer(i18n.get("error-server-offline"))`

### ❌ 2. Статические клавиатуры в глобальной области
В Aiogram 3 и мультиязычных ботах вы **не можете** импортировать готовую клавиатуру из константы (в начале файла). Если вы так сделаете, язык клавиатуры "застрянет" на том, который был при запуске бота.

* **Плохо:**
```python
# Клавиатура сгенерирована статично один раз
main_menu_kb = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text=i18n_service.get("btn-features"), callback_data="bot_features")
]])

@router.message()
async def handler(msg, i18n):
    # При смене языка текст клавиатуры не обновится!
    await msg.answer("Текст", reply_markup=main_menu_kb)
```

* **Хорошо:**
Всегда используйте функции, возвращающие **Билдеры** (Builders) или генерирующие разметку внутри тела хендлера:
```python
def get_main_menu_kb(i18n: I18n) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=i18n.get("btn-features"), callback_data="bot_features")
    return builder.as_markup()

@router.message()
async def handler(msg: Message, i18n: I18n):
    # Клавиатура генерируется при каждом вызове с нужным языком
    await msg.answer("Текст", reply_markup=get_main_menu_kb(i18n))
```

### ❌ 3. Склейка переводов (Конкатенация строк)
Не дробите предложения на несколько ключей локализации и не склеивайте их через `+` или f-строки. В разных языках порядок слов может кардинально отличаться.

* **Плохо:**
```python
# Python
await message.answer(f'{i18n.get("msg-hello")} {username}, {i18n.get("msg-welcome")}')
```

* **Хорошо:**
Сделайте один большой ключ во Fluent-файле и передайте параметры:
```ftl
# FTL
msg-welcome-user = { $greeting } { $username }, добро пожаловать на наш сервер!
```
```python
# Python
await message.answer(i18n.get("msg-welcome-user", greeting="Привет", username=message.from_user.first_name))
```

### ❌ 4. Принудительная перезапись языка без ведома пользователя
Не обновляйте язык в БД самостоятельно, если пользователь просто прислал сообщение на другом языке клиента. Язык должен меняться **только явно** — через команду `/language` или `/start`. `LanguageMiddleware` сам разберется с первичной установкой.

---

Соблюдая эти простые правила, мы сохраним проект Enterprise-уровня и избежим "макаронного" кода! 🚀
