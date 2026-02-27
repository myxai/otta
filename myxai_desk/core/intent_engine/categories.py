"""Tool group definitions and rule-based route classification."""

from __future__ import annotations

import re

# ── L1 tool groups ─────────────────────────────────────────────────

TOOL_GROUPS: dict[str, set[str]] = {
    "fs": {"exec", "read_file", "list_dir", "write_file", "edit_file"},
    "search": {"web_search", "web_fetch", "smart_fetch"},
    "browser": set(),  # dynamically filled with MCP browser tools
    "schedule": {"cron"},
    "comm": {"message", "spawn"},
}

BASE_TOOLS: set[str] = {"exec", "read_file", "list_dir"}

# ── Route rules (ordered, first match wins after collecting all) ───

_ROUTE_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(
        r"打开.*页面|点击.*按钮|浏览器|截图|screenshot|browser|playwright|"
        r"网页操作|填写.*表单|click|navigate|scroll|fill|type.*input|"
        r"自动化|爬取|scrape|crawl",
        re.IGNORECASE,
    ), "browser"),
    (re.compile(
        r"搜索|查找|查询|搜一下|谷歌|百度|google|search|bing|"
        r"新闻|资讯|最新|天气|汇率|股价",
        re.IGNORECASE,
    ), "search"),
    (re.compile(
        r"https?://\S|www\.\S|抓取|获取.*(?:网页|页面|内容)|打开.*链接|"
        r"简报|摘要|fetch\b|下载",
        re.IGNORECASE,
    ), "search"),
    (re.compile(
        r"文件|目录|读取|写入|编辑|创建.*文件|删除.*文件|移动|复制|"
        r"read_file|write_file|edit_file|list_dir",
        re.IGNORECASE,
    ), "fs"),
    (re.compile(
        r"git|命令|执行|运行|安装|pip|npm|apt|brew|终端|terminal|shell|cmd|"
        r"编译|构建|build|compile",
        re.IGNORECASE,
    ), "fs"),
    (re.compile(
        r"提醒|定时|闹钟|计划|cron|schedule|remind|timer|"
        r"每天|每周|每月|分钟后|小时后",
        re.IGNORECASE,
    ), "schedule"),
    (re.compile(
        r"发送|消息|通知|message|send|notify|后台|子任务|spawn",
        re.IGNORECASE,
    ), "comm"),
]


def classify(user_text: str) -> list[str]:
    """Return a list of matched route labels (may be multiple)."""
    matched: list[str] = []
    for pattern, label in _ROUTE_RULES:
        if pattern.search(user_text) and label not in matched:
            matched.append(label)
    return matched or ["fs"]


def collect_tools(
    route_labels: list[str],
    *,
    mcp_tool_names: list[str] | None = None,
    always_include: set[str] | None = None,
) -> set[str]:
    """Gather the union of tool names for the given route labels."""
    tools: set[str] = set(always_include or BASE_TOOLS)
    for label in route_labels:
        group = TOOL_GROUPS.get(label)
        if group is not None:
            tools |= group
    if "browser" in route_labels and mcp_tool_names:
        tools |= {n for n in mcp_tool_names if n.startswith("mcp_")}
    return tools
