"""Text normalisation and stable case-key generation for the Intent Engine.

``normalize_text`` strips filler words, applies low-risk synonym
normalisation, collapses whitespace and lowercases.  Negation and scope
modifiers (不要/别/禁止/仅/只/除了/排除/无需) are explicitly protected.

``build_case_key`` extracts a short, stable intent fingerprint that can be
used to match logically identical tasks across paraphrases.
"""

from __future__ import annotations

import hashlib
import re

# ── Protected phrases: negation / scope modifiers that MUST survive ───
# These are shielded from filler/synonym processing via placeholder swap.
_PROTECTED_WORDS = (
    "不要", "别", "禁止", "仅", "只", "除了", "排除", "不", "无需",
    "没有", "不能", "不可以", "不许", "不得", "勿", "不用",
)
_PROTECTED_RE = re.compile(
    "|".join(re.escape(w) for w in sorted(_PROTECTED_WORDS, key=len, reverse=True)),
)

_PUNCT = re.compile(r"[，。！？、；：""''（）【】《》\s,.!?;:\"'()\[\]{}<>]+")
_FILLER = re.compile(
    r"帮我|请|麻烦|一下|吧|呢|啊|哦|嗯|了|的|把|给我|帮忙|可以|能不能|能否",
)
_WHITESPACE = re.compile(r"\s+")

# Low-risk synonym normalisation.
# RULES:
#   - Only collapse verbs/nouns where conflation is SAFE for routing.
#   - NEVER touch high-risk fs/system action words (删除/清空/格式化/写入 etc.)
#   - NEVER add no-op pairs (下载→下载).
_SYNONYM_PAIRS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"搜索|查找|搜一下|查一下|找一下"), "查询"),
    (re.compile(r"跟踪|追踪|监测"), "监控"),
    (re.compile(r"汇总|简报|报表"), "报告"),
    (re.compile(r"拷贝"), "复制"),
    (re.compile(r"看看|瞧瞧"), "查看"),
    (re.compile(r"获取|抓取"), "获取"),
    (re.compile(r"售价|报价"), "价格"),
]

_VERB_MAP: dict[str, str] = {
    "搜索": "search", "查找": "search", "查询": "search", "搜一下": "search",
    "查一下": "search", "找": "search", "看看": "search",
    "删除": "delete", "移除": "delete", "清除": "delete", "清空": "delete",
    "移动": "move", "搬": "move",
    "复制": "copy", "拷贝": "copy",
    "重命名": "rename",
    "压缩": "compress", "解压": "extract",
    "创建": "create", "新建": "create", "建": "create",
    "编辑": "edit", "修改": "edit", "改": "edit",
    "读取": "read", "打开": "open", "查看": "read",
    "写入": "write", "保存": "write",
    "安装": "install", "卸载": "uninstall",
    "运行": "run", "执行": "run",
    "下载": "download", "上传": "upload",
    "发送": "send", "通知": "notify",
    "监控": "monitor", "分析": "analyze",
    "提醒": "remind", "定时": "schedule",
    "抓取": "fetch", "获取": "fetch",
}

_ZH_VERB_RE = re.compile("|".join(re.escape(k) for k in _VERB_MAP), re.IGNORECASE)

_NOUN_EXTRACT = re.compile(
    r"(?:文件|目录|文件夹|新闻|天气|汇率|股价|房价|网页|页面|链接|"
    r"脚本|程序|代码|报告|数据|接口|服务|消息|任务|图片|视频|音频|"
    r"邮件|日志|配置|环境|系统|网络|磁盘|进程|"
    r"[a-zA-Z][a-zA-Z0-9_./\\-]*)",
    re.IGNORECASE,
)


def normalize_text(text: str) -> str:
    """Strip filler words, apply synonym normalisation, collapse whitespace.

    Negation and scope modifiers are protected from removal via placeholder
    swap so that "不要删除" keeps "不要" intact.
    """
    t = text.strip()

    # 1. Shield protected words with placeholders
    shields: list[str] = []
    def _shield(m: re.Match) -> str:
        idx = len(shields)
        shields.append(m.group())
        return f"\x00P{idx}\x00"
    t = _PROTECTED_RE.sub(_shield, t)

    # 2. Remove fillers, normalise punctuation/whitespace
    t = _FILLER.sub("", t)
    t = _PUNCT.sub(" ", t)
    t = _WHITESPACE.sub(" ", t).strip().lower()

    # 3. Low-risk synonym replacement
    for pat, repl in _SYNONYM_PAIRS:
        t = pat.sub(repl, t)

    # 4. Restore protected words
    for idx, word in enumerate(shields):
        t = t.replace(f"\x00p{idx}\x00", word.lower())

    return t


def build_case_key(text_norm: str) -> str:
    """Generate a short stable key from normalised text.

    Format: ``<verb>_<noun_hash6>``  e.g. ``search_a3f2b1``
    Falls back to a pure hash when no verb is detected.
    """
    verb = "task"
    m = _ZH_VERB_RE.search(text_norm)
    if m:
        verb = _VERB_MAP.get(m.group(), "task")
    else:
        en = re.search(
            r"\b(search|delete|move|copy|rename|create|edit|read|write|"
            r"run|install|download|upload|send|monitor|analyze|remind|"
            r"schedule|fetch|open|compress|extract)\b",
            text_norm, re.IGNORECASE,
        )
        if en:
            verb = en.group().lower()

    nouns = _NOUN_EXTRACT.findall(text_norm)
    noun_part = "_".join(nouns[:3]).lower() if nouns else ""

    raw = f"{verb}_{noun_part}" if noun_part else verb
    h = hashlib.md5(text_norm.encode()).hexdigest()[:6]
    return f"{raw}_{h}"
