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
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

log = logging.getLogger("myxai")

_RECENCY_DAYS = 30
_RECENCY_BOOST = 0.03
_PLAN_REUSE_BOOST = 0.05
_MIN_SIM_FOR_ROUTING = 0.55
_MIN_SIM_SHORT_TEXT = 0.65
_SHORT_TEXT_THRESHOLD = 6
_TOP2_GAP_MIN = 0.08
_CASE_KEY_CANDIDATES_LIMIT = 20


@dataclass
class CaseRouteResult:
    """Routing evidence derived from a historical case."""
    category: str
    case_conf: float
    case_id: str
    plan_kind_hint: str      # golden / candidate / cached / none
    similarity: float


@dataclass
class SearchSpans:
    """Timing spans for case_router.search() — observability only."""
    init_ms: float = 0.0
    embed_ms: float = 0.0
    sqlite_ms: float = 0.0
    hnsw_ms: float = 0.0
    rerank_ms: float = 0.0
    total_ms: float = 0.0
    embed_provider: str = ""     # litellm / hash
    search_path: str = ""        # key_filtered / global / skipped
    candidates_count: int = 0
    cache_hit: bool = False

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


_last_spans: SearchSpans | None = None


def get_last_spans() -> SearchSpans | None:
    """Return timing spans from the most recent search() call."""
    return _last_spans


def _effective_min_sim(text: str) -> float:
    """Return the minimum similarity threshold, raised for short text."""
    if len(text.strip()) <= _SHORT_TEXT_THRESHOLD:
        return _MIN_SIM_SHORT_TEXT
    return _MIN_SIM_FOR_ROUTING


def search(text: str, case_key: str = "") -> CaseRouteResult | None:
    """Find the best matching historical case and score it for routing.

    When *case_key* is provided, candidates are first filtered by key prefix
    (verb bucket) in SQLite, then scored by vector similarity within that set.
    Falls back to full HNSW search when focused search yields nothing.

    Short text (<=12 chars) uses a higher similarity threshold to avoid
    embedding instability causing random matches.

    Does NOT increment ``usage_count`` — that belongs to the execution phase.
    Returns ``None`` when no case exceeds the minimum similarity threshold.
    """
    global _last_spans
    spans = SearchSpans()
    t_total = time.perf_counter()

    min_sim = _effective_min_sim(text)

    # Canonicalize case_key via alias table (nightly learning output)
    if case_key:
        try:
            from myxai_desk.core.intent_engine.user_lexicon import canonicalize_case_key
            case_key = canonicalize_case_key(case_key)
        except Exception:
            pass

    # -- init --
    t0 = time.perf_counter()
    try:
        from myxai_desk.core.intent_engine.case_store import _ensure_init
        from myxai_desk.core.intent_engine.embedder import embed_text, is_semantic
        _ensure_init()
    except Exception:
        log.debug("[case_router] init failed", exc_info=True)
        spans.init_ms = (time.perf_counter() - t0) * 1000
        spans.total_ms = (time.perf_counter() - t_total) * 1000
        spans.search_path = "init_failed"
        _last_spans = spans
        return None
    spans.init_ms = (time.perf_counter() - t0) * 1000

    # -- embed query --
    t0 = time.perf_counter()
    vec = embed_text(text)
    spans.embed_ms = (time.perf_counter() - t0) * 1000
    try:
        from myxai_desk.core.intent_engine.embedder import get_provider_name
        spans.embed_provider = get_provider_name()
    except Exception:
        spans.embed_provider = "local" if is_semantic() else "hash"

    if vec is None:
        spans.total_ms = (time.perf_counter() - t_total) * 1000
        spans.search_path = "embed_failed"
        _last_spans = spans
        return None

    # If semantic embedding unavailable, use lexical fallback (FTS5 BM25)
    if not is_semantic():
        log.debug("[case_router] hash-only embeddings — switching to lexical fallback (FTS5 BM25)")
        result = _search_lexical_fallback(text, case_key, spans, min_sim=min_sim)
        spans.embed_provider = "hash->lexical"
        spans.total_ms = (time.perf_counter() - t_total) * 1000
        _last_spans = spans
        return result

    # Strategy: focused (key-filtered) first, then global fallback.
    result = None
    if case_key:
        result = _search_by_key(vec, case_key, spans, min_sim=min_sim)
        spans.search_path = "key_filtered"
    if result is None:
        result = _search_global(vec, spans, min_sim=min_sim)
        if not spans.search_path:
            spans.search_path = "global"
        elif result is not None:
            spans.search_path = "key_filtered->global"

    spans.total_ms = (time.perf_counter() - t_total) * 1000
    _last_spans = spans
    return result


def _search_by_key(
    vec: list[float], case_key: str, spans: SearchSpans,
    *, min_sim: float = _MIN_SIM_FOR_ROUTING,
) -> CaseRouteResult | None:
    """Filter candidates by case_key prefix, then rank by cosine similarity."""
    from myxai_desk.core.storage.sqlite import execute

    key_prefix = case_key.rsplit("_", 1)[0] + "_" if "_" in case_key else case_key

    t0 = time.perf_counter()
    rows = execute(
        """SELECT id FROM ie_cases
           WHERE case_key LIKE ? AND outcome = 'success'
           ORDER BY last_used_at DESC NULLS LAST, created_at DESC
           LIMIT ?""",
        (key_prefix + "%", _CASE_KEY_CANDIDATES_LIMIT),
        readonly=True,
    )
    spans.sqlite_ms += (time.perf_counter() - t0) * 1000

    if not rows:
        return None

    candidate_ids = {r["id"] for r in rows}
    spans.candidates_count = len(candidate_ids)
    return _score_candidates(vec, candidate_ids, spans, min_sim=min_sim)


def _search_global(
    vec: list[float], spans: SearchSpans,
    *, min_sim: float = _MIN_SIM_FOR_ROUTING,
) -> CaseRouteResult | None:
    """Full HNSW search across all cases with top-2 gap rejection."""
    from myxai_desk.core.intent_engine.hnsw_index import search as hnsw_search
    from myxai_desk.core.storage.sqlite import execute

    t0 = time.perf_counter()
    raw = hnsw_search(vec, top_k=5)
    spans.hnsw_ms += (time.perf_counter() - t0) * 1000

    if not raw:
        return None

    scored: list[CaseRouteResult] = []
    for case_id, sim in raw:
        if sim < min_sim:
            continue
        t0 = time.perf_counter()
        rows = execute(
            "SELECT * FROM ie_cases WHERE id = ?", (case_id,), readonly=True
        )
        spans.sqlite_ms += (time.perf_counter() - t0) * 1000
        if not rows:
            continue
        row = dict(rows[0])
        if row.get("outcome") != "success":
            continue
        scored.append(_row_to_result(row, sim))

    if not scored:
        return None

    scored.sort(key=lambda c: c.case_conf, reverse=True)
    best = scored[0]

    # Top-2 gap check: if confidence gap is too small, the match is ambiguous
    if len(scored) >= 2:
        gap = best.case_conf - scored[1].case_conf
        if gap < _TOP2_GAP_MIN:
            log.debug(
                "[case_router] top2 gap too small (%.3f < %.3f), rejecting case match",
                gap, _TOP2_GAP_MIN,
            )
            return None

    return best


def _score_candidates(
    query_vec: list[float],
    candidate_ids: set[str],
    spans: SearchSpans,
    *, min_sim: float = _MIN_SIM_FOR_ROUTING,
) -> CaseRouteResult | None:
    """Score a pre-filtered set of case IDs by cosine similarity to *query_vec*.

    Uses stored ``text_norm`` for re-embedding (consistent with the query
    vector which is also built from norm_text).  Falls back to on-the-fly
    normalisation of ``task_text`` when ``text_norm`` is absent.

    Applies top-2 gap rejection to avoid ambiguous matches.
    """
    import math
    from myxai_desk.core.storage.sqlite import execute
    from myxai_desk.core.intent_engine.embedder import embed_text

    q_norm = math.sqrt(sum(v * v for v in query_vec)) or 1.0

    scored: list[CaseRouteResult] = []
    for cid in candidate_ids:
        t0 = time.perf_counter()
        rows = execute(
            "SELECT * FROM ie_cases WHERE id = ?", (cid,), readonly=True
        )
        spans.sqlite_ms += (time.perf_counter() - t0) * 1000
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

        t0 = time.perf_counter()
        cvec = embed_text(embed_source)
        spans.rerank_ms += (time.perf_counter() - t0) * 1000
        if cvec is None:
            continue

        dot = sum(a * b for a, b in zip(query_vec, cvec))
        c_norm = math.sqrt(sum(v * v for v in cvec)) or 1.0
        sim = dot / (q_norm * c_norm)

        if sim < min_sim:
            continue

        scored.append(_row_to_result(row, sim))

    if not scored:
        return None

    scored.sort(key=lambda c: c.case_conf, reverse=True)
    best = scored[0]

    if len(scored) >= 2:
        gap = best.case_conf - scored[1].case_conf
        if gap < _TOP2_GAP_MIN:
            log.debug(
                "[case_router] key-filtered top2 gap too small (%.3f), rejecting",
                gap,
            )
            return None

    return best


def _search_lexical_fallback(
    text: str, case_key: str, spans: SearchSpans,
    *, min_sim: float = _MIN_SIM_FOR_ROUTING,
) -> CaseRouteResult | None:
    """Lexical (FTS5 BM25) fallback when semantic embedding is unavailable.
    
    This ensures case retrieval remains functional even without vector models,
    using SQLite's built-in full-text search with BM25 ranking.
    
    Strategy:
    1. If case_key provided: search within case_key prefix (focused)
    2. Otherwise: search across all cases (global)
    3. BM25 ranking + recency/plan-reuse boosting
    
    Returns None if no cases match or all scores fall below threshold.
    """
    from myxai_desk.core.storage.sqlite import execute
    
    t0 = time.perf_counter()
    
    try:
        # Build FTS5 query (escape special chars)
        fts_query = text.replace('"', '""')
        
        log.debug(f"[case_router] lexical fallback: text={text!r}, case_key={case_key!r}, fts_query={fts_query!r}")
        
        if case_key:
            # Focused search: filter by case_key prefix
            key_prefix = case_key.rsplit("_", 1)[0] + "_" if "_" in case_key else case_key
            rows = execute(
                """
                SELECT 
                    c.id,
                    c.route_label,
                    c.best_plan_kind,
                    c.last_used_at,
                    c.plan_success_rate,
                    c.created_at,
                    bm25(ie_cases_fts) AS score
                FROM ie_cases_fts
                JOIN ie_cases c ON c.rowid = ie_cases_fts.rowid
                WHERE ie_cases_fts MATCH ?
                  AND c.case_key LIKE ?
                  AND c.outcome = 'success'
                ORDER BY score DESC
                LIMIT 5
                """,
                (fts_query, key_prefix + "%"),
                readonly=True,
            )
            spans.search_path = "lexical_key_filtered"
        else:
            # Global search: no case_key filter
            rows = execute(
                """
                SELECT 
                    c.id,
                    c.route_label,
                    c.best_plan_kind,
                    c.last_used_at,
                    c.plan_success_rate,
                    c.created_at,
                    bm25(ie_cases_fts) AS score
                FROM ie_cases_fts
                JOIN ie_cases c ON c.rowid = ie_cases_fts.rowid
                WHERE ie_cases_fts MATCH ?
                  AND c.outcome = 'success'
                ORDER BY score DESC
                LIMIT 5
                """,
                (fts_query,),
                readonly=True,
            )
            spans.search_path = "lexical_global"
        
        spans.sqlite_ms += (time.perf_counter() - t0) * 1000
        spans.candidates_count = len(rows)
        
        log.debug(f"[case_router] lexical search returned {len(rows)} rows")
        
        if not rows:
            return None
        
        # Re-rank with recency and plan-reuse boosts
        t0 = time.perf_counter()
        best: CaseRouteResult | None = None
        
        for row in rows:
            row_dict = dict(row)
            # BM25 score is negative (closer to 0 = better)
            # Normalize to 0-1 range (treat -10 as 0, -1 as ~0.9)
            bm25_score = max(0.0, min(1.0, 1.0 + row_dict["score"] / 10.0))
            
            # Apply same boosting logic as _row_to_result
            conf = bm25_score
            conf = _apply_recency_boost(conf, row_dict)
            conf = _apply_plan_reuse_boost(conf, row_dict)
            conf = max(0.0, min(1.0, conf))
            
            if conf < min_sim:
                continue
            
            category = row_dict.get("route_label", "general")
            if "," in category:
                category = category.split(",")[0].strip()
            
            plan_kind = row_dict.get("best_plan_kind", "") or "none"
            
            candidate = CaseRouteResult(
                category=category,
                case_conf=conf,
                case_id=row_dict["id"],
                plan_kind_hint=plan_kind,
                similarity=bm25_score,
            )
            
            if best is None or candidate.case_conf > best.case_conf:
                best = candidate
        
        spans.rerank_ms += (time.perf_counter() - t0) * 1000
        return best
        
    except Exception:
        log.debug("[case_router] lexical fallback failed", exc_info=True)
        spans.sqlite_ms += (time.perf_counter() - t0) * 1000
        spans.search_path = "lexical_failed"
        return None


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
