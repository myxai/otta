"""Intent predictor — IE 2.0 taxonomy-aware classification and tool filtering.

Dimensions:
  - routing_method: rule / model / case_reuse
  - execution_path: llm_loop / plan_reuse (written back after execution)
  - risk_level: low / medium / high

Misroute guards:
  - Semantic consistency check (category vs text content)
  - High-risk gate (warn/log when confidence is low)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from myxai_desk.core.intent_engine import config as ie_config
from myxai_desk.core.intent_engine.categories import (
    collect_tools,
    get_risk,
)
from myxai_desk.core.intent_engine.dao import insert_run, update_outcome

log = logging.getLogger("myxai")

_FALLBACK_CONF = 0.70
_SEARCH_DOMINANCE_WINDOW = 200
_SEARCH_DOMINANCE_THRESHOLD = 0.60
_SEARCH_DOMINANCE_PENALTY = 0.15

# ── File-verb patterns for misroute guard ────────────────────────

import re

_FS_VERB_PATTERN = re.compile(
    r"文件|目录|路径|\.(?:txt|csv|json|xml|py|js|md|zip|tar|pdf|docx?|xlsx?)|"
    r"read_file|write_file|edit_file|list_dir|/home/|/tmp/|C:\\|D:\\|~/",
    re.IGNORECASE,
)
_SEARCH_DANGEROUS_PATTERN = re.compile(
    r"删除|移动|重命名|覆盖|格式化|清空",
    re.IGNORECASE,
)


@dataclass
class PredictResult:
    """Holds the output of a single predict() call."""

    run_id: str | None = None
    route_labels: list[str] = field(default_factory=list)
    route_conf: float = 0.0
    decision_mode: str = "rule"       # legacy compat
    allowed_tools: set[str] = field(default_factory=set)
    tools_before: int = 0
    tools_after: int = 0
    hints: str = ""

    # PR-3 plan reuse fields
    decision: str = "llm"             # llm | reuse_plan
    plan_steps: list[dict] | None = None
    latency_ms: float = 0.0

    # IE 2.0 taxonomy fields
    routing_method: str = "rule"      # rule | model | case_reuse
    execution_path: str = ""          # llm_loop | plan_reuse (written after execution)
    risk_level: str = "low"           # low | medium | high
    matched_rule_id: str = ""
    fallback_reason: str = ""
    misroute_suspect: bool = False

    # IE 3.0 confidence calibration
    rule_conf: float = 0.0
    case_id: str = ""
    case_conf: float = 0.0
    llm_conf: float = 0.0
    confidence_source: str = ""       # rule | case | llm | fused
    arbiter_reason: str = ""
    evidence_json: str = ""
    case_key: str = ""
    text_norm: str = ""

    # ── helper methods ─────────────────────────────────────────────

    @property
    def confidence(self) -> float:
        return self.route_conf

    def filter_tools(self, all_defs: list[dict]) -> list[dict]:
        """Return the subset of tool definitions matching allowed_tools."""
        if not self.allowed_tools:
            return all_defs
        return [
            d for d in all_defs
            if d.get("function", {}).get("name", "") in self.allowed_tools
        ]

    def save(self, session_id: str = "", user_text: str = "", context: dict | None = None) -> str | None:
        """Persist this prediction as an ie_runs row. Returns run_id."""
        self.run_id = insert_run(
            session_id=session_id,
            user_text=user_text,
            context=context,
            route_label=",".join(self.route_labels),
            route_conf=self.route_conf,
            decision_mode=self.decision_mode,
            decision=self.decision,
            tool_group=list(self.allowed_tools),
            tools_before=self.tools_before,
            tools_after=self.tools_after,
            routing_method=self.routing_method,
            risk_level=self.risk_level,
            matched_rule_id=self.matched_rule_id,
            fallback_reason=self.fallback_reason,
        )
        if self.run_id:
            from myxai_desk.core.intent_engine.dao import update_ie_run
            extras: dict[str, Any] = {}
            if self.latency_ms > 0:
                extras["latency_ms"] = self.latency_ms
            if self.misroute_suspect:
                extras["misroute_suspect"] = 1
            if self.rule_conf > 0:
                extras["rule_conf"] = self.rule_conf
            if self.case_id:
                extras["case_id"] = self.case_id
            if self.case_conf > 0:
                extras["case_conf"] = self.case_conf
            if self.llm_conf > 0:
                extras["llm_conf"] = self.llm_conf
            if self.confidence_source:
                extras["confidence_source"] = self.confidence_source
            if self.arbiter_reason:
                extras["arbiter_reason"] = self.arbiter_reason
            if self.evidence_json:
                extras["evidence_json"] = self.evidence_json
            if self.case_key:
                extras["case_key"] = self.case_key
            if extras:
                update_ie_run(self.run_id, **extras)
        return self.run_id

    def write_outcome(self, outcome: str) -> None:
        if self.run_id:
            update_outcome(self.run_id, outcome)


def predict(
    user_text: str,
    context: dict[str, Any] | None = None,
    *,
    all_tool_defs: list[dict] | None = None,
    mcp_tool_names: list[str] | None = None,
) -> PredictResult:
    """Classify intent and determine which tools are relevant."""
    ctx = context or {}
    result = PredictResult()
    t0 = time.perf_counter()

    cfg = ie_config.get()
    always_include = set(cfg.get("base_tools_always_included", []))

    # --- Step 0: text normalisation ---
    from myxai_desk.core.intent_engine.normalizer import normalize_text, build_case_key
    text_norm = normalize_text(user_text)
    case_key = build_case_key(text_norm)
    result.text_norm = text_norm
    result.case_key = case_key

    # --- Step 1: rule router (scored confidence) ---
    # Rules use raw text because regex patterns target original expressions
    # (paths, URLs, exact keywords); score_rule also checks raw for boost signals.
    from myxai_desk.core.intent_engine.rule_router import route as rule_route
    rule_hit = rule_route(user_text)

    if rule_hit:
        result.rule_conf = rule_hit.rule_conf
        result.matched_rule_id = rule_hit.rule_id
    else:
        result.rule_conf = 0.0

    # --- Step 2: case router (historical evidence) ---
    # Uses text_norm so that synonym-normalised text produces stable embeddings.
    case_hit = None
    if not ctx.get("skip_case_search", False):
        try:
            from myxai_desk.core.intent_engine.case_router import search as case_search
            case_hit = case_search(text_norm, case_key=case_key)
            if case_hit:
                result.case_id = case_hit.case_id
                result.case_conf = case_hit.case_conf
                log.debug("[predict] case_hit: cat=%s conf=%.3f sim=%.3f id=%s",
                          case_hit.category, case_hit.case_conf,
                          case_hit.similarity, case_hit.case_id)
        except Exception:
            log.debug("[predict] case_router failed", exc_info=True)

    # --- Step 3: arbiter fusion ---
    from myxai_desk.core.intent_engine.arbiter import (
        fuse as arbiter_fuse,
        should_call_llm,
        fuse_with_llm,
    )
    fused = arbiter_fuse(rule_hit, case_hit, user_text=user_text)

    # --- Step 3.5: LLM arbitration (conditional) ---
    if should_call_llm(fused, rule_hit, case_hit, ctx):
        try:
            from myxai_desk.core.intent_engine.llm_router import classify as llm_classify
            llm_hit = llm_classify(user_text, ctx)
            if llm_hit:
                fused = fuse_with_llm(fused, llm_hit)
                result.llm_conf = llm_hit.confidence
                result.routing_method = "model"
                log.info("[predict] LLM arbiter: cat=%s conf=%.3f reason=%s",
                         llm_hit.category, llm_hit.confidence, llm_hit.rationale)
        except Exception:
            log.debug("[predict] llm_router failed", exc_info=True)

    # --- Step 4: apply fused result ---
    result.route_labels = fused.route_labels or ["general"]
    result.route_conf = round(fused.confidence, 4)
    result.confidence_source = fused.confidence_source
    result.arbiter_reason = fused.arbiter_reason
    result.evidence_json = fused.to_evidence_json()
    result.risk_level = fused.risk_level or "low"

    if not result.routing_method or result.routing_method == "rule":
        if fused.confidence_source == "case":
            result.routing_method = "case_reuse"
        elif fused.confidence_source == "llm":
            result.routing_method = "model"
        else:
            result.routing_method = "rule"
    result.decision_mode = result.routing_method

    # Search dominance guard: penalise case-only search when search is overrepresented
    if (
        result.arbiter_reason == "case_only"
        and result.route_labels == ["search"]
        and _is_search_dominant()
    ):
        result.route_conf = max(0.0, result.route_conf - _SEARCH_DOMINANCE_PENALTY)
        fused.confidence = result.route_conf
        log.info("[predict] search_dominance penalty applied (conf now %.3f)", result.route_conf)

    # Fallback guard
    if fused.confidence < _FALLBACK_CONF:
        result.route_labels = ["general"]
        result.fallback_reason = fused.fallback_reason or "low_confidence"

    # Risk level: highest among matched categories
    result.risk_level = _max_risk([get_risk(lb) for lb in result.route_labels])

    # --- Step 5: collect allowed tools ---
    result.allowed_tools = collect_tools(
        result.route_labels,
        mcp_tool_names=mcp_tool_names,
        always_include=always_include,
    )
    if all_tool_defs is not None:
        result.tools_before = len(all_tool_defs)
        result.tools_after = len(result.filter_tools(all_tool_defs))

    # --- Step 6: misroute guard ---
    result.misroute_suspect = _check_misroute(user_text, result)
    if result.misroute_suspect:
        log.info("[predict] misroute_suspect=1 for labels=%s text=%.60s",
                 result.route_labels, user_text)

    # --- Step 7: case retrieval hints ---
    if not ctx.get("skip_case_search", False):
        try:
            from myxai_desk.core.intent_engine.case_store import retrieve_hints
            result.hints = retrieve_hints(
                text_norm,
                route_labels=result.route_labels,
                conf=result.route_conf,
            )
        except Exception:
            log.debug("[predict] retrieve_hints failed", exc_info=True)

    # --- Step 8: plan reuse via arbiter ---
    if not ctx.get("skip_case_search", False):
        try:
            from myxai_desk.core.intent_engine.arbiter import maybe_reuse
            decision, steps = maybe_reuse(text_norm, result, ctx)
            result.decision = decision
            result.plan_steps = steps
            if decision == "reuse_plan":
                result.routing_method = "case_reuse"
                result.decision_mode = "case_reuse"
        except Exception:
            log.debug("[predict] arbiter.maybe_reuse failed", exc_info=True)

    result.latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    return result


# ── Misroute guard ───────────────────────────────────────────────

_NEGATION_RE = re.compile(
    r"不要|不能|不可以|不许|不得|不用|别|禁止|无需|勿",
)


def _check_misroute(user_text: str, result: PredictResult) -> bool:
    """Lightweight semantic consistency check.

    Flags:
      - category=fs but text has no file verbs/paths → suspect
      - category=search but text has destructive verbs → suspect
    """
    labels = set(result.route_labels)

    if "fs" in labels and not _FS_VERB_PATTERN.search(user_text):
        return True

    if "search" in labels and _SEARCH_DANGEROUS_PATTERN.search(user_text):
        return True

    _check_negation_integrity(user_text, result.text_norm)

    return False


def _check_negation_integrity(raw: str, norm: str) -> None:
    """Warn when a negation modifier present in *raw* is absent from *norm*.

    This acts as a safety net against normalisation silently stripping
    negation/scope words, which could invert the user's intent.
    """
    for m in _NEGATION_RE.finditer(raw):
        word = m.group().lower()
        if word not in norm:
            log.warning(
                "[predict] negation leak: '%s' in raw but missing from norm_text "
                "(raw=%.60s norm=%.60s)",
                word, raw, norm,
            )


_RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


def _max_risk(levels: list[str]) -> str:
    if not levels:
        return "low"
    return max(levels, key=lambda r: _RISK_ORDER.get(r, 0))


def _is_search_dominant() -> bool:
    """Check if 'search' category dominates recent routing decisions.

    When search accounts for > 60% of the last 200 runs, case_reuse results
    for search become less trustworthy and should be penalised.
    """
    try:
        from myxai_desk.core.storage.sqlite import execute
        rows = execute(
            """SELECT route_label FROM ie_runs
               ORDER BY created_at DESC LIMIT ?""",
            (_SEARCH_DOMINANCE_WINDOW,),
            readonly=True,
        )
        if not rows or len(rows) < 20:
            return False
        search_count = sum(
            1 for r in rows if (r.get("route_label") or "").startswith("search")
        )
        ratio = search_count / len(rows)
        if ratio > _SEARCH_DOMINANCE_THRESHOLD:
            log.info(
                "[predict] search dominance detected: %.1f%% of last %d runs",
                ratio * 100, len(rows),
            )
            return True
    except Exception:
        log.debug("[predict] search dominance check failed", exc_info=True)
    return False
