"""Locale detection and management."""

from __future__ import annotations


def detect_locale_from_browser(accept_language: str | None = None) -> str:
    """Detect user locale from browser Accept-Language header.
    
    Args:
        accept_language: Browser Accept-Language header value
        
    Returns:
        Locale code (e.g., "zh", "en")
    """
    if not accept_language:
        return "zh"  # default to Chinese for MyxAI Desk
    
    # Parse Accept-Language header (e.g., "zh-CN,zh;q=0.9,en;q=0.8")
    langs = []
    for part in accept_language.split(","):
        lang = part.split(";")[0].strip().lower()
        # Extract primary language code
        if "-" in lang:
            lang = lang.split("-")[0]
        langs.append(lang)
    
    # Return first supported language
    supported = {"zh", "en"}
    for lang in langs:
        if lang in supported:
            return lang
    
    return "zh"


def get_system_locale() -> str:
    """Get system default locale.
    
    Returns:
        Locale code (e.g., "zh", "en")
    """
    import locale
    try:
        lang, _ = locale.getdefaultlocale()
        if lang and lang.startswith("zh"):
            return "zh"
        return "en"
    except Exception:
        return "zh"
