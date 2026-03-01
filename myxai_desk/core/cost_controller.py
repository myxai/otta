"""Cost controller — upgrades budget tracking from bookkeeping to decision-making.

Evaluates current spending against configured limits and returns an
actionable *CostDecision* before each LLM call.  The decision controls:

- **model_tier**: which model tier to use (turbo / plus / max)
- **allow_llm**: whether LLM calls are allowed at all
- **fallback**: what to do if LLM is blocked (reuse / deterministic / reject)
- **reason**: human-readable explanation for observability

The controller reads the same token/cost config used by the dashboard
(``token_cost_config.json``) so there is a single source of truth.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

log = logging.getLogger("myxai")

# Tier thresholds (percentage of daily limit consumed)
_TIER_PLUS_PCT = 60    # switch from max → plus at 60%
_TIER_TURBO_PCT = 80   # switch from plus → turbo at 80%
_BLOCK_LLM_PCT = 100   # block LLM entirely at 100%


@dataclass
class CostDecision:
    """Actionable output of the cost controller."""

    allow_llm: bool = True
    model_tier: str = "max"       # max | plus | turbo
    fallback: str = "none"        # none | reuse | deterministic | reject
    reason: str = ""
    daily_usage_pct: float = 0.0
    monthly_usage_pct: float = 0.0
    budget_remaining_tokens: int = 0


def evaluate(
    *,
    route_label: str = "",
    security_mode: str = "",
    ie_result: Any | None = None,
) -> CostDecision:
    """Evaluate budget state and return a cost decision.

    This is the main entry point — called before the LLM loop.
    """
    decision = CostDecision()

    try:
        usage = _get_today_usage()
        cost_cfg = _get_cost_config()
    except Exception:
        log.debug("[cost_controller] failed to load usage/config", exc_info=True)
        return decision

    daily_limit = cost_cfg.get("dailyLimit", 0)
    monthly_limit = cost_cfg.get("monthlyLimit", 0)

    if daily_limit <= 0 and monthly_limit <= 0:
        return decision

    total_today = usage.get("total_tokens", 0)

    # Daily percentage
    if daily_limit > 0:
        daily_limit_tokens = daily_limit * 1_000_000
        decision.daily_usage_pct = round(total_today / daily_limit_tokens * 100, 1)
        decision.budget_remaining_tokens = max(0, int(daily_limit_tokens - total_today))

    # Monthly percentage
    if monthly_limit > 0:
        monthly_tokens = _get_monthly_tokens()
        monthly_limit_tokens = monthly_limit * 1_000_000
        decision.monthly_usage_pct = round(monthly_tokens / monthly_limit_tokens * 100, 1)

    max_pct = max(decision.daily_usage_pct, decision.monthly_usage_pct)

    has_reuse_path = (
        ie_result is not None
        and hasattr(ie_result, "decision")
        and ie_result.decision == "reuse_plan"
    )

    if max_pct >= _BLOCK_LLM_PCT:
        decision.allow_llm = False
        decision.model_tier = "turbo"
        decision.fallback = "reuse" if has_reuse_path else "deterministic"
        decision.reason = (
            f"daily budget exhausted ({decision.daily_usage_pct:.0f}% used)"
            if decision.daily_usage_pct >= _BLOCK_LLM_PCT
            else f"monthly budget exhausted ({decision.monthly_usage_pct:.0f}% used)"
        )
        log.warning("[cost_controller] LLM blocked: %s", decision.reason)
    elif max_pct >= _TIER_TURBO_PCT:
        decision.model_tier = "turbo"
        decision.reason = f"budget high ({max_pct:.0f}%), downgraded to turbo"
        log.info("[cost_controller] %s", decision.reason)
    elif max_pct >= _TIER_PLUS_PCT:
        decision.model_tier = "plus"
        decision.reason = f"budget moderate ({max_pct:.0f}%), downgraded to plus"
        log.info("[cost_controller] %s", decision.reason)

    return decision


def select_model(base_model: str, tier: str) -> str:
    """Map a base model name to the appropriate tier variant.

    This uses simple heuristics on model name patterns.  Projects can
    override by providing an explicit ``model_tiers`` mapping in
    ``desk_settings.json``.
    """
    if tier == "max" or not base_model:
        return base_model

    overrides = _get_tier_overrides()
    if overrides:
        mapped = overrides.get(tier)
        if mapped:
            return mapped

    model_lower = base_model.lower()

    if tier == "turbo":
        if "claude" in model_lower:
            return base_model.replace("sonnet", "haiku").replace("opus", "haiku")
        if "gpt-4" in model_lower:
            return base_model.replace("gpt-4o", "gpt-4o-mini").replace("gpt-4", "gpt-4o-mini")
        if "deepseek" in model_lower and "chat" not in model_lower:
            return base_model.replace("deepseek-reasoner", "deepseek-chat")
        return base_model

    if tier == "plus":
        if "claude" in model_lower and "opus" in model_lower:
            return base_model.replace("opus", "sonnet")
        if "gpt-4o" in model_lower and "mini" not in model_lower:
            return base_model
        return base_model

    return base_model


# ── Internal helpers ─────────────────────────────────────────────


def _get_today_usage() -> dict:
    from apps.llm_utils import get_token_usage
    return get_token_usage()


def _get_monthly_tokens() -> int:
    try:
        from apps.llm_utils import get_token_history
        history = get_token_history(days=30)
        return sum(d.get("tokens", 0) for d in history)
    except Exception:
        return 0


def _get_cost_config() -> dict:
    try:
        from myxai_desk.core.token_cost_service import get_token_cost_config
        return get_token_cost_config()
    except Exception:
        return {}


def _get_tier_overrides() -> dict:
    """Load optional explicit model tier mappings from desk_settings."""
    try:
        from myxai_desk.core.intent_engine.config import get as ie_get
        cfg = ie_get()
        return cfg.get("model_tiers", {})
    except Exception:
        return {}
