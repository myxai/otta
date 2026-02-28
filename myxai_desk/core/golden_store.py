"""Golden Store — DB read/write layer for golden plans and candidate lifecycle.

Owns: ``golden_plans`` table creation, golden/candidate queries,
promotion, and stats recording.  ``golden_candidates`` table is
owned by execution_radar; this module only reads/updates it.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from myxai_desk.core.storage.sqlite import connect, ensure_table, execute

log = logging.getLogger("myxai")

_TABLES_READY = False

CANDIDATE_FAIL_THRESHOLD = 3


# ── Data classes ──────────────────────────────────────────────────


@dataclass
class GoldenPlan:
    case_key: str
    version: int
    golden_plan_json: str
    replayable: bool
    source_candidate_id: Optional[str]
    created_at: str
    last_used_at: Optional[str]
    stats: dict[str, Any] = field(default_factory=dict)


@dataclass
class GoldenCandidate:
    candidate_id: str
    case_key: str
    candidate_plan_json: str
    quality_score: float
    removed_steps: int
    status: str
    used_count: int
    fail_count: int
    created_at: str
    last_used_at: Optional[str]


# ── Table init ────────────────────────────────────────────────────


def _init_golden_tables() -> None:
    global _TABLES_READY
    if _TABLES_READY:
        return

    ensure_table(
        "golden_plans",
        """
        case_key            TEXT PRIMARY KEY,
        version             INTEGER NOT NULL DEFAULT 1,
        golden_plan_json    TEXT NOT NULL,
        replayable          INTEGER NOT NULL DEFAULT 1,
        source_candidate_id TEXT,
        created_at          TEXT NOT NULL,
        last_used_at        TEXT,
        stats_json          TEXT NOT NULL DEFAULT '{}'
        """,
    )

    try:
        execute("SELECT 1 FROM golden_plans LIMIT 0", readonly=True)
    except Exception:
        pass

    _backfill_candidate_columns()
    _TABLES_READY = True


def _backfill_candidate_columns() -> None:
    """Ensure golden_candidates has the extra columns PR-2 needs."""
    extras = [
        ("used_count", "INTEGER NOT NULL DEFAULT 0"),
        ("fail_count", "INTEGER NOT NULL DEFAULT 0"),
        ("last_used_at", "TEXT"),
    ]
    for col, typedef in extras:
        try:
            execute(f"SELECT {col} FROM golden_candidates LIMIT 1", readonly=True)
        except Exception:
            try:
                with connect() as conn:
                    conn.execute(
                        f"ALTER TABLE golden_candidates ADD COLUMN {col} {typedef}"
                    )
            except Exception:
                pass


# ── case_key computation ──────────────────────────────────────────


def compute_case_key(
    user_text: str,
    route_labels: list[str] | None = None,
    security_mode: str = "",
) -> str:
    """Deterministic case_key from user intent + context.

    Formula: ``sha256(route_sig | security_mode | normalized_keywords)[:24]``

    Both the execution side and the radar pipeline must call this with
    equivalent inputs so that candidates match at lookup time.
    """
    route_sig = "|".join(sorted(route_labels or []))
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", (user_text or "").lower())
    norm_kw = "|".join(sorted(set(tokens)))
    raw = f"{route_sig}|{security_mode}|{norm_kw}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


# ── GoldenStore ───────────────────────────────────────────────────


class GoldenStore:
    """All golden-plan / candidate DB operations in one place."""

    def __init__(self) -> None:
        _init_golden_tables()

    # 1) Fetch verified golden plan
    def get_golden_plan(self, case_key: str) -> Optional[GoldenPlan]:
        rows = execute(
            "SELECT * FROM golden_plans WHERE case_key = ? AND replayable = 1",
            (case_key,),
            readonly=True,
        )
        if not rows:
            return None
        r = rows[0]
        return GoldenPlan(
            case_key=r["case_key"],
            version=r["version"],
            golden_plan_json=r["golden_plan_json"],
            replayable=bool(r["replayable"]),
            source_candidate_id=r.get("source_candidate_id"),
            created_at=r["created_at"],
            last_used_at=r.get("last_used_at"),
            stats=_safe_json(r.get("stats_json", "{}")),
        )

    # 2) Fetch best candidate (new or used, not invalid/promoted)
    def get_best_candidate(self, case_key: str) -> Optional[GoldenCandidate]:
        rows = execute(
            """SELECT * FROM golden_candidates
               WHERE case_key = ? AND status IN ('new', 'used')
               ORDER BY quality_score DESC, created_at DESC
               LIMIT 1""",
            (case_key,),
            readonly=True,
        )
        if not rows:
            return None
        r = rows[0]
        return GoldenCandidate(
            candidate_id=r["candidate_id"],
            case_key=r["case_key"],
            candidate_plan_json=(
                r.get("candidate_plan_json") or "[]"
            ),
            quality_score=r.get("quality_score", 0.0),
            removed_steps=r.get("removed_steps", 0),
            status=r.get("status", "new"),
            used_count=r.get("used_count", 0),
            fail_count=r.get("fail_count", 0),
            created_at=r["created_at"],
            last_used_at=r.get("last_used_at"),
        )

    # 3) Mark candidate usage result
    def mark_candidate_used(self, candidate_id: str, ok: bool) -> None:
        now = _now_iso()
        if ok:
            execute(
                """UPDATE golden_candidates
                   SET status = CASE WHEN status = 'new' THEN 'used' ELSE status END,
                       used_count = used_count + 1,
                       last_used_at = ?
                   WHERE candidate_id = ?""",
                (now, candidate_id),
            )
        else:
            execute(
                """UPDATE golden_candidates
                   SET fail_count = fail_count + 1,
                       last_used_at = ?,
                       status = CASE WHEN fail_count + 1 >= ? THEN 'invalid' ELSE status END
                   WHERE candidate_id = ?""",
                (now, CANDIDATE_FAIL_THRESHOLD, candidate_id),
            )

    # 4) Promote candidate → golden plan
    def promote_candidate_to_golden(
        self,
        *,
        case_key: str,
        candidate_id: str,
        golden_plan_json: str,
        now_iso: str | None = None,
    ) -> GoldenPlan:
        now = now_iso or _now_iso()

        old_version = 0
        rows = execute(
            "SELECT version FROM golden_plans WHERE case_key = ?",
            (case_key,),
            readonly=True,
        )
        if rows:
            old_version = rows[0].get("version", 0)

        new_version = old_version + 1

        execute(
            """INSERT OR REPLACE INTO golden_plans
               (case_key, version, golden_plan_json, replayable,
                source_candidate_id, created_at, last_used_at, stats_json)
               VALUES (?, ?, ?, 1, ?, ?, ?, '{}')""",
            (case_key, new_version, golden_plan_json, candidate_id, now, now),
        )

        execute(
            "UPDATE golden_candidates SET status = 'promoted' WHERE candidate_id = ?",
            (candidate_id,),
        )

        return GoldenPlan(
            case_key=case_key,
            version=new_version,
            golden_plan_json=golden_plan_json,
            replayable=True,
            source_candidate_id=candidate_id,
            created_at=now,
            last_used_at=now,
            stats={},
        )

    # 5) Record golden usage stats
    def record_golden_use(
        self,
        *,
        case_key: str,
        ok: bool,
        attempts_count: int = 0,
        duration_ms: int | None = None,
        run_id: str | None = None,
        now_iso: str | None = None,
    ) -> None:
        now = now_iso or _now_iso()

        rows = execute(
            "SELECT stats_json FROM golden_plans WHERE case_key = ?",
            (case_key,),
            readonly=True,
        )
        if not rows:
            return

        stats: dict[str, Any] = _safe_json(rows[0].get("stats_json", "{}"))
        sc = stats.get("success_count", 0)
        fc = stats.get("fail_count", 0)

        if ok:
            stats["success_count"] = sc + 1
        else:
            stats["fail_count"] = fc + 1

        total = sc + fc + 1
        old_avg = stats.get("avg_attempts", 0.0)
        stats["avg_attempts"] = round(
            old_avg + (attempts_count - old_avg) / total, 2
        )

        if duration_ms is not None:
            old_dur = stats.get("avg_duration_ms", 0.0)
            stats["avg_duration_ms"] = round(
                old_dur + (duration_ms - old_dur) / total, 2
            )

        stats["last_outcome"] = "success" if ok else "fail"
        if run_id:
            stats["last_run_id"] = run_id

        execute(
            "UPDATE golden_plans SET last_used_at = ?, stats_json = ? WHERE case_key = ?",
            (now, json.dumps(stats, ensure_ascii=False), case_key),
        )


# ── Helpers ───────────────────────────────────────────────────────


def parse_candidate_plan(candidate_plan_json: str) -> list[dict]:
    """Convert candidate storage format to plan_runner format.

    Candidates store ``args_json`` as a JSON string; plan_runner expects
    ``args`` as a dict.
    """
    raw = json.loads(candidate_plan_json) if isinstance(candidate_plan_json, str) else candidate_plan_json
    steps: list[dict] = []
    for s in raw:
        tool_name = s.get("tool_name", "")
        if not tool_name:
            continue
        args = s.get("args") or s.get("args_json", "{}")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except (json.JSONDecodeError, TypeError):
                args = {}
        steps.append({"tool_name": tool_name, "args": args})
    return steps


def _safe_json(val: Any) -> Any:
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return {}
    return val if isinstance(val, dict) else {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
