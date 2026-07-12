from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats, BotCommandScopeChat

from mc_ping_bot.config import config
from mc_ping_bot.services.cache import RedisCacheManager

USER_PRIVATE_COMMANDS = [
    BotCommand(command="start", description="Запустить бота"),
    BotCommand(command="info", description="Статус сервера"),
    BotCommand(command="players", description="Список игроков"),
    BotCommand(command="ping", description="Проверить пинг"),
    BotCommand(command="motd", description="Получить MOTD"),
    BotCommand(command="version", description="Версия сервера"),
    BotCommand(command="ip", description="Получить IP адрес"),
    BotCommand(command="help", description="Помощь"),
    BotCommand(command="commands", description="Обновить меню команд"),
    BotCommand(command="configuration", description="Настройки"),
    BotCommand(command="set_chat_server", description="Привязать сервер"),
    BotCommand(command="set_chat_gamechat", description="Настроить игровой чат"),
]

GROUP_COMMANDS = [
    BotCommand(command="info", description="Статус сервера"),
    BotCommand(command="players", description="Список игроков"),
    BotCommand(command="ping", description="Проверить пинг"),
    BotCommand(command="motd", description="Получить MOTD"),
    BotCommand(command="version", description="Версия сервера"),
    BotCommand(command="ip", description="Получить IP адрес"),
    BotCommand(command="auth", description="Авторизация"),
]

ADMIN_COMMANDS = USER_PRIVATE_COMMANDS + [
    BotCommand(command="moder", description="Панель модератора"),
    BotCommand(command="tickets", description="Управление тикетами"),
]

async def set_global_commands(bot: Bot):
    """
    Устанавливает дефолтные команды для групп и ЛС глобально.
    Вызывается один раз при старте бота.
    """
    await bot.set_my_commands(GROUP_COMMANDS, scope=BotCommandScopeAllGroupChats())
    await bot.set_my_commands(USER_PRIVATE_COMMANDS, scope=BotCommandScopeAllPrivateChats())

async def update_user_commands(bot: Bot, user_id: int, role: str, cache: RedisCacheManager, force: bool = False):
    """
    Обновляет индивидуальное меню команд пользователя в зависимости от его роли.
    Использует Redis для предотвращения Rate Limit'ов Telegram API (Too Many Requests).
    """
    version = getattr(config, "commands_version", "v1")
    
    if not force:
        # Проверяем наличие флага в Redis
        is_set = await cache.check_commands_setup(version, user_id, role)
        if is_set:
            return # Команды уже актуальны для этой версии и роли

    # Выбираем нужный список команд в зависимости от прав доступа
    commands = ADMIN_COMMANDS if role in ["admin", "moder"] else USER_PRIVATE_COMMANDS
    
    # Устанавливаем индивидуальные команды конкретному пользователю
    await bot.set_my_commands(commands, scope=BotCommandScopeChat(chat_id=user_id))
    
    # Сохраняем флаг в Redis на 1 час (3600 секунд)
    await cache.set_commands_setup(version, user_id, role, ttl=3600)
