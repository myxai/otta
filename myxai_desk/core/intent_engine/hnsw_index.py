"""HNSW vector index for case retrieval.

Uses hnswlib when available; falls back to brute-force cosine search.
Index file: ``~/.nanobot/models/intent_engine/hnsw.index``
Mapping file: ``~/.nanobot/models/intent_engine/id_map.json``
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from threading import Lock
from typing import Any

log = logging.getLogger("myxai")

_INDEX_DIR = Path.home() / ".nanobot" / "models" / "intent_engine"
_INDEX_FILE = _INDEX_DIR / "hnsw.index"
_MAP_FILE = _INDEX_DIR / "id_map.json"
_lock = Lock()

_index: Any | None = None
_id_map: list[str] = []
_brute_vecs: list[list[float]] = []
_use_hnswlib = False


def _ensure_dir() -> None:
    _INDEX_DIR.mkdir(parents=True, exist_ok=True)


def _load_id_map() -> list[str]:
    if _MAP_FILE.exists():
        try:
            return json.loads(_MAP_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_id_map(mapping: list[str]) -> None:
    _ensure_dir()
    _MAP_FILE.write_text(json.dumps(mapping, ensure_ascii=False), encoding="utf-8")


def init(dim: int, max_elements: int = 50000) -> None:
    """Initialise or load the HNSW index."""
    global _index, _id_map, _use_hnswlib, _brute_vecs
    with _lock:
        _id_map = _load_id_map()
        try:
            import hnswlib
            _index = hnswlib.Index(space="cosine", dim=dim)
            if _INDEX_FILE.exists() and _id_map:
                _index.load_index(str(_INDEX_FILE), max_elements=max(max_elements, len(_id_map) + 1000))
            else:
                _index.init_index(max_elements=max_elements, ef_construction=200, M=16)
            _index.set_ef(50)
            _use_hnswlib = True
            log.info("[hnsw] hnswlib index loaded, %d items", len(_id_map))
        except ImportError:
            _use_hnswlib = False
            _brute_vecs = []
            log.info("[hnsw] hnswlib not available, using brute-force fallback")


def add(case_id: str, vector: list[float]) -> None:
    """Add a vector to the index."""
    global _id_map, _brute_vecs
    with _lock:
        idx = len(_id_map)
        _id_map.append(case_id)
        if _use_hnswlib and _index is not None:
            cur = _index.get_max_elements()
            if idx >= cur:
                _index.resize_index(cur + 10000)
            _index.add_items([vector], [idx])
            _ensure_dir()
            _index.save_index(str(_INDEX_FILE))
        else:
            _brute_vecs.append(vector)
        _save_id_map(_id_map)


def search(vector: list[float], top_k: int = 5) -> list[tuple[str, float]]:
    """Return up to *top_k* ``(case_id, similarity)`` pairs."""
    with _lock:
        if not _id_map:
            return []
        if _use_hnswlib and _index is not None:
            k = min(top_k, len(_id_map))
            labels, distances = _index.knn_query([vector], k=k)
            results = []
            for lbl, dist in zip(labels[0], distances[0]):
                if 0 <= lbl < len(_id_map):
                    sim = 1.0 - dist
                    results.append((_id_map[lbl], sim))
            return results
        return _brute_search(vector, top_k)


def _brute_search(query: list[float], top_k: int) -> list[tuple[str, float]]:
    """Cosine similarity brute-force search."""
    q_norm = math.sqrt(sum(v * v for v in query)) or 1.0
    scored: list[tuple[str, float]] = []
    for i, vec in enumerate(_brute_vecs):
        if i >= len(_id_map):
            break
        dot = sum(a * b for a, b in zip(query, vec))
        v_norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        sim = dot / (q_norm * v_norm)
        scored.append((_id_map[i], sim))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def count() -> int:
    return len(_id_map)
