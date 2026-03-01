"""Arbiter — three-way evidence fusion, LLM trigger logic, and plan-reuse.

Responsibilities:
  1. Fuse rule_hit + case_hit into a single confidence / category.
  2. Apply strong-signal override when case_only (prevent case label pollution).
  3. Decide whether to invoke the LLM router (``should_call_llm``).
  4. Incorporate LLM result into the fused decision (``fuse_with_llm``).
  5. Decide whether to reuse a cached plan (``maybe_reuse`` — legacy, kept).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from myxai_desk.core.intent_engine import config as ie_config

if TYPE_CHECKING:
    from myxai_desk.core.intent_engine.case_router import CaseRouteResult
    from myxai_desk.core.intent_engine.llm_router import LLMRouteResult
    from myxai_desk.core.intent_engine.predictor import PredictResult
    from myxai_desk.core.intent_engine.rule_router import RuleRouteResult

log = logging.getLogger("myxai")

# ── Fusion weights ────────────────────────────────────────────────
_RULE_WEIGHT = 0.6
_CASE_WEIGHT = 0.4
_CONFLICT_THRESHOLD = 0.08
_LLM_TRIGGER_CONF = 0.75
_FALLBACK_CONF = 0.70
_HIGH_RISK_RULE_MIN = 0.85

# ── Strong-signal patterns for case_only override ────────────────
# These lightweight regex checks prevent case pollution from forcing
# obviously wrong categories (e.g. "1+1=?" → search, "写首诗" → search).

_SIGNAL_MATH = re.compile(
    r"\d+\s*[+\-*/÷×^%]\s*\d|=\s*\?|"
    r"计算|算一下|求值|求解|方程|等于多少|"
    r"√|∑|∫|sin\b|cos\b|tan\b|log\b|ln\b|π|"
    r"平方|立方|阶乘|导数|积分|极限",
    re.IGNORECASE,
)
_SIGNAL_CREATIVE = re.compile(
    r"写.*(?:诗|文|故事|小说|文案|脚本|歌词|对联|散文|作文|邮件|信)|"
    r"来一首|来一篇|来一段|来个.*(?:故事|笑话|段子)|"
    r"生成.*(?:文本|内容|文章)|创作|编写|改写|润色|续写|仿写|"
    r"翻译|translate",
    re.IGNORECASE,
)
_SIGNAL_OPERATE = re.compile(
    r"打开|关闭|删除|移动|下载|安装|运行|执行|卸载",
    re.IGNORECASE,
)

_STRONG_SIGNALS: list[tuple[re.Pattern[str], str, float]] = [
    (_SIGNAL_MATH,     "math",     0.90),
    (_SIGNAL_CREATIVE, "creative", 0.88),
    (_SIGNAL_OPERATE,  "fs",       0.75),
]


def _strong_signal_override(user_text: str, case_category: str) -> tuple[str, float, str] | None:
    """Check if *user_text* has a strong signal that contradicts *case_category*.

    Returns ``(correct_category, confidence, reason)`` when an override should
    be applied, or ``None`` when the case category looks plausible.
    """
    for pattern, category, conf in _STRONG_SIGNALS:
        if pattern.search(user_text) and case_category != category:
            return category, conf, f"strong_signal_{category}_overrides_{case_category}"
    return None


@dataclass
class FusedResult:
    """Merged routing decision from up to three evidence sources."""
    category: str = "general"
    confidence: float = 0.0
    confidence_source: str = "rule"    # rule / case / llm / fused
    risk_level: str = "low"
    rule_hit: Any = None               # RuleRouteResult | None
    case_hit: Any = None               # CaseRouteResult | None
    llm_hit: Any = None                # LLMRouteResult | None
    arbiter_reason: str = ""
    fallback_reason: str = ""
    route_labels: list[str] = field(default_factory=list)

    def to_evidence_json(self) -> str:
        """Serialise evidence summary for persistence."""
        d: dict[str, Any] = {
            "category": self.category,
            "confidence": round(self.confidence, 4),
            "source": self.confidence_source,
        }
        if self.rule_hit:
            d["rule"] = {
                "category": self.rule_hit.category,
                "conf": round(self.rule_hit.rule_conf, 4),
                "rule_id": self.rule_hit.rule_id,
            }
        if self.case_hit:
            d["case"] = {
                "category": self.case_hit.category,
                "conf": round(self.case_hit.case_conf, 4),
                "case_id": self.case_hit.case_id,
            }
        if self.llm_hit:
            d["llm"] = {
                "category": self.llm_hit.category,
                "conf": round(self.llm_hit.confidence, 4),
                "rationale": self.llm_hit.rationale,
            }
        if self.arbiter_reason:
            d["reason"] = self.arbiter_reason
        return json.dumps(d, ensure_ascii=False)


# ── Public API ────────────────────────────────────────────────────

def fuse(
    rule_hit: RuleRouteResult | None,
    case_hit: CaseRouteResult | None,
    *,
    user_text: str = "",
) -> FusedResult:
    """Merge rule and case evidence into one decision.

    When only case evidence exists (``case_only``), a lightweight strong-signal
    check is applied to catch obvious misclassifications (e.g. "1+1=?" wrongly
    tagged as *search* by case history).
    """
    result = FusedResult()

    if rule_hit and case_hit:
        if rule_hit.category == case_hit.category:
            result.category = rule_hit.category
            result.confidence = (
                rule_hit.rule_conf * _RULE_WEIGHT
                + case_hit.case_conf * _CASE_WEIGHT
            )
            result.confidence_source = "fused"
            result.arbiter_reason = "rule_case_agree"
            result.route_labels = [m.category for m in rule_hit.all_matches]
        else:
            if rule_hit.rule_conf >= case_hit.case_conf:
                result.category = rule_hit.category
                result.confidence = rule_hit.rule_conf
                result.confidence_source = "rule"
                result.route_labels = [m.category for m in rule_hit.all_matches]
            else:
                result.category = case_hit.category
                result.confidence = case_hit.case_conf
                result.confidence_source = "case"
                result.route_labels = [case_hit.category]
            result.arbiter_reason = "rule_case_conflict"
        result.rule_hit = rule_hit
        result.case_hit = case_hit
        result.risk_level = rule_hit.risk_level

    elif rule_hit:
        result.category = rule_hit.category
        result.confidence = rule_hit.rule_conf
        result.confidence_source = "rule"
        result.arbiter_reason = "rule_only"
        result.rule_hit = rule_hit
        result.risk_level = rule_hit.risk_level
        result.route_labels = [m.category for m in rule_hit.all_matches]

    elif case_hit:
        result.category = case_hit.category
        result.confidence = case_hit.case_conf
        result.confidence_source = "case"
        result.arbiter_reason = "case_only"
        result.case_hit = case_hit
        result.route_labels = [case_hit.category]

        # ── Strong-signal override for case_only ──
        if user_text:
            override = _strong_signal_override(user_text, case_hit.category)
            if override:
                cat, conf, reason = override
                log.info(
                    "[arbiter] strong_signal override: %s → %s (was case=%s conf=%.3f)",
                    reason, cat, case_hit.category, case_hit.case_conf,
                )
                result.category = cat
                result.confidence = conf
                result.confidence_source = "rule"
                result.arbiter_reason = reason
                result.route_labels = [cat]

    else:
        result.category = "general"
        result.confidence = 0.5
        result.confidence_source = "rule"
        result.arbiter_reason = "no_evidence"
        result.fallback_reason = "no_rule_no_case"
        result.route_labels = ["general"]

    return result


def should_call_llm(
    fused: FusedResult,
    rule_hit: RuleRouteResult | None,
    case_hit: CaseRouteResult | None,
    context: dict[str, Any] | None = None,
) -> bool:
    """Determine whether the LLM should arbitrate this decision.

    Cold-start is now **inferred** from evidence rather than relying on the
    caller to pass a flag.  A task is considered cold-start when no case was
    found *and* the rule evidence alone is weak (< threshold).
    """
    ctx = context or {}
    if not ctx.get("llm_enabled", True):
        return False

    if fused.confidence < _LLM_TRIGGER_CONF:
        return True

    if fused.category == "general" and fused.fallback_reason:
        return True

    if rule_hit and case_hit and rule_hit.category != case_hit.category:
        gap = abs(rule_hit.rule_conf - case_hit.case_conf)
        if gap < _CONFLICT_THRESHOLD:
            return True

    if fused.risk_level == "high":
        rule_conf = rule_hit.rule_conf if rule_hit else 0
        if rule_conf < _HIGH_RISK_RULE_MIN:
            return True

    # Cold-start: no case evidence and rule evidence is weak / absent.
    if case_hit is None:
        rule_conf = rule_hit.rule_conf if rule_hit else 0
        if rule_conf < 0.80:
            return True

    return False


def fuse_with_llm(fused: FusedResult, llm_hit: LLMRouteResult) -> FusedResult:
    """Incorporate LLM classification into an existing fused result."""
    fused.llm_hit = llm_hit

    if fused.confidence_source == "fused" and fused.arbiter_reason == "rule_case_agree":
        fused.confidence = min(1.0, fused.confidence + llm_hit.confidence * 0.15)
        fused.arbiter_reason = "rule_case_agree_llm_boost"
    elif fused.arbiter_reason in ("rule_case_conflict", "no_evidence", "case_only"):
        if llm_hit.confidence > fused.confidence:
            fused.category = llm_hit.category
            fused.confidence = llm_hit.confidence
            fused.confidence_source = "llm"
            fused.route_labels = [llm_hit.category]
        fused.arbiter_reason = f"{fused.arbiter_reason}_llm_resolved"
    else:
        blend = fused.confidence * 0.7 + llm_hit.confidence * 0.3
        if llm_hit.confidence > fused.confidence and llm_hit.category != fused.category:
            fused.category = llm_hit.category
            fused.route_labels = [llm_hit.category]
        fused.confidence = min(1.0, blend)
        fused.confidence_source = "fused"
        fused.arbiter_reason = f"{fused.arbiter_reason}_llm_blend"

    if llm_hit.risk_level == "high":
        from myxai_desk.core.intent_engine.categories import get_risk
        fused.risk_level = max(
            fused.risk_level, llm_hit.risk_level,
            key=lambda r: {"low": 0, "medium": 1, "high": 2}.get(r, 0),
        )

    return fused


# ── Plan reuse decision (legacy, preserved) ───────────────────────

def maybe_reuse(
    user_text: str,
    predict_result: PredictResult,
    context: dict[str, Any] | None = None,
) -> tuple[str, list[dict] | None]:
    """Decide whether to reuse a cached plan.

    Returns ``("reuse_plan", steps)`` or ``("llm", None)``.
    """
    cfg = ie_config.get()
    sim_threshold = cfg.get("case_reuse_sim_threshold", 0.92)
    high_risk_tools = set(cfg.get("high_risk_tools", ["exec"]))

    try:
        from myxai_desk.core.intent_engine.case_store import search_similar
        matches = search_similar(user_text, top_k=1, min_sim=sim_threshold)
    except Exception:
        log.debug("[arbiter] case search failed", exc_info=True)
        return "llm", None

    if not matches:
        return "llm", None

    best = matches[0]
    sim = best.get("similarity", 0)
    outcome = best.get("outcome", "")
    plan_raw = best.get("plan_json", "[]")

    if outcome != "success":
        return "llm", None

    if sim < sim_threshold:
        return "llm", None

    if isinstance(plan_raw, str):
        try:
            plan_steps = json.loads(plan_raw)
        except Exception:
            return "llm", None
    else:
        plan_steps = plan_raw

    if not isinstance(plan_steps, list) or not plan_steps:
        return "llm", None

    case_route = best.get("route_label", "")
    current_route = ",".join(predict_result.route_labels)
    if case_route and current_route and case_route != current_route:
        return "llm", None

    for step in plan_steps:
        tool = step.get("tool_name", "")
        if tool in high_risk_tools:
            log.info("[arbiter] rejecting reuse: high-risk tool %s", tool)
            return "llm", None

    log.info("[arbiter] reuse plan from case %s (sim=%.3f, steps=%d)",
             best.get("id", "?"), sim, len(plan_steps))
    return "reuse_plan", plan_steps
