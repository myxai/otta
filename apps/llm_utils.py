"""Shared LLM call utility for all apps."""

import json
import os
import threading
from datetime import date, timedelta
from pathlib import Path

_KNOWN_LITELLM_PREFIXES = (
    "openai/", "azure/", "anthropic/", "bedrock/", "vertex_ai/",
    "cohere/", "huggingface/", "ollama/", "deepseek/", "groq/",
    "together_ai/", "openrouter/", "gemini/", "mistral/",
)

_USAGE_DIR = Path.home() / ".nanobot" / "usage"
_TOKEN_FILE = _USAGE_DIR / "token_usage.json"
_TASK_FILE = _USAGE_DIR / "task_usage.json"

_token_lock = threading.Lock()
# {"2026-02-23": {"input": 800, "output": 700}, ...}
_token_data: dict[str, dict] = {}
_loaded = False

_task_lock = threading.Lock()
# {"2026-02-24": {"chat": {"input":..,"output":..,"search":..,"count":..}, ...}}
_task_data: dict[str, dict] = {}
_task_loaded = False


def _ensure_loaded():
    global _token_data, _loaded
    if _loaded:
        return
    _USAGE_DIR.mkdir(parents=True, exist_ok=True)
    if _TOKEN_FILE.exists():
        try:
            raw = json.loads(_TOKEN_FILE.read_text(encoding="utf-8"))
            for k, v in raw.items():
                if isinstance(v, int):
                    _token_data[k] = {"input": v, "output": 0}
                elif isinstance(v, dict):
                    _token_data[k] = v
        except Exception:
            _token_data = {}
    _loaded = True


def _persist():
    try:
        _USAGE_DIR.mkdir(parents=True, exist_ok=True)
        _TOKEN_FILE.write_text(
            json.dumps(_token_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def record_tokens(prompt_tokens: int = 0, completion_tokens: int = 0):
    with _token_lock:
        _ensure_loaded()
        today = date.today().isoformat()
        day = _token_data.setdefault(today, {"input": 0, "output": 0})
        day["input"] = day.get("input", 0) + prompt_tokens
        day["output"] = day.get("output", 0) + completion_tokens
        _persist()


def get_token_usage() -> dict:
    with _token_lock:
        _ensure_loaded()
        today = date.today().isoformat()
        day = _token_data.get(today, {"input": 0, "output": 0})
        return {
            "date": today,
            "input_tokens": day.get("input", 0),
            "output_tokens": day.get("output", 0),
            "total_tokens": day.get("input", 0) + day.get("output", 0),
        }


def get_token_history(days: int = 30) -> list[dict]:
    """Return daily token usage for the last N days."""
    with _token_lock:
        _ensure_loaded()
        result = []
        today = date.today()
        for i in range(days):
            d = (today - timedelta(days=days - 1 - i)).isoformat()
            day = _token_data.get(d, {"input": 0, "output": 0})
            inp = day.get("input", 0) if isinstance(day, dict) else day
            out = day.get("output", 0) if isinstance(day, dict) else 0
            result.append({"date": d, "input": inp, "output": out, "tokens": inp + out})
        return result


def _ensure_task_loaded():
    global _task_data, _task_loaded
    if _task_loaded:
        return
    _USAGE_DIR.mkdir(parents=True, exist_ok=True)
    if _TASK_FILE.exists():
        try:
            _task_data = json.loads(_TASK_FILE.read_text(encoding="utf-8"))
        except Exception:
            _task_data = {}
    _task_loaded = True


def _persist_task():
    try:
        _USAGE_DIR.mkdir(parents=True, exist_ok=True)
        _TASK_FILE.write_text(
            json.dumps(_task_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"[llm_utils] _persist_task error: {e}")


def record_task_usage(
    category: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    search_calls: int = 0,
):
    """Record per-category, per-day usage (tokens + search + call count)."""
    try:
        with _task_lock:
            _ensure_task_loaded()
            today = date.today().isoformat()
            day = _task_data.setdefault(today, {})
            cat = day.setdefault(category, {"input": 0, "output": 0, "search": 0, "count": 0})
            cat["input"] += prompt_tokens
            cat["output"] += completion_tokens
            cat["search"] += search_calls
            cat["count"] += 1
            _persist_task()
        print(f"[llm_utils] record_task_usage: {category} +{prompt_tokens}/{completion_tokens} (file={'exists' if _TASK_FILE.exists() else 'MISSING'})")
    except Exception as e:
        print(f"[llm_utils] record_task_usage error: {e}")


def get_category_usage(days: int = 7) -> dict:
    """Return aggregated per-category usage over the last *days* days."""
    with _task_lock:
        _ensure_task_loaded()
        today = date.today()
        merged: dict[str, dict] = {}
        for i in range(days):
            d = (today - timedelta(days=i)).isoformat()
            day = _task_data.get(d, {})
            for cat, vals in day.items():
                if not isinstance(vals, dict):
                    continue
                if cat not in merged:
                    merged[cat] = {"input": 0, "output": 0, "search": 0, "count": 0}
                merged[cat]["input"] += vals.get("input", 0)
                merged[cat]["output"] += vals.get("output", 0)
                merged[cat]["search"] += vals.get("search", 0)
                merged[cat]["count"] += vals.get("count", 0)

    if not merged:
        with _token_lock:
            _ensure_loaded()
            total_in = 0
            total_out = 0
            for i in range(days):
                d = (today - timedelta(days=i)).isoformat()
                day = _token_data.get(d, {})
                if isinstance(day, dict):
                    total_in += day.get("input", 0)
                    total_out += day.get("output", 0)
            if total_in or total_out:
                merged["chat"] = {
                    "input": total_in, "output": total_out,
                    "search": 0, "count": max((total_in + total_out) // 3000, 1),
                }

    return {"categories": merged, "days": days}


def snapshot_today_tokens() -> dict:
    """Return a snapshot of today's global token totals for diff-based tracking."""
    with _token_lock:
        _ensure_loaded()
        today = date.today().isoformat()
        day = _token_data.get(today, {"input": 0, "output": 0})
        return {"input": day.get("input", 0), "output": day.get("output", 0)}


def litellm_model_name(model: str, api_base: str | None) -> str:
    """Ensure *model* has a provider prefix that litellm understands."""
    if any(model.startswith(p) for p in _KNOWN_LITELLM_PREFIXES):
        return model
    if api_base:
        return f"openai/{model}"
    return model


def llm_call(
    messages: list[dict],
    model: str,
    api_key: str,
    api_base: str | None = None,
    temperature: float = 0.5,
    max_tokens: int = 2048,
) -> str:
    """Thin wrapper around litellm.completion with auto provider detection."""
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    import litellm

    resolved = litellm_model_name(model, api_base)
    resp = litellm.completion(
        model=resolved,
        messages=messages,
        api_key=api_key,
        api_base=api_base,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    usage = getattr(resp, "usage", None)
    if usage:
        record_tokens(
            prompt_tokens=getattr(usage, "prompt_tokens", 0),
            completion_tokens=getattr(usage, "completion_tokens", 0),
        )
    return resp.choices[0].message.content or ""
