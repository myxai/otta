"""FastText model training for intent classification.

Models are versioned at ``~/.nanobot/models/intent_engine/fasttext/vN.bin``.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

log = logging.getLogger("myxai")

_MODELS_DIR = Path.home() / ".nanobot" / "models" / "intent_engine" / "fasttext"
_META_FILE = _MODELS_DIR / "meta.json"


def _ensure_dir() -> None:
    _MODELS_DIR.mkdir(parents=True, exist_ok=True)


def _load_meta() -> dict:
    if _META_FILE.exists():
        try:
            return json.loads(_META_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"current_version": 0, "versions": []}


def _save_meta(meta: dict) -> None:
    _ensure_dir()
    _META_FILE.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def train(dataset_path: Path) -> dict:
    """Train a fastText model and save as a new version.

    Returns a result dict with version, path, and metrics.
    """
    _ensure_dir()
    meta = _load_meta()
    new_version = meta["current_version"] + 1
    model_file = _MODELS_DIR / f"v{new_version}.bin"

    try:
        import fasttext
        model = fasttext.train_supervised(
            input=str(dataset_path),
            epoch=25,
            lr=0.5,
            wordNgrams=2,
            dim=50,
            loss="softmax",
        )
        model.save_model(str(model_file))

        n_labels = len(model.labels)
        result = model.test(str(dataset_path))
        train_precision = round(result[1], 4)
        train_recall = round(result[2], 4)
    except ImportError:
        log.warning("[train] fasttext not installed, creating placeholder")
        model_file.write_text("placeholder")
        n_labels = 0
        train_precision = 0.0
        train_recall = 0.0

    version_info = {
        "version": new_version,
        "path": str(model_file),
        "dataset": str(dataset_path),
        "created_at": datetime.now().isoformat(),
        "n_labels": n_labels,
        "train_precision": train_precision,
        "train_recall": train_recall,
    }

    meta["current_version"] = new_version
    meta["versions"].append(version_info)
    _save_meta(meta)

    log.info("[train] v%d saved: precision=%.3f recall=%.3f labels=%d",
             new_version, train_precision, train_recall, n_labels)
    return version_info


def get_current_model_path() -> Path | None:
    meta = _load_meta()
    v = meta.get("current_version", 0)
    if v <= 0:
        return None
    p = _MODELS_DIR / f"v{v}.bin"
    return p if p.exists() else None


def list_versions() -> list[dict]:
    meta = _load_meta()
    return meta.get("versions", [])


def rollback(target_version: int) -> dict | None:
    """Roll back to a previous model version."""
    meta = _load_meta()
    target_path = _MODELS_DIR / f"v{target_version}.bin"
    if not target_path.exists():
        return None
    meta["current_version"] = target_version
    _save_meta(meta)
    log.info("[train] rolled back to v%d", target_version)
    return {"version": target_version, "path": str(target_path)}
