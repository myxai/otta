"""Scheduler executor for the daily healthcheck pipeline.

Exposes ``run_healthcheck`` which is the callback registered with
``SchedulerService.register_executor("healthcheck", ...)``.
"""

from __future__ import annotations

import logging

log = logging.getLogger("myxai")


def run_healthcheck(task, slot, trigger: str) -> None:  # noqa: ANN001
    """Scheduler executor callback — runs the full healthcheck pipeline."""
    sched_for = slot.scheduled_for.strftime("%Y-%m-%d")
    log.info(
        "[scheduler] healthcheck pipeline (scheduled_for=%s, trigger=%s)",
        sched_for,
        trigger,
    )

    from myxai_desk.apps.healthcheck.pipeline import run_daily_healthcheck

    run_daily_healthcheck(run_date=sched_for)
