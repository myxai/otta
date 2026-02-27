"""Evaluation runner for Intent Engine models.

Runs a fixed test set against the current model and reports accuracy metrics.
Results are saved to ``~/.nanobot/models/intent_engine/eval_results/``.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

log = logging.getLogger("myxai")

_EVAL_DIR = Path.home() / ".nanobot" / "models" / "intent_engine" / "eval_results"


def run_eval(
    model_path: Path | None = None,
    eval_set_path: Path | None = None,
) -> dict:
    """Evaluate the current or specified model against an eval set.

    Returns metrics dict with accuracy, mismatch rate, etc.
    """
    _EVAL_DIR.mkdir(parents=True, exist_ok=True)

    if model_path is None:
        from myxai_desk.core.intent_engine.trainer.train_fasttext import get_current_model_path
        model_path = get_current_model_path()

    if model_path is None or not model_path.exists():
        return {"error": "no model available", "status": "skip"}

    if eval_set_path is None:
        eval_set_path = _find_latest_eval_set()
        if eval_set_path is None:
            from myxai_desk.core.intent_engine.trainer.dataset_builder import build_eval_set
            eval_set_path, _ = build_eval_set()

    if eval_set_path is None or not eval_set_path.exists():
        return {"error": "no eval set available", "status": "skip"}

    results = _evaluate(model_path, eval_set_path)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    version = model_path.stem
    out_file = _EVAL_DIR / f"{version}_eval_{ts}.json"
    out_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    log.info("[eval] %s: accuracy=%.3f mismatch=%.3f",
             version, results.get("accuracy", 0), results.get("route_mismatch_rate", 0))
    return results


def _evaluate(model_path: Path, eval_path: Path) -> dict:
    """Run fastText model evaluation."""
    try:
        import fasttext
        model = fasttext.load_model(str(model_path))
    except ImportError:
        return _evaluate_fallback(eval_path)
    except Exception as e:
        return {"error": str(e), "status": "fail"}

    lines = eval_path.read_text(encoding="utf-8").strip().split("\n")
    total = 0
    correct = 0
    mismatches: list[dict] = []

    for line in lines:
        if not line.startswith("__label__"):
            continue
        parts = line.split(" ", 1)
        if len(parts) < 2:
            continue
        true_label = parts[0]
        text = parts[1]
        total += 1

        pred = model.predict(text, k=1)
        pred_label = pred[0][0] if pred[0] else ""
        pred_conf = float(pred[1][0]) if pred[1] else 0.0

        if pred_label == true_label:
            correct += 1
        else:
            if len(mismatches) < 20:
                mismatches.append({
                    "text": text[:80],
                    "true": true_label,
                    "predicted": pred_label,
                    "confidence": round(pred_conf, 3),
                })

    accuracy = correct / total if total > 0 else 0.0
    return {
        "status": "ok",
        "model": model_path.name,
        "total": total,
        "correct": correct,
        "accuracy": round(accuracy, 4),
        "route_mismatch_rate": round(1.0 - accuracy, 4),
        "mismatches_sample": mismatches,
        "evaluated_at": datetime.now().isoformat(),
    }


def _evaluate_fallback(eval_path: Path) -> dict:
    """When fasttext is not installed, return a basic stats-only result."""
    lines = eval_path.read_text(encoding="utf-8").strip().split("\n")
    total = sum(1 for l in lines if l.startswith("__label__"))
    return {
        "status": "no_model",
        "total": total,
        "note": "fasttext not installed, evaluation skipped",
    }


def _find_latest_eval_set() -> Path | None:
    datasets_dir = Path.home() / ".nanobot" / "models" / "intent_engine" / "datasets"
    if not datasets_dir.exists():
        return None
    eval_files = sorted(datasets_dir.glob("eval_*.txt"), reverse=True)
    return eval_files[0] if eval_files else None


def get_eval_history(limit: int = 10) -> list[dict]:
    """Load recent evaluation results."""
    if not _EVAL_DIR.exists():
        return []
    files = sorted(_EVAL_DIR.glob("*.json"), reverse=True)[:limit]
    results = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            data["file"] = f.name
            results.append(data)
        except Exception:
            pass
    return results
