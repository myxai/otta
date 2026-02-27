"""Scheduler job for daily Intent Engine training and evaluation.

Registered as an executor callback for ``SchedulerService``.
"""

from __future__ import annotations

import logging

log = logging.getLogger("myxai")


def run_ie_training(task: dict, slot: dict, trigger: str) -> dict:
    """Scheduler callback: build dataset, train, evaluate.

    Returns an artifacts dict for the task_runs record.
    """
    log.info("[ie_scheduler] starting daily training job (trigger=%s)", trigger)
    artifacts: dict = {"steps": []}

    # Step 1: build dataset
    try:
        from myxai_desk.core.intent_engine.trainer.dataset_builder import build_dataset
        dataset_path, ds_stats = build_dataset()
        artifacts["steps"].append({"step": "dataset", "status": "ok", "stats": ds_stats})
        if dataset_path is None:
            artifacts["steps"][-1]["status"] = "skip"
            artifacts["note"] = "insufficient training data"
            log.info("[ie_scheduler] insufficient data, skipping training")
            return artifacts
    except Exception as e:
        artifacts["steps"].append({"step": "dataset", "status": "error", "error": str(e)})
        log.warning("[ie_scheduler] dataset build failed", exc_info=True)
        return artifacts

    # Step 2: train
    try:
        from myxai_desk.core.intent_engine.trainer.train_fasttext import train
        train_result = train(dataset_path)
        artifacts["steps"].append({"step": "train", "status": "ok", "result": train_result})
    except Exception as e:
        artifacts["steps"].append({"step": "train", "status": "error", "error": str(e)})
        log.warning("[ie_scheduler] training failed", exc_info=True)
        return artifacts

    # Step 3: evaluate
    try:
        from myxai_desk.core.intent_engine.trainer.eval_runner import run_eval
        eval_result = run_eval()
        artifacts["steps"].append({"step": "eval", "status": "ok", "result": eval_result})
    except Exception as e:
        artifacts["steps"].append({"step": "eval", "status": "error", "error": str(e)})
        log.warning("[ie_scheduler] evaluation failed", exc_info=True)

    log.info("[ie_scheduler] daily job complete: %d steps", len(artifacts["steps"]))
    return artifacts
