from typing import Any, Dict

# Простая, но легковесная структура локализации
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "ru": {
        "server_offline": "🔴 <b>Сервер оффлайн</b>\nОшибка: {desc}",
        "invalid_address": "❌ <b>Недопустимый адрес</b>\nПричина: {desc}",
        "wait_timeout": "⏳ <b>Таймаут</b>\nСервер не ответил вовремя.",
        "players_online": "👥 Игроки онлайн",
        "update_btn": "🔄 Обновить",
    },
    "en": {
        "server_offline": "🔴 <b>Server Offline</b>\nError: {desc}",
        "invalid_address": "❌ <b>Invalid Address</b>\nReason: {desc}",
        "wait_timeout": "⏳ <b>Timeout</b>\nServer did not respond in time.",
        "players_online": "👥 Players Online",
        "update_btn": "🔄 Refresh",
    }
}


class I18nManager:
    """
    Менеджер локализации на основе Python-словарей.
    """

    def __init__(self, default_lang: str = "ru"):
        self.default_lang = default_lang
        self.translations = TRANSLATIONS

    def get(self, key: str, lang_code: str = None, **kwargs: Any) -> str:
        """
        Возвращает переведенную строку по ключу.
        Если ключ не найден в запрошенном языке, фоллбечит на default_lang.
        Если и там нет — возвращает сам ключ.
        """
        # Защита от передачи несуществующего языка (например, 'fr')
        lang = lang_code if lang_code in self.translations else self.default_lang
        
        # Получаем строку из выбранного языка
        text = self.translations[lang].get(
            key,
            # Фоллбек на язык по умолчанию
            self.translations[self.default_lang].get(key, key)
        )
        
        if kwargs:
            try:
                return text.format(**kwargs)
            except KeyError:
                # На случай, если в строке есть параметры форматирования, 
                # которые не были переданы, отдаем как есть, чтобы не ронять бота.
                pass
                
        return text

# Глобальный инстанс для удобства импорта
i18n = I18nManager()
