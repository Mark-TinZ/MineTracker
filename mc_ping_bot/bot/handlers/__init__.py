"""Инициализация и маршрутизация хэндлеров бота."""

from __future__ import annotations

from aiogram import Dispatcher

from .start import router as start_router
from .user import router as user_router
from .group import router as group_router
from .admin import router as admin_router
from .commands import router as commands_router
from .help import router as help_router
from .configuration import router as configuration_router
from .errors import error_router


def setup_routers(dp: Dispatcher) -> None:
    """Регистрирует роутеры в диспетчере.

    Важен порядок регистрации: специфичные хэндлеры первыми,
    fallback-хэндлеры (если есть) последними.
    """
    dp.include_router(admin_router)
    dp.include_router(commands_router)
    dp.include_router(start_router)
    dp.include_router(help_router)
    dp.include_router(configuration_router)
    dp.include_router(user_router)
    dp.include_router(group_router)
    dp.include_router(error_router)
