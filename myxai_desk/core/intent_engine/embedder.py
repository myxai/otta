"""Text embedding for case retrieval.

Uses LiteLLM embedding API when available.  Falls back to a deterministic
hash-based fingerprint **only for exact-match cache keys** — it is NOT
suitable for semantic similarity search and callers can detect this via
``is_semantic()``.

The embedding dimension is auto-detected on first successful LiteLLM call
and cached so that the HNSW index always uses a consistent dim.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from collections import Counter
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

log = logging.getLogger("myxai")

_HASH_DIM = 128
_DIM_CACHE_FILE = Path.home() / ".nanobot" / "models" / "intent_engine" / "embed_dim.json"
_lock = Lock()

_resolved_dim: int | None = None
_provider_available: bool | None = None


def _load_dim_cache() -> int | None:
    try:
        if _DIM_CACHE_FILE.exists():
            data = json.loads(_DIM_CACHE_FILE.read_text(encoding="utf-8"))
            return int(data["dim"])
    except Exception:
        pass
    return None


def _save_dim_cache(dim: int) -> None:
    try:
        _DIM_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _DIM_CACHE_FILE.write_text(json.dumps({"dim": dim}), encoding="utf-8")
    except Exception:
        pass


def get_dim() -> int:
    """Return the expected embedding dimension.

    Tries cached LiteLLM dim first, then falls back to hash dim.
    """
    global _resolved_dim
    if _resolved_dim is not None:
        return _resolved_dim
    cached = _load_dim_cache()
    if cached:
        _resolved_dim = cached
        return cached
    return _HASH_DIM


def is_semantic() -> bool:
    """True when the embedding provider produces real semantic vectors."""
    return _provider_available is True


def embed_text(text: str) -> list[float] | None:
    """Return an embedding vector for *text*.

    Tries LiteLLM first.  On failure, returns a hash-based vector of
    ``_HASH_DIM`` dimensions, but marks the provider as unavailable so
    callers can choose to ignore low-quality results.
    """
    vec = _embed_litellm(text)
    if vec is not None:
        return vec
    return _embed_hash(text)


# ── LiteLLM embedding ─────────────────────────────────────────────

def _get_embedding_config() -> dict | None:
    try:
        from nanobot.config.loader import load_config
        config = load_config()
        model = config.agents.defaults.model
        p = config.get_provider(model)
        if not p.api_key:
            return None
        return {
            "api_key": p.api_key,
            "api_base": getattr(p, "api_base", None),
        }
    except Exception:
        return None


def _embed_litellm(text: str) -> list[float] | None:
    global _resolved_dim, _provider_available
    cfg = _get_embedding_config()
    if not cfg:
        _provider_available = False
        return None
    try:
        import os
        os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
        import litellm
        resp = litellm.embedding(
            model="text-embedding-3-small",
            input=[text[:8000]],
            api_key=cfg["api_key"],
            api_base=cfg.get("api_base"),
        )
        vec = resp.data[0]["embedding"]

        with _lock:
            if _resolved_dim is None:
                _resolved_dim = len(vec)
                _save_dim_cache(_resolved_dim)
                log.info("[ie_embed] auto-detected embedding dim=%d", _resolved_dim)
            elif len(vec) != _resolved_dim:
                log.error(
                    "[ie_embed] dim mismatch: got %d, expected %d — dropping vector",
                    len(vec), _resolved_dim,
                )
                return None

        _provider_available = True
        return vec
    except Exception:
        log.debug("[ie_embed] litellm embedding failed", exc_info=True)
        _provider_available = False
        return None


# ── Hash-based fallback embedding ──────────────────────────────────

_STOP_WORDS = {"的", "了", "是", "在", "我", "有", "和", "就", "不", "人",
               "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
               "你", "会", "着", "没有", "看", "好", "自己", "这", "他", "她",
               "the", "a", "an", "is", "are", "was", "were", "be", "been",
               "to", "of", "and", "in", "that", "it", "for", "on", "with"}


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[\u4e00-\u9fff]|[a-zA-Z]+", text.lower())
    return [t for t in tokens if t not in _STOP_WORDS]


def _embed_hash(text: str) -> list[float]:
    """Deterministic hash-based embedding.

    Useful ONLY for exact/near-exact text cache lookups — not for semantic
    similarity.  Callers should check ``is_semantic()`` before trusting
    similarity scores from this path.
    """
    dim = _HASH_DIM
    tokens = _tokenize(text)
    vec = [0.0] * dim
    if not tokens:
        return vec
    counts = Counter(tokens)
    for token, freq in counts.items():
        h = hashlib.md5(token.encode("utf-8")).hexdigest()
        for i in range(0, min(len(h), dim * 2), 2):
            idx = (int(h[i:i+2], 16)) % dim
            sign = 1.0 if int(h[i], 16) < 8 else -1.0
            vec[idx] += sign * math.log1p(freq)
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]
