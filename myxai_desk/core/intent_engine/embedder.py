"""Text embedding for case retrieval.

Uses LiteLLM embedding API when available, falls back to a simple
TF-IDF-like fingerprint for offline/no-model scenarios.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

log = logging.getLogger("myxai")

_DIM = 128  # default dimension for fallback embeddings


def embed_text(text: str) -> list[float] | None:
    """Return an embedding vector for *text*.

    Tries LiteLLM first; falls back to a deterministic hash-based vector.
    """
    vec = _embed_litellm(text)
    if vec is not None:
        return vec
    return _embed_hash(text)


def get_dim() -> int:
    """Return the expected embedding dimension."""
    return _DIM


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
    cfg = _get_embedding_config()
    if not cfg:
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
        return vec
    except Exception:
        log.debug("[ie_embed] litellm embedding failed", exc_info=True)
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
    """Deterministic hash-based embedding of fixed dimension."""
    tokens = _tokenize(text)
    vec = [0.0] * _DIM
    if not tokens:
        return vec
    counts = Counter(tokens)
    for token, freq in counts.items():
        h = hashlib.md5(token.encode("utf-8")).hexdigest()
        for i in range(0, min(len(h), _DIM * 2), 2):
            idx = (int(h[i:i+2], 16)) % _DIM
            sign = 1.0 if int(h[i], 16) < 8 else -1.0
            vec[idx] += sign * math.log1p(freq)
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]
