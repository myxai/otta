"""Today's Reading App — personal interest recommendation engine.

Data sources:
  - Chrome / Edge browser history
  - nanobot conversation history (chat messages)

Pipeline:
  1. Read browser history + recent chat conversations
  2. Filter noise
  3. **LLM interest analysis** — extract interests, classify (work/study/life),
     and generate high-quality search queries in one step.
     Falls back to rule-based extraction + classification when LLM unavailable.
  4. **Web search** (Brave → Bing → DuckDuckGo auto-fallback) using
     LLM-generated (or rule-built) queries
  5. **LLM report generation** — curate a personalised daily reading from
     real search results with explanations and action items
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
                os.unlink(tmp_name)
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


def _build_chat_block(sessions: list[dict], limit: int = 60) -> str:
    """Build a concise conversation summary block for the LLM prompt."""
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
            if not content or role not in ("user", "assistant"):
                continue
            # Truncate long messages
            preview = content[:200].replace("\n", " ")
            if len(content) > 200:
                preview += "…"
            prefix = "👤 用户" if role == "user" else "🤖 助手"
            lines.append(f"- {prefix}: {preview}")

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
    return resp.choices[0].message.content or ""


# ===================================================================
# Step 3+4 ALT — LLM-based interest analysis (replaces rule-based)
# ===================================================================

_INTEREST_ANALYSIS_PROMPT = """\
你是一个个人兴趣分析专家。下面是用户最近的两个数据来源：
1. 浏览器历史摘要（页面标题 + 域名）
2. 与 AI 助手的对话记录（用户提问和讨论的主题）

请你综合这两个来源：
1. 推断出用户真正的**兴趣主题**（忽略工具/平台本身的名字，比如 github、chatgpt、bing 等不是兴趣）
2. 将兴趣归入适用的类别：work（工作/职业相关）、study（学习/研究相关）、life（生活/娱乐相关）
3. 为每个**有内容的**类别生成 2-4 个高质量搜索词

关键规则：
- **综合分析两个来源**。对话中讨论的主题往往比浏览历史更能反映深层兴趣和当前关注
- **只输出确实有兴趣的类别**。如果数据中完全没有某类内容，该类别留空数组即可，不要凑数
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


def _build_history_block(records: list[dict], limit: int = 80) -> str:
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
    prompt = _INTEREST_ANALYSIS_PROMPT.format(
        history_block=history_block,
        chat_block=chat_block,
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
# Step 5 — Web search  (the crucial new step)
# ===================================================================

# -- 5a. Brave Search API -------------------------------------------------

def _brave_search(query: str, api_key: str, count: int = 8) -> list[dict]:
    """Call Brave Web Search API."""
    params = urllib.parse.urlencode({
        "q": query, "count": count, "freshness": "pw",
    })
    url = f"https://api.search.brave.com/res/v1/web/search?{params}"
    req = urllib.request.Request(url, headers={
        "X-Subscription-Token": api_key,
        "Accept": "application/json",
        "Accept-Encoding": "identity",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "description": re.sub(r"<[^>]+>", "", r.get("description", "")),
            "age": r.get("age", ""),
        }
        for r in data.get("web", {}).get("results", [])
    ]


def _bing_search(query: str, count: int = 8) -> list[dict]:
    """Free fallback search via Bing HTML (cn.bing.com, works in China)."""
    params = urllib.parse.urlencode({"q": query, "count": str(count)})
    url = f"https://cn.bing.com/search?{params}"
    req = urllib.request.Request(url, headers={
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    # Split by result blocks — Bing uses <li class="b_algo" data-id ...>
    parts = re.split(r'<li\s+class="b_algo"[^>]*>', html)
    results: list[dict] = []
    for part in parts[1:]:                       # skip content before first result
        if len(results) >= count:
            break
        end = part.find("</li>")
        block = part[:end] if end > 0 else part[:2000]
        # Title link inside <h2>
        link_m = re.search(
            r'<h2[^>]*>.*?<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>',
            block, re.DOTALL,
        )
        if not link_m:
            continue
        href = link_m.group(1)
        title = _html.unescape(re.sub(r"<[^>]+>", "", link_m.group(2))).strip()
        if not title:
            continue
        desc_m = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
        desc = ""
        if desc_m:
            desc = _html.unescape(re.sub(r"<[^>]+>", "", desc_m.group(1))).strip()
        results.append({
            "title": title,
            "url": href,
            "description": desc[:300],
            "age": "",
        })
    return results


def _ddg_search(query: str, count: int = 8) -> list[dict]:
    """Free fallback search via DuckDuckGo HTML (may not work in China)."""
    form_data = urllib.parse.urlencode({"q": query, "b": ""}).encode()
    req = urllib.request.Request(
        "https://html.duckduckgo.com/html/",
        data=form_data,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    links = re.findall(
        r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
        html, re.DOTALL,
    )
    snippets = re.findall(
        r'class="result__snippet"[^>]*>(.*?)</a>',
        html, re.DOTALL,
    )

    results: list[dict] = []
    for i, (raw_href, raw_title) in enumerate(links):
        if len(results) >= count:
            break
        uddg = re.search(r'uddg=([^&]+)', raw_href)
        actual_url = urllib.parse.unquote(uddg.group(1)) if uddg else raw_href
        if not actual_url or actual_url.startswith("//"):
            continue
        title = re.sub(r"<[^>]+>", "", raw_title).strip()
        desc = re.sub(r"<[^>]+>", "", snippets[i]).strip() if i < len(snippets) else ""
        if not title:
            continue
        results.append({
            "title": title,
            "url": actual_url,
            "description": desc[:300],
            "age": "",
        })
    return results


# Ordered list of (name, function) — tried top to bottom after Brave
_FREE_ENGINES: list[tuple[str, callable]] = [
    ("Bing", _bing_search),
    ("DuckDuckGo", _ddg_search),
]


def _web_search(query: str, brave_api_key: str | None = None,
                count: int = 8,
                _session_state: dict | None = None) -> list[dict]:
    """Unified search with automatic fallback: Brave → Bing → DuckDuckGo.

    *_session_state* is a mutable dict shared across calls within one search
    session.  After a Brave timeout/error the key ``"skip_brave"`` is set so
    subsequent queries in the same batch skip the 30-second timeout.

    Always returns a list (possibly empty), never raises.
    """
    import time as _time
    if _session_state is None:
        _session_state = {}

    if brave_api_key and not _session_state.get("skip_brave"):
        try:
            results = _brave_search(query, brave_api_key, count)
            if results:
                return results
        except Exception as exc:
            print(f"[daily_digest] brave failed — disabling for this session: {exc}")
            _session_state["skip_brave"] = True

    for engine_name, engine_fn in _FREE_ENGINES:
        try:
            results = engine_fn(query, count)
            if results:
                return results
        except Exception as exc:
            print(f"[daily_digest] {engine_name} failed: {exc}")
            _time.sleep(0.5)

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

def _fmt_results(results: list[dict], limit: int = 15) -> str:
    """Format search results into a readable block for the LLM prompt."""
    if not results:
        return "(无搜索结果)"
    lines = []
    for i, r in enumerate(results[:limit], 1):
        lines.append(
            f"{i}. [{r['title']}]({r['url']})\n"
            f"   关联兴趣: {r.get('query_keyword', '?')}\n"
            f"   摘要: {r['description'][:200]}"
        )
    return "\n".join(lines)


_CAT_META = {
    "work":  {"emoji": "🧠", "zh": "工作推荐"},
    "study": {"emoji": "📚", "zh": "学习推荐"},
    "life":  {"emoji": "🌿", "zh": "生活推荐"},
}

# ── HTML card template shown to LLM as output example ──
_HTML_CARD_EXAMPLE = """\
<div class="dr-card">
  <h3><a href="真实URL" target="_blank">标题</a></h3>
  <span class="dr-tag">关联兴趣关键词</span>
  <p class="dr-desc">一句话说明亮点或核心内容</p>
  <p class="dr-action">💡 建议行动或推荐理由</p>
</div>"""


def build_report_prompt(categories: dict[str, list],
                        search_results: dict[str, list[dict]],
                        date_str: str) -> str:
    def _top_kw(cat, n=8):
        return ", ".join(i["keyword"] for i in categories.get(cat, [])[:n])

    profile_lines = []
    for cat in ("work", "study", "life"):
        kws = _top_kw(cat)
        if kws:
            profile_lines.append(f"- {_CAT_META[cat]['zh']}：{kws}")
    interest_block = "\n".join(profile_lines) if profile_lines else "- (未检测到明确兴趣)"

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

    # Per-category section headers the LLM should output
    cat_section_hints = []
    for cat in active_cats:
        meta = _CAT_META[cat]
        cat_section_hints.append(
            f'<section class="dr-section">\n'
            f'  <h2>{meta["emoji"]} {meta["zh"]}</h2>\n'
            f'  <!-- 从该类搜索结果中精选 3-5 条卡片 -->\n'
            f'</section>'
        )
    sections_hint = "\n".join(cat_section_hints)

    return f"""你是一个高质量个人阅读策展人。根据用户浏览兴趣、AI 对话主题和全网搜索结果，精选最有价值的推荐。

今日日期：{date_str}

═══ 用户今日兴趣画像 ═══
{interest_block}

═══ 全网搜索结果（真实链接，请从中精选） ═══

{results_block}

═══ 输出要求 ═══

请输出一段**纯 HTML**（不要 Markdown、不要 ```html 包裹），直接以 <h1> 开头。

重要规则：
1. **必须使用搜索结果中的真实 URL**，禁止编造链接
2. 所有 <a> 标签加 target="_blank"
3. 每个类别精选 3-5 条内容，用卡片展示
4. **只输出有搜索结果的类别**
5. 用中文输出

HTML 结构要求（严格使用以下 CSS class）：

<h1>📅 {date_str} 今日私读</h1>

{sections_hint}

每条推荐用卡片格式：
{_HTML_CARD_EXAMPLE}

最后加上：
<section class="dr-section dr-focus">
  <h2>🔥 今日重点关注</h2>
  <p>1-2 个最强兴趣主题的趋势洞察</p>
</section>
<section class="dr-section dr-actions">
  <h2>🎯 今日建议行动</h2>
  <ul><li>具体可执行行动 1</li><li>行动 2</li></ul>
</section>

现在请直接输出 HTML："""


# ===================================================================
# Step 7 — Call LLM
# ===================================================================

def generate_report_llm(prompt: str, model: str, api_key: str,
                        api_base: str | None = None) -> str:
    return _llm_call(
        messages=[{"role": "user", "content": prompt}],
        model=model,
        api_key=api_key,
        api_base=api_base,
        temperature=0.7,
        max_tokens=4096,
    )


def _esc(text: str) -> str:
    """Minimal HTML-escape for user-supplied text."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def generate_report_fallback(categories: dict[str, list],
                             search_results: dict[str, list[dict]],
                             date_str: str) -> str:
    """HTML report when LLM is unavailable — still uses real search links."""
    parts: list[str] = [f'<h1>📅 {date_str} 今日私读</h1>']

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
                search_stats: dict | None = None) -> dict:
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "date": date_str,
        "content": content,
        "interests": interests,
        "search_stats": search_stats,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
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
        progress_cb("正在生成今日私读…")

    if has_llm:
        try:
            prompt = build_report_prompt(categories, search_results, date_str)
            report_text = generate_report_llm(prompt, model, api_key, api_base)
        except Exception as exc:
            print(f"[daily_digest] LLM report error, falling back: {exc}")
            report_text = generate_report_fallback(
                categories, search_results, date_str,
            )
    else:
        report_text = generate_report_fallback(
            categories, search_results, date_str,
        )

    # ── 7. Save ─────────────────────────────────────────────────────
    report_data = save_report(
        report_text, date_str, interests_summary, search_stats,
    )

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
