import contextvars
from pathlib import Path
from typing import Any, Dict

from fluent.runtime import FluentLocalization, FluentResourceLoader

# Глобальная переменная контекста для текущей локали внутри таски
current_locale = contextvars.ContextVar("current_locale", default="en")


class I18n:
    """
    Обертка над Mozilla Fluent для загрузки .ftl бандлов и форматирования строк.
    """
    def __init__(self, locales_dir: str):
        self.locales_dir = Path(locales_dir)
        # Loader подставляет {locale} в путь: locales_dir/ru/messages.ftl
        self.loader = FluentResourceLoader(str(self.locales_dir / "{locale}"))
        self._localizations: Dict[str, FluentLocalization] = {}

    def _get_localization(self, locale: str) -> FluentLocalization:
        if locale not in self._localizations:
            # Fallback всегда на 'en'
            self._localizations[locale] = FluentLocalization(
                [locale, "en"], ["messages.ftl"], self.loader
            )
        return self._localizations[locale]

    def get(self, msg_id: str, **kwargs: Any) -> str:
        """
        Получает перевод для ключа. Если локаль не передана, берет из contextvars.
        """
        locale = current_locale.get()
        l10n = self._get_localization(locale)
        val = l10n.format_value(msg_id, kwargs)
        
        # Если перевод не найден, fluent вернет сам ключ (например, msg_id)
        # В идеале можно логировать такие случаи
        return val


# Создаем глобальный инстанс.
# mc_ping_bot/services/i18n.py -> parent.parent -> mc_ping_bot/locales
locales_path = Path(__file__).parent.parent / "locales"
i18n_service = I18n(str(locales_path))
