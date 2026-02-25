"""Runtime budget enforcement for Prompt App execution.

Tracks per-app daily token and search-call usage, and blocks execution
when the declared ``budgets.tokens_per_day`` or ``search_calls_per_day``
limits are exceeded.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from myxai_desk.core.storage.paths import USAGE_DIR, ensure_dir


_BUDGET_FILE = USAGE_DIR / "app_budgets.json"
_lock = Lock()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _load() -> dict:
    ensure_dir(USAGE_DIR)
    if _BUDGET_FILE.exists():
        try:
            return json.loads(_BUDGET_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save(data: dict) -> None:
    ensure_dir(USAGE_DIR)
    _BUDGET_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8",
    )


def get_app_usage(app_id: str) -> dict:
    """Return today's usage for *app_id*."""
    data = _load()
    today = _today()
    day_data = data.get(app_id, {}).get(today, {})
    return {
        "date": today,
        "tokens_used": day_data.get("tokens", 0),
        "search_calls_used": day_data.get("search_calls", 0),
    }


def check_budget(app_id: str, tokens_limit: int = 0,
                 search_limit: int = 0) -> tuple[bool, str]:
    """Check if *app_id* is within budget.

    Returns ``(ok, reason)``.  If ``ok`` is False, ``reason`` explains why.
    """
    usage = get_app_usage(app_id)
    if tokens_limit > 0 and usage["tokens_used"] >= tokens_limit:
        return False, f"Token budget exhausted: {usage['tokens_used']}/{tokens_limit}"
    if search_limit > 0 and usage["search_calls_used"] >= search_limit:
        return False, f"Search budget exhausted: {usage['search_calls_used']}/{search_limit}"
    return True, ""


def record_tokens(app_id: str, tokens: int) -> None:
    """Record *tokens* consumed by *app_id* today."""
    with _lock:
        data = _load()
        today = _today()
        data.setdefault(app_id, {})
        day = data[app_id].setdefault(today, {"tokens": 0, "search_calls": 0})
        day["tokens"] = day.get("tokens", 0) + tokens
        _save(data)


def record_search_call(app_id: str) -> None:
    """Record one search call for *app_id* today."""
    with _lock:
        data = _load()
        today = _today()
        data.setdefault(app_id, {})
        day = data[app_id].setdefault(today, {"tokens": 0, "search_calls": 0})
        day["search_calls"] = day.get("search_calls", 0) + 1
        _save(data)
