"""路由迁移仪表盘 - 显示各模块路由的迁移状态"""

from flask import Flask


def print_migration_dashboard(app: Flask) -> None:
    """打印路由迁移仪表盘，显示各模块的迁移状态."""
    from myxai_desk.web.migration_guards import dump_routes
    
    print("\n" + "=" * 70)
    print("路由迁移仪表盘")
    print("=" * 70)
    
    # 定义要检查的模块
    modules = [
        ("Gateway", "/api/gateway", "[OK] 已迁移"),
        ("Scheduler", "/api/scheduler", "[OK] 已迁移"),
        ("Config", "/api/config", "[OK] 已迁移"),
        ("Security", "/api/security", "[OK] 已迁移"),
        ("MCP", "/api/mcp", "[PENDING] 待迁移"),
        ("Apps", "/api/apps", "[PENDING] 待迁移 (大模块)"),
        ("Profile", "/api/profile", "[PENDING] 待迁移"),
    ]
    
    for name, prefix, status in modules:
        routes = dump_routes(app, prefix)
        if not routes:
            continue
        
        # 统计 endpoint 来源
        blueprint_count = 0
        old_count = 0
        
        for path, methods, endpoint in routes:
            if "." in endpoint:  # Blueprint endpoint
                blueprint_count += 1
            else:  # Old endpoint
                old_count += 1
        
        print(f"\n{name} ({prefix}*)")
        print("-" * 70)
        print(f"  状态: {status}")
        print(f"  路由数: {len(routes)}")
        print(f"  来自 Blueprint: {blueprint_count}")
        print(f"  来自 app.py: {old_count}")
        
        # 显示前几个路由示例
        if len(routes) <= 5:
            for path, methods, endpoint in routes:
                print(f"    - {path} -> {endpoint}")
        else:
            for path, methods, endpoint in routes[:3]:
                print(f"    - {path} -> {endpoint}")
            print(f"    ... 还有 {len(routes) - 3} 个路由")
    
    print("\n" + "=" * 70)
    print(f"迁移进度: 4/7 模块已完成 (57%)")
    print("=" * 70 + "\n")
