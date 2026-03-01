"""Nightly semantic learner — LLM-powered incremental learning for Intent Engine.

Architecture: LLM only runs offline (nightly), outputs are versioned local assets.
White day: zero LLM calls, consume learned assets only.
Night:     aggregate → sanitize → LLM → persist → version control.

Privacy: PII sanitized before LLM. Full audit trail (what was sent, what was learned).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, date, timedelta, timezone
from typing import Any, Dict, List
from uuid import uuid4

log = logging.getLogger("myxai")

# ── PII Sanitization ──────────────────────────────────────────────

_PII_PATTERNS = [
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[EMAIL]'),
    (re.compile(r'\b1[3-9]\d{9}\b'), '[PHONE]'),
    (re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'), '[PHONE]'),
    (re.compile(r'[A-Za-z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*'), '[PATH]'),
    (re.compile(r'/(?:home|usr|var|tmp|etc|opt|Users)/[^\s]+'), '[PATH]'),
    (re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'), '[IP]'),
    (re.compile(r'https?://[^\s]+'), '[URL]'),
]


def sanitize_text(text: str) -> str:
    """Remove PII (email, phone, paths, IP, URL) before sending to LLM."""
    if not text:
        return text
    t = text
    for pattern, replacement in _PII_PATTERNS:
        t = pattern.sub(replacement, t)
    return t


# ── Trigger Conditions ────────────────────────────────────────────

@dataclass
class LearningTrigger:
    new_runs_min: int = 20
    misroute_min: int = 5
    case_key_split_threshold: float = 0.3

    def should_trigger(self, stats: Dict[str, Any]) -> tuple[bool, str]:
        new_runs = stats.get("new_runs", 0)
        misroutes = stats.get("misroute_suspects", 0)
        split_rate = stats.get("case_key_split_rate", 0.0)

        if new_runs >= self.new_runs_min:
            return True, f"new_runs={new_runs} >= {self.new_runs_min}"
        if misroutes >= self.misroute_min:
            return True, f"misroutes={misroutes} >= {self.misroute_min}"
        if split_rate > self.case_key_split_threshold:
            return True, f"case_key_split={split_rate:.2%} > {self.case_key_split_threshold:.2%}"
        return False, "no trigger conditions met"


# ── Data Aggregation ──────────────────────────────────────────────

def get_daily_stats(target_date: date | None = None) -> Dict[str, Any]:
    """Aggregate ie_runs statistics for a given date."""
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    try:
        from myxai_desk.core.storage.sqlite import execute
        date_str = target_date.isoformat()

        rows = execute(
            "SELECT COUNT(*) as cnt FROM ie_runs WHERE local_date = ?",
            (date_str,), readonly=True,
        )
        new_runs = rows[0]["cnt"] if rows else 0

        rows = execute(
            "SELECT COUNT(*) as cnt FROM ie_runs WHERE local_date = ? AND misroute_suspect = 1",
            (date_str,), readonly=True,
        )
        misroutes = rows[0]["cnt"] if rows else 0

        rows = execute(
            """SELECT COUNT(DISTINCT case_key) as ukeys, COUNT(*) as total
               FROM ie_runs WHERE local_date = ? AND case_key IS NOT NULL AND case_key != ''""",
            (date_str,), readonly=True,
        )
        ukeys = rows[0]["ukeys"] if rows else 0
        total = rows[0]["total"] if rows else 0
        split_rate = ukeys / total if total > 0 else 0.0

        return {
            "date": date_str, "new_runs": new_runs,
            "misroute_suspects": misroutes, "unique_case_keys": ukeys,
            "total_runs": total, "case_key_split_rate": round(split_rate, 4),
        }
    except Exception:
        log.error("[nightly_learner] get_daily_stats failed", exc_info=True)
        return {"date": (target_date or date.today()).isoformat(), "new_runs": 0, "error": True}


def aggregate_learning_input(
    target_date: date | None = None,
    max_samples: int = 200,
    sanitize: bool = True,
) -> Dict[str, Any]:
    """Aggregate and optionally sanitize data for LLM learning.

    Returns dict with ``successful_runs``, ``misroutes``, ``case_key_freq``,
    and the raw/sanitized text sent to the LLM (for audit).
    """
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    try:
        from myxai_desk.core.storage.sqlite import execute
        date_str = target_date.isoformat()

        rows = execute(
            """SELECT user_text, case_key, route_label, outcome
               FROM ie_runs WHERE local_date = ? AND outcome = 'success'
               ORDER BY created_at DESC LIMIT ?""",
            (date_str, max_samples // 2), readonly=True,
        )
        _s = sanitize_text if sanitize else (lambda x: x)
        successful = [
            {"user_text": _s(r["user_text"] or ""), "case_key": r["case_key"] or "",
             "route_label": r["route_label"] or ""}
            for r in rows
        ]

        rows = execute(
            """SELECT user_text, case_key, route_label, outcome
               FROM ie_runs WHERE local_date = ? AND misroute_suspect = 1
               ORDER BY created_at DESC LIMIT ?""",
            (date_str, max_samples // 4), readonly=True,
        )
        misroutes = [
            {"user_text": _s(r["user_text"] or ""), "case_key": r["case_key"] or "",
             "route_label": r["route_label"] or ""}
            for r in rows
        ]

        rows = execute(
            """SELECT case_key, COUNT(*) as freq
               FROM ie_runs WHERE local_date = ? AND case_key IS NOT NULL AND case_key != ''
               GROUP BY case_key ORDER BY freq DESC LIMIT 50""",
            (date_str,), readonly=True,
        )
        case_key_freq = {r["case_key"]: r["freq"] for r in rows}

        return {
            "date": date_str, "successful_runs": successful,
            "misroutes": misroutes, "case_key_freq": case_key_freq,
            "total_samples": len(successful) + len(misroutes),
            "sanitized": sanitize,
        }
    except Exception:
        log.error("[nightly_learner] aggregate failed", exc_info=True)
        return {"date": (target_date or date.today()).isoformat(), "error": True}


# ── LLM Prompt Generation ────────────────────────────────────────

_LEXICON_SYSTEM = """你是意图识别系统的语言习惯学习助手。
分析用户查询记录(已脱敏)，提取用户特有的语言模式。

输出严格 JSON，包含3个字段：
1. synonyms: 同义词映射（用户缩写/别称→标准形式）
2. verb_map: 动词变体→标准动词（英文）
3. stop_phrases: 需要过滤的用户口头禅

注意：
- 只提取高频模式
- 不要过度泛化（如"的"→""）
- 高风险词（删除/格式化）不要映射为其他动词
仅输出JSON。"""

def _build_lexicon_prompt(input_data: Dict[str, Any]) -> list[dict]:
    """Build messages for user lexicon generation.
    
    Only sends sanitized query text + route labels. No hash keys (they carry
    zero semantic information and would confuse the model).
    """
    samples = input_data.get("successful_runs", [])[:50]
    user_msg = "用户查询样本:\n\n"
    for i, run in enumerate(samples, 1):
        user_msg += f"{i}. {run['user_text']}"
        if run.get("route_label"):
            user_msg += f"  [route:{run['route_label']}]"
        user_msg += "\n"

    misroutes = input_data.get("misroutes", [])[:20]
    if misroutes:
        user_msg += "\n疑似误路由样本:\n\n"
        for i, run in enumerate(misroutes, 1):
            user_msg += f"{i}. {run['user_text']}"
            if run.get("route_label"):
                user_msg += f"  [route:{run['route_label']}]"
            user_msg += "\n"

    return [
        {"role": "system", "content": _LEXICON_SYSTEM},
        {"role": "user", "content": user_msg},
    ]


# ── LLM Call ──────────────────────────────────────────────────────

class LlmCallError(Exception):
    """Raised when LLM call fails, carrying the error detail for audit."""
    pass


def _call_llm(messages: list[dict], max_tokens: int = 1024) -> str:
    """Call LLM for lexicon learning. Always expects JSON object output.
    
    Returns:
        The response content string.
        
    Raises:
        LlmCallError: with descriptive message if anything goes wrong.
    """
    # Use the main model config (same API key / model as chat), not the
    # intent-engine router_model which may use a different cheap key.
    try:
        from app import _get_model_config
        mcfg = _get_model_config()
    except Exception as e:
        raise LlmCallError(f"Failed to load model config: {e}")

    model = mcfg.get("model")
    api_key = mcfg.get("api_key")
    api_base = mcfg.get("api_base")

    if not model or not api_key:
        raise LlmCallError(f"Model config incomplete: model={model}, api_key={'set' if api_key else 'missing'}")

    import os
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

    try:
        import litellm
    except ImportError as e:
        raise LlmCallError(f"litellm not installed: {e}")

    _KNOWN_PREFIXES = (
        "openai/", "anthropic/", "azure/", "deepseek/",
        "groq/", "together_ai/", "openrouter/", "gemini/", "mistral/",
    )
    litellm_model = model
    if not any(model.startswith(px) for px in _KNOWN_PREFIXES) and api_base:
        litellm_model = f"openai/{model}"

    kwargs = {
        "model": litellm_model,
        "messages": messages,
        "api_key": api_key,
        "api_base": api_base,
        "temperature": 0.3,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    
    log.info(f"[nightly_learner] Calling LLM: model={litellm_model}, api_base={api_base}")
    
    try:
        resp = litellm.completion(**kwargs)
    except Exception as e:
        raise LlmCallError(f"litellm.completion() failed: {type(e).__name__}: {e}")

    content = resp.choices[0].message.content or ""
    
    log.info(f"[nightly_learner] LLM raw response ({len(content)} chars): {content[:300]!r}")
    
    content = content.strip()
    
    # Remove markdown code fence if present
    if content.startswith("```"):
        lines = content.split("\n")
        if lines[0].strip().lower() in ("```json", "```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines).strip()

    if not content:
        raise LlmCallError(f"LLM returned empty content (model={model}, raw_len={len(resp.choices[0].message.content or '')})")

    usage = resp.usage
    try:
        from apps.llm_utils import record_task_usage
        record_task_usage(
            "nightly_learning",
            usage.prompt_tokens if usage else 0,
            usage.completion_tokens if usage else 0,
            0,
        )
    except Exception:
        pass

    return content


def _parse_json(raw: str | None) -> Any:
    """Parse JSON from LLM response, handling edge cases."""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        try:
            start = raw.index("{")
            end = raw.rindex("}") + 1
            return json.loads(raw[start:end])
        except (ValueError, json.JSONDecodeError):
            try:
                start = raw.index("[")
                end = raw.rindex("]") + 1
                return json.loads(raw[start:end])
            except (ValueError, json.JSONDecodeError):
                return None


# ── Audit Records ─────────────────────────────────────────────────

def _save_audit_record(
    run_id: str,
    *,
    status: str,
    input_stats: dict,
    prompt_sent: str = "",
    llm_response_raw: str = "",
    artifacts_produced: dict | None = None,
    model_used: str = "",
    token_cost: int = 0,
    error_log: str = "",
) -> None:
    """Persist a full audit record for the nightly learning run."""
    try:
        from myxai_desk.core.storage.sqlite import execute
        now = datetime.now(timezone.utc).isoformat()
        execute(
            """UPDATE semantic_runs SET
                status = ?, input_stats_json = ?, output_artifacts_json = ?,
                model_used = ?, token_cost = ?, error_log = ?, completed_at = ?
               WHERE id = ?""",
            (
                status,
                json.dumps({
                    **input_stats,
                    "prompt_sent": prompt_sent,
                    "llm_response_raw": llm_response_raw,
                }, ensure_ascii=False),
                json.dumps(artifacts_produced or {}, ensure_ascii=False),
                model_used,
                token_cost,
                error_log,
                now,
                run_id,
            ),
        )
    except Exception:
        log.error("[nightly_learner] audit record failed", exc_info=True)


# ── Main Pipeline ─────────────────────────────────────────────────

def run_nightly_learning(
    target_date: date | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> Dict[str, Any]:
    """Run the full nightly learning pipeline.

    Args:
        target_date: Date to analyze (defaults to yesterday)
        dry_run: If True, aggregate + build prompt but skip LLM call
        force: If True, bypass trigger conditions

    Returns:
        Dict with status, run_id, artifacts, audit details
    """
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    from myxai_desk.core.intent_engine import config as ie_config
    from myxai_desk.core.intent_engine.dao import init_ie_tables
    from myxai_desk.core.storage.sqlite import execute

    init_ie_tables()

    cfg = ie_config.get()
    if not cfg.get("nightly_learning_enabled", False) and not force:
        return {"status": "disabled", "reason": "nightly_learning_enabled is False"}

    sanitize = cfg.get("nightly_learning_sanitize_pii", True)
    max_samples = cfg.get("nightly_learning_max_samples", 200)

    run_id = uuid4().hex[:16]
    now = datetime.now(timezone.utc).isoformat()
    execute(
        "INSERT INTO semantic_runs (id, run_date, status, created_at) VALUES (?, ?, 'running', ?)",
        (run_id, target_date.isoformat(), now),
    )

    # --- Check trigger ---
    stats = get_daily_stats(target_date)
    trigger = LearningTrigger(
        new_runs_min=cfg.get("nightly_learning_min_runs", 20),
        misroute_min=cfg.get("nightly_learning_min_misroutes", 5),
    )
    should_run, reason = trigger.should_trigger(stats)

    if not should_run and not force:
        _save_audit_record(run_id, status="skipped", input_stats=stats)
        return {"status": "skipped", "reason": reason, "run_id": run_id, "stats": stats}

    log.info(f"[nightly_learner] Starting: {reason} (force={force})")

    # --- Aggregate ---
    input_data = aggregate_learning_input(target_date, max_samples=max_samples, sanitize=sanitize)

    if dry_run:
        messages = _build_lexicon_prompt(input_data)
        prompt_text = "\n".join(m["content"] for m in messages)
        _save_audit_record(
            run_id, status="dry_run", input_stats={**stats, **input_data},
            prompt_sent=prompt_text,
        )
        return {
            "status": "dry_run", "run_id": run_id, "stats": stats,
            "input_data": input_data, "prompt_preview": prompt_text[:2000],
        }

    if not cfg.get("nightly_learning_use_llm", True):
        _save_audit_record(run_id, status="local_only", input_stats={**stats, **input_data})
        return {"status": "local_only", "run_id": run_id, "reason": "LLM disabled by config"}

    # --- LLM Call: User Lexicon (single task, single output) ---
    artifacts: Dict[str, Any] = {}
    lexicon_messages = _build_lexicon_prompt(input_data)
    lexicon_prompt_text = "\n\n---\n\n".join(f"[{m['role']}]\n{m['content']}" for m in lexicon_messages)
    lexicon_raw = ""
    error_msg = ""
    final_status = "completed"
    
    try:
        from app import _get_model_config
        model_used = _get_model_config().get("model", "unknown")
    except Exception:
        model_used = "unknown"

    try:
        lexicon_raw = _call_llm(lexicon_messages, max_tokens=2048)
        lexicon_data = _parse_json(lexicon_raw)
        
        if lexicon_data and isinstance(lexicon_data, dict):
            syn = lexicon_data.get("synonyms", {})
            verb = lexicon_data.get("verb_map", {})
            stop = lexicon_data.get("stop_phrases", [])
            
            if syn or verb or stop:
                from myxai_desk.core.intent_engine.user_lexicon import save_lexicon
                lid = save_lexicon(
                    synonyms=syn, verb_map=verb, stop_phrases=stop,
                    source="nightly_learning",
                )
                artifacts["lexicon_id"] = lid
                artifacts["lexicon_learned"] = {"synonyms": len(syn), "verbs": len(verb), "stop_phrases": len(stop)}
                log.info(f"[nightly_learner] Lexicon saved: {lid} (syn={len(syn)}, verb={len(verb)}, stop={len(stop)})")
            else:
                artifacts["lexicon_empty"] = True
                log.info("[nightly_learner] Lexicon: valid but empty (no patterns in samples)")
        elif lexicon_data is None:
            final_status = "error"
            error_msg = f"JSON parse failed. Raw response: {lexicon_raw[:500]}"
            artifacts["lexicon_parse_error"] = error_msg
            log.warning(f"[nightly_learner] Lexicon parse failed, raw={lexicon_raw!r}")
        else:
            final_status = "error"
            error_msg = f"Expected dict, got {type(lexicon_data).__name__}: {str(lexicon_data)[:300]}"
            artifacts["lexicon_type_error"] = error_msg
            log.warning(f"[nightly_learner] Lexicon wrong type: {lexicon_data!r}")

    except LlmCallError as e:
        final_status = "error"
        error_msg = str(e)
        artifacts["llm_error"] = error_msg
        log.error(f"[nightly_learner] LLM call error: {e}")
    except Exception as e:
        final_status = "error"
        error_msg = f"{type(e).__name__}: {e}"
        artifacts["unexpected_error"] = error_msg
        log.error(f"[nightly_learner] Unexpected error", exc_info=True)

    # --- Audit ---
    _save_audit_record(
        run_id,
        status=final_status,
        input_stats={**stats, "total_samples": input_data.get("total_samples", 0)},
        prompt_sent=lexicon_prompt_text,
        llm_response_raw=lexicon_raw or "",
        artifacts_produced=artifacts,
        model_used=model_used,
        error_log=error_msg,
    )

    log.info(f"[nightly_learner] Done: status={final_status}, artifacts={list(artifacts.keys())}")
    return {"status": final_status, "run_id": run_id, "stats": stats, "artifacts": artifacts}


# ── Query Functions (for UI) ──────────────────────────────────────

def get_learning_runs(limit: int = 20, offset: int = 0) -> list[dict]:
    """Get paginated list of nightly learning runs."""
    try:
        from myxai_desk.core.storage.sqlite import execute
        from myxai_desk.core.intent_engine.dao import init_ie_tables
        init_ie_tables()
        rows = execute(
            """SELECT id, run_date, status, model_used, token_cost,
                      error_log, created_at, completed_at
               FROM semantic_runs
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (limit, offset), readonly=True,
        )
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_learning_run_detail(run_id: str) -> dict | None:
    """Get full detail of a learning run (including audit: what was sent, learned)."""
    try:
        from myxai_desk.core.storage.sqlite import execute
        rows = execute(
            "SELECT * FROM semantic_runs WHERE id = ?",
            (run_id,), readonly=True,
        )
        if not rows:
            return None
        row = dict(rows[0])
        for k in ("input_stats_json", "output_artifacts_json"):
            if row.get(k):
                try:
                    row[k] = json.loads(row[k])
                except Exception:
                    pass
        return row
    except Exception:
        return None
