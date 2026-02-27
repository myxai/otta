"""Shared LLM call utility for all apps."""

import json
import logging
import os
import re
import threading
from datetime import date, timedelta
from pathlib import Path

log = logging.getLogger("myxai.apps.llm_utils")

_KNOWN_LITELLM_PREFIXES = (
    "openai/",
    "azure/",
    "anthropic/",
    "bedrock/",
    "vertex_ai/",
    "cohere/",
    "huggingface/",
    "ollama/",
    "deepseek/",
    "groq/",
    "together_ai/",
    "openrouter/",
    "gemini/",
    "mistral/",
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
            log.warning("_ensure_loaded: failed to load token file", exc_info=True)
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
        log.warning("_persist: failed to save token usage", exc_info=True)


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
        inp = day.get("input", 0)
        out = day.get("output", 0)
        return {
            "date": today,
            "input_tokens": inp,
            "output_tokens": out,
            "total_tokens": inp + out,
        }


def calculate_cost(input_tokens: int, output_tokens: int, input_price: float, output_price: float) -> float:
    """Calculate cost in yuan based on token usage and pricing.
    
    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        input_price: Price per million input tokens (in yuan)
        output_price: Price per million output tokens (in yuan)
    
    Returns:
        Total cost in yuan
    """
    input_cost = (input_tokens / 1_000_000) * input_price
    output_cost = (output_tokens / 1_000_000) * output_price
    return input_cost + output_cost


def get_token_usage_with_cost(config: dict | None = None) -> dict:
    """Get today's token usage with cost calculation.
    
    Args:
        config: Configuration dict containing tokenCost settings
    
    Returns:
        Dict with token usage, cost, and alert status
    """
    with _token_lock:
        _ensure_loaded()
        today = date.today().isoformat()
        day = _token_data.get(today, {"input": 0, "output": 0})
        inp = day.get("input", 0)
        out = day.get("output", 0)
        
        result = {
            "date": today,
            "input_tokens": inp,
            "output_tokens": out,
            "total_tokens": inp + out,
            "cost": 0.0,
            "daily_limit": 0.0,
            "monthly_limit": 0.0,
            "daily_usage_pct": 0.0,
            "monthly_usage_pct": 0.0,
            "alert_level": "green",  # green, yellow, red
        }
        
        if config and "tokenCost" in config:
            cost_cfg = config["tokenCost"]
            input_price = cost_cfg.get("inputPrice", 0)
            output_price = cost_cfg.get("outputPrice", 0)
            daily_limit = cost_cfg.get("dailyLimit", 0)  # in M tokens (百万)
            monthly_limit = cost_cfg.get("monthlyLimit", 0)  # in M tokens (百万)
            
            # Calculate cost if prices are set
            if input_price or output_price:
                result["cost"] = calculate_cost(inp, out, input_price, output_price)
            
            result["daily_limit"] = daily_limit
            result["monthly_limit"] = monthly_limit
            
            # Calculate daily percentage based on token count
            if daily_limit > 0:
                daily_limit_tokens = daily_limit * 1000000  # M tokens to tokens
                result["daily_usage_pct"] = ((inp + out) / daily_limit_tokens) * 100
            
            # Calculate monthly percentage (sum of last 30 days)
            monthly_tokens = 0
            monthly_cost = 0.0
            for i in range(30):
                d = (date.today() - timedelta(days=i)).isoformat()
                day_data = _token_data.get(d, {"input": 0, "output": 0})
                day_inp = day_data.get("input", 0)
                day_out = day_data.get("output", 0)
                monthly_tokens += day_inp + day_out
                if input_price or output_price:
                    monthly_cost += calculate_cost(day_inp, day_out, input_price, output_price)
            
            if monthly_limit > 0:
                monthly_limit_tokens = monthly_limit * 1000000  # M tokens to tokens
                result["monthly_usage_pct"] = (monthly_tokens / monthly_limit_tokens) * 100
            
            if input_price or output_price:
                result["monthly_cost"] = monthly_cost
            
            # Determine alert level based on token usage percentage
            max_pct = max(result["daily_usage_pct"], result["monthly_usage_pct"])
            if max_pct >= 100:
                result["alert_level"] = "red"
            elif max_pct >= 80:
                result["alert_level"] = "yellow"
        
        return result


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


def get_cost_history(days: int = 30, config: dict | None = None) -> list[dict]:
    """Return daily token usage with cost for the last N days.
    
    Args:
        days: Number of days to retrieve
        config: Configuration dict containing tokenCost settings
    
    Returns:
        List of dicts with date, tokens, and cost
    """
    with _token_lock:
        _ensure_loaded()
        result = []
        today = date.today()
        
        input_price = 0
        output_price = 0
        if config and "tokenCost" in config:
            cost_cfg = config["tokenCost"]
            input_price = cost_cfg.get("inputPrice", 0)
            output_price = cost_cfg.get("outputPrice", 0)
        
        for i in range(days):
            d = (today - timedelta(days=days - 1 - i)).isoformat()
            day = _token_data.get(d, {"input": 0, "output": 0})
            inp = day.get("input", 0) if isinstance(day, dict) else day
            out = day.get("output", 0) if isinstance(day, dict) else 0
            cost = calculate_cost(inp, out, input_price, output_price)
            result.append({
                "date": d,
                "input": inp,
                "output": out,
                "tokens": inp + out,
                "cost": round(cost, 4)
            })
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
            log.warning("_ensure_task_loaded: failed to load task file", exc_info=True)
            _task_data = {}
    _task_loaded = True


def _persist_task():
    try:
        _USAGE_DIR.mkdir(parents=True, exist_ok=True)
        _TASK_FILE.write_text(
            json.dumps(_task_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        log.exception("[llm_utils] _persist_task error")


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
        log.debug(
            "[llm_utils] record_task_usage: %s +%d/%d (file=%s)",
            category, prompt_tokens, completion_tokens,
            "exists" if _TASK_FILE.exists() else "MISSING",
        )
    except Exception:
        log.exception("[llm_utils] record_task_usage error")


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
                    "input": total_in,
                    "output": total_out,
                    "search": 0,
                    "count": max((total_in + total_out) // 3000, 1),
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
    """Ensure *model* has a provider prefix that litellm understands.
    
    Auto-detection logic:
    1. If model already has a known prefix (e.g., "ollama/qwen3"), respect it
    2. If api_base looks like Ollama, use "ollama/" prefix
    3. If api_base is set but not recognized, use "openai/" prefix (generic)
    4. Otherwise, assume it's a direct model name (e.g., OpenAI official)
    
    Known patterns:
    - Ollama: localhost:11434, 127.0.0.1:11434, *:11434, */ollama/*, ollama.* domains
    - vLLM/llama.cpp: require explicit "openai/" prefix or provider config
    """
    # Respect user's explicit provider prefix
    if any(model.startswith(p) for p in _KNOWN_LITELLM_PREFIXES):
        return model
    
    # No api_base means using default provider (e.g., OpenAI official API)
    if not api_base:
        return model
    
    # Normalize api_base for pattern matching
    base_lower = api_base.lower()
    
    # Detect Ollama endpoints
    ollama_patterns = [
        # Port 11434 (default Ollama port)
        r":11434",
        # Path contains /ollama/
        r"[:/]ollama[:/]",
        # Domain starts with ollama
        r"//ollama\.",
    ]
    
    if any(re.search(pattern, base_lower) for pattern in ollama_patterns):
        log.info(f"[llm_utils] Auto-detected Ollama endpoint: {api_base} → ollama/{model}")
        return f"ollama/{model}"
    
    # For other custom endpoints, default to OpenAI-compatible
    # Users can explicitly pass "provider/model" to override
    log.debug(f"[llm_utils] Using OpenAI-compatible endpoint: {api_base} → openai/{model}")
    return f"openai/{model}"


def llm_call(
    messages: list[dict],
    model: str,
    api_key: str,
    api_base: str | None = None,
    temperature: float = 0.5,
    max_tokens: int = 2048,
) -> str:
    """Thin wrapper around litellm.completion with auto provider detection.
    
    Args:
        messages: Chat messages in OpenAI format
        model: Model name, can include provider prefix (e.g., "ollama/qwen3")
        api_key: API key (use "dummy" for local models)
        api_base: API base URL (auto-detects Ollama endpoints)
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
        
    Returns:
        Generated text content
        
    Raises:
        LLMCallError: Wrapped exception with detailed error info
    """
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    import litellm

    resolved = litellm_model_name(model, api_base)
    
    try:
        log.debug(
            f"[llm_utils] Calling LLM: model={resolved}, "
            f"api_base={api_base}, temp={temperature}, max_tokens={max_tokens}"
        )
        
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
            prompt_tokens = getattr(usage, "prompt_tokens", 0)
            completion_tokens = getattr(usage, "completion_tokens", 0)
            record_tokens(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            log.debug(
                f"[llm_utils] LLM call successful: "
                f"{prompt_tokens} prompt + {completion_tokens} completion tokens"
            )
        
        content = resp.choices[0].message.content or ""
        if not content:
            log.warning("[llm_utils] LLM returned empty content")
        
        return content
        
    except Exception as e:
        error_info = {
            "model": model,
            "resolved_model": resolved,
            "api_base": api_base,
            "error_type": type(e).__name__,
            "error_message": str(e),
        }
        
        # Log detailed error for debugging
        log.error(
            f"[llm_utils] LLM call failed: {error_info['error_type']}: {error_info['error_message']}\n"
            f"  Model: {model} → {resolved}\n"
            f"  API Base: {api_base}\n"
            f"  Messages: {len(messages)} messages"
        )
        
        # Provide user-friendly error messages
        error_msg = f"LLM 调用失败: {error_info['error_type']}"
        
        # Check for common error patterns
        error_str = str(e).lower()
        if "not found" in error_str or "404" in error_str:
            error_msg += f"\n模型 '{model}' 未找到"
            if api_base and "ollama" not in resolved:
                error_msg += f"\n提示: 如果使用 Ollama，请确保 api_base 包含 'ollama' 或使用 localhost:11434"
        elif "unauthorized" in error_str or "401" in error_str or "403" in error_str:
            error_msg += "\nAPI 密钥无效或权限不足"
        elif "connection" in error_str or "timeout" in error_str:
            error_msg += f"\n无法连接到 API 端点: {api_base or 'default'}"
        elif "rate limit" in error_str or "429" in error_str:
            error_msg += "\n请求频率超限，请稍后重试"
        else:
            error_msg += f"\n{error_info['error_message']}"
        
        # Wrap and re-raise with context
        raise LLMCallError(error_msg, original_error=e, **error_info) from e


class LLMCallError(Exception):
    """Wrapper for LLM call errors with detailed context."""
    
    def __init__(self, message: str, original_error: Exception = None, **context):
        super().__init__(message)
        self.original_error = original_error
        self.context = context
    
    def __str__(self):
        return f"{super().__str__()}"
    
    def __repr__(self):
        return f"LLMCallError({self.args[0]!r}, context={self.context})"
