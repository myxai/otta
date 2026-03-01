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

_STRONG_MATH = re.compile(
    r"\d+\s*[+\-*/÷×^%]\s*\d|=\s*\?|计算|求解|方程|"
    r"√|∑|∫|sin|cos|tan|log|ln|π|平方|立方|阶乘|导数|积分|极限",
    re.IGNORECASE,
)
_STRONG_CREATIVE = re.compile(
    r"写|作文|诗|故事|小说|文案|脚本|歌词|对联|散文|"
    r"生成|创作|编写|改写|润色|翻译|仿写|续写|摘要|总结",
    re.IGNORECASE,
)
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
            r"^(?:你好|hi|hello|hey|嗨|早上好|晚上好|谢谢|thanks|再见|bye|goodbye)\b",
            re.IGNORECASE,
        ),
        negative=re.compile(
            r"搜索|查找|文件|目录|执行|运行|打开|下载|安装|浏览器|"
            r"监控|报告|删除|移动|复制|编辑|创建|写|翻译|计算",
            re.IGNORECASE,
        ),
        priority=100,
        base_conf=0.85,
        weak_features=_WEAK_PHRASES,
    ),

    # ── math: expressions, computation, numeric reasoning ──
    Rule(
        rule_id="math_expr",
        category="math",
        pattern=re.compile(
            r"\d+\s*[+\-*/÷×^%]\s*\d|=\s*\?|"
            r"计算|算一下|求值|求解|方程|等于多少|标准差|平均数|中位数|众数|方差|"
            r"加法|减法|乘法|除法|开方|根号|"
            r"√|∑|∫|sin\b|cos\b|tan\b|log\b|ln\b|π|sqrt|"
            r"平方|立方|阶乘|导数|积分|极限|概率|排列|组合|统计|"
            r"calculate|compute|solve|factorial|equation|divided\s+by|"
            r"mean|median|mode|variance|standard\s+deviation",
            re.IGNORECASE,
        ),
        negative=re.compile(
            r"搜索|查找|查询|百度|谷歌|google|bing|监控|报告",
            re.IGNORECASE,
        ),
        priority=95,
        base_conf=0.88,
        strong_features=_STRONG_MATH,
    ),

    # ── creative: writing, generation, translation ──
    Rule(
        rule_id="creative_write",
        category="creative",
        pattern=re.compile(
            r"写.*(?:诗|文|故事|小说|文案|脚本|歌词|对联|散文|段落|作文|邮件|信|注释|说明)|"
            r"讲.*(?:故事|笑话|段子)|"
            r"来一首|来一篇|来一段|来个.*(?:故事|笑话|段子)|"
            r"生成.*(?:文本|内容|文章|报告)|创作|编写|改写|润色|续写|仿写|"
            r"翻译|translate|comment|documentation|"
            r"write\s+.*(?:poem|story|article|essay|email|script|lyrics|paragraph|letter|comment)|"
            r"generate\s+.*(?:text|content|description|report|documentation)|"
            r"create\s+.*(?:story|poem|slogan|content)|"
            r"compose|draft|rewrite|polish|rephrase|paraphrase|summarize|summary|"
            r"tell\s+.*(?:story|tale|joke)",
            re.IGNORECASE,
        ),
        negative=re.compile(
            r"搜索|查找|文件|目录|执行|运行|下载|安装|浏览器|监控",
            re.IGNORECASE,
        ),
        priority=90,
        base_conf=0.85,
        strong_features=_STRONG_CREATIVE,
        weak_features=_WEAK_PHRASES,
    ),

    # ── ask: knowledge Q&A that doesn't need web search ──
    Rule(
        rule_id="ask_knowledge",
        category="ask",
        pattern=re.compile(
            r"^(?:你是谁|介绍一下|解释|什么是|什么叫|叫做|为什么|怎么理解|帮我理解|"
            r"什么意思|怎么回事|有什么区别|有何不同|对比一下|比较)|"
            r"是什么|的区别|的不同|是什么意思|如何理解|怎样理解|怎么看待|"
            r"what\s+is|what's|what\s+are|explain|why\s+is|why\s+does|why\s+do|"
            r"how\s+does|how\s+do|how\s+to\s+understand|can\s+you\s+explain|"
            r"what.*difference|difference\s+between|what\s+does.*mean|"
            r"what.*meaning",
            re.IGNORECASE,
        ),
        negative=re.compile(
            r"搜索|查找|文件|目录|执行|运行|打开|下载|安装|浏览器|"
            r"监控|报告|删除|移动|复制|编辑|创建|写|翻译|计算|"
            r"最新|新闻|今天|实时|当前|"
            r"latest|today|current|recent|now|file|directory|search|find",
            re.IGNORECASE,
        ),
        priority=88,
        base_conf=0.80,
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
            r"新闻|资讯|最新|天气|汇率|股价|房价|价格|行情|指数|"
            r"find.*(?:recent|latest|new)|look\s+up",
            re.IGNORECASE,
        ),
        priority=70,
        base_conf=0.78,
        strong_features=_STRONG_SEARCH,
        weak_features=_WEAK_PHRASES,
    ),
    Rule(
        rule_id="search_monitoring",
        category="search",
        pattern=re.compile(
            r"监控|报告|报表|分析|调研|趋势|对比|统计.*(?:数据|信息)|"
            r"摘要|总结.*(?:信息|新闻|内容)|"
            r"monitor|report|analyze|compare.*(?:models|products|prices)",
            re.IGNORECASE,
        ),
        negative=re.compile(
            r"文件|目录|统计.*(?:目录|文件|磁盘)|"
            r"^(?:写|生成|创作|制作).*(?:报告|简报|报表)|"  # 排除"写报告"、"生成报告"
            r"保存.*(?:报告|报表)|导出.*(?:报告|报表)",  # 排除"保存报告"
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
            r"环境变量|PATH|chmod|chown|sudo|"
            r"磁盘.*(?:空间|剩余|容量)|CPU.*使用率|内存.*使用|"
            r"disk.*(?:space|usage)|cpu.*usage|memory.*usage|"
            r"重启|restart|杀掉|kill|停止|stop|启动|start|"  # 新增
            r"进程|process|服务|service.*(?:重启|启动|停止)|"  # 新增
            r"install.*(?:python|node|java|package)",
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
            r"压缩|解压|整理.*(?:文件|目录|下载)|"
            r"保存到|保存为|另存为|导出为|导出到|写入到|"  # 新增：明确的保存操作
            r"read_file|write_file|edit_file|list_dir|"
            r"delete.*file|move.*file|copy.*file|read.*(?:file|config)|edit.*\.(py|js|json|txt|md)|"
            r"list.*(?:file|directory|dir)|"
            r"save\s+to|save\s+as|export\s+to|export\s+as|write\s+to",  # 新增英文
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
            r"查看.*git|查git|git.*状态|git.*历史|git.*日志|"
            r"提交|commit|推送|push|拉取|pull|合并|merge|"  # 新增：Git操作
            r"编译|构建|build|compile|运行.*(?:脚本|程序|代码)|执行.*(?:脚本|命令)",
            re.IGNORECASE,
        ),
        negative=re.compile(
            r"搜索|查找|查询|监控|报告|分析|趋势",
            re.IGNORECASE,
        ),
        priority=45,
        base_conf=0.72,
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
