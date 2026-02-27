"""Build fastText training datasets from ie_runs data.

Output format: ``__label__<route_label> <cleaned text>``
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from myxai_desk.core.storage.sqlite import execute

log = logging.getLogger("myxai")

_MODELS_DIR = Path.home() / ".nanobot" / "models" / "intent_engine"
_DATASET_DIR = _MODELS_DIR / "datasets"


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[^\u4e00-\u9fff\w\s.,;:!?]", "", text)
    return text[:500]


def build_dataset(
    *,
    min_samples: int = 10,
    outcome_filter: str = "success",
) -> tuple[Path | None, dict]:
    """Generate a fastText-format training file from ie_runs.

    Returns (file_path, stats_dict) or (None, stats) if insufficient data.
    """
    from myxai_desk.core.intent_engine.dao import init_ie_tables
    init_ie_tables()

    rows = execute(
        """SELECT user_text, route_label, outcome
           FROM ie_runs
           WHERE outcome = ? AND route_label != ''
           ORDER BY created_at""",
        (outcome_filter,),
        readonly=True,
    )

    stats: dict = {"total_rows": len(rows), "labels": {}, "output_lines": 0}
    lines: list[str] = []

    for r in rows:
        labels = r["route_label"].split(",")
        text = _clean(r["user_text"])
        if not text or not labels[0]:
            continue
        primary_label = labels[0].strip()
        line = f"__label__{primary_label} {text}"
        lines.append(line)
        stats["labels"][primary_label] = stats["labels"].get(primary_label, 0) + 1

    stats["output_lines"] = len(lines)

    if len(lines) < min_samples:
        log.info("[dataset] insufficient data: %d lines (need %d)", len(lines), min_samples)
        return None, stats

    _DATASET_DIR.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = _DATASET_DIR / f"train_{ts}.txt"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    log.info("[dataset] built %s (%d lines, %d labels)", out_path.name, len(lines), len(stats["labels"]))
    return out_path, stats


def build_eval_set(
    *,
    sample_ratio: float = 0.2,
    max_samples: int = 200,
) -> tuple[Path | None, dict]:
    """Split a portion of data into an evaluation set."""
    from myxai_desk.core.intent_engine.dao import init_ie_tables
    init_ie_tables()

    rows = execute(
        """SELECT user_text, route_label, outcome
           FROM ie_runs
           WHERE outcome = 'success' AND route_label != ''
           ORDER BY RANDOM()""",
        readonly=True,
    )

    n = min(int(len(rows) * sample_ratio), max_samples)
    if n < 5:
        return None, {"total": len(rows), "sampled": 0}

    eval_rows = rows[:n]
    lines = []
    for r in eval_rows:
        text = _clean(r["user_text"])
        label = r["route_label"].split(",")[0].strip()
        if text and label:
            lines.append(f"__label__{label} {text}")

    if not lines:
        return None, {"total": len(rows), "sampled": 0}

    _DATASET_DIR.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = _DATASET_DIR / f"eval_{ts}.txt"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path, {"total": len(rows), "sampled": len(lines)}
