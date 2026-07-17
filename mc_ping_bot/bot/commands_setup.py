from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats, BotCommandScopeChat

from mc_ping_bot.config import config
from mc_ping_bot.services.cache import RedisCacheManager
from mc_ping_bot.services.i18n import i18n_service, current_locale

def _get_user_private_commands(locale: str = "en") -> list[BotCommand]:
    # It is safe to use current_locale context manually for this generation
    token = current_locale.set(locale)
    try:
        return [
            BotCommand(command="start", description=i18n_service.get("cmd-start-desc", default="Start bot")),
            BotCommand(command="info", description=i18n_service.get("cmd-info-desc", default="Server status")),
            BotCommand(command="players", description=i18n_service.get("cmd-players-desc", default="Players list")),
            BotCommand(command="ping", description=i18n_service.get("cmd-ping-desc", default="Check ping")),
            BotCommand(command="motd", description=i18n_service.get("cmd-motd-desc", default="Get MOTD")),
            BotCommand(command="version", description=i18n_service.get("cmd-version-desc", default="Server version")),
            BotCommand(command="ip", description=i18n_service.get("cmd-ip-desc", default="Get IP address")),
            BotCommand(command="help", description=i18n_service.get("cmd-help-desc", default="Help")),
            BotCommand(command="commands", description=i18n_service.get("cmd-commands-desc", default="Update commands menu")),
            BotCommand(command="configuration", description=i18n_service.get("cmd-configuration-desc", default="Settings")),
            BotCommand(command="set_chat_server", description=i18n_service.get("cmd-set-chat-server-desc", default="Bind server")),
            BotCommand(command="set_chat_gamechat", description=i18n_service.get("cmd-set-chat-gamechat-desc", default="Setup gamechat")),
        ]
    finally:
        current_locale.reset(token)

def _get_group_commands(locale: str = "en") -> list[BotCommand]:
    token = current_locale.set(locale)
    try:
        return [
            BotCommand(command="info", description=i18n_service.get("cmd-info-desc", default="Server status")),
            BotCommand(command="players", description=i18n_service.get("cmd-players-desc", default="Players list")),
            BotCommand(command="ping", description=i18n_service.get("cmd-ping-desc", default="Check ping")),
            BotCommand(command="motd", description=i18n_service.get("cmd-motd-desc", default="Get MOTD")),
            BotCommand(command="version", description=i18n_service.get("cmd-version-desc", default="Server version")),
            BotCommand(command="ip", description=i18n_service.get("cmd-ip-desc", default="Get IP address")),
            BotCommand(command="auth", description=i18n_service.get("cmd-auth-desc", default="Authentication")),
        ]
    finally:
        current_locale.reset(token)

def _get_admin_commands(locale: str = "en") -> list[BotCommand]:
    token = current_locale.set(locale)
    try:
        cmds = _get_user_private_commands(locale)
        cmds.extend([
            BotCommand(command="moder", description=i18n_service.get("cmd-moder-desc", default="Moderator panel")),
            BotCommand(command="tickets", description=i18n_service.get("cmd-tickets-desc", default="Manage tickets")),
            BotCommand(command="maintenance", description=i18n_service.get("cmd-maintenance-desc", default="Maintenance mode")),
        ])
        return cmds
    finally:
        current_locale.reset(token)

async def set_global_commands(bot: Bot):
    """
    Устанавливает дефолтные команды для групп и ЛС глобально для всех поддерживаемых языков.
    Вызывается один раз при старте бота.
    """
    from mc_ping_bot.bot.middlewares.i18n import SUPPORTED_LOCALES
    
    # Сначала устанавливаем без language_code (дефолтные, обычно en)
    await bot.set_my_commands(_get_group_commands("en"), scope=BotCommandScopeAllGroupChats())
    await bot.set_my_commands(_get_user_private_commands("en"), scope=BotCommandScopeAllPrivateChats())
    
    # Затем для каждого поддерживаемого языка
    for loc in SUPPORTED_LOCALES:
        await bot.set_my_commands(_get_group_commands(loc), scope=BotCommandScopeAllGroupChats(), language_code=loc)
        await bot.set_my_commands(_get_user_private_commands(loc), scope=BotCommandScopeAllPrivateChats(), language_code=loc)

async def update_user_commands(bot: Bot, user_id: int, role: str, cache: RedisCacheManager, force: bool = False):
    """
    Обновляет индивидуальное меню команд пользователя в зависимости от его роли.
    Использует Redis для предотвращения Rate Limit'ов Telegram API (Too Many Requests).
    """
    version = getattr(config, "commands_version", "v1")
    
    # Язык текущей таски уже установлен в current_locale благодаря LanguageMiddleware
    locale = current_locale.get()
    
    if not force:
        # Проверяем наличие флага в Redis
        is_set = await cache.check_commands_setup(version, user_id, role)
        if is_set:
            return # Команды уже актуальны для этой версии и роли

    # Выбираем нужный список команд в зависимости от прав доступа
    commands = _get_admin_commands(locale) if role in ["admin", "moder"] else _get_user_private_commands(locale)
    
    # Устанавливаем индивидуальные команды конкретному пользователю
    await bot.set_my_commands(commands, scope=BotCommandScopeChat(chat_id=user_id))
    
    # Сохраняем флаг в Redis на 1 час (3600 секунд)
    await cache.set_commands_setup(version, user_id, role, ttl=3600)
