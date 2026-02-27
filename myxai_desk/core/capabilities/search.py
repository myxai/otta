"""Search capability — quota management + governance wrapper.

Architecture note
-----------------
In the normal Agent loop, search is performed by **nanobot's built-in
search tools or MCP tools**.  ``governance.py`` logs audit entries.

This module provides:
  - ``QuotaManager``: always active — tracks daily per-engine usage limits
    regardless of whether nanobot or the standalone path performs the search.
  - ``SearchCapability``: standalone fallback for Prompt App runtime.

``QuotaManager`` is also called from the **Policy Engine** rule
``rules/net.py`` to enforce budget limits before nanobot even executes.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from myxai_desk.core.storage.paths import USAGE_DIR, ensure_dir


class QuotaManager:
    """Per-engine daily usage / limit tracker."""

    def __init__(self, limits: dict[str, int] | None = None):
        self._limits = limits or {"brave": 1000, "baidu": 100}
        self._file = USAGE_DIR / "search_usage.json"

    def _load(self) -> dict:
        ensure_dir(USAGE_DIR)
        if self._file.exists():
            try:
                return json.loads(self._file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save(self, data: dict) -> None:
        ensure_dir(USAGE_DIR)
        self._file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def get_usage(self) -> dict:
        data = self._load()
        today = self._today()
        engines: dict[str, dict] = {}
        for eng, limit in self._limits.items():
            day_data = data.get(eng, {}).get(today, {})
            engines[eng] = {
                "used": day_data.get("count", 0),
                "limit": limit,
                "remaining": max(0, limit - day_data.get("count", 0)),
            }
        return {"date": today, "engines": engines}

    def can_use(self, engine: str) -> bool:
        usage = self.get_usage()
        eng = usage["engines"].get(engine)
        if not eng:
            return True
        return eng["remaining"] > 0

    def record(self, engine: str) -> None:
        data = self._load()
        today = self._today()
        data.setdefault(engine, {})
        day_data = data[engine].setdefault(today, {"count": 0})
        day_data["count"] = day_data.get("count", 0) + 1
        self._save(data)


class SearchCapability:
    """Standalone search (fallback for Prompt App runtime).

    In the Agent loop, nanobot handles search via its own tools.
    See ``governance.py`` for the post-execution governance hooks.
    """

    def __init__(self, *, quota: QuotaManager | None = None, audit_ledger: Any = None):
        self.quota = quota or QuotaManager()
        self._audit = audit_ledger

    async def search(
        self, query: str, *, engine: str = "auto", max_results: int = 10
    ) -> list[dict]:
        """Execute a web search.  Returns list of ``{title, url, snippet}``."""
        if engine == "auto":
            for eng in ("brave", "baidu"):
                if self.quota.can_use(eng):
                    engine = eng
                    break
            else:
                return [{"error": "All search quotas exhausted for today"}]

        if not self.quota.can_use(engine):
            return [{"error": f"Quota exhausted for {engine}"}]

        self.quota.record(engine)

        # Delegate to the existing web_search module for actual API calls
        try:
            from apps.web_search import multi_engine_search

            results = await _run_search(query, engine, max_results)
        except ImportError:
            results = [{"error": "Search backend not available"}]

        if self._audit:
            self._audit.append_entry(
                capability="search.web",
                args={"query": query, "engine": engine},
                action_id="",
                result_summary=f"results={len(results)}",
            )

        return results


async def _run_search(query: str, engine: str, max_results: int) -> list[dict]:
    """Bridge to the legacy ``apps/web_search`` module."""
    try:
        from apps.web_search import multi_engine_search

        raw = multi_engine_search(query, engine=engine, max_results=max_results)
        if isinstance(raw, list):
            return raw
        return [{"raw": str(raw)}]
    except Exception as e:
        return [{"error": str(e)}]
