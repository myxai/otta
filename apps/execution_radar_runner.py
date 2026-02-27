"""Scheduler executor for the daily execution radar pipeline.

Exposes ``run_execution_radar`` which is the callback registered with
``SchedulerService.register_executor("execution_radar", ...)``.
"""

from __future__ import annotations

import logging

log = logging.getLogger("myxai")


def run_execution_radar(task, slot, trigger: str) -> None:  # noqa: ANN001
    """Scheduler executor callback — runs the full execution radar pipeline."""
    sched_for = slot.scheduled_for.strftime("%Y-%m-%d")
    log.info(
        "[scheduler] execution_radar pipeline (scheduled_for=%s, trigger=%s)",
        sched_for,
        trigger,
    )

    from myxai_desk.apps.execution_radar.pipeline import run_daily_radar

    run_daily_radar(run_date=sched_for)
