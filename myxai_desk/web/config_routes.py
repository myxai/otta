"""Config 路由 — nanobot 配置管理.

迁移自 app.py 的 /api/config 路由。
"""

from flask import Blueprint, jsonify, request, current_app

from myxai_desk.web.migration_guards import mark
from myxai_desk.core.config_service import get_config, save_config

bp = Blueprint("config", __name__, url_prefix="/api/config")


@bp.get("")
def get():
    """获取 nanobot 配置."""
    mark("[NEW] config/get")
    
    # 检查 nanobot 是否可用
    from app import NANOBOT_AVAILABLE
    if not NANOBOT_AVAILABLE:
        return jsonify({"error": "nanobot 未安装"}), 400
    
    try:
        cfg = get_config()
        return jsonify(cfg)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.post("")
def save():
    """保存 nanobot 配置."""
    mark("[NEW] config/save")
    
    # 检查 nanobot 是否可用
    from app import NANOBOT_AVAILABLE
    if not NANOBOT_AVAILABLE:
        return jsonify({"error": "nanobot 未安装"}), 400
    
    try:
        data = request.json
        if not data:
            return jsonify({"error": "配置数据为空"}), 400
        
        save_config(data)
        
        # 配置更改后需要重置 agent
        # 这里直接调用 app.py 的 _reset_agent() 函数
        from app import _reset_agent
        _reset_agent()
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
