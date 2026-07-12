"""Фабрики inline-клавиатур бота.

Все клавиатуры создаются через фабричные функции, что обеспечивает
единообразие и централизованное управление элементами интерфейса.
"""

from __future__ import annotations

from typing import Callable

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .callback_data import (
    AdminCallback,
    LanguageCallback,
    MenuCallback,
    RefreshCallback,
    ServerConfCallback,
)


def get_refresh_kb(
    target: str, _: Callable[[str], str] | None = None,
) -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой «Обновить» для результата пинга."""
    builder = InlineKeyboardBuilder()
    text = _("btn_refresh") if _ else "🔄 Обновить"
    builder.button(text=text, callback_data=RefreshCallback(t=target))
    return builder.as_markup()


def get_monitor_settings_kb(
    chat_id: int, _: Callable[[str], str] | None = None,
) -> InlineKeyboardMarkup:
    """Клавиатура настроек мониторинга для конкретного чата."""
    builder = InlineKeyboardBuilder()

    t_notify = _("btn_notify_toggle") if _ else "🔔 Уведомления"
    t_resend = _("btn_resend") if _ else "🔄 Пересоздать"
    t_delete = _("btn_delete_server") if _ else "🗑 Удалить"
    t_tps = "⚡ TPS"

    builder.button(
        text=t_notify,
        callback_data=ServerConfCallback(action="notify", chat_id=chat_id),
    )
    builder.button(
        text=t_tps,
        callback_data=ServerConfCallback(action="toggle_tps", chat_id=chat_id),
    )
    builder.button(
        text=t_resend,
        callback_data=ServerConfCallback(action="resend", chat_id=chat_id),
    )
    builder.button(
        text=t_delete,
        callback_data=ServerConfCallback(action="delete", chat_id=chat_id),
    )
    builder.adjust(2, 2)
    return builder.as_markup()


def get_language_kb() -> InlineKeyboardMarkup:
    """Клавиатура выбора языка."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🇷🇺 Русский", callback_data=LanguageCallback(code="ru"))
    builder.button(text="🇬🇧 English", callback_data=LanguageCallback(code="en"))
    builder.adjust(2)
    return builder.as_markup()


def get_main_menu_kb(_: Callable[[str], str]) -> InlineKeyboardMarkup:
    """Главное меню бота (после /start)."""
    builder = InlineKeyboardBuilder()
    builder.button(text=_("btn_help"), callback_data=MenuCallback(action="help"))
    builder.button(
        text=_("btn_features"), callback_data=MenuCallback(action="features"),
    )
    builder.button(
        text=_("btn_about"), callback_data=MenuCallback(action="about"),
    )
    builder.adjust(1)
    return builder.as_markup()


def get_help_kb(_: Callable[[str], str]) -> InlineKeyboardMarkup:
    """Клавиатура справки (основная)."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=_("btn_help_sections") if _ else "❓ Решение проблем", callback_data=MenuCallback(action="help_sections"),
    )
    builder.button(
        text=_("btn_features"), callback_data=MenuCallback(action="features"),
    )
    builder.button(
        text=_("btn_about"), callback_data=MenuCallback(action="about"),
    )
    builder.button(
        text=_("btn_back"), callback_data=MenuCallback(action="back"),
    )
    builder.adjust(1, 2, 1)
    return builder.as_markup()

def get_help_sections_kb(_: Callable[[str], str]) -> InlineKeyboardMarkup:
    """Клавиатура с разделами помощи."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⚙️ Проблемы с добавлением", callback_data=MenuCallback(action="help_add"))
    builder.button(text="📡 Ошибка мониторинга", callback_data=MenuCallback(action="help_monitor"))
    builder.button(text="🎫 Задать вопрос (Тикет)", callback_data=MenuCallback(action="help_ticket"))
    builder.button(text=_("btn_back"), callback_data=MenuCallback(action="help"))
    builder.adjust(1)
    return builder.as_markup()


def get_back_kb(_: Callable[[str], str]) -> InlineKeyboardMarkup:
    """Клавиатура с одной кнопкой «Назад» → главное меню."""
    builder = InlineKeyboardBuilder()
    builder.button(text=_("btn_back"), callback_data=MenuCallback(action="back"))
    return builder.as_markup()


def get_admin_kb(_: Callable[[str], str] | None = None) -> InlineKeyboardMarkup:
    """Клавиатура админ-панели (/moder)."""
    builder = InlineKeyboardBuilder()

    t_ban_u = _("btn_banlist_users") if _ else "📜 Банлист (Юзеры)"
    t_ban_ip = _("btn_banlist_ips") if _ else "🚫 Банлист (IP)"
    t_servers = _("btn_server_list") if _ else "📡 Серверы"
    t_tickets = _("btn_tickets") if _ else "🎫 Тикеты"
    t_close = _("btn_close") if _ else "✖ Закрыть"

    builder.button(
        text=t_ban_u, callback_data=AdminCallback(action="banlist_users"),
    )
    builder.button(
        text=t_ban_ip, callback_data=AdminCallback(action="banlist_ips"),
    )
    builder.button(
        text=t_servers, callback_data=AdminCallback(action="servers"),
    )
    builder.button(
        text=t_tickets, callback_data=AdminCallback(action="tickets"),
    )
    builder.button(
        text=t_close, callback_data=AdminCallback(action="close"),
    )
    builder.adjust(2, 2, 1)
    return builder.as_markup()
