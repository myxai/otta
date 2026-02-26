"""Language resource loader."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("myxai.core.i18n.loader")


def load_locale(locale: str) -> dict[str, str]:
    """Load language resources from JSON file.
    
    Args:
        locale: Locale code (e.g., "zh", "en")
        
    Returns:
        Dictionary of key-value pairs for translations
    """
    locale_dir = Path(__file__).parent / "locales"
    locale_file = locale_dir / f"{locale}.json"
    
    if not locale_file.exists():
        # Fallback to Chinese
        locale_file = locale_dir / "zh.json"
    
    if not locale_file.exists():
        return {}
    
    try:
        with open(locale_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        log.warning("Failed to load locale file %s", locale_file, exc_info=True)
        return {}


def merge_messages(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge two message dictionaries (for plugin extensions).
    
    Args:
        base: Base message dictionary
        override: Override message dictionary
        
    Returns:
        Merged dictionary
    """
    result = base.copy()
    result.update(override)
    return result
