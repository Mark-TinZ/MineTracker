"""Типизированные CallbackData-классы для inline-клавиатур.

Использование типизированных CallbackData вместо строковых callback_data
обеспечивает безопасность типов, автоматическую сериализацию/десериализацию
и защиту от коллизий префиксов.
"""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class RefreshCallback(CallbackData, prefix="r"):
    """Callback для кнопки обновления статуса сервера.

    Attributes:
        t: Target (IP-адрес, домен или короткий ID из Redis).
    """
    t: str


class ServerConfCallback(CallbackData, prefix="sconf"):
    """Callback для настроек мониторинга сервера в чате.

    Attributes:
        action: Действие (notify, resend, delete).
        chat_id: ID чата, к которому применяется действие.
    """
    action: str
    chat_id: int


class LanguageCallback(CallbackData, prefix="lang"):
    """Callback для выбора языка пользователем.

    Attributes:
        code: Код языка (ru, en).
    """
    code: str


class AdminCallback(CallbackData, prefix="adm"):
    """Callback для кнопок админ-панели (/moder).

    Attributes:
        action: Действие (banlist_users, banlist_ips, servers, close).
    """
    action: str


class MenuCallback(CallbackData, prefix="menu"):
    """Callback для навигации по меню /start.

    Attributes:
        action: Действие (help, settings, features, about, back).
    """
    action: str
