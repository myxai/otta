"""IE 2.0 — Category definitions, risk levels, and tool allowlists.

Design goals (see docs/intent-engine/ie-2.0-taxonomy.md):
  - Orthogonal dimensions: routing_method vs execution_path
  - Default-safe: fallback never lands on high-risk tool groups
  - Observable: every routing decision is explainable
  - Extensible: categories/rules/models can evolve independently
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# ── Risk levels ──────────────────────────────────────────────────

RiskLevel = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class Category:
    name: str
    risk: RiskLevel
    tools: frozenset[str]
    description: str = ""


# ── Category registry ────────────────────────────────────────────

CATEGORIES: dict[str, Category] = {
    "search": Category(
        "search", "low",
        frozenset({"web_search", "web_fetch", "smart_fetch"}),
        "联网检索 / 监控 / 报告 / 趋势 / 对比（明确需要上网）",
    ),
    "ask": Category(
        "ask", "low",
        frozenset(),
        "知识问答 / 概念解释 / 不需要联网的信息类问题",
    ),
    "math": Category(
        "math", "low",
        frozenset(),
        "数学计算 / 表达式求值 / 数值推理",
    ),
    "creative": Category(
        "creative", "low",
        frozenset(),
        "文本生成 / 写作 / 翻译 / 润色 / 诗歌 / 故事 / 文案",
    ),
    "fs": Category(
        "fs", "high",
        frozenset({"exec", "read_file", "list_dir", "write_file", "edit_file"}),
        "文件系统读写、整理、移动、删除",
    ),
    "browser": Category(
        "browser", "medium",
        frozenset(),   # dynamically filled with MCP tools
        "浏览器自动化",
    ),
    "net": Category(
        "net", "medium",
        frozenset({"web_fetch", "smart_fetch"}),
        "HTTP/API 调用、抓取",
    ),
    "system": Category(
        "system", "high",
        frozenset({"exec"}),
        "系统设置、进程、安装、网络配置",
    ),
    "schedule": Category(
        "schedule", "low",
        frozenset({"cron"}),
        "定时任务 / 提醒",
    ),
    "comm": Category(
        "comm", "low",
        frozenset({"message", "spawn"}),
        "消息 / 通知 / 子任务",
    ),
    "general": Category(
        "general", "low",
        frozenset({"exec", "read_file", "list_dir", "web_search", "web_fetch", "smart_fetch"}),
        "无法明确归类的任务（安全兜底）",
    ),
    "chat": Category(
        "chat", "low",
        frozenset(),
        "纯对话（寒暄/闲聊，不启用工具）",
    ),
}

BASE_TOOLS: set[str] = {"exec", "read_file", "list_dir"}

# Legacy compatibility alias
TOOL_GROUPS: dict[str, set[str]] = {
    name: set(cat.tools) for name, cat in CATEGORIES.items()
}


# ── Public API ───────────────────────────────────────────────────

def get_risk(category: str) -> RiskLevel:
    """Return the default risk level for a category."""
    cat = CATEGORIES.get(category)
    return cat.risk if cat else "low"


def collect_tools(
    route_labels: list[str],
    *,
    mcp_tool_names: list[str] | None = None,
    always_include: set[str] | None = None,
) -> set[str]:
    """Gather the union of tool names for the given route labels."""
    tools: set[str] = set(always_include or BASE_TOOLS)
    for label in route_labels:
        cat = CATEGORIES.get(label)
        if cat is not None:
            tools |= cat.tools
    if "browser" in route_labels and mcp_tool_names:
        tools |= {n for n in mcp_tool_names if n.startswith("mcp_")}
    return tools


def classify(user_text: str) -> list[str]:
    """Classify via the structured rule engine in ``rules.py``."""
    from myxai_desk.core.intent_engine.rules import match_rules
    result = match_rules(user_text)
    return [r.category for r in result] if result else ["general"]


def classify_detailed(user_text: str) -> tuple[list[str], list]:
    """Return (labels, matched_rule_objects) for observability."""
    from myxai_desk.core.intent_engine.rules import match_rules
    result = match_rules(user_text)
    if not result:
        return ["general"], []
    return [r.category for r in result], result
