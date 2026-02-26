"""i18n 路由 — 国际化支持.

提供前端语言资源和语言切换功能。
"""

import logging

from flask import Blueprint, jsonify, request

from myxai_desk.web.migration_guards import mark

log = logging.getLogger("myxai.web.i18n_routes")
from myxai_desk.core.i18n import get_translator

bp = Blueprint("i18n", __name__, url_prefix="/api/i18n")


@bp.get("/messages")
def get_messages():
    """获取指定语言的消息字典.
    
    Query params:
        locale: 语言代码（zh/en），默认 zh
    """
    mark("[NEW] i18n/messages")
    
    locale = request.args.get("locale", "zh")
    
    try:
        t = get_translator()
        
        # If requested locale is different from current, switch temporarily
        original_locale = t.locale
        if locale != original_locale:
            t.set_locale(locale)
        
        # Return all messages
        messages = t._messages.copy()
        
        # Restore original locale
        if locale != original_locale:
            t.set_locale(original_locale)
        
        return jsonify(messages)
    
    except Exception as e:
        log.exception("Failed to get i18n messages")
        return jsonify({"error": str(e)}), 500


@bp.post("/locale")
def set_locale():
    """设置当前语言.
    
    Body:
        locale: 语言代码（zh/en）
    """
    mark("[NEW] i18n/locale/set")
    
    data = request.get_json() or {}
    locale = data.get("locale")
    
    if not locale:
        return jsonify({"error": "locale is required"}), 400
    
    if locale not in ["zh", "en"]:
        return jsonify({"error": "Unsupported locale"}), 400
    
    try:
        t = get_translator()
        t.set_locale(locale)
        
        return jsonify({
            "locale": locale,
            "message": "Locale switched successfully"
        })
    
    except Exception as e:
        log.exception("Failed to set locale")
        return jsonify({"error": str(e)}), 500


@bp.get("/locale")
def get_locale():
    """获取当前语言."""
    mark("[NEW] i18n/locale/get")
    
    try:
        t = get_translator()
        return jsonify({"locale": t.locale})
    
    except Exception as e:
        log.exception("Failed to get locale")
        return jsonify({"error": str(e)}), 500
