"""HNSW vector index for case retrieval.

Uses hnswlib when available; falls back to brute-force cosine search.
Index file: ``~/.nanobot/models/intent_engine/hnsw.index``
Mapping file: ``~/.nanobot/models/intent_engine/id_map.json``
Dim cache:   ``~/.nanobot/models/intent_engine/index_dim.json``

On ``init(dim)``, if the requested dimension differs from the persisted
index dimension, the on-disk index is wiped and a fresh one is created.
Callers (``case_store._ensure_init``) are responsible for re-populating
the index from ``ie_cases`` after a dim-change rebuild.
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
_DIM_FILE = _INDEX_DIR / "index_dim.json"
_lock = Lock()

_index: Any | None = None
_id_map: list[str] = []
_brute_vecs: list[list[float]] = []
_use_hnswlib = False
_current_dim: int = 0
_rebuilt = False


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


def _load_persisted_dim() -> int | None:
    try:
        if _DIM_FILE.exists():
            return int(json.loads(_DIM_FILE.read_text(encoding="utf-8"))["dim"])
    except Exception:
        pass
    return None


def _save_persisted_dim(dim: int) -> None:
    _ensure_dir()
    _DIM_FILE.write_text(json.dumps({"dim": dim}), encoding="utf-8")


def was_rebuilt() -> bool:
    """True if init() had to wipe and rebuild the index due to a dim change."""
    return _rebuilt


def init(dim: int, max_elements: int = 50000) -> None:
    """Initialise or load the HNSW index.

    If *dim* differs from the persisted index dimension, the on-disk index
    and id_map are wiped.  ``was_rebuilt()`` returns True so that the caller
    can re-populate the index from the database.
    """
    global _index, _id_map, _use_hnswlib, _brute_vecs, _current_dim, _rebuilt
    with _lock:
        _current_dim = dim
        _rebuilt = False

        persisted_dim = _load_persisted_dim()
        need_rebuild = persisted_dim is not None and persisted_dim != dim

        if need_rebuild:
            log.warning(
                "[hnsw] dim changed %d -> %d — wiping index for rebuild",
                persisted_dim, dim,
            )
            _wipe_index_files()
            _rebuilt = True

        _id_map = _load_id_map()

        try:
            import hnswlib
            _index = hnswlib.Index(space="cosine", dim=dim)
            if _INDEX_FILE.exists() and _id_map and not need_rebuild:
                _index.load_index(str(_INDEX_FILE), max_elements=max(max_elements, len(_id_map) + 1000))
            else:
                _index.init_index(max_elements=max_elements, ef_construction=200, M=16)
            _index.set_ef(50)
            _use_hnswlib = True
            log.info("[hnsw] hnswlib index ready, %d items, dim=%d%s",
                     len(_id_map), dim, " (rebuilt)" if need_rebuild else "")
        except ImportError:
            _use_hnswlib = False
            _brute_vecs = []
            log.info("[hnsw] hnswlib not available, using brute-force fallback (dim=%d)", dim)

        _save_persisted_dim(dim)


def _wipe_index_files() -> None:
    """Remove on-disk index and id_map so they can be re-created."""
    for f in (_INDEX_FILE, _MAP_FILE):
        try:
            if f.exists():
                f.unlink()
        except Exception:
            log.debug("[hnsw] failed to remove %s", f, exc_info=True)
    # Reset in-memory state
    global _id_map, _brute_vecs
    _id_map = []
    _brute_vecs = []


def add(case_id: str, vector: list[float]) -> None:
    """Add a vector to the index. Rejects vectors with mismatched dimensions."""
    global _id_map, _brute_vecs
    if _current_dim and len(vector) != _current_dim:
        log.error("[hnsw] dim mismatch: vector=%d, index=%d — rejecting add for %s",
                  len(vector), _current_dim, case_id)
        return
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
    if _current_dim and len(vector) != _current_dim:
        log.error("[hnsw] search dim mismatch: vector=%d, index=%d — returning empty",
                  len(vector), _current_dim)
        return []
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
