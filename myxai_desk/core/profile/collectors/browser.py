"""Browser history collector — privacy-first metadata extraction.

By default (security mode 1-2), only metadata is stored: domain,
title_keywords (locally extracted), timestamp_bucket, dwell_time_bucket,
and category_tag.  Higher security modes can unlock title / full URL
retention.
"""

from __future__ import annotations

import os
import re
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from myxai_desk.core.profile.events import BrowserVisited, EventStore

# ── Browser history paths (Windows) ───────────────────────────────

_LOCAL = os.environ.get("LOCALAPPDATA", "")

CHROME_HISTORY_PATHS = [
    Path(_LOCAL) / "Google" / "Chrome" / "User Data" / "Default" / "History",
    Path(_LOCAL) / "Google" / "Chrome" / "User Data" / "Profile 1" / "History",
]
EDGE_HISTORY_PATHS = [
    Path(_LOCAL) / "Microsoft" / "Edge" / "User Data" / "Default" / "History",
    Path(_LOCAL) / "Microsoft" / "Edge" / "User Data" / "Profile 1" / "History",
]

# ── Noise filters ─────────────────────────────────────────────────

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

# ── Domain → category mapping ────────────────────────────────────

_CATEGORY_MAP: dict[str, str] = {}
for _d in ("github.com", "gitlab.com", "bitbucket.org", "stackoverflow.com",
           "dev.to", "hashnode.dev", "npmjs.com", "pypi.org"):
    _CATEGORY_MAP[_d] = "开发"
for _d in ("arxiv.org", "scholar.google.com", "paperswithcode.com"):
    _CATEGORY_MAP[_d] = "研究"
for _d in ("docs.python.org", "docs.microsoft.com", "learn.microsoft.com",
           "developer.mozilla.org"):
    _CATEGORY_MAP[_d] = "文档"
for _d in ("news.ycombinator.com", "techcrunch.com", "36kr.com"):
    _CATEGORY_MAP[_d] = "新闻"
for _d in ("zhihu.com", "juejin.cn", "csdn.net", "cnblogs.com", "medium.com",
           "towardsdatascience.com"):
    _CATEGORY_MAP[_d] = "社区"
for _d in ("youtube.com", "bilibili.com"):
    _CATEGORY_MAP[_d] = "视频"

_AI_KEYWORDS = {"ai", "llm", "gpt", "agent", "transformer", "openai",
                "langchain", "大模型", "人工智能", "机器学习"}

# ── Stopwords for keyword extraction ─────────────────────────────

_STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "can",
    "was", "one", "has", "from", "with", "this", "that", "have",
    "will", "your", "what", "when", "make", "like", "just",
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都",
    "一", "上", "也", "很", "到", "说", "要", "去", "你", "会",
    "home", "page", "index", "null", "undefined", "error",
    "com", "org", "net", "http", "https", "www",
}


def _chrome_ts_to_dt(chrome_ts: int) -> datetime:
    epoch_start = datetime(1601, 1, 1, tzinfo=timezone.utc)
    return epoch_start + timedelta(microseconds=chrome_ts)


def _is_blocked(url: str, domain: str) -> bool:
    if any(frag in domain for frag in BLOCKED_DOMAIN_FRAGMENTS):
        return True
    return any(pat.search(url) for pat in BLOCKED_URL_PATTERNS)


def _extract_keywords(title: str) -> list[str]:
    words = re.findall(r'[\w\u4e00-\u9fff]{2,}', title.lower())
    return [w for w in words if w not in _STOPWORDS][:8]


def _timestamp_bucket(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d_%H")


def _dwell_bucket(visit_count: int) -> str:
    if visit_count >= 10:
        return "heavy"
    if visit_count >= 4:
        return "moderate"
    return "light"


def _categorise(domain: str, title: str) -> str:
    for pattern, cat in _CATEGORY_MAP.items():
        if pattern in domain:
            return cat
    lower_title = title.lower()
    if any(kw in lower_title for kw in _AI_KEYWORDS):
        return "AI"
    return "其他"


# ── Core reader ───────────────────────────────────────────────────

def read_browser_history(hours: int = 24, browser: str = "auto") -> list[dict]:
    """Read Chrome/Edge history from the last *hours*."""
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
                domain = parsed.netloc.lower()
                if _is_blocked(url, domain):
                    continue
                if len(title.strip()) < 3:
                    continue
                dt = (_chrome_ts_to_dt(last_visit_time)
                      if last_visit_time
                      else datetime.now(timezone.utc))
                records.append({
                    "url": url,
                    "title": title.strip(),
                    "domain": domain,
                    "visit_count": visit_count or 1,
                    "ts": dt.isoformat(),
                    "dt": dt,
                })
            conn.close()
        except Exception as exc:
            print(f"[browser_collector] read error ({hist_path}): {exc}")
        finally:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass

    return records


def collect_to_events(
    hours: int = 24,
    browser: str = "auto",
    store: EventStore | None = None,
    *,
    security_mode: int = 1,
) -> int:
    """Read browser history and record as privacy-first profile events.

    *security_mode* controls data granularity:
      1 — metadata only (default)
      2 — also retain page title
      4 — also retain full URL
    """
    store = store or EventStore()
    records = read_browser_history(hours=hours, browser=browser)
    for r in records:
        dt = r.get("dt", datetime.now(timezone.utc))
        event = BrowserVisited(
            domain=r["domain"],
            title_keywords=_extract_keywords(r["title"]),
            timestamp_bucket=_timestamp_bucket(dt),
            dwell_time_bucket=_dwell_bucket(r.get("visit_count", 1)),
            category_tag=_categorise(r["domain"], r["title"]),
            ts=r["ts"],
            visit_count=r.get("visit_count", 1),
            title=r["title"] if security_mode >= 2 else "",
            url=r["url"] if security_mode >= 4 else "",
        )
        store.record(event)
    return len(records)
