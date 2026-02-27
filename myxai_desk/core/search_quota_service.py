"""搜索 API 额度配置服务 — 管理搜索引擎的每日额度设置.

这是 MyxAI Desk 应用层面的搜索配置。
"""

import json
import logging
from typing import Any

from myxai_desk.core.storage.paths import SEARCH_QUOTA_CONFIG_FILE, ensure_dir

log = logging.getLogger("myxai.search_quota_service")


def get_search_quota_config() -> dict[str, Any]:
    """读取搜索 API 额度配置.
    
    Returns:
        配置字典，包含每个引擎的日额度限制:
        - brave: int, Brave Search 日额度
        - baidu: int, 百度搜索 日额度
    """
    if not SEARCH_QUOTA_CONFIG_FILE.exists():
        return {
            "brave": 1000,
            "baidu": 100,
        }
    
    try:
        with open(SEARCH_QUOTA_CONFIG_FILE, encoding="utf-8") as f:
            config = json.load(f)
            # Ensure default values
            config.setdefault("brave", 1000)
            config.setdefault("baidu", 100)
            return config
    except Exception:
        log.warning("Failed to load search quota config", exc_info=True)
        return {
            "brave": 1000,
            "baidu": 100,
        }


def save_search_quota_config(config: dict[str, Any]) -> None:
    """保存搜索 API 额度配置.
    
    Args:
        config: 配置字典，包含各引擎的额度
    """
    try:
        ensure_dir(SEARCH_QUOTA_CONFIG_FILE.parent)
        with open(SEARCH_QUOTA_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        log.info("[search_quota] Config saved")
    except Exception:
        log.exception("Failed to save search quota config")
        raise
