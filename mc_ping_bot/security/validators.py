import re
from typing import List


# Регулярное выражение для проверки символов (кириллица, латиница, цифры, подчеркивание).
# Длина от 3 до 16 символов — стандарт для большинства серверов Minecraft.
NICKNAME_PATTERN = re.compile(r"^[a-zA-Zа-яА-ЯёЁ0-9_]{3,16}$")

# Список запрещенных слов/корней (Bad words / Reserved words)
BANNED_WORDS: List[str] = [
    "admin",
    "root",
    "moderator",
    "sys",
    "owner",
    # Сюда можно добавить список нецензурных слов
]

# Регулярное выражение для проверки запрещенных слов.
# Используем границы слов \b, чтобы избежать "Scunthorpe problem".
# Например, \badmin\b заблокирует ник "admin", но разрешит ник "myadministrator".
# Флаг re.IGNORECASE (игнорирование регистра) и re.UNICODE (поддержка кириллицы в \b).
BANNED_WORDS_PATTERN = re.compile(
    rf"\b({'|'.join(map(re.escape, BANNED_WORDS))})\b",
    flags=re.IGNORECASE | re.UNICODE
)


def is_valid_nickname(nickname: str) -> bool:
    """
    Проверяет никнейм на соответствие стандартам и отсутствие запрещенных слов.
    
    Args:
        nickname (str): Никнейм игрока для проверки.
        
    Returns:
        bool: True, если никнейм корректен и безопасен, иначе False.
    """
    if not nickname:
        return False
        
    # 1. Базовая проверка: разрешенные символы и длина (только a-z, а-я, 0-9, _)
    if not NICKNAME_PATTERN.fullmatch(nickname):
        return False
        
    # 2. Проверка по блеклисту слов с учетом Scunthorpe problem
    # Поскольку ник обычно состоит из одного слова без пробелов (с _), 
    # паттерн с \b отлично сработает, так как _ считается частью слова в \w.
    # Поэтому, чтобы \b сработало на словах, разделенных подчеркиванием, 
    # мы можем временно заменить _ на пробел для проверки блеклиста, 
    # либо оставить как есть, если мы баним цельные никнеймы.
    
    # Для более надежной проверки заменим `_` на пробел перед поиском блеклиста,
    # чтобы ник вида "super_admin_123" разбился на "super admin 123" и \b сработал.
    sanitized_for_check = nickname.replace("_", " ")
    
    if BANNED_WORDS_PATTERN.search(sanitized_for_check):
        return False
        
    return True
