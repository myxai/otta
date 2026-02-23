"""Daily Briefing (每日私享会) — personal curator & deep-dive exploration.

Your private information curator that understands your interests over time,
picks the most relevant content, and lets you explore any item in depth.

Data sources:
  - Chrome / Edge browser history
  - nanobot conversation history (chat messages)
  - Historical interest profile (multi-day trend tracking)

Pipeline:
  1. Read browser history + recent chat conversations
  2. Filter noise
  3. LLM interest analysis with trend awareness — extract interests,
     classify (work/study/life), and generate search queries.
     Falls back to rule-based extraction when LLM unavailable.
  4. Web search (Brave / Baidu auto-fallback)
  5. LLM report generation — personalised daily reading with
     real search results, tailored to user context
  6. Deep-dive exploration — click any card to start a contextual chat
"""

import html as _html
import json
import os
import re
import shutil
import sqlite3
import tempfile
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Browser history paths (Windows)
# ---------------------------------------------------------------------------
_LOCAL = os.environ.get("LOCALAPPDATA", "")

CHROME_HISTORY_PATHS = [
    Path(_LOCAL) / "Google" / "Chrome" / "User Data" / "Default" / "History",
    Path(_LOCAL) / "Google" / "Chrome" / "User Data" / "Profile 1" / "History",
]
EDGE_HISTORY_PATHS = [
    Path(_LOCAL) / "Microsoft" / "Edge" / "User Data" / "Default" / "History",
    Path(_LOCAL) / "Microsoft" / "Edge" / "User Data" / "Profile 1" / "History",
]

# ---------------------------------------------------------------------------
# Filtering rules
# ---------------------------------------------------------------------------
BLOCKED_DOMAIN_FRAGMENTS = [
    "accounts.google.com", "login.microsoftonline.com", "login.live.com",
    "signin", "passport", "sso.",
    "alipay.com", "pay.", "bank.",
    "mail.google.com", "outlook.live.com", "mail.qq.com", "mail.163.com",
    "web.whatsapp.com", "web.telegram.org",
    "localhost", "127.0.0.1", "192.168.",
]

BLOCKED_URL_PATTERNS = [
    re.compile(r"/login", re.I),
    re.compile(r"/signin", re.I),
    re.compile(r"/auth", re.I),
    re.compile(r"/oauth", re.I),
    re.compile(r"/search\?", re.I),
    re.compile(r"/results\?", re.I),
    re.compile(r"^https?://[^/]+/?$"),
]

# ---------------------------------------------------------------------------
# Category classification
# ---------------------------------------------------------------------------
WORK_DOMAINS = {
    "github.com", "gitlab.com", "bitbucket.org", "stackoverflow.com",
    "stackexchange.com", "dev.to", "hashnode.dev",
    "docs.python.org", "docs.microsoft.com", "learn.microsoft.com",
    "developer.mozilla.org", "npmjs.com", "pypi.org",
    "hub.docker.com", "vercel.com", "netlify.com",
    "aws.amazon.com", "cloud.google.com", "azure.microsoft.com",
    "jenkins.io", "circleci.com", "travis-ci.org",
}

WORK_KEYWORDS = {
    "api", "sdk", "framework", "library", "code", "programming",
    "developer", "engineering", "deploy", "docker", "kubernetes",
    "database", "server", "backend", "frontend", "devops", "cicd",
    "git", "pipeline", "microservice", "architecture", "debug",
    "testing", "agile", "sprint", "release", "版本", "部署", "开发",
    "接口", "框架", "工具", "组件", "源码",
}

STUDY_DOMAINS = {
    "arxiv.org", "scholar.google.com", "semanticscholar.org",
    "coursera.org", "udemy.com", "edx.org", "khanacademy.org",
    "medium.com", "towardsdatascience.com",
    "wikipedia.org", "zhihu.com", "juejin.cn", "csdn.net",
    "segmentfault.com", "infoq.cn", "cnblogs.com",
    "youtube.com", "bilibili.com",
}

STUDY_KEYWORDS = {
    "tutorial", "guide", "course", "learn", "paper", "research",
    "algorithm", "theory", "study", "model", "neural", "transformer",
    "machine learning", "deep learning", "ai",
    "教程", "学习", "入门", "进阶", "论文", "原理", "解析",
    "机器学习", "深度学习", "人工智能", "训练", "模型",
}

LIFE_DOMAINS = {
    "amazon.com", "amazon.cn", "jd.com", "taobao.com", "tmall.com",
    "pinduoduo.com", "suning.com",
    "news.qq.com", "news.sina.com.cn", "toutiao.com", "163.com",
    "douban.com", "dianping.com", "meituan.com",
    "ctrip.com", "booking.com", "tripadvisor.com",
    "smzdm.com", "xiaohongshu.com", "weibo.com",
}

LIFE_KEYWORDS = {
    "review", "recommendation", "buy", "price", "deal", "coupon",
    "health", "fitness", "recipe", "travel", "hotel", "flight",
    "restaurant", "movie", "book", "game", "music",
    "评测", "推荐", "购买", "价格", "优惠", "折扣",
    "健康", "健身", "食谱", "旅行", "电影", "音乐",
    "攻略", "测评", "种草", "开箱",
}

# ---------------------------------------------------------------------------
# Stop words
# ---------------------------------------------------------------------------
STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would",
    "should", "can", "could", "may", "might", "must",
    "that", "this", "these", "those", "there", "here",
    "with", "from", "into", "about", "for", "and", "but", "or",
    "not", "no", "all", "any", "each", "every", "some",
    "more", "most", "other", "what", "which", "who", "how",
    "when", "where", "why", "if", "then", "than", "too", "very",
    "just", "also", "only", "so", "now", "new", "get", "one",
    "use", "you", "your", "we", "our", "they", "their", "my",
    "http", "https", "www", "com", "org", "net", "html", "php",
    "page", "home", "index", "site", "web", "free", "online",
    "search", "api", "app", "tool", "best", "top", "list",
    "based", "using", "like", "make", "open", "source",
    "de", "la", "en", "el", "les", "des",
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
    "都", "一", "上", "也", "很", "到", "说", "要", "去", "你",
    "会", "着", "没有", "看", "好", "自己", "这", "那", "他", "她",
    "首页", "官网", "登录", "注册", "搜索", "更多", "下载",
}

# Domain base-names that should never become interest keywords.
# These are platform/infrastructure names, not user interests.
_DOMAIN_NOISE = {
    # Search engines
    "google", "bing", "baidu", "yahoo", "duckduckgo", "yandex", "sogou",
    # Code platforms
    "github", "gitlab", "bitbucket", "stackoverflow", "stackexchange",
    "gitee", "codeberg",
    # Big tech
    "microsoft", "apple", "amazon", "facebook", "meta", "twitter",
    "instagram", "tiktok", "reddit", "quora", "linkedin", "pinterest",
    # Video / music
    "youtube", "bilibili", "youku", "iqiyi", "netflix", "spotify",
    # Wiki
    "wikipedia", "fandom", "wikia",
    # E-commerce (CN)
    "taobao", "tmall", "jd.com", "pinduoduo", "suning",
    # Social / chat
    "alipay", "wechat", "weixin", "weibo", "douyin", "zhihu",
    "douban", "xiaohongshu", "meituan", "dianping", "ctrip",
    "discord", "slack", "telegram", "whatsapp", "mochat",
    "dingtalk", "feishu", "lark",
    # Email
    "outlook", "gmail", "hotmail", "protonmail",
    # Browsers
    "chrome", "firefox", "edge", "safari", "opera", "brave",
    # Infra / hosting
    "cloudflare", "vercel", "netlify", "heroku", "railway",
    "docker", "npm", "pypi", "conda", "brew",
    "localhost", "127",
    # AI products & LLM providers — must not become "interests"
    "nanobot", "chatgpt", "openai", "anthropic", "deepseek",
    "dashscope", "moonshot", "groq", "gemini", "claude", "xclaude",
    "qwen", "tongyi", "wenxin", "ernie", "llama", "mistral",
    "copilot", "cursor", "coze", "dify", "langchain", "llamaindex",
    # Common UI / generic fragments that leak from page titles
    "windows", "linux", "macos", "ubuntu", "android", "ios",
    "desktop", "client", "server", "download", "install", "update",
    "settings", "personal", "account", "profile", "dashboard",
    "version", "release", "latest", "official",
    "ultra", "lightweight", "powerful", "simple", "fast", "easy",
}

# ---------------------------------------------------------------------------
# Report storage
# ---------------------------------------------------------------------------
_APPS_DIR = Path.home() / ".nanobot" / "apps"
_DIGEST_DIR = _APPS_DIR / "daily_digest"
_REPORTS_DIR = _DIGEST_DIR / "reports"
_PROFILE_FILE = _DIGEST_DIR / "user_profile.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chrome_ts_to_dt(chrome_time: int):
    if not chrome_time:
        return None
    epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
    return epoch + timedelta(microseconds=chrome_time)


def find_browser_history_paths() -> list[dict]:
    results = []
    for p in CHROME_HISTORY_PATHS:
        if p.exists():
            results.append({"path": str(p), "browser": "Chrome"})
    for p in EDGE_HISTORY_PATHS:
        if p.exists():
            results.append({"path": str(p), "browser": "Edge"})
    return results


# ---------------------------------------------------------------------------
# Step 1 — Read browser history
# ---------------------------------------------------------------------------

def read_browser_history(hours: int = 24, browser: str = "auto") -> list[dict]:
    targets: list[Path] = []
    if browser in ("auto", "chrome"):
        targets.extend(p for p in CHROME_HISTORY_PATHS if p.exists())
    if browser in ("auto", "edge"):
        targets.extend(p for p in EDGE_HISTORY_PATHS if p.exists())

    if not targets:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_chrome = int(
        (cutoff - datetime(1601, 1, 1, tzinfo=timezone.utc)).total_seconds()
        * 1_000_000
    )

    records: list[dict] = []
    seen_urls: set[str] = set()

    for hist_path in targets:
        tmp_fd, tmp_name = tempfile.mkstemp(suffix=".db")
        os.close(tmp_fd)
        try:
            shutil.copy2(str(hist_path), tmp_name)
            conn = sqlite3.connect(tmp_name)
            cur = conn.cursor()
            cur.execute(
                "SELECT url, title, visit_count, last_visit_time "
                "FROM urls WHERE last_visit_time > ? "
                "ORDER BY last_visit_time DESC",
                (cutoff_chrome,),
            )
            for url, title, visit_count, last_visit_time in cur.fetchall():
                if not url or not title or url in seen_urls:
                    continue
                seen_urls.add(url)
                parsed = urlparse(url)
                records.append({
                    "url": url,
                    "title": title.strip(),
                    "domain": parsed.netloc.lower(),
                    "visit_count": visit_count or 1,
                    "timestamp": (
                        _chrome_ts_to_dt(last_visit_time).isoformat()
                        if last_visit_time else None
                    ),
                    "browser": "Chrome" if "Chrome" in str(hist_path) else "Edge",
                })
            conn.close()
        except Exception as exc:
            print(f"[daily_digest] read error ({hist_path}): {exc}")
        finally:
            try:
                from apps.safe_fs import safe_remove
                safe_remove(tmp_name)
            except OSError:
                pass

    return records


# ---------------------------------------------------------------------------
# Step 2 — Filter noise
# ---------------------------------------------------------------------------

def filter_history(records: list[dict]) -> list[dict]:
    filtered = []
    for r in records:
        domain = r["domain"]
        url = r["url"]
        if any(frag in domain for frag in BLOCKED_DOMAIN_FRAGMENTS):
            continue
        if any(pat.search(url) for pat in BLOCKED_URL_PATTERNS):
            continue
        if len(r["title"]) < 3:
            continue
        filtered.append(r)
    return filtered


# ---------------------------------------------------------------------------
# Step 2b — Read nanobot conversation history
# ---------------------------------------------------------------------------

_CHAT_HISTORY_FILE = Path.home() / ".nanobot" / "desktop_history" / "sessions.json"


def read_chat_history(hours: int = 72) -> list[dict]:
    """Read recent nanobot chat conversations.

    Returns a list of ``{"session_title": ..., "messages": [...]}`` dicts,
    one per session that was updated within the last *hours*.
    """
    if not _CHAT_HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(_CHAT_HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    sessions = []
    for sid, sess in data.items():
        updated = sess.get("updated_at", "")
        if not updated:
            continue
        try:
            ts = datetime.fromisoformat(updated.replace("Z", "+00:00"))
        except Exception:
            continue
        if ts < cutoff:
            continue
        msgs = sess.get("messages", [])
        if not msgs:
            continue
        sessions.append({
            "session_title": sess.get("title", sid),
            "updated_at": updated,
            "messages": msgs,
        })

    sessions.sort(key=lambda s: s["updated_at"], reverse=True)
    return sessions


def _build_chat_block(sessions: list[dict], limit: int = 40) -> str:
    """Build a concise conversation summary block for the LLM prompt.

    Only user messages are included — they reflect intent more directly
    and the assistant replies roughly double the token count with little
    extra signal for interest analysis.
    """
    if not sessions:
        return ""

    lines: list[str] = []
    for sess in sessions:
        title = sess.get("session_title", "").strip()
        if title:
            lines.append(f"\n### 对话: {title}")

        msgs = sess.get("messages", [])
        for m in msgs:
            role = m.get("role", "")
            content = (m.get("content") or "").strip()
            if not content or role != "user":
                continue
            preview = content[:150].replace("\n", " ")
            if len(content) > 150:
                preview += "…"
            lines.append(f"- 👤 {preview}")

            if len(lines) >= limit:
                break
        if len(lines) >= limit:
            break

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Step 3 — Extract interest keywords
# ---------------------------------------------------------------------------

def extract_keywords(records: list[dict], top_n: int = 30) -> list[dict]:
    counts: Counter = Counter()
    kw_records: dict[str, list] = defaultdict(list)

    # Also try to extract multi-word phrases (much better for search)
    phrase_counts: Counter = Counter()
    phrase_records: dict[str, list] = defaultdict(list)

    for r in records:
        title = r["title"]
        weight = min(r["visit_count"], 10)

        parts = re.split(r'[-–—|·•/\\:：,，]', title)
        for part in parts:
            part = part.strip()
            if len(part) < 2:
                continue

            # Single tokens
            tokens = re.findall(
                r'[a-zA-Z][a-zA-Z0-9+#.]{1,}|[\u4e00-\u9fff]{2,6}', part
            )
            for tok in tokens:
                tok_lower = tok.lower()
                if tok_lower in STOP_WORDS or tok_lower in _DOMAIN_NOISE:
                    continue
                if len(tok_lower) < 2:
                    continue
                counts[tok_lower] += weight
                if len(kw_records[tok_lower]) < 3:
                    kw_records[tok_lower].append(r)

            # Multi-word English phrases (2-4 words) — much better search terms
            en_phrases = re.findall(
                r'[A-Za-z][a-z]+(?:\s+[A-Za-z][a-z]+){1,3}', part
            )
            for phrase in en_phrases:
                p_lower = phrase.lower().strip()
                p_words = p_lower.split()
                if len(p_lower) < 5:
                    continue
                # Skip if any non-stop-word is a known platform/noise name
                content_words = [w for w in p_words if w not in STOP_WORDS]
                if not content_words:
                    continue
                if any(w in _DOMAIN_NOISE for w in content_words):
                    continue
                phrase_counts[p_lower] += weight * 2
                if len(phrase_records[p_lower]) < 3:
                    phrase_records[p_lower].append(r)

    # Merge: phrases first (higher quality), then single tokens
    merged: list[dict] = []
    seen = set()

    for phrase, cnt in phrase_counts.most_common(top_n):
        if cnt < 2:
            continue
        merged.append({
            "keyword": phrase,
            "count": cnt,
            "records": phrase_records.get(phrase, []),
        })
        seen.update(phrase.split())

    for kw, cnt in counts.most_common(top_n * 2):
        if kw in seen:
            continue
        if kw in _DOMAIN_NOISE:
            continue
        merged.append({
            "keyword": kw,
            "count": cnt,
            "records": kw_records.get(kw, []),
        })
        seen.add(kw)
        if len(merged) >= top_n:
            break

    return merged


# ---------------------------------------------------------------------------
# Step 4 — Classify into work / study / life
# ---------------------------------------------------------------------------

def classify_interests(keywords: list[dict]) -> dict[str, list]:
    categories: dict[str, list] = {"work": [], "study": [], "life": []}

    for item in keywords:
        kw = item["keyword"]
        domains = {r["domain"] for r in item.get("records", [])}

        scores = {"work": 0, "study": 0, "life": 0}
        for d in domains:
            for wd in WORK_DOMAINS:
                if wd in d:
                    scores["work"] += 3
            for sd in STUDY_DOMAINS:
                if sd in d:
                    scores["study"] += 3
            for ld in LIFE_DOMAINS:
                if ld in d:
                    scores["life"] += 3

        for wk in WORK_KEYWORDS:
            if wk in kw or kw in wk:
                scores["work"] += 2
        for sk in STUDY_KEYWORDS:
            if sk in kw or kw in sk:
                scores["study"] += 2
        for lk in LIFE_KEYWORDS:
            if lk in kw or kw in lk:
                scores["life"] += 2

        best = max(scores, key=lambda k: scores[k])
        if scores[best] == 0:
            best = "life"
        categories[best].append(item)

    return categories


# ===================================================================
# LLM helper — unified call with auto provider prefix
# ===================================================================

# litellm needs a provider prefix (e.g. "openai/qwen-plus") for models it
# doesn't natively recognise.  When an api_base is provided, the model is
# almost certainly served via an OpenAI-compatible endpoint, so we prepend
# "openai/" automatically unless a prefix is already present.

_KNOWN_LITELLM_PREFIXES = (
    "openai/", "azure/", "anthropic/", "bedrock/", "vertex_ai/",
    "cohere/", "huggingface/", "ollama/", "deepseek/", "groq/",
    "together_ai/", "openrouter/", "gemini/", "mistral/",
)


def _litellm_model_name(model: str, api_base: str | None) -> str:
    """Ensure *model* has a provider prefix that litellm understands."""
    if any(model.startswith(p) for p in _KNOWN_LITELLM_PREFIXES):
        return model
    if api_base:
        return f"openai/{model}"
    return model


def _llm_call(
    messages: list[dict],
    model: str,
    api_key: str,
    api_base: str | None = None,
    temperature: float = 0.5,
    max_tokens: int = 2048,
) -> str:
    """Thin wrapper around litellm.completion with auto provider detection."""
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    import litellm

    resolved = _litellm_model_name(model, api_base)
    resp = litellm.completion(
        model=resolved,
        messages=messages,
        api_key=api_key,
        api_base=api_base,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    usage = getattr(resp, "usage", None)
    if usage:
        from apps.llm_utils import record_tokens
        record_tokens(
            prompt_tokens=getattr(usage, "prompt_tokens", 0),
            completion_tokens=getattr(usage, "completion_tokens", 0),
        )
    return resp.choices[0].message.content or ""


# ===================================================================
# Step 3+4 ALT — LLM-based interest analysis (replaces rule-based)
# ===================================================================

_INTEREST_ANALYSIS_PROMPT = """\
你是用户的私人兴趣分析专家。下面是用户最近的多维数据：
1. 浏览器历史摘要（页面标题 + 域名）
2. 与 AI 助手的对话记录（用户提问和讨论的主题）
3. 近期兴趣趋势（过去几天的关注方向）

请你综合分析：
1. 推断出用户真正的**兴趣主题**（忽略工具/平台本身的名字，比如 github、chatgpt、bing 等不是兴趣）
2. 将兴趣归入适用的类别：work（工作/职业相关）、study（学习/研究相关）、life（生活/娱乐相关）
3. 为每个**有内容的**类别生成 2-4 个高质量搜索词

关键规则：
- **综合分析所有数据源**。对话中讨论的主题往往比浏览历史更能反映深层兴趣
- **关注兴趣变化**。如果近几天出现新的关注方向，优先为其生成搜索词
- **持续关注的深化**。对于用户连续多天关注的主题，搜索词应更深入、更具体
- **只输出确实有兴趣的类别**。如果数据中完全没有某类内容，该类别留空数组即可
- 搜索词必须是**语义完整的自然语言短句**，可以直接粘贴到搜索引擎使用
  - 好的搜索词："Python FastAPI 异步性能优化最佳实践"、"2026年最佳降噪耳机评测对比"
  - 差的搜索词："python"、"耳机"、"FastAPI OR performance"（太短 / 不完整 / 拼凑）
- 搜索词要面向发现**新的高质量内容**（文章、教程、开源项目、评测、深度解读等）
- 可以中英文混用，取决于该主题更适合哪种语言搜索
- 兴趣主题用简短词组描述（3-10 字），搜索词用完整句式（8-25 字）

═══ 用户浏览历史 ═══
{history_block}

═══ 用户 AI 对话记录 ═══
{chat_block}

═══ 近期兴趣趋势 ═══
{trend_block}

═══ 请严格以 JSON 格式输出，不要输出其他内容 ═══
```json
{json_schema}
```"""

_INTEREST_JSON_SCHEMA = """\
{
  "work": {
    "interests": ["兴趣主题A", "兴趣主题B"],
    "queries": ["语义完整的搜索词1", "语义完整的搜索词2"]
  },
  "study": {
    "interests": ["兴趣主题C"],
    "queries": ["语义完整的搜索词3"]
  },
  "life": {
    "interests": [],
    "queries": []
  }
}"""


def _build_history_block(records: list[dict], limit: int = 50) -> str:
    """Build a concise browsing history block for the LLM prompt."""
    seen_titles: set[str] = set()
    lines: list[str] = []

    sorted_recs = sorted(records, key=lambda r: r.get("visit_count", 1), reverse=True)
    for r in sorted_recs:
        title = r["title"].strip()
        # Crude dedup — skip if title already seen (exact match)
        title_key = title.lower()[:60]
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        domain = r["domain"]
        visits = r.get("visit_count", 1)
        lines.append(f"- [{domain}] {title}" + (f" (×{visits})" if visits > 1 else ""))
        if len(lines) >= limit:
            break
    return "\n".join(lines)


def llm_analyze_interests(
    records: list[dict],
    model: str,
    api_key: str,
    api_base: str | None = None,
    chat_sessions: list[dict] | None = None,
) -> dict | None:
    """Use LLM to extract interests, classify, and generate search queries.

    Analyses both browser history *records* and nanobot *chat_sessions*.
    Returns dict like ``{"work": {"interests": [...], "queries": [...]}, ...}``
    or *None* on failure.
    """
    if not records and not chat_sessions:
        return None

    history_block = _build_history_block(records) if records else "（无浏览记录）"
    chat_block = _build_chat_block(chat_sessions or []) or "（无对话记录）"
    trend_block = _load_interest_history(days=7) or "（首次使用，暂无历史趋势）"
    prompt = _INTEREST_ANALYSIS_PROMPT.format(
        history_block=history_block,
        chat_block=chat_block,
        trend_block=trend_block,
        json_schema=_INTEREST_JSON_SCHEMA,
    )

    try:
        text = _llm_call(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            api_key=api_key,
            api_base=api_base,
            temperature=0.3,
            max_tokens=1024,
        )

        # Extract JSON from markdown code block if present
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        json_str = json_match.group(1) if json_match else text.strip()
        data = json.loads(json_str)

        # Validate structure
        result: dict = {}
        for cat in ("work", "study", "life"):
            entry = data.get(cat, {})
            result[cat] = {
                "interests": [str(s) for s in entry.get("interests", [])][:8],
                "queries": [str(s) for s in entry.get("queries", [])][:4],
            }
        total_q = sum(len(v["queries"]) for v in result.values())
        if total_q == 0:
            print("[daily_digest] LLM returned zero queries — falling back to rules")
            return None

        print(
            f"[daily_digest] LLM analysis: "
            + ", ".join(f"{c}={len(v['queries'])}q" for c, v in result.items())
        )
        return result
    except Exception as exc:
        print(f"[daily_digest] LLM analysis failed: {exc}")
        return None


# ===================================================================
# Step 5 — Web search  (delegates to shared apps.web_search module)
# ===================================================================

from apps.web_search import multi_engine_search as _multi_engine_search


def _web_search(query: str, brave_api_key: str | None = None,
                baidu_api_key: str | None = None,
                count: int = 8,
                _session_state: dict | None = None) -> list[dict]:
    """Search via available APIs (Baidu / Brave).

    Delegates to the shared multi-engine search in apps.web_search.
    Always returns a list (possibly empty), never raises.
    """
    try:
        results, engine = _multi_engine_search(
            query, brave_api_key=brave_api_key,
            baidu_api_key=baidu_api_key, count=count,
        )
        if results:
            print(f"[daily_digest] search OK via {engine}: {len(results)} results")
        return results
    except Exception as exc:
        print(f"[daily_digest] search failed for '{query[:60]}': {exc}")
        return []


# -- 5b. Smart query building strategy ------------------------------------
#
# Instead of one query per keyword × template, we combine multiple keywords
# into fewer, higher-quality queries to reduce API calls.

_CAT_QUERY_SUFFIXES = {
    "work": [
        "latest tool OR release OR open source",
        "best practices OR tutorial OR guide",
    ],
    "study": [
        "tutorial OR paper OR deep dive",
        "research OR course OR explained",
    ],
    "life": [
        "best OR review OR recommendation",
        "tips OR guide OR buying guide",
    ],
}


def build_search_queries(categories: dict[str, list],
                         max_kw_per_cat: int = 4) -> dict[str, list[str]]:
    """Build compact search queries — combine keywords to minimise API calls.

    Strategy: top keywords are grouped, producing ~2 queries per category
    instead of 2*N.
    """
    queries: dict[str, list[str]] = {"work": [], "study": [], "life": []}

    for cat, suffixes in _CAT_QUERY_SUFFIXES.items():
        kws = [item["keyword"] for item in categories.get(cat, [])[:max_kw_per_cat]]
        if not kws:
            continue

        if len(kws) == 1:
            for suffix in suffixes:
                queries[cat].append(f"{kws[0]} {suffix}")
        else:
            # Split keywords into two groups for two focused queries
            mid = max(1, len(kws) // 2)
            for i, suffix in enumerate(suffixes):
                group = kws[:mid] if i == 0 else kws[mid:]
                if not group:
                    group = kws[:1]
                combined = " OR ".join(group)
                queries[cat].append(f"({combined}) {suffix}")

    return queries


# -- 5c. Run all searches and deduplicate ----------------------------------

def search_for_recommendations(
    queries: dict[str, list[str]],
    brave_api_key: str | None = None,
    baidu_api_key: str | None = None,
    results_per_query: int = 8,
    progress_cb=None,
) -> dict[str, list[dict]]:
    """Execute web searches per category and return deduplicated results.

    *queries* is ``{"work": ["q1", ...], "study": [...], "life": [...]}``,
    produced either by LLM (``llm_analyze_interests``) or by the rule-based
    ``build_search_queries``.
    """
    all_results: dict[str, list[dict]] = {"work": [], "study": [], "life": []}
    seen_urls: set[str] = set()
    total_queries = sum(len(v) for v in queries.values())
    done = 0
    session: dict = {}

    for cat, cat_queries in queries.items():
        for q in cat_queries:
            done += 1
            label = q[:40]

            if progress_cb:
                progress_cb(f"搜索中 ({done}/{total_queries}): {label} …")
            print(f"[daily_digest] search [{cat}]: {q}")

            hits = _web_search(
                q, brave_api_key=brave_api_key,
                baidu_api_key=baidu_api_key,
                count=results_per_query, _session_state=session,
            )
            for h in hits:
                normalized = h["url"].rstrip("/").lower()
                if normalized in seen_urls:
                    continue
                seen_urls.add(normalized)
                h["query_keyword"] = q[:50]
                all_results[cat].append(h)

    for cat in all_results:
        print(f"[daily_digest] search results [{cat}]: {len(all_results[cat])}")

    return all_results


# ===================================================================
# Step 6 — Build LLM prompt (includes real search results)
# ===================================================================

def _fmt_results(results: list[dict], limit: int = 10) -> str:
    """Format search results into a readable block for the LLM prompt."""
    if not results:
        return "(无搜索结果)"
    lines = []
    for i, r in enumerate(results[:limit], 1):
        lines.append(
            f"{i}. [{r['title']}]({r['url']})\n"
            f"   关联兴趣: {r.get('query_keyword', '?')}\n"
            f"   摘要: {r['description'][:120]}"
        )
    return "\n".join(lines)


_CAT_META = {
    "work":  {"emoji": "🧠", "zh": "工作精选"},
    "study": {"emoji": "📚", "zh": "学习精选"},
    "life":  {"emoji": "🌿", "zh": "生活精选"},
}


def _load_interest_history(days: int = 7) -> str:
    """Load interests from past reports to build a multi-day user profile."""
    if not _REPORTS_DIR.exists():
        return ""
    today = datetime.now().strftime("%Y-%m-%d")
    lines: list[str] = []
    for f in sorted(_REPORTS_DIR.glob("*.json"), reverse=True):
        if f.stem == today:
            continue
        if len(lines) >= days:
            break
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            interests = d.get("interests")
            if not interests:
                continue
            day_kws: list[str] = []
            for cat in ("work", "study", "life"):
                for item in (interests.get(cat) or [])[:5]:
                    kw = item["keyword"] if isinstance(item, dict) else str(item)
                    day_kws.append(kw)
            if day_kws:
                lines.append(f"- {f.stem}: {', '.join(day_kws)}")
        except Exception:
            pass
    return "\n".join(lines)


def _update_user_profile(interests: dict) -> None:
    """Incrementally update persistent user profile with today's interests."""
    _DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    profile: dict = {}
    if _PROFILE_FILE.exists():
        try:
            profile = json.loads(_PROFILE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    kw_counts: dict = profile.get("keyword_counts", {})
    for cat in ("work", "study", "life"):
        for item in (interests.get(cat) or []):
            kw = item["keyword"] if isinstance(item, dict) else str(item)
            kw_counts[kw] = kw_counts.get(kw, 0) + 1

    top_keywords = sorted(kw_counts.items(), key=lambda x: x[1], reverse=True)[:50]
    profile["keyword_counts"] = dict(top_keywords)
    profile["last_updated"] = datetime.now().astimezone().isoformat()

    _PROFILE_FILE.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8",
    )

_JSON_SCHEMA_EXAMPLE = """\
{
  "sections": [
    {
      "category": "work",
      "items": [
        {"title":"文章标题","url":"https://真实链接","tag":"关联关键词","desc":"推荐理由","action":"具体建议"}
      ]
    }
  ],
  "focus": "今日重点洞察（1-2句）",
  "actions": ["建议行动1","建议行动2"]
}"""


def build_report_prompt(categories: dict[str, list],
                        search_results: dict[str, list[dict]],
                        date_str: str,
                        prev_titles: list[str] | None = None) -> str:
    def _top_kw(cat, n=8):
        return ", ".join(i["keyword"] for i in categories.get(cat, [])[:n])

    profile_lines = []
    for cat in ("work", "study", "life"):
        kws = _top_kw(cat)
        if kws:
            profile_lines.append(f"- {_CAT_META[cat]['zh']}：{kws}")
    interest_block = "\n".join(profile_lines) if profile_lines else "- (未检测到明确兴趣)"

    history_block = _load_interest_history(days=7)
    if history_block:
        interest_block += "\n\n近一周关注变化趋势：\n" + history_block

    results_block_parts = []
    active_cats = []
    for cat in ("work", "study", "life"):
        results = search_results.get(cat, [])
        if not results:
            continue
        active_cats.append(cat)
        meta = _CAT_META[cat]
        results_block_parts.append(
            f"### {meta['emoji']} {meta['zh']}搜索结果\n{_fmt_results(results)}"
        )
    results_block = "\n\n".join(results_block_parts) if results_block_parts else "(无搜索结果)"

    active_cats_hint = ", ".join(
        f'"{c}"' for c in active_cats
    ) if active_cats else '"work"'

    if prev_titles:
        dedup_list = "\n".join(f"- {t}" for t in prev_titles)
        dedup_block = (
            "以下是昨天已经推荐过的内容标题，今天的推荐**必须与这些完全不同**，"
            "不要推荐相同主题、相同工具、相同项目的内容：\n"
            f"{dedup_list}\n\n"
            "同时，今天输出的各条卡片之间也不能主题重复。"
        )
    else:
        dedup_block = "今天输出的各条卡片之间不能主题重复，每条必须是不同的话题/工具/项目。"

    return f"""你是用户的私人资讯策展人，像一位见多识广的老朋友在私下分享最值得关注的内容。
你非常了解这位用户——他最近在关注什么、工作中遇到什么挑战、学习什么新东西、生活中对什么感兴趣。
你的目标不是堆砌链接，而是挑选"他一定不想错过"的内容，用他能共鸣的方式呈现。

今日日期：{date_str}

═══ 用户兴趣画像（你对他的了解） ═══
{interest_block}

═══ 全网搜索结果（真实链接，请从中精选） ═══

{results_block}

═══ 去重要求（非常重要） ═══

{dedup_block}

═══ 输出要求 ═══

请输出一个**纯 JSON 对象**（不要 Markdown 包裹、不要 ```json 标记、不要任何其他文字），严格遵循以下 schema：

{_JSON_SCHEMA_EXAMPLE}

字段说明：
- sections: 数组，每个元素对应一个类别。category 只能是 {active_cats_hint} 中有搜索结果的类别
- items: 每个类别精选 3-5 条最有价值的内容。如果有价值的不多，宁少勿凑
- title: 文章标题
- url: **必须使用搜索结果中的真实 URL**，禁止编造
- tag: 关联的用户兴趣关键词
- desc: 推荐理由——结合用户兴趣说"这对你有什么用"，语气像朋友分享，不要泛泛复述标题
- action: 针对用户当前情况的一句具体建议
- focus: 结合用户最核心的兴趣，给出 1-2 个深度洞察
- actions: 2-3 个和用户当前关注直接相关的具体行动

规则：
1. 必须使用搜索结果中的真实 URL，禁止编造链接
2. 只输出有搜索结果的类别
3. 用中文输出所有文本字段
4. 当天各条卡片主题必须彼此不同
5. 质量优先于数量

现在请直接输出 JSON："""


# ===================================================================
# Step 7 — Call LLM
# ===================================================================

def generate_report_llm(prompt: str, model: str, api_key: str,
                        api_base: str | None = None,
                        date_str: str = "") -> tuple[str, dict | None]:
    """Generate report via LLM.  Returns (html_content, items_data_or_None)."""
    raw = _llm_call(
        messages=[{"role": "user", "content": prompt}],
        model=model,
        api_key=api_key,
        api_base=api_base,
        temperature=0.7,
        max_tokens=2048,
    )
    parsed = _extract_json_from_llm(raw)
    if parsed:
        html = _json_to_html(parsed, date_str)
        print("[daily_digest] JSON output parsed OK, rendered via template")
        return html, parsed
    print("[daily_digest] JSON parse failed, using raw LLM output as HTML")
    return raw, None


def _esc(text: str) -> str:
    """Minimal HTML-escape for user-supplied text."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _json_to_html(data: dict, date_str: str) -> str:
    """Render the structured JSON report into HTML matching existing CSS classes."""
    parts: list[str] = [f'<h1>\U0001f4c5 {date_str} 每日私享会</h1>']

    for sec in data.get("sections", []):
        cat = sec.get("category", "")
        meta = _CAT_META.get(cat)
        if not meta:
            continue
        parts.append(f'<section class="dr-section">')
        parts.append(f'<h2>{meta["emoji"]} {meta["zh"]}</h2>')
        for item in sec.get("items", []):
            title = _esc(str(item.get("title", "")))
            url = _esc(str(item.get("url", "")))
            tag = _esc(str(item.get("tag", "")))
            desc = _esc(str(item.get("desc", "")))
            action = _esc(str(item.get("action", "")))
            parts.append(
                f'<div class="dr-card">'
                f'<h3><a href="{url}" target="_blank">{title}</a></h3>'
                f'<span class="dr-tag">{tag}</span>'
                f'<p class="dr-desc">{desc}</p>'
            )
            if action:
                parts.append(f'<p class="dr-action">\U0001f4a1 {action}</p>')
            parts.append('</div>')
        parts.append('</section>')

    focus = data.get("focus", "")
    if focus:
        parts.append('<section class="dr-section dr-focus">')
        parts.append('<h2>\U0001f525 今日重点关注</h2>')
        parts.append(f'<p>{_esc(focus)}</p>')
        parts.append('</section>')

    actions = data.get("actions", [])
    if actions:
        parts.append('<section class="dr-section dr-actions">')
        parts.append('<h2>\U0001f3af 今日建议行动</h2>')
        parts.append('<ul>')
        for a in actions:
            parts.append(f'<li>{_esc(str(a))}</li>')
        parts.append('</ul>')
        parts.append('</section>')

    return "\n".join(parts)


def _extract_json_from_llm(text: str) -> dict | None:
    """Try to parse a JSON object from LLM output, handling common wrapping."""
    text = text.strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        if first_nl != -1:
            text = text[first_nl + 1:]
        if text.endswith("```"):
            text = text[:-3].strip()

    for start_char, end_char in [("{", "}"), ]:
        idx_start = text.find(start_char)
        idx_end = text.rfind(end_char)
        if idx_start != -1 and idx_end > idx_start:
            candidate = text[idx_start:idx_end + 1]
            try:
                obj = json.loads(candidate)
                if isinstance(obj, dict) and "sections" in obj:
                    return obj
            except json.JSONDecodeError:
                pass
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    return None


def generate_report_fallback(categories: dict[str, list],
                             search_results: dict[str, list[dict]],
                             date_str: str) -> str:
    """HTML report when LLM is unavailable — still uses real search links."""
    parts: list[str] = [f'<h1>📅 {date_str} 每日私享会</h1>']

    for cat in ("work", "study", "life"):
        meta = _CAT_META[cat]
        results = search_results.get(cat, [])
        kws = [i["keyword"] for i in categories.get(cat, [])[:5]]
        if not results and not kws:
            continue
        parts.append(f'<section class="dr-section">')
        parts.append(f'<h2>{meta["emoji"]} {meta["zh"]}</h2>')
        if results:
            for r in results[:5]:
                title = _esc(r["title"][:80])
                url = _esc(r["url"])
                desc = _esc(r["description"][:150])
                kw = _esc(r.get("query_keyword", ""))
                parts.append(
                    f'<div class="dr-card">'
                    f'<h3><a href="{url}" target="_blank">{title}</a></h3>'
                    f'<span class="dr-tag">{kw}</span>'
                    f'<p class="dr-desc">{desc}</p>'
                    f'</div>'
                )
        else:
            parts.append(f'<p>关注关键词：{_esc(", ".join(kws))}（未能获取搜索结果）</p>')
        parts.append('</section>')

    all_kws = []
    for cat in ("work", "study", "life"):
        all_kws.extend(categories.get(cat, []))
    all_kws.sort(key=lambda x: x.get("count", 0), reverse=True)

    parts.append('<section class="dr-section dr-focus">')
    parts.append('<h2>🔥 今日重点关注</h2>')
    if all_kws:
        parts.append(f'<p>你今天最关注的主题是：<strong>{_esc(all_kws[0]["keyword"])}</strong></p>')
    parts.append('</section>')

    parts.append('<section class="dr-section dr-actions">')
    parts.append('<h2>🎯 今日建议行动</h2>')
    parts.append('<ul>')
    parts.append('<li>点击上方链接深入阅读你感兴趣的内容</li>')
    parts.append('<li>将有价值的文章加入收藏或笔记</li>')
    parts.append('</ul>')
    parts.append('</section>')

    return "\n".join(parts)


# ===================================================================
# Report persistence
# ===================================================================

def save_report(content: str, date_str: str | None = None,
                interests: dict | None = None,
                search_stats: dict | None = None,
                search_results: dict | None = None,
                items: dict | None = None) -> dict:
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    sr_compact: dict[str, list[dict]] | None = None
    if search_results:
        sr_compact = {}
        for cat, sr_items in search_results.items():
            sr_compact[cat] = [
                {"title": r["title"][:120], "url": r["url"],
                 "description": r["description"][:300],
                 "query_keyword": r.get("query_keyword", "")}
                for r in sr_items[:20]
            ]
    data = {
        "date": date_str,
        "content": content,
        "interests": interests,
        "search_stats": search_stats,
        "search_results": sr_compact,
        "generated_at": datetime.now().astimezone().isoformat(),
    }
    if items is not None:
        data["items"] = items
    (_REPORTS_DIR / f"{date_str}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return data


def load_report(date_str: str | None = None) -> dict | None:
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    fp = _REPORTS_DIR / f"{date_str}.json"
    if fp.exists():
        return json.loads(fp.read_text(encoding="utf-8"))
    return None


def _extract_prev_titles(date_str: str) -> list[str]:
    """Extract card titles from yesterday's report to avoid duplication."""
    import re
    from datetime import timedelta
    yesterday = (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    rpt = load_report(yesterday)
    if not rpt:
        return []
    items = rpt.get("items")
    if items and isinstance(items, dict):
        titles = []
        for sec in items.get("sections", []):
            for it in sec.get("items", []):
                t = it.get("title", "").strip()
                if t:
                    titles.append(t)
        if titles:
            return titles
    content = rpt.get("content", "")
    if not content:
        return []
    titles = re.findall(r'<h3[^>]*>(.*?)</h3>', content, re.S)
    return [re.sub(r"<[^>]+>", "", t).strip() for t in titles if t.strip()]


def list_reports(limit: int = 30) -> list[dict]:
    if not _REPORTS_DIR.exists():
        return []
    reports = []
    for f in sorted(_REPORTS_DIR.glob("*.json"), reverse=True)[:limit]:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            reports.append({
                "date": d.get("date", f.stem),
                "generated_at": d.get("generated_at", ""),
            })
        except Exception:
            pass
    return reports


def delete_report(date_str: str) -> bool:
    from apps.safe_fs import safe_remove
    fp = _REPORTS_DIR / f"{date_str}.json"
    if fp.exists():
        safe_remove(fp)
        return True
    return False


# ===================================================================
# Explore — deep-dive into a specific content item
# ===================================================================

_EXPLORE_PROMPT_TEMPLATE = """\
你是用户的私人资讯分析师。用户对下面这条资讯产生了兴趣，请帮助他深入理解。

【资讯标题】{title}
【摘要】{description}
【来源链接】{url}
【关联兴趣】{keyword}

{context_block}

请输出（中文）：
1. **核心要点**：用 3-5 个要点概括这条资讯的关键信息
2. **为什么值得关注**：结合用户的兴趣方向，解释这条内容对他的潜在价值
3. **延伸思考**：提出 2-3 个值得进一步探索的方向或问题
4. **行动建议**：给出 1-2 条具体可执行的下一步

风格要求：像一位见多识广的同事在私下交流，语气自然、信息量大、不说废话。"""


def build_explore_prompt(item: dict, interests: dict | None = None) -> str:
    """Build a chat prompt for exploring a specific digest content item."""
    title = item.get("title", "")
    description = item.get("description", "")
    url = item.get("url", "")
    keyword = item.get("query_keyword", "")

    context_lines = []
    if interests:
        for cat in ("work", "study", "life"):
            kws = interests.get(cat, [])
            if kws:
                cat_name = {"work": "工作", "study": "学习", "life": "生活"}[cat]
                kw_text = ", ".join(
                    k["keyword"] if isinstance(k, dict) else str(k) for k in kws[:5]
                )
                context_lines.append(f"- {cat_name}兴趣：{kw_text}")
    context_block = (
        "【用户兴趣画像】\n" + "\n".join(context_lines)
        if context_lines else ""
    )

    return _EXPLORE_PROMPT_TEMPLATE.format(
        title=title,
        description=description,
        url=url,
        keyword=keyword,
        context_block=context_block,
    )


# ===================================================================
# Orchestrator — run the full pipeline
# ===================================================================

def run_daily_digest(config: dict, progress_cb=None) -> dict:
    """Execute the full daily digest pipeline.

    New pipeline: history → filter → **LLM interest analysis** (with rule-based
    fallback) → web search → LLM report generation.

    Returns ``{"status": "ok"|"error", "report": ..., "interests": ...}``.
    """
    browser = config.get("browser", "auto")
    hours = config.get("history_hours", 24)
    date_str = datetime.now().strftime("%Y-%m-%d")

    model = config.get("model")
    api_key = config.get("api_key")
    api_base = config.get("api_base")
    brave_api_key = config.get("brave_api_key") or None
    baidu_api_key = config.get("baidu_api_key") or None
    has_llm = bool(model and api_key)

    print(f"[daily_digest] starting — browser={browser}, hours={hours}, llm={has_llm}")

    # ── 1. Collect ──────────────────────────────────────────────────
    if progress_cb:
        progress_cb("正在读取浏览器历史和对话记录…")
    raw = read_browser_history(hours=hours, browser=browser)
    print(f"[daily_digest] raw history: {len(raw)} records")

    chat_hours = config.get("chat_hours", 72)
    chat_sessions = read_chat_history(hours=chat_hours)
    chat_msg_count = sum(len(s.get("messages", [])) for s in chat_sessions)
    print(f"[daily_digest] chat sessions: {len(chat_sessions)}, messages: {chat_msg_count}")

    if not raw and not chat_sessions:
        return {
            "status": "error",
            "message": "未找到浏览器历史记录或对话记录。请确认浏览器已安装或有过对话。",
        }

    # ── 2. Filter ───────────────────────────────────────────────────
    filtered = filter_history(raw)
    print(f"[daily_digest] after filter: {len(filtered)} records")

    # ── 3+4. Analyse interests & build search queries ───────────────
    #   Try LLM first; fall back to rule-based extraction + classification.
    llm_analysis: dict | None = None
    search_queries: dict[str, list[str]] = {"work": [], "study": [], "life": []}
    interests_summary: dict[str, list] = {"work": [], "study": [], "life": []}
    # categories is only needed for rule-based path & report building
    categories: dict[str, list] = {"work": [], "study": [], "life": []}

    if has_llm:
        if progress_cb:
            progress_cb("正在通过 AI 分析兴趣…")
        llm_analysis = llm_analyze_interests(
            filtered, model, api_key, api_base,
            chat_sessions=chat_sessions,
        )

    if llm_analysis:
        # LLM path — use its queries & interests directly
        for cat in ("work", "study", "life"):
            entry = llm_analysis[cat]
            search_queries[cat] = entry["queries"]
            interests_summary[cat] = [
                {"keyword": kw, "count": 0} for kw in entry["interests"]
            ]
            # Build a compatible categories structure for report prompt
            categories[cat] = [
                {"keyword": kw, "count": 0, "records": []}
                for kw in entry["interests"]
            ]
        print("[daily_digest] using LLM-generated search queries")
    else:
        # Fallback — rule-based
        if progress_cb:
            progress_cb("正在提取兴趣关键词…")
        keywords = extract_keywords(filtered)
        print(f"[daily_digest] rule-based keywords: {len(keywords)}")
        categories = classify_interests(keywords)
        interests_summary = {
            cat: [{"keyword": i["keyword"], "count": i["count"]} for i in items[:10]]
            for cat, items in categories.items()
        }
        search_queries = build_search_queries(categories)
        print("[daily_digest] using rule-based search queries")

    print(
        "[daily_digest] queries: "
        + ", ".join(f"{c}={len(q)}" for c, q in search_queries.items())
    )

    # ── 5. Web search ───────────────────────────────────────────────
    if progress_cb:
        progress_cb("正在全网搜索推荐内容…")

    search_results = search_for_recommendations(
        search_queries,
        brave_api_key=brave_api_key,
        baidu_api_key=baidu_api_key,
        progress_cb=progress_cb,
    )

    total_r = sum(len(v) for v in search_results.values())
    search_stats = {
        "total_queries": sum(len(v) for v in search_queries.values()),
        "total_results": total_r,
    }
    print(f"[daily_digest] total search results: {total_r}")

    # ── 6. Generate report ──────────────────────────────────────────
    if progress_cb:
        progress_cb("正在生成每日私享会…")

    prev_titles = _extract_prev_titles(date_str)
    if prev_titles:
        print(f"[daily_digest] dedup: {len(prev_titles)} titles from yesterday")

    items_data: dict | None = None
    if has_llm:
        try:
            prompt = build_report_prompt(categories, search_results, date_str,
                                         prev_titles=prev_titles)
            report_text, items_data = generate_report_llm(
                prompt, model, api_key, api_base, date_str=date_str,
            )
        except Exception as exc:
            print(f"[daily_digest] LLM report error, falling back: {exc}")
            report_text = generate_report_fallback(
                categories, search_results, date_str,
            )
    else:
        report_text = generate_report_fallback(
            categories, search_results, date_str,
        )

    # ── 7. Save + update profile ─────────────────────────────────────
    report_data = save_report(
        report_text, date_str, interests_summary, search_stats,
        search_results=search_results,
        items=items_data,
    )
    try:
        _update_user_profile(interests_summary)
    except Exception as exc:
        print(f"[daily_digest] profile update error: {exc}")

    return {
        "status": "ok",
        "report": report_data,
        "interests": interests_summary,
        "stats": {
            "raw_count": len(raw),
            "filtered_count": len(filtered),
            "chat_sessions": len(chat_sessions),
            "chat_messages": chat_msg_count,
            "keyword_count": sum(len(v) for v in interests_summary.values()),
            "search_queries": search_stats["total_queries"],
            "search_results": search_stats["total_results"],
        },
    }
