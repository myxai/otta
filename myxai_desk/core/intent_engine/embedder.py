"""Local-first text embedding for Intent Engine case retrieval.

Uses a local sentence-transformers model (zero network dependency).
Falls back to a deterministic hash-based fingerprint when the local model
is unavailable (e.g. dependency not installed). Callers detect this via
``is_semantic()``.

No LiteLLM / OpenAI calls. No network side effects. Deterministic.

Model: ``intfloat/multilingual-e5-small`` (384 dim, ~120-200MB, multilingual).
Override via IE config key ``embedding_model``.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from threading import Lock

log = logging.getLogger("myxai")

_MODEL_DIR = Path.home() / ".nanobot" / "models" / "intent_engine"
_DEFAULT_MODEL = "intfloat/multilingual-e5-small"
_DEFAULT_DIM = 384
_HASH_DIM = 128
_lock = Lock()

_model = None
_model_name: str = ""
_model_dim: int = 0
_provider_available: bool = False
_init_attempted: bool = False


# ── Public API ────────────────────────────────────────────────────

def get_dim() -> int:
    """Return the embedding dimension (model dim when loaded, hash dim otherwise)."""
    if _model_dim > 0:
        return _model_dim
    return _HASH_DIM


def is_semantic() -> bool:
    """True when the embedding provider produces real semantic vectors."""
    return _provider_available


def get_provider_name() -> str:
    """Return the active provider name for observability."""
    if _provider_available:
        return "local"
    return "hash"


def embed_text(text: str) -> list[float] | None:
    """Return an embedding vector for *text*.

    Tries local model first. Falls back to hash-based vector, but marks
    the provider as non-semantic so callers can choose to skip similarity
    search.
    """
    vec = _embed_local_cached(text)
    if vec is not None:
        return vec
    return _embed_hash(text)


def warmup() -> None:
    """Eagerly load the model and run a throwaway encode.

    Call during application init (NOT on the request path) to eliminate
    cold-start latency from the first real predict() call.
    """
    _ensure_model()
    if _model is not None:
        try:
            _model.encode("warmup", show_progress_bar=False)
            log.info("[ie_embed] warmup complete, model=%s dim=%d", _model_name, _model_dim)
        except Exception:
            log.debug("[ie_embed] warmup encode failed", exc_info=True)


# ── Local model ───────────────────────────────────────────────────

def _get_model_name() -> str:
    """Resolve model name from IE config or use default."""
    try:
        from myxai_desk.core.intent_engine import config as ie_config
        return ie_config.get("embedding_model") or _DEFAULT_MODEL
    except Exception:
        return _DEFAULT_MODEL


def _configure_hf_mirror() -> None:
    """Set HuggingFace mirror for regions where huggingface.co is unreachable."""
    import os
    if not os.environ.get("HF_ENDPOINT"):
        try:
            from myxai_desk.core.intent_engine import config as ie_config
            mirror = ie_config.get("hf_mirror")
            if mirror:
                os.environ["HF_ENDPOINT"] = mirror
                return
        except Exception:
            pass
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")


def _ensure_model() -> None:
    """Load the sentence-transformers model (once)."""
    global _model, _model_name, _model_dim, _provider_available, _init_attempted

    if _init_attempted:
        return
    with _lock:
        if _init_attempted:
            return
        _init_attempted = True

        _configure_hf_mirror()
        model_name = _get_model_name()
        cache_dir = str(_MODEL_DIR / "st_cache")

        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(
                model_name,
                cache_folder=cache_dir,
            )
            _model_dim = _model.get_sentence_embedding_dimension()
            _model_name = model_name
            _provider_available = True
            log.info("[ie_embed] local model loaded: %s (dim=%d)", model_name, _model_dim)
        except ImportError:
            log.warning(
                "[ie_embed] sentence-transformers not installed — "
                "case retrieval degraded to hash-only. "
                "Install: pip install sentence-transformers"
            )
            _provider_available = False
        except Exception:
            log.warning("[ie_embed] failed to load model %s", model_name, exc_info=True)
            _provider_available = False


def _embed_local(text: str) -> list[float] | None:
    """Encode text with the local model. Returns None if model unavailable."""
    _ensure_model()
    if _model is None:
        return None
    try:
        vec = _model.encode(text, show_progress_bar=False, normalize_embeddings=True)
        return vec.tolist()
    except Exception:
        log.debug("[ie_embed] local encode failed", exc_info=True)
        return None


# ── Cache layer ───────────────────────────────────────────────────

@lru_cache(maxsize=2048)
def _cache_key_embed(cache_key: str) -> tuple[float, ...] | None:
    """Cache wrapper keyed by hash(model + text). Returns tuple for hashability."""
    vec = _embed_local(cache_key)
    if vec is None:
        return None
    return tuple(vec)


def _embed_local_cached(text: str) -> list[float] | None:
    """Embed with LRU cache. Key = model_name + normalized text."""
    _ensure_model()
    if _model is None:
        return None

    cache_key = text[:8000]
    result = _cache_key_embed(cache_key)
    if result is None:
        return None
    return list(result)


def get_cache_info():
    """Return LRU cache hit/miss stats for monitoring."""
    return _cache_key_embed.cache_info()


# ── Hash-based fallback embedding ─────────────────────────────────

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
