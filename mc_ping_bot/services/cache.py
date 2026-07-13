import json
from typing import Any, Dict, Optional

from redis.asyncio import Redis


class RedisCacheManager:
    """
    Service Layer для работы с Redis: кеширование ответов серверов и управление версиями команд.
    """

    def __init__(self, redis: Redis):
        self.redis = redis

    async def get_server_data(self, ip: str, port: int) -> Optional[Dict[str, Any]]:
        """
        Получает закешированные данные сервера.
        """
        key = f"server_data:{ip}:{port}"
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None

    async def set_server_data(self, ip: str, port: int, data: Dict[str, Any], ttl: int = 300) -> None:
        """
        Сохраняет результаты пинга сервера в кеш.
        По умолчанию TTL (время жизни) = 300 секунд (5 минут).
        """
        key = f"server_data:{ip}:{port}"
        # Сериализуем dict в JSON строку
        await self.redis.set(key, json.dumps(data), ex=ttl)

    async def check_commands_setup(self, version: str, chat_id: int, role: str) -> bool:
        """
        Проверяет, были ли уже установлены команды для данного чата/роли в текущей версии.
        """
        key = f"commands_setup:{version}:{chat_id}:{role}"
        return await self.redis.exists(key) > 0

    async def set_commands_setup(self, version: str, chat_id: int, role: str, ttl: int = 3600) -> None:
        """
        Помечает, что команды для данного чата/роли в текущей версии установлены.
        TTL = 3600 секунд (1 час).
        """
        key = f"commands_setup:{version}:{chat_id}:{role}"
        await self.redis.set(key, "1", ex=ttl)

    async def get_user_lang(self, tg_id: int) -> Optional[str]:
        """Получает закешированный язык пользователя."""
        key = f"user_lang:{tg_id}"
        lang = await self.redis.get(key)
        return lang

    async def set_user_lang(self, tg_id: int, lang: str, ttl: int = 86400) -> None:
        """Сохраняет язык пользователя в кеш. По умолчанию на 24 часа."""
        key = f"user_lang:{tg_id}"
        await self.redis.set(key, lang, ex=ttl)
