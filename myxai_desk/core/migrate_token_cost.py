"""一次性迁移脚本：将 tokenCost 从 config.json 迁移到独立配置文件."""

import json
import logging
from pathlib import Path

log = logging.getLogger("myxai")


def migrate_token_cost_config():
    """将 tokenCost 从 config.json 迁移到 token_cost_config.json.
    
    这是一次性迁移，会：
    1. 读取 config.json 中的 tokenCost 字段
    2. 保存到 token_cost_config.json
    3. 从 config.json 中删除 tokenCost 字段
    
    如果已经迁移过或没有 tokenCost 字段，则跳过。
    """
    try:
        from nanobot.config.loader import get_config_path
        from myxai_desk.core.storage.paths import TOKEN_COST_CONFIG_FILE, ensure_dir
        
        config_path = get_config_path()
        if not config_path.exists():
            log.debug("[migration] config.json not found, skipping migration")
            return
        
        # 读取 config.json
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
        
        # 检查是否有 tokenCost 字段
        token_cost = config.get("tokenCost")
        if not token_cost:
            log.debug("[migration] No tokenCost field in config.json, skipping migration")
            return
        
        log.info("[migration] Found tokenCost in config.json, migrating...")
        
        # 迁移到独立配置文件
        ensure_dir(TOKEN_COST_CONFIG_FILE.parent)
        with open(TOKEN_COST_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(token_cost, f, indent=2, ensure_ascii=False)
        log.info(f"[migration] Saved tokenCost to {TOKEN_COST_CONFIG_FILE}")
        
        # 从 config.json 中删除 tokenCost
        del config["tokenCost"]
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        log.info(f"[migration] Removed tokenCost from {config_path}")
        
        log.info("[migration] ✅ Successfully migrated tokenCost config")
        
    except Exception as e:
        log.warning(f"[migration] Token cost config migration failed: {e}", exc_info=True)


if __name__ == "__main__":
    # 手动运行迁移脚本
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    print("=" * 60)
    print("Token Cost Config Migration")
    print("=" * 60)
    migrate_token_cost_config()
    print("\n✅ Migration completed.")
    print("You can now restart the application without Pydantic errors.")

