"""配置服务 — 读写 nanobot 配置文件.

提供配置管理的核心功能，供路由和其他模块使用。
"""

import json
from pathlib import Path
from typing import Any


def get_config() -> dict[str, Any]:
    """读取 nanobot 配置文件.
    
    Returns:
        配置字典
        
    Raises:
        FileNotFoundError: 配置文件不存在
        Exception: 其他读取错误
    """
    from nanobot.config.loader import get_config_path
    
    config_path = get_config_path()
    if not config_path.exists():
        raise FileNotFoundError("配置文件不存在，请先初始化")
    
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def save_config(config_data: dict[str, Any]) -> None:
    """保存配置到 nanobot 配置文件.
    
    Args:
        config_data: 配置字典
        
    Raises:
        Exception: 保存失败
    """
    from nanobot.config.loader import get_config_path
    
    config_path = get_config_path()
    
    # 确保父目录存在
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2, ensure_ascii=False)
