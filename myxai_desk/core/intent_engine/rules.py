"""IE 2.0 — Structured rule engine for intent classification.

Each rule has:
  - rule_id: unique identifier
  - category: target category
  - patterns: keyword/regex list (match any → hit)
  - negative_patterns: exclusion list (match any → suppress this rule)
  - priority: conflict arbitration (higher wins)

Design principles:
  A. fs/system require explicit file/system verbs (conservative match)
  B. search covers monitoring + reporting tasks
  C. fallback = general, never fs/system
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Rule:
    rule_id: str
    category: str
    pattern: re.Pattern[str]
    negative: re.Pattern[str] | None = None
    priority: int = 0
    risk_override: str | None = None
    base_conf: float = 0.70
    strong_features: re.Pattern[str] | None = None
    weak_features: re.Pattern[str] | None = None


# ── Rule definitions (ordered by priority DESC) ──────────────────

_STRONG_FS = re.compile(
    r"删除|移动|重命名|压缩|解压|复制|覆盖|格式化|清空|"
    r"\.(?:txt|csv|json|xml|py|js|md|zip|tar|pdf|docx?|xlsx?)|"
    r"/home/|/tmp/|C:\\|D:\\|~/|read_file|write_file|edit_file|list_dir",
    re.IGNORECASE,
)
_STRONG_SYSTEM = re.compile(
    r"pip\s+install|npm\s+install|apt\s+|brew\s+|sudo|chmod|chown|systemctl|"
    r"registry|注册表|防火墙",
    re.IGNORECASE,
)
_STRONG_SEARCH = re.compile(
    r"https?://\S|www\.\S|谷歌|百度|google|bing|"
    r"新闻|资讯|天气|汇率|股价|房价|价格|行情|指数",
    re.IGNORECASE,
)
_STRONG_BROWSER = re.compile(
    r"playwright|screenshot|截图|click|navigate|scroll|fill|scrape|crawl",
    re.IGNORECASE,
)
_STRONG_SCHEDULE = re.compile(
    r"cron|每天|每周|每月|分钟后|小时后|定时",
    re.IGNORECASE,
)
_WEAK_PHRASES = re.compile(
    r"处理|搞一下|看看|帮我|试试|弄一下|搞个|整一下|来个",
    re.IGNORECASE,
)


RULES: list[Rule] = [
    # ── chat: pure conversation (highest priority, catches greetings etc.) ──
    Rule(
        rule_id="chat_greeting",
        category="chat",
        pattern=re.compile(
            r"^(?:你好|hi|hello|hey|嗨|早上好|晚上好|谢谢|thanks|再见|bye|"
            r"你是谁|介绍一下|解释|什么是|为什么|怎么理解|帮我理解)\b",
            re.IGNORECASE,
        ),
        negative=re.compile(
            r"搜索|查找|文件|目录|执行|运行|打开|下载|安装|浏览器|"
            r"监控|报告|删除|移动|复制|编辑|创建",
            re.IGNORECASE,
        ),
        priority=100,
        base_conf=0.85,
        weak_features=_WEAK_PHRASES,
    ),

    # ── browser: web automation ──
    Rule(
        rule_id="browser_automation",
        category="browser",
        pattern=re.compile(
            r"打开.*页面|点击.*按钮|浏览器|截图|screenshot|browser|playwright|"
            r"网页操作|填写.*表单|click|navigate|scroll|fill|type.*input|"
            r"爬取|scrape|crawl",
            re.IGNORECASE,
        ),
        priority=80,
        base_conf=0.80,
        strong_features=_STRONG_BROWSER,
        weak_features=_WEAK_PHRASES,
    ),

    # ── search: information retrieval / monitoring / reporting ──
    Rule(
        rule_id="search_query",
        category="search",
        pattern=re.compile(
            r"搜索|查找|查询|搜一下|谷歌|百度|google|search|bing|"
            r"新闻|资讯|最新|天气|汇率|股价|房价|价格|行情|指数",
            re.IGNORECASE,
        ),
        priority=70,
        base_conf=0.75,
        strong_features=_STRONG_SEARCH,
        weak_features=_WEAK_PHRASES,
    ),
    Rule(
        rule_id="search_monitoring",
        category="search",
        pattern=re.compile(
            r"监控|报告|报表|分析|调研|趋势|对比|统计.*(?:数据|信息)|"
            r"摘要|总结.*(?:信息|新闻|内容)",
            re.IGNORECASE,
        ),
        negative=re.compile(
            r"文件|目录|统计.*(?:目录|文件|磁盘)",
            re.IGNORECASE,
        ),
        priority=70,
        base_conf=0.70,
        strong_features=_STRONG_SEARCH,
        weak_features=_WEAK_PHRASES,
    ),
    Rule(
        rule_id="search_fetch",
        category="search",
        pattern=re.compile(
            r"https?://\S|www\.\S|抓取|获取.*(?:网页|页面|内容)|打开.*链接|"
            r"简报|fetch\b|下载.*(?:网页|内容|资料)",
            re.IGNORECASE,
        ),
        priority=65,
        base_conf=0.72,
        strong_features=_STRONG_SEARCH,
        weak_features=_WEAK_PHRASES,
    ),

    # ── system: high-risk system operations ──
    Rule(
        rule_id="system_ops",
        category="system",
        pattern=re.compile(
            r"安装|pip\s+install|npm\s+install|apt\s+|brew\s+|"
            r"系统设置|网络配置|防火墙|注册表|registry|systemctl|service\s+|"
            r"环境变量|PATH|chmod|chown|sudo",
            re.IGNORECASE,
        ),
        priority=60,
        base_conf=0.78,
        strong_features=_STRONG_SYSTEM,
        weak_features=_WEAK_PHRASES,
    ),

    # ── fs: file system operations (require explicit file verbs) ──
    Rule(
        rule_id="fs_file_ops",
        category="fs",
        pattern=re.compile(
            r"文件|目录|读取|写入|编辑|创建.*文件|删除.*文件|"
            r"移动.*(?:文件|目录|文件夹)|复制.*(?:文件|目录)|重命名|"
            r"压缩|解压|整理.*(?:文件|目录|下载)|read_file|write_file|edit_file|list_dir",
            re.IGNORECASE,
        ),
        priority=50,
        base_conf=0.75,
        strong_features=_STRONG_FS,
        weak_features=_WEAK_PHRASES,
    ),
    Rule(
        rule_id="fs_dev_ops",
        category="fs",
        pattern=re.compile(
            r"git\s|git\b|命令|终端|terminal|shell|cmd|"
            r"编译|构建|build|compile|运行.*(?:脚本|程序|代码)|执行.*(?:脚本|命令)",
            re.IGNORECASE,
        ),
        negative=re.compile(
            r"搜索|查找|查询|监控|报告|分析|趋势",
            re.IGNORECASE,
        ),
        priority=45,
        base_conf=0.65,
        strong_features=_STRONG_FS,
        weak_features=_WEAK_PHRASES,
    ),

    # ── net: HTTP/API calls ──
    Rule(
        rule_id="net_api",
        category="net",
        pattern=re.compile(
            r"API|接口|请求|POST|GET|PUT|DELETE|webhook|curl|httpx|"
            r"调用.*(?:服务|接口)|发送.*请求",
            re.IGNORECASE,
        ),
        priority=40,
        base_conf=0.72,
        weak_features=_WEAK_PHRASES,
    ),

    # ── schedule: timers / reminders ──
    Rule(
        rule_id="schedule_timer",
        category="schedule",
        pattern=re.compile(
            r"提醒|定时|闹钟|计划|cron|schedule|remind|timer|"
            r"每天|每周|每月|分钟后|小时后",
            re.IGNORECASE,
        ),
        priority=30,
        base_conf=0.78,
        strong_features=_STRONG_SCHEDULE,
        weak_features=_WEAK_PHRASES,
    ),

    # ── comm: messaging / spawning ──
    Rule(
        rule_id="comm_message",
        category="comm",
        pattern=re.compile(
            r"发送|消息|通知|message|send|notify|后台|子任务|spawn",
            re.IGNORECASE,
        ),
        priority=20,
        base_conf=0.68,
        weak_features=_WEAK_PHRASES,
    ),
]


@dataclass
class RuleMatch:
    """A single rule hit with context."""
    rule_id: str
    category: str
    priority: int
    risk_override: str | None = None
    conf: float = 0.0


def match_rules(user_text: str) -> list[RuleMatch]:
    """Run all rules against *user_text*, return de-duplicated matches.

    Rules are evaluated in definition order, de-duplicated by category,
    and sorted by priority (highest first).
    """
    hits: list[RuleMatch] = []
    seen_cats: set[str] = set()

    for rule in RULES:
        if not rule.pattern.search(user_text):
            continue
        if rule.negative and rule.negative.search(user_text):
            continue
        if rule.category in seen_cats:
            continue
        seen_cats.add(rule.category)
        hits.append(RuleMatch(
            rule_id=rule.rule_id,
            category=rule.category,
            priority=rule.priority,
            risk_override=rule.risk_override,
        ))

    hits.sort(key=lambda h: h.priority, reverse=True)
    return hits
