"""Enhanced WebSearchTool — API-only search via Brave and Baidu.

Only uses official search APIs (Brave Search API / Baidu qianfan web_search).
Which API is used depends on which API key is configured; both can coexist
and will cascade (Baidu → Brave by default).

Includes per-engine daily quota tracking with optional hard limit.

Legacy HTML-scraping helpers (_so_search etc.) are retained for
daily_digest's direct import but are NOT used by the agent tool.
"""

import html as _html
import json
import re
import threading
import time
from datetime import date
from pathlib import Path
from typing import Any

import httpx
from nanobot.agent.tools.base import Tool

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

_SKIP_COOLDOWN = 300
_skip_engines: dict[str, float] = {}


def _should_skip(engine: str) -> bool:
    ts = _skip_engines.get(engine)
    if ts is None:
        return False
    if time.time() - ts > _SKIP_COOLDOWN:
        del _skip_engines[engine]
        return False
    return True


def _mark_skip(engine: str) -> None:
    _skip_engines[engine] = time.time()


def _strip_tags(html_str: str) -> str:
    return re.sub(r"<[^>]+>", "", html_str)


# ── Quota tracking ─────────────────────────────────────────────────

_DEFAULT_DAILY_LIMITS = {
    "baidu": 100,
    "brave": 1000,
}


_USAGE_DIR = Path.home() / ".nanobot" / "usage"
_SEARCH_FILE = _USAGE_DIR / "search_usage.json"
_SEARCH_HISTORY_FILE = _USAGE_DIR / "search_history.json"


class QuotaManager:
    """Thread-safe daily API call counter with optional hard limit.
    Persists counts to disk so data survives app restarts."""

    def __init__(self):
        self._lock = threading.Lock()
        self._date: str = ""
        self._counts: dict[str, int] = {}
        self._limits: dict[str, int] = self._load_limits_from_config()
        self._quota_only: bool = True
        self._loaded = False
        self._history: dict[str, int] = {}

    def _load_limits_from_config(self) -> dict[str, int]:
        """Load quota limits from config file or use defaults."""
        try:
            from myxai_desk.core.search_quota_service import get_search_quota_config
            config = get_search_quota_config()
            return {
                "brave": config.get("brave", 1000),
                "baidu": config.get("baidu", 100),
            }
        except Exception:
            return dict(_DEFAULT_DAILY_LIMITS)

    def _ensure_loaded(self):
        if self._loaded:
            return
        _USAGE_DIR.mkdir(parents=True, exist_ok=True)
        if _SEARCH_FILE.exists():
            try:
                data = json.loads(_SEARCH_FILE.read_text(encoding="utf-8"))
                self._date = data.get("date", "")
                self._counts = data.get("counts", {})
            except Exception:
                pass
        if _SEARCH_HISTORY_FILE.exists():
            try:
                self._history = json.loads(_SEARCH_HISTORY_FILE.read_text(encoding="utf-8"))
            except Exception:
                self._history = {}
        self._loaded = True

    def _persist(self):
        try:
            _USAGE_DIR.mkdir(parents=True, exist_ok=True)
            _SEARCH_FILE.write_text(
                json.dumps(
                    {
                        "date": self._date,
                        "counts": self._counts,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _persist_history(self):
        try:
            _USAGE_DIR.mkdir(parents=True, exist_ok=True)
            _SEARCH_HISTORY_FILE.write_text(
                json.dumps(self._history, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def _reset_if_new_day(self):
        self._ensure_loaded()
        today = date.today().isoformat()
        if today != self._date:
            if self._date and sum(self._counts.values()) > 0:
                self._history[self._date] = sum(self._counts.values())
                self._persist_history()
            self._date = today
            self._counts = {}
            self._persist()

    def set_limits(self, limits: dict[str, int]):
        with self._lock:
            self._limits.update(limits)

    def set_quota_only(self, enabled: bool):
        with self._lock:
            self._quota_only = enabled

    @property
    def quota_only(self) -> bool:
        with self._lock:
            return self._quota_only

    def can_use(self, engine: str) -> bool:
        with self._lock:
            self._reset_if_new_day()
            if not self._quota_only:
                return True
            limit = self._limits.get(engine, 1000)
            return self._counts.get(engine, 0) < limit

    def record(self, engine: str):
        with self._lock:
            self._reset_if_new_day()
            self._counts[engine] = self._counts.get(engine, 0) + 1
            self._persist()

    def get_usage(self) -> dict:
        with self._lock:
            self._reset_if_new_day()
            return {
                "date": self._date,
                "quota_only": self._quota_only,
                "engines": {
                    eng: {
                        "used": self._counts.get(eng, 0),
                        "limit": self._limits.get(eng, 1000),
                    }
                    for eng in self._limits
                },
            }

    def get_history(self, days: int = 30) -> list[dict]:
        from datetime import timedelta

        with self._lock:
            self._reset_if_new_day()
            today_total = sum(self._counts.values())
            result = []
            td = date.today()
            for i in range(days):
                d = (td - timedelta(days=days - 1 - i)).isoformat()
                if d == self._date:
                    result.append({"date": d, "calls": today_total})
                else:
                    result.append({"date": d, "calls": self._history.get(d, 0)})
            return result


quota = QuotaManager()


# ── API-based engines ──────────────────────────────────────────────


def _brave_search(query: str, api_key: str, count: int = 8) -> list[dict]:
    """Brave Search API."""
    resp = httpx.get(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": query, "count": count, "freshness": "pw"},
        headers={
            "X-Subscription-Token": api_key,
            "Accept": "application/json",
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    results = [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "description": _strip_tags(r.get("description", "")),
        }
        for r in data.get("web", {}).get("results", [])
    ]
    if results:
        print(f"[web_search] brave returned {len(results)} results")
    return results


def _baidu_api_search(query: str, api_key: str, count: int = 8) -> list[dict]:
    """Baidu qianfan web_search API.

    Docs: https://cloud.baidu.com/doc/qianfan-api/s/Wmbq4z7e5
    Free: 100 calls/day, up to 100k/day with pay-as-you-go.
    """
    top_k = min(count, 50)
    payload = {
        "messages": [{"role": "user", "content": query[:72]}],
        "search_source": "baidu_search_v2",
        "resource_type_filter": [{"type": "web", "top_k": top_k}],
        "search_recency_filter": "month",
    }
    resp = httpx.post(
        "https://qianfan.baidubce.com/v2/ai_search/web_search",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()

    if "code" in data and data["code"]:
        raise RuntimeError(f"Baidu API error {data['code']}: {data.get('message', '')}")

    results: list[dict] = []
    for ref in data.get("references", []):
        title = ref.get("title", "").strip()
        url = ref.get("url", "").strip()
        desc = ref.get("snippet", "") or ref.get("content", "")
        if title and url:
            results.append(
                {
                    "title": title,
                    "url": url,
                    "description": _strip_tags(desc)[:400],
                }
            )
    if results:
        print(f"[web_search] baidu_api returned {len(results)} results")
    return results


# ── Multi-engine orchestrator (API-only) ───────────────────────────


def multi_engine_search(
    query: str,
    brave_api_key: str | None = None,
    baidu_api_key: str | None = None,
    count: int = 8,
    preferred_engine: str | None = None,
) -> tuple[list[dict], str]:
    """Search using available API keys. Returns (results, engine_used).

    Respects daily quota limits managed by the global `quota` manager.
    Priority: baidu_api → brave (both tried if keys exist).
    """
    engines: list[tuple[str, Any]] = []

    def _add(name: str, force: bool = False):
        if any(e[0] == name for e in engines):
            return
        if not force and _should_skip(name):
            return
        if not quota.can_use(name):
            usage = quota.get_usage()
            eng_info = usage["engines"].get(name, {})
            print(
                f"[web_search] {name} daily quota exhausted "
                f"({eng_info.get('used', '?')}/{eng_info.get('limit', '?')})"
            )
            return
        if name == "brave" and brave_api_key:
            engines.append(("brave", lambda q, n: _brave_search(q, brave_api_key, n)))
        elif name == "baidu" and baidu_api_key:
            engines.append(("baidu", lambda q, n: _baidu_api_search(q, baidu_api_key, n)))

    if preferred_engine in ("brave", "baidu"):
        _add(preferred_engine, force=True)

    _add("baidu")
    _add("brave")

    if not engines:
        if quota.quota_only:
            usage = quota.get_usage()
            parts = []
            for eng, info in usage["engines"].items():
                if info["used"] >= info["limit"]:
                    parts.append(f"{eng}: {info['used']}/{info['limit']}")
            if parts:
                return [], f"quota_exhausted:{','.join(parts)}"
        return [], "none"

    for engine_name, search_fn in engines:
        try:
            results = search_fn(query, count)
            quota.record(engine_name)
            if results:
                return results, engine_name
            print(f"[web_search] {engine_name} returned 0 results for '{query[:80]}'")
        except Exception as exc:
            print(f"[web_search] {engine_name} error for '{query[:80]}': {exc}")
            _mark_skip(engine_name)

    return [], "none"


# ── Legacy HTML-scrape helpers (used by daily_digest only) ─────────


def _so_search(query: str, count: int = 8) -> list[dict]:
    """360 Search (so.com) HTML scrape — reliable for Chinese queries."""
    resp = httpx.get(
        "https://www.so.com/s",
        params={"q": query, "pn": "1"},
        headers={"User-Agent": _UA, "Accept-Language": "zh-CN,zh;q=0.9"},
        timeout=15,
        follow_redirects=True,
    )
    resp.raise_for_status()
    raw = resp.text
    results: list[dict] = []

    blocks = re.split(r'<li\s+class="res-list"', raw)
    for block in blocks[1:]:
        if len(results) >= count:
            break
        end = block.find("</li>")
        chunk = block[:end] if end > 0 else block[:3000]

        link_m = re.search(r"<a\s([^>]+)>([\s\S]*?)</a>", chunk)
        if not link_m:
            continue

        attrs = link_m.group(1)
        mdurl_m = re.search(r'data-mdurl="([^"]+)"', attrs)
        href_m = re.search(r'href="([^"]+)"', attrs)
        href = (mdurl_m.group(1) if mdurl_m else "") or (href_m.group(1) if href_m else "")
        if not href.startswith("http"):
            continue

        title = _html.unescape(_strip_tags(link_m.group(2))).strip()
        if not title:
            continue

        desc = ""
        desc_m = re.search(r'<p[^>]*class="[^"]*res-desc[^"]*"[^>]*>([\s\S]*?)</p>', chunk)
        if desc_m:
            desc = _html.unescape(_strip_tags(desc_m.group(1))).strip()

        results.append({"title": title, "url": href, "description": desc[:400]})

    if results:
        print(f"[web_search] so.com returned {len(results)} results")
    else:
        print("[web_search] so.com parsed 0 results")
    return results


def legacy_html_search(
    query: str,
    brave_api_key: str | None = None,
    count: int = 8,
) -> tuple[list[dict], str]:
    """HTML-scrape fallback chain for daily_digest: 360 → Brave API."""
    if brave_api_key:
        try:
            results = _brave_search(query, brave_api_key, count)
            if results:
                return results, "brave"
        except Exception as exc:
            print(f"[web_search] brave error: {exc}")

    try:
        results = _so_search(query, count)
        if results:
            return results, "so"
    except Exception as exc:
        print(f"[web_search] so.com error: {exc}")

    return [], "none"


# ── Enhanced WebSearchTool ─────────────────────────────────────────


class EnhancedWebSearchTool(Tool):
    """Web search via Brave Search API and/or Baidu qianfan API.

    Which API is used depends on which keys are provided.
    Respects daily quota managed by the global QuotaManager.
    """

    name = "web_search"
    description = (
        "Search the web for information. Returns titles, URLs, "
        "and brief descriptions. "
        "For detailed page content, use web_fetch on specific result URLs."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "count": {
                "type": "integer",
                "description": "Number of results (1-10)",
                "minimum": 1,
                "maximum": 10,
            },
        },
        "required": ["query"],
    }

    def __init__(
        self,
        brave_api_key: str | None = None,
        baidu_api_key: str | None = None,
        max_results: int = 5,
    ):
        self.brave_api_key = brave_api_key
        self.baidu_api_key = baidu_api_key
        self.max_results = max_results

    async def execute(self, query: str, count: int | None = None, **kw: Any) -> str:
        n = min(max(count or self.max_results, 1), 10)
        results, used_engine = multi_engine_search(
            query,
            brave_api_key=self.brave_api_key,
            baidu_api_key=self.baidu_api_key,
            count=n,
        )

        if not results:
            if used_engine.startswith("quota_exhausted"):
                return (
                    "搜索 API 今日免费额度已用完，无法执行搜索。"
                    "请稍后再试或在设置中关闭「仅使用免费额度」。\n"
                    f"Detail: {used_engine}"
                )
            return f"No results found for: {query}"

        lines = [f"Search results for: {query}  (engine: {used_engine})\n"]
        for i, item in enumerate(results[:n], 1):
            title = item.get("title", "")
            url = item.get("url", "")
            desc = item.get("description", "")
            lines.append(f"{i}. {title}\n   {url}")
            if desc:
                lines.append(f"   {desc}")
        return "\n".join(lines)
