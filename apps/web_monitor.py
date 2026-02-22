"""Web Monitor App — track changes on web pages.

Supports two detection modes:
  - hash: compare SHA-256 of extracted text (fast, no LLM cost)
  - llm:  use LLM to summarise what changed (smarter, costs tokens)
"""

import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

_APP_DIR = Path.home() / ".nanobot" / "apps" / "web_monitor"
_SITES_FILE = _APP_DIR / "sites.json"
_SNAPSHOTS_DIR = _APP_DIR / "snapshots"
_HISTORY_DIR = _APP_DIR / "history"

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


# ── Persistence helpers ─────────────────────────────────────────────

def _ensure_dirs():
    _APP_DIR.mkdir(parents=True, exist_ok=True)
    _SNAPSHOTS_DIR.mkdir(exist_ok=True)
    _HISTORY_DIR.mkdir(exist_ok=True)


def _load_sites() -> list[dict]:
    if _SITES_FILE.exists():
        try:
            return json.loads(_SITES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_sites(sites: list[dict]):
    _ensure_dirs()
    _SITES_FILE.write_text(
        json.dumps(sites, ensure_ascii=False, indent=2), encoding="utf-8",
    )


def _load_snapshot(site_id: str) -> dict | None:
    fp = _SNAPSHOTS_DIR / f"{site_id}.json"
    if fp.exists():
        try:
            return json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def _save_snapshot(site_id: str, text_hash: str, text: str):
    _ensure_dirs()
    (_SNAPSHOTS_DIR / f"{site_id}.json").write_text(
        json.dumps({
            "hash": text_hash,
            "text": text[:50000],
            "saved_at": datetime.now().astimezone().isoformat(),
        }, ensure_ascii=False),
        encoding="utf-8",
    )


def _append_history(site_id: str, entry: dict):
    _ensure_dirs()
    fp = _HISTORY_DIR / f"{site_id}.json"
    history = []
    if fp.exists():
        try:
            history = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            pass
    history.insert(0, entry)
    history = history[:100]
    fp.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Page fetching ───────────────────────────────────────────────────

def _fetch_page(url: str, timeout: int = 20) -> str:
    """Fetch URL and return extracted body text (tags stripped)."""
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    body_m = re.search(r"<body[^>]*>(.*)</body>", html, re.DOTALL | re.IGNORECASE)
    text = body_m.group(1) if body_m else html
    # Strip script/style
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Strip tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ── Site management ─────────────────────────────────────────────────

def add_site(url: str, name: str = "", mode: str = "hash") -> dict:
    """Add a new site to monitor. Returns the new site entry."""
    sites = _load_sites()
    site_id = uuid.uuid4().hex[:12]
    if not name:
        name = urllib.parse.urlparse(url).netloc or url[:40]
    entry = {
        "id": site_id,
        "url": url,
        "name": name,
        "mode": mode if mode in ("hash", "llm") else "hash",
        "enabled": True,
        "added_at": datetime.now().astimezone().isoformat(),
        "last_checked": None,
        "last_changed": None,
        "status": "pending",
    }
    sites.append(entry)
    _save_sites(sites)
    return entry


def remove_site(site_id: str) -> bool:
    sites = _load_sites()
    before = len(sites)
    sites = [s for s in sites if s["id"] != site_id]
    if len(sites) == before:
        return False
    _save_sites(sites)
    # Clean up snapshot and history
    snap = _SNAPSHOTS_DIR / f"{site_id}.json"
    if snap.exists():
        snap.unlink()
    hist = _HISTORY_DIR / f"{site_id}.json"
    if hist.exists():
        hist.unlink()
    return True


def list_sites() -> list[dict]:
    return _load_sites()


def get_history(site_id: str, limit: int = 30) -> list[dict]:
    fp = _HISTORY_DIR / f"{site_id}.json"
    if not fp.exists():
        return []
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
        return data[:limit]
    except Exception:
        return []


# ── Change detection ────────────────────────────────────────────────

def check_site(
    site_id: str,
    model: str | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
) -> dict:
    """Check a single site for changes. Returns a status dict."""
    sites = _load_sites()
    site = next((s for s in sites if s["id"] == site_id), None)
    if not site:
        return {"error": "站点不存在"}

    url = site["url"]
    mode = site.get("mode", "hash")
    now_iso = datetime.now().astimezone().isoformat()

    try:
        text = _fetch_page(url)
    except Exception as exc:
        site["status"] = "error"
        site["last_checked"] = now_iso
        _save_sites(sites)
        return {"error": f"抓取失败: {exc}", "site_id": site_id}

    new_hash = hashlib.sha256(text.encode()).hexdigest()
    prev = _load_snapshot(site_id)

    changed = False
    summary = ""

    if prev is None:
        # First check — just save baseline
        summary = "首次抓取，已保存基准快照"
    elif prev["hash"] != new_hash:
        changed = True
        if mode == "llm" and model and api_key:
            try:
                from apps.llm_utils import llm_call
                old_text = prev.get("text", "")[:3000]
                new_text = text[:3000]
                prompt = (
                    "以下是一个网页的前后两个版本的文本内容。"
                    "请简要总结发生了哪些变化（用中文，100字以内）。\n\n"
                    f"【旧版本】\n{old_text}\n\n"
                    f"【新版本】\n{new_text}"
                )
                summary = llm_call(
                    messages=[{"role": "user", "content": prompt}],
                    model=model, api_key=api_key, api_base=api_base,
                    temperature=0.3, max_tokens=256,
                )
            except Exception as exc:
                summary = f"内容已变化（LLM 分析失败: {exc}）"
        else:
            summary = "内容已变化"
    else:
        summary = "无变化"

    # Update snapshot
    _save_snapshot(site_id, new_hash, text)

    # Update site status
    site["last_checked"] = now_iso
    site["status"] = "changed" if changed else "ok"
    if changed:
        site["last_changed"] = now_iso
    _save_sites(sites)

    # Record history if changed or first check
    if changed or prev is None:
        _append_history(site_id, {
            "timestamp": now_iso,
            "changed": changed,
            "summary": summary,
            "hash": new_hash[:16],
        })

    return {
        "site_id": site_id,
        "changed": changed,
        "summary": summary,
    }


def check_all_sites(
    model: str | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
    progress_cb=None,
) -> list[dict]:
    """Check all enabled sites. Returns list of results."""
    sites = _load_sites()
    enabled = [s for s in sites if s.get("enabled", True)]
    results = []
    for i, s in enumerate(enabled):
        if progress_cb:
            progress_cb(f"检查中 ({i+1}/{len(enabled)}): {s['name'][:30]}…")
        print(f"[web_monitor] checking {s['name']} ({s['url'][:60]})")
        r = check_site(s["id"], model=model, api_key=api_key, api_base=api_base)
        results.append(r)
        time.sleep(0.5)
    return results
