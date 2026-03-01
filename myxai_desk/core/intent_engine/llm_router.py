"""LLM router — uses a language model for intent classification arbitration.

Only called when rule + case evidence is insufficient (low confidence,
conflict, cold start, or high-risk with weak evidence).  Designed to be
toggleable and to degrade gracefully when offline.

Cost control:  Uses a dedicated ``router_model`` (IE config key) that
defaults to a cheap/fast model, separate from the main executor model.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

log = logging.getLogger("myxai")

_VALID_CATEGORIES = frozenset({
    "search", "fs", "browser", "net", "system",
    "schedule", "comm", "general", "chat",
})

_HIGH_RISK_DISCOUNT = 0.85

_SYSTEM_PROMPT = """你是 Intent Router Arbiter。根据用户输入，输出 JSON：
{
  "category": "search|fs|browser|net|system|schedule|comm|general|chat",
  "risk_level": "low|medium|high",
  "confidence": 0.0-1.0,
  "case_key": "简短稳定的意图key（英文或拼音均可）",
  "rationale": "不超过20字的理由"
}
规则：
- 如果不确定，降低 confidence，不要硬猜。
- 高风险（fs/system）只有在有明确动词/对象时才能给高置信。
仅输出 JSON。"""


@dataclass
class LLMRouteResult:
    category: str
    risk_level: str
    confidence: float
    case_key: str
    rationale: str


def classify(user_text: str, context: dict | None = None) -> LLMRouteResult | None:
    """Call an LLM to classify intent. Returns None on failure or when disabled."""
    ctx = context or {}
    if not ctx.get("llm_enabled", True):
        return None

    try:
        raw = _call_llm(user_text)
        if raw is None:
            return None
        return _parse_response(raw)
    except Exception:
        log.debug("[llm_router] classify failed", exc_info=True)
        return None


def _resolve_model_and_provider() -> tuple[str, object] | None:
    """Resolve which model + provider to use for routing.

    Priority:
      1. ``intent_engine.router_model`` in desk_settings.json (cheap/fast)
      2. Fall back to the main ``agents.defaults.model``
    """
    try:
        from nanobot.config.loader import load_config
        from myxai_desk.core.intent_engine import config as ie_config
        config = load_config()

        router_model = ie_config.get("router_model")
        if router_model:
            try:
                p = config.get_provider(router_model)
                if p and p.api_key:
                    return router_model, p
            except Exception:
                log.debug("[llm_router] router_model %s unavailable, trying default", router_model)

        model = config.agents.defaults.model
        p = config.get_provider(model)
        if not p.api_key:
            return None
        return model, p
    except Exception:
        log.debug("[llm_router] config load failed", exc_info=True)
        return None


def _call_llm(user_text: str) -> dict | None:
    """Invoke the LLM and parse the JSON response."""
    resolved = _resolve_model_and_provider()
    if resolved is None:
        return None
    model, p = resolved

    try:
        import os
        os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
        import litellm

        api_base = getattr(p, "api_base", None)
        _KNOWN = ("openai/", "anthropic/", "azure/", "deepseek/",
                   "groq/", "together_ai/", "openrouter/", "gemini/", "mistral/")
        litellm_model = model
        if not any(model.startswith(px) for px in _KNOWN) and api_base:
            litellm_model = f"openai/{model}"

        kwargs: dict = {
            "model": litellm_model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_text[:2000]},
            ],
            "api_key": p.api_key,
            "api_base": api_base,
            "temperature": 0.1,
            "max_tokens": 200,
        }

        try:
            resp = litellm.completion(**kwargs, response_format={"type": "json_object"})
        except Exception:
            resp = litellm.completion(**kwargs)

        content = resp.choices[0].message.content or ""
        content = content.strip()
        if content.startswith("```"):
            content = content.strip("`").removeprefix("json").strip()
        return json.loads(content)
    except Exception:
        log.debug("[llm_router] LLM call failed", exc_info=True)
        return None


def _parse_response(data: dict) -> LLMRouteResult | None:
    """Validate and convert the raw LLM JSON into a LLMRouteResult."""
    category = str(data.get("category", "general")).strip().lower()
    if category not in _VALID_CATEGORIES:
        category = "general"

    risk = str(data.get("risk_level", "low")).strip().lower()
    if risk not in ("low", "medium", "high"):
        risk = "low"

    try:
        conf = float(data.get("confidence", 0.5))
        conf = max(0.0, min(1.0, conf))
    except (TypeError, ValueError):
        conf = 0.5

    if risk == "high":
        conf *= _HIGH_RISK_DISCOUNT

    case_key = str(data.get("case_key", ""))[:100]
    rationale = str(data.get("rationale", ""))[:100]

    return LLMRouteResult(
        category=category,
        risk_level=risk,
        confidence=round(conf, 4),
        case_key=case_key,
        rationale=rationale,
    )
