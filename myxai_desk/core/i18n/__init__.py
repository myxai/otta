"""i18n core module — internationalization support for MyxAI Desk.

Provides translation services for backend, frontend, and plugins.
"""

from .translator import I18N, get_translator, init_i18n

__all__ = ["I18N", "get_translator", "init_i18n"]
