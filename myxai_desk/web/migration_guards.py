"""迁移护栏工具.

提供路由迁移过程中的保护机制，包括：
1. 统一打 NEW/OLD 标记
2. 路由重复检测
3. 路由信息导出（用于调试）
"""

import logging

log = logging.getLogger("myxai")


def mark(tag: str):
    """标记路由是新实现还是旧实现.
    
    Args:
        tag: 标记字符串，格式如 "[NEW] module/endpoint" 或 "[OLD] module/endpoint"
    """
    log.info(tag)


def assert_no_duplicate_routes(app, prefix: str = "/api/"):
    """检查是否有重复的路由定义.
    
    在应用启动时调用，确保同一个 METHOD + PATH 只注册一次。
    如果发现重复路由，会抛出 RuntimeError。
    
    Args:
        app: Flask 应用实例
        prefix: 要检查的路由前缀，默认为 "/api/"
        
    Raises:
        RuntimeError: 当发现重复路由时
    """
    seen = {}
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith(prefix):
            continue
        # 只检查 REST 方法
        methods = tuple(
            sorted(m for m in rule.methods if m in {"GET", "POST", "PUT", "DELETE", "PATCH"})
        )
        if not methods:
            continue
        key = (rule.rule, methods)
        if key in seen:
            raise RuntimeError(
                f"Duplicate route detected: {key} "
                f"endpoints={seen[key]} & {rule.endpoint}"
            )
        seen[key] = rule.endpoint


def dump_routes(app, startswith: str):
    """导出以指定前缀开头的路由信息（用于调试）.
    
    Args:
        app: Flask 应用实例
        startswith: 路由前缀，如 "/api/gateway"
        
    Returns:
        排序后的路由列表，每项为 (路径, 方法列表, 端点名称)
    """
    out = []
    for rule in app.url_map.iter_rules():
        if rule.rule.startswith(startswith):
            methods = sorted(m for m in rule.methods if m in {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"})
            out.append((rule.rule, methods, rule.endpoint))
    return sorted(out)
