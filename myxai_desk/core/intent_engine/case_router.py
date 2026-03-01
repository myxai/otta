"""Case router — retrieves similar historical cases for routing decisions.

Unlike ``case_store.search_similar`` (used for plan-reuse), this module
is designed for *routing*: it returns a scored ``CaseRouteResult`` with
``case_conf`` adjusted by recency and plan-reuse success rate.

When a ``case_key`` is provided the router first tries a *focused* search
by filtering candidates from SQLite that share the same key or key-prefix,
then falls back to full HNSW search if the focused path yields nothing.
This avoids cross-intent interference (e.g. "监控房价" matching "整理下载目录").
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

log = logging.getLogger("myxai")

_RECENCY_DAYS = 30
_RECENCY_BOOST = 0.03
_PLAN_REUSE_BOOST = 0.05
_MIN_SIM_FOR_ROUTING = 0.45
_CASE_KEY_CANDIDATES_LIMIT = 20


@dataclass
class CaseRouteResult:
    """Routing evidence derived from a historical case."""
    category: str
    case_conf: float
    case_id: str
    plan_kind_hint: str      # golden / candidate / cached / none
    similarity: float


def search(text: str, case_key: str = "") -> CaseRouteResult | None:
    """Find the best matching historical case and score it for routing.

    When *case_key* is provided, candidates are first filtered by key prefix
    (verb bucket) in SQLite, then scored by vector similarity within that set.
    Falls back to full HNSW search when focused search yields nothing.

    Does NOT increment ``usage_count`` — that belongs to the execution phase.
    Returns ``None`` when no case exceeds the minimum similarity threshold.
    """
    try:
        from myxai_desk.core.intent_engine.case_store import _ensure_init
        from myxai_desk.core.intent_engine.embedder import embed_text, is_semantic
        _ensure_init()
    except Exception:
        log.debug("[case_router] init failed", exc_info=True)
        return None

    vec = embed_text(text)
    if vec is None:
        return None

    if not is_semantic():
        log.debug("[case_router] hash-only embeddings — skipping semantic search, "
                   "case_router degraded to rule-only routing")
        return None

    # Strategy: focused (key-filtered) first, then global fallback.
    result = None
    if case_key:
        result = _search_by_key(vec, case_key)
    if result is None:
        result = _search_global(vec)
    return result


def _search_by_key(vec: list[float], case_key: str) -> CaseRouteResult | None:
    """Filter candidates by case_key prefix, then rank by cosine similarity."""
    from myxai_desk.core.storage.sqlite import execute
    from myxai_desk.core.intent_engine.embedder import embed_text

    key_prefix = case_key.rsplit("_", 1)[0] + "_" if "_" in case_key else case_key

    rows = execute(
        """SELECT id FROM ie_cases
           WHERE case_key LIKE ? AND outcome = 'success'
           ORDER BY last_used_at DESC NULLS LAST, created_at DESC
           LIMIT ?""",
        (key_prefix + "%", _CASE_KEY_CANDIDATES_LIMIT),
        readonly=True,
    )
    if not rows:
        return None

    candidate_ids = {r["id"] for r in rows}
    return _score_candidates(vec, candidate_ids)


def _search_global(vec: list[float]) -> CaseRouteResult | None:
    """Full HNSW search across all cases."""
    from myxai_desk.core.intent_engine.hnsw_index import search as hnsw_search
    from myxai_desk.core.storage.sqlite import execute

    raw = hnsw_search(vec, top_k=5)
    if not raw:
        return None

    best: CaseRouteResult | None = None
    for case_id, sim in raw:
        if sim < _MIN_SIM_FOR_ROUTING:
            continue
        rows = execute(
            "SELECT * FROM ie_cases WHERE id = ?", (case_id,), readonly=True
        )
        if not rows:
            continue
        row = dict(rows[0])
        if row.get("outcome") != "success":
            continue
        candidate = _row_to_result(row, sim)
        if best is None or candidate.case_conf > best.case_conf:
            best = candidate
    return best


def _score_candidates(
    query_vec: list[float],
    candidate_ids: set[str],
) -> CaseRouteResult | None:
    """Score a pre-filtered set of case IDs by cosine similarity to *query_vec*.

    Uses stored ``text_norm`` for re-embedding (consistent with the query
    vector which is also built from norm_text).  Falls back to on-the-fly
    normalisation of ``task_text`` when ``text_norm`` is absent.
    """
    import math
    from myxai_desk.core.storage.sqlite import execute
    from myxai_desk.core.intent_engine.embedder import embed_text

    q_norm = math.sqrt(sum(v * v for v in query_vec)) or 1.0

    best: CaseRouteResult | None = None
    for cid in candidate_ids:
        rows = execute(
            "SELECT * FROM ie_cases WHERE id = ?", (cid,), readonly=True
        )
        if not rows:
            continue
        row = dict(rows[0])

        embed_source = row.get("text_norm", "") or ""
        if not embed_source:
            raw = row.get("task_text", "")
            if not raw:
                continue
            from myxai_desk.core.intent_engine.normalizer import normalize_text
            embed_source = normalize_text(raw)

        cvec = embed_text(embed_source)
        if cvec is None:
            continue

        dot = sum(a * b for a, b in zip(query_vec, cvec))
        c_norm = math.sqrt(sum(v * v for v in cvec)) or 1.0
        sim = dot / (q_norm * c_norm)

        if sim < _MIN_SIM_FOR_ROUTING:
            continue

        candidate = _row_to_result(row, sim)
        if best is None or candidate.case_conf > best.case_conf:
            best = candidate

    return best


def _row_to_result(row: dict, sim: float) -> CaseRouteResult:
    conf = sim
    conf = _apply_recency_boost(conf, row)
    conf = _apply_plan_reuse_boost(conf, row)
    conf = max(0.0, min(1.0, conf))

    category = row.get("route_label", "general")
    if "," in category:
        category = category.split(",")[0].strip()

    plan_kind = row.get("best_plan_kind", "") or "none"
    return CaseRouteResult(
        category=category,
        case_conf=round(conf, 4),
        case_id=row.get("id", ""),
        plan_kind_hint=plan_kind,
        similarity=round(sim, 4),
    )


def _apply_recency_boost(conf: float, row: dict) -> float:
    """Boost confidence if the case was used recently."""
    last_used = row.get("last_used_at") or row.get("created_at", "")
    if not last_used:
        return conf
    try:
        dt = datetime.fromisoformat(last_used.replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - dt).days
        if age_days <= _RECENCY_DAYS:
            conf += _RECENCY_BOOST
    except Exception:
        pass
    return conf


def _apply_plan_reuse_boost(conf: float, row: dict) -> float:
    """Boost confidence when the case has a strong plan-reuse track record."""
    success_count = row.get("success_count", 0) or 0
    fail_count = row.get("fail_count", 0) or 0
    total = success_count + fail_count
    if total >= 2:
        rate = success_count / total
        if rate >= 0.8:
            conf += _PLAN_REUSE_BOOST
    return conf
