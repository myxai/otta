"""Token 成本配置服务 — 管理 Token 单价和预警设置.

这是 MyxAI Desk 应用层面的统计配置，与 nanobot 配置无关。
"""

import json
import logging
from typing import Any

from myxai_desk.core.storage.paths import TOKEN_COST_CONFIG_FILE, ensure_dir

log = logging.getLogger("myxai.token_cost_service")


def get_token_cost_config() -> dict[str, Any]:
    """读取 Token 成本配置.
    
    Returns:
        配置字典，包含:
        - inputPrice: float, 输入单价（元/百万token）
        - outputPrice: float, 输出单价（元/百万token）
        - dailyLimit: float, 日预警额度（元）
        - monthlyLimit: float, 月预警额度（元）
    """
    if not TOKEN_COST_CONFIG_FILE.exists():
        return {
            "inputPrice": 0,
            "outputPrice": 0,
            "dailyLimit": 0,
            "monthlyLimit": 0,
        }
    
    try:
        with open(TOKEN_COST_CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        log.warning("Failed to load token cost config", exc_info=True)
        return {
            "inputPrice": 0,
            "outputPrice": 0,
            "dailyLimit": 0,
            "monthlyLimit": 0,
        }


def save_token_cost_config(config: dict[str, Any]) -> None:
    """保存 Token 成本配置.
    
    Args:
        config: 配置字典
    """
    try:
        ensure_dir(TOKEN_COST_CONFIG_FILE.parent)
        with open(TOKEN_COST_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        log.info("[token_cost] Config saved")
    except Exception:
        log.exception("Failed to save token cost config")
        raise
