"""Translator implementation."""

from __future__ import annotations

from typing import Any

from .loader import load_locale, merge_messages
from .locale import get_system_locale


class I18N:
    """Translator for internationalization support."""
    
    def __init__(self, locale: str | None = None):
        """Initialize translator.
        
        Args:
            locale: Locale code (e.g., "zh", "en"). If None, uses system locale.
        """
        self.locale = locale or get_system_locale()
        self._messages = load_locale(self.locale)
        self._extensions: dict[str, dict[str, str]] = {}
    
    def t(self, key: str, **kwargs: Any) -> str:
        """Translate a key to localized string.
        
        Args:
            key: Translation key (e.g., "security.mode.Observer")
            **kwargs: Format arguments for string interpolation
            
        Returns:
            Translated string, or key itself if not found
        """
        text = self._messages.get(key, key)
        
        # String interpolation if kwargs provided
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, ValueError):
                pass
        
        return text
    
    def extend(self, namespace: str, messages: dict[str, str]) -> None:
        """Extend translations (for plugins).
        
        Args:
            namespace: Plugin namespace (e.g., "plugin.email")
            messages: Additional translations
        """
        self._extensions[namespace] = messages
        self._messages = merge_messages(self._messages, messages)
    
    def set_locale(self, locale: str) -> None:
        """Switch to a different locale at runtime.
        
        Args:
            locale: New locale code
        """
        self.locale = locale
        self._messages = load_locale(locale)
        
        # Re-apply extensions
        for ext_messages in self._extensions.values():
            self._messages = merge_messages(self._messages, ext_messages)


# Global translator instance
_translator: I18N | None = None


def init_i18n(locale: str | None = None) -> I18N:
    """Initialize global translator.
    
    Args:
        locale: Locale code. If None, uses system locale.
        
    Returns:
        Translator instance
    """
    global _translator
    _translator = I18N(locale)
    return _translator


def get_translator() -> I18N:
    """Get global translator instance.
    
    Returns:
        Translator instance
        
    Raises:
        RuntimeError: If translator not initialized
    """
    if _translator is None:
        raise RuntimeError("i18n not initialized. Call init_i18n() first.")
    return _translator
