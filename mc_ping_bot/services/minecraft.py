import asyncio
import re
from typing import Any, Dict

from mcstatus import JavaServer

from mc_ping_bot.security.ssrf import SSRFSecurityError, resolve_and_validate_ip
from mc_ping_bot.security.validators import is_valid_nickname
from mc_ping_bot.services.cache import RedisCacheManager


class MinecraftService:
    """
    Ядро бизнес-логики для опроса Minecraft серверов.
    Реализует правильный безопасный Pipeline с поддержкой SRV записей и защитой от SSRF.
    """

    def __init__(self, cache_manager: RedisCacheManager):
        self.cache = cache_manager

    async def get_server_info(self, address: str, port: int = 25565) -> Dict[str, Any]:
        # Шаг 1: Ищем изначальный адрес и порт в Redis-кеше
        cached_data = await self.cache.get_server_data(address, port)
        if cached_data:
            cached_data["from_cache"] = True
            return cached_data

        try:
            # Шаг 2: Получаем финальный таргет через mcstatus.
            # Эта функция выполняет резолв SRV-записей. 
            # Финальный адрес сохранится в server.address.host и server.address.port
            target_address = f"{address}:{port}" if port != 25565 else address
            server = await JavaServer.async_lookup(target_address)
            
            # Шаг 3: Теперь прогоняем итоговый хост, куда ведет SRV, через нашу защиту от SSRF.
            # Если SRV-запись злонамеренно ведет на 127.0.0.1 или локальную сеть — это будет заблокировано.
            safe_ip, safe_port = await resolve_and_validate_ip(server.address.host, server.address.port)
            
            # Шаг 4: Создаем НОВЫЙ безопасный объект для пинга, так как server.address неизменяем
            safe_server = JavaServer(safe_ip, safe_port)

            # Шаг 5: Выполняем статус-запрос с таймаутом
            status = await asyncio.wait_for(safe_server.async_status(), timeout=10.0)

            # Парсинг результата и очистка никнеймов (Scunthorpe & Спам)
            players = []
            if status.players and status.players.sample:
                for p in status.players.sample:
                    if is_valid_nickname(p.name):
                        players.append(p.name)

            data = {
                "online": True,
                "ip": address,
                "port": port,
                "resolved_ip": safe_ip,
                "version": status.version.name if status.version else "Unknown",
                "latency": round(status.latency),
                "players_online": status.players.online if status.players else 0,
                "players_max": status.players.max if status.players else 0,
                "player_names": players,
                "motd": self._clean_motd(status.description)
            }

            # Сохранение результата в Redis-кеш
            await self.cache.set_server_data(address, port, data)
            return data

        except SSRFSecurityError as e:
            return {"online": False, "error": "invalid_address", "desc": str(e)}
        except (asyncio.TimeoutError, TimeoutError):
            return {"online": False, "error": "wait_timeout", "desc": "Превышено время ожидания сервера."}
        except Exception as e:
            return {"online": False, "error": "server_offline", "desc": str(e)}

    def _clean_motd(self, description: Any) -> str:
        """Очищает MOTD от цветовых кодов."""
        if not description:
            return ""
        if isinstance(description, dict):
            text = description.get('text', '') + "".join(
                [x.get('text', '') for x in description.get('extra', [])]
            )
        elif isinstance(description, list):
            text = "".join([x.get('text', '') if isinstance(x, dict) else str(x) for x in description])
        else:
            text = str(description)
            
        clean_text = re.sub(r'§[0-9a-fk-or]', '', text)
        clean_text = re.sub(r'\x1b\[[0-9;]*m', '', clean_text)
        return clean_text.strip()
