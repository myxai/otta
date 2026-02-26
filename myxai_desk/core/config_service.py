"""配置服务 — 读写 nanobot 配置文件.

提供配置管理的核心功能，供路由和其他模块使用。

敏感数据策略
-----------
API Key 和密码等敏感字段在保存时被提取到系统 keyring（或加密文件），
配置文件中仅保留占位符 ``<<KEYRING>>``。读取时自动从 keyring 合并回完整值。
"""

import json
import logging
from typing import Any

from myxai_desk.core.storage import secrets

log = logging.getLogger("myxai.config_service")

# Provider name → JSON path segments to the apiKey field
_PROVIDER_KEY_PATHS: dict[str, tuple[str, ...]] = {
    "openrouter": ("providers", "openrouter", "apiKey"),
    "anthropic": ("providers", "anthropic", "apiKey"),
    "openai": ("providers", "openai", "apiKey"),
    "deepseek": ("providers", "deepseek", "apiKey"),
    "gemini": ("providers", "gemini", "apiKey"),
    "groq": ("providers", "groq", "apiKey"),
    "moonshot": ("providers", "moonshot", "apiKey"),
    "zhipu": ("providers", "zhipu", "apiKey"),
    "dashscope": ("providers", "dashscope", "apiKey"),
    "siliconflow": ("providers", "siliconflow", "apiKey"),
    "minimax": ("providers", "minimax", "apiKey"),
    "aihubmix": ("providers", "aihubmix", "apiKey"),
}

_SEARCH_KEY_PATHS: dict[str, tuple[str, ...]] = {
    "baidu": ("tools", "web", "search", "baiduApiKey"),
    "brave": ("tools", "web", "search", "apiKey"),
}


def _deep_get(d: dict, keys: tuple[str, ...]) -> str | None:
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur if isinstance(cur, str) else None


def _deep_set(d: dict, keys: tuple[str, ...], value: str) -> None:
    cur = d
    for k in keys[:-1]:
        if k not in cur or not isinstance(cur[k], dict):
            cur[k] = {}
        cur = cur[k]
    cur[keys[-1]] = value


def _extract_secrets(config_data: dict) -> dict:
    """Extract sensitive keys from config into keyring, replace with placeholder."""
    for provider, path in _PROVIDER_KEY_PATHS.items():
        val = _deep_get(config_data, path)
        if val and not secrets.is_secret_ref(val):
            secrets.store_provider_key(provider, val)
            _deep_set(config_data, path, secrets.SECRET_REF)

    for name, path in _SEARCH_KEY_PATHS.items():
        val = _deep_get(config_data, path)
        if val and not secrets.is_secret_ref(val):
            secrets.store_search_key(name, val)
            _deep_set(config_data, path, secrets.SECRET_REF)

    return config_data


def _merge_secrets(config_data: dict) -> dict:
    """Merge secrets from keyring back into config dict for runtime use."""
    for provider, path in _PROVIDER_KEY_PATHS.items():
        val = _deep_get(config_data, path)
        if secrets.is_secret_ref(val):
            real = secrets.retrieve_provider_key(provider)
            if real:
                _deep_set(config_data, path, real)

    for name, path in _SEARCH_KEY_PATHS.items():
        val = _deep_get(config_data, path)
        if secrets.is_secret_ref(val):
            real = secrets.retrieve_search_key(name)
            if real:
                _deep_set(config_data, path, real)

    return config_data


def get_config() -> dict[str, Any]:
    """读取 nanobot 配置文件（敏感字段从 keyring 合并）.

    Returns:
        完整配置字典（含真实 API Key）

    Raises:
        FileNotFoundError: 配置文件不存在
    """
    from nanobot.config.loader import get_config_path

    config_path = get_config_path()
    if not config_path.exists():
        raise FileNotFoundError("配置文件不存在，请先初始化")

    with open(config_path, encoding="utf-8") as f:
        cfg = json.load(f)

    return _merge_secrets(cfg)


def save_config(config_data: dict[str, Any]) -> None:
    """保存配置（敏感字段提取到 keyring，配置文件中写占位符）.

    Args:
        config_data: 配置字典（含真实 API Key）
    """
    from nanobot.config.loader import get_config_path

    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    _extract_secrets(config_data)

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2, ensure_ascii=False)

    log.info("[config] saved — sensitive keys stored in %s", secrets.backend_info()["backend"])
