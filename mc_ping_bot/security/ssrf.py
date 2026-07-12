import asyncio
import socket
import ipaddress
from typing import Tuple


class SSRFSecurityError(Exception):
    """Исключение, выбрасываемое при обнаружении SSRF угрозы."""
    pass


async def resolve_and_validate_ip(host: str, port: int = 25565) -> Tuple[str, int]:
    """
    Асинхронно резолвит хост и строго валидирует полученные IP-адреса.
    Блокирует попытки SSRF атак через приватные, локальные и мультикаст адреса.
    
    Возвращает:
        Tuple[str, int]: Разрезолвленный безопасный IP-адрес и порт.
        (Использовать именно возвращенный IP для подключения, чтобы избежать DNS Rebinding)
    """
    loop = asyncio.get_running_loop()
    
    try:
        # Резолвим адрес (поддерживаем как IPv4, так и IPv6)
        addr_info = await loop.getaddrinfo(
            host, 
            port, 
            family=socket.AF_UNSPEC, 
            type=socket.SOCK_STREAM
        )
    except socket.gaierror as e:
        raise SSRFSecurityError(f"Не удалось разрезолвить хост '{host}': {e}")

    # Извлекаем все уникальные IP-адреса, которые вернул DNS
    resolved_ips = list(set(info[4][0] for info in addr_info))
    
    if not resolved_ips:
        raise SSRFSecurityError(f"DNS не вернул A/AAAA записей для '{host}'")

    safe_ip = None

    for ip_str in resolved_ips:
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            raise SSRFSecurityError(f"Получен некорректный IP-адрес: {ip_str}")

        # Строгая валидация (SSRF Protection)
        if ip_obj.is_private:
            raise SSRFSecurityError(f"IP {ip_str} принадлежит приватной сети (RFC 1918). Доступ заблокирован.")
        
        if ip_obj.is_loopback:
            raise SSRFSecurityError(f"IP {ip_str} является loopback-адресом. Доступ заблокирован.")
        
        if ip_obj.is_link_local:
            raise SSRFSecurityError(f"IP {ip_str} является link-local адресом. Доступ заблокирован.")
        
        if ip_obj.is_multicast:
            raise SSRFSecurityError(f"IP {ip_str} является multicast-адресом. Доступ заблокирован.")
        
        if ip_obj.is_reserved or ip_obj.is_unspecified:
            raise SSRFSecurityError(f"IP {ip_str} зарезервирован или не определен. Доступ заблокирован.")
            
        # Если хотя бы один IP прошел проверку, запоминаем его. 
        # (Обычно берем первый безопасный IP)
        if safe_ip is None:
            safe_ip = ip_str
            
    if not safe_ip:
         raise SSRFSecurityError("Не найдено безопасных IP-адресов для подключения.")

    return safe_ip, port
