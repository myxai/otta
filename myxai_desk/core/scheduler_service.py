"""SchedulerService — catch-up scheduling with due-detection and compensation.

Instead of relying on exact-minute time matching, this service computes which
scheduled task periods have been *missed* (because the app/PC was off) and
compensates according to each task's catchup_policy.

Trigger points:
    1. App startup       — ``on_app_start()``
    2. OS sleep resume   — ``on_resume()``
    3. Periodic heartbeat — ``tick()``  (called every 60 s by the existing timer)
    
Timezone handling:
    - All stored timestamps (started_at, finished_at, scheduled_for) use UTC
    - All schedule time comparisons (HH:MM matching, day boundaries) use local time
    - Idempotency keys use local date for daily/weekly/monthly schedules
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

try:
    from croniter import croniter
except ImportError:
    croniter = None  # type: ignore[assignment,misc]

from myxai_desk.core.storage import sqlite as db
from myxai_desk.core.timeutil import local_date_str, now_local, now_utc, to_local, utc_isoformat

if TYPE_CHECKING:
    from collections.abc import Callable

log = logging.getLogger("scheduler")

# ── Types ──────────────────────────────────────────────────────────────

CatchupPolicy = Literal["NONE", "LATEST_ONLY", "ALL_MISSED"]

CATCHUP_DEFAULTS: dict[str, Any] = {
    "catchup_policy": "LATEST_ONLY",
    "catchup_window_hours": 24,
    "max_catchup_runs": 1,
}


@dataclass
class DueSlot:
    """Represents one missed schedule period that should be compensated."""

    task_id: str
    scheduled_for: datetime
    idempotency_key: str


@dataclass
class TaskDescriptor:
    """Unified view of a scheduled task regardless of source (official / custom)."""

    task_id: str
    schedule: dict
    cron_expr: str
    created_at: str
    last_success_at: str | None
    catchup_policy: CatchupPolicy = "LATEST_ONLY"
    catchup_window_hours: int = 24
    max_catchup_runs: int = 1
    extra: dict = field(default_factory=dict)


# ── task_runs table helpers ────────────────────────────────────────────

_TABLE_INIT = False
_TABLE_LOCK = threading.Lock()


def _ensure_task_runs_table() -> None:
    global _TABLE_INIT
    if _TABLE_INIT:
        return
    with _TABLE_LOCK:
        if _TABLE_INIT:
            return
        db.ensure_table(
            "task_runs",
            """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            scheduled_for TEXT NOT NULL,
            trigger TEXT DEFAULT 'tick',
            started_at TEXT,
            finished_at TEXT,
            status TEXT DEFAULT 'pending',
            error TEXT DEFAULT '',
            artifacts TEXT DEFAULT '{}',
            UNIQUE(idempotency_key)
        """,
        )
        _TABLE_INIT = True


def has_successful_run(idempotency_key: str) -> bool:
    _ensure_task_runs_table()
    rows = db.execute(
        "SELECT 1 FROM task_runs WHERE idempotency_key = ? AND status = 'success' LIMIT 1",
        (idempotency_key,),
        readonly=True,
    )
    return len(rows) > 0


def record_run_start(
    task_id: str, idempotency_key: str, scheduled_for: str, trigger: str
) -> int | None:
    """Insert a 'running' record. Returns None if the key already exists."""
    _ensure_task_runs_table()
    now_iso = utc_isoformat()
    try:
        rows = db.execute(
            """INSERT INTO task_runs
               (task_id, idempotency_key, scheduled_for, trigger, started_at, status)
               VALUES (?, ?, ?, ?, ?, 'running')""",
            (task_id, idempotency_key, scheduled_for, trigger, now_iso),
        )
        # fetch last insert id
        rows = db.execute("SELECT last_insert_rowid() AS rid", readonly=True)
        return rows[0]["rid"] if rows else None
    except Exception:
        return None


def record_run_finish(
    idempotency_key: str, *, success: bool, error: str = "", artifacts: str = "{}"
) -> None:
    _ensure_task_runs_table()
    now_iso = utc_isoformat()
    status = "success" if success else "failed"
    db.execute(
        "UPDATE task_runs SET finished_at = ?, status = ?, error = ?, artifacts = ? "
        "WHERE idempotency_key = ?",
        (now_iso, status, error, artifacts, idempotency_key),
    )


def get_recent_runs(task_id: str, limit: int = 20) -> list[dict]:
    _ensure_task_runs_table()
    return db.execute(
        "SELECT * FROM task_runs WHERE task_id = ? ORDER BY id DESC LIMIT ?",
        (task_id, limit),
        readonly=True,
    )


def get_today_runs() -> list[dict]:
    """Return all task_runs for today (local date)."""
    _ensure_task_runs_table()
    today = local_date_str()
    return db.execute(
        "SELECT * FROM task_runs WHERE scheduled_for LIKE ? ORDER BY id",
        (f"{today}%",),
        readonly=True,
    )


def get_running_tasks() -> list[dict]:
    """Return task_runs currently in 'running' status."""
    _ensure_task_runs_table()
    return db.execute(
        "SELECT * FROM task_runs WHERE status = 'running' ORDER BY id",
        readonly=True,
    )


def cleanup_stale_running() -> int:
    """Mark any leftover 'running' records as 'failed'.

    This handles cases where the app was killed mid-execution.
    Should be called once at startup before the scheduler begins ticking.
    Returns the number of records cleaned up.
    """
    _ensure_task_runs_table()
    stale = db.execute(
        "SELECT idempotency_key FROM task_runs WHERE status = 'running'",
        readonly=True,
    )
    if not stale:
        return 0
    now_iso = utc_isoformat()
    db.execute(
        "UPDATE task_runs SET status = 'failed', finished_at = ?, "
        "error = 'interrupted (app restart)' WHERE status = 'running'",
        (now_iso,),
    )
    log.info("[scheduler] cleaned up %d stale running records", len(stale))
    return len(stale)


# ── Idempotency key generation ─────────────────────────────────────────


def make_idempotency_key(task_id: str, due: datetime, mode: str) -> str:
    """Generate idempotency key using local timezone for date-based schedules.
    
    This ensures that daily/weekly/monthly tasks are keyed by local calendar date,
    not UTC date, so that users in different timezones see consistent behavior.
    """
    due_local = to_local(due) if due.tzinfo else due
    
    if mode == "daily":
        return f"{task_id}:{due_local.strftime('%Y-%m-%d')}"
    if mode == "weekly":
        iso_year, iso_week, _ = due_local.isocalendar()
        return f"{task_id}:{iso_year}-W{iso_week:02d}"
    if mode == "monthly":
        return f"{task_id}:{due_local.strftime('%Y-%m')}"
    # interval or fallback — use full timestamp (minute-precision)
    return f"{task_id}:{due_local.strftime('%Y-%m-%dT%H:%M')}"


# ── Due-slot computation ───────────────────────────────────────────────


def _schedule_to_cron(schedule: dict) -> str:
    """Convert a custom-app schedule dict to a cron expression."""
    time_str = schedule.get("time", "")
    if not time_str or ":" not in time_str:
        return ""
    hh, mm = time_str.split(":")[:2]
    mode = schedule.get("mode", "daily")
    if mode == "daily":
        return f"{mm} {hh} * * *"
    if mode == "weekly":
        dow = schedule.get("day_of_week", 0)
        return f"{mm} {hh} * * {dow}"
    if mode == "monthly":
        dom = schedule.get("day_of_month", 1)
        return f"{mm} {hh} {dom} * *"
    if mode == "interval":
        return f"{mm} {hh} * * *"
    return ""


def compute_due_slots(task: TaskDescriptor, now: datetime | None = None) -> list[DueSlot]:
    """Return the list of due slots that should be compensated for *task*.

    The algorithm:
      1. Pick anchor = last_success_at (or created_at if never run).
      2. Generate cron iterations from anchor forward.
      3. Collect slots where due_time <= now and within catchup_window.
      4. Apply catchup_policy to decide which slots to keep.
      
    All schedule comparisons use local timezone for consistency with user expectations.
    """
    if task.catchup_policy == "NONE":
        return _compute_exact_match(task, now)

    now = now or now_local()
    mode = task.schedule.get("mode", "daily")

    if mode == "interval":
        return _compute_interval_slots(task, now)

    return _compute_cron_slots(task, now)


def _compute_exact_match(task: TaskDescriptor, now: datetime | None = None) -> list[DueSlot]:
    """NONE policy — only trigger on exact minute match (legacy behaviour).
    
    Uses local time for all comparisons to match user expectations.
    """
    now = now or now_local()
    current_hm = now.strftime("%H:%M")
    sched = task.schedule
    sched_time = sched.get("time", "")
    if current_hm != sched_time:
        return []

    mode = sched.get("mode", "daily")
    if mode == "weekly" and now.weekday() != sched.get("day_of_week", 0):
        return []
    if mode == "monthly" and now.day != sched.get("day_of_month", 1):
        return []
    if mode == "interval":
        interval = max(1, sched.get("interval_days", 1))
        last = sched.get("last_triggered")
        if last:
            try:
                last_dt = datetime.fromisoformat(last)
                # Ensure both are naive or both are aware for comparison
                now_cmp = now.replace(tzinfo=None) if now.tzinfo else now
                last_dt_cmp = last_dt.replace(tzinfo=None) if last_dt.tzinfo else last_dt
                if (now_cmp - last_dt_cmp).days < interval:
                    return []
            except Exception:
                pass

    key = make_idempotency_key(task.task_id, now, mode)
    if has_successful_run(key):
        return []
    return [DueSlot(task_id=task.task_id, scheduled_for=now, idempotency_key=key)]


def _compute_cron_slots(task: TaskDescriptor, now: datetime) -> list[DueSlot]:
    """Compute missed cron-based due slots within catchup_window.
    
    Note: croniter requires naive datetime, so we strip timezone info for computation,
    but ensure all comparisons are done with consistent timezone handling.
    """
    if croniter is None:
        log.warning("croniter not installed — falling back to exact match")
        return _compute_exact_match(task, now)

    cron_expr = task.cron_expr
    if not cron_expr:
        cron_expr = _schedule_to_cron(task.schedule)
    if not cron_expr:
        return []

    # Convert now to naive for croniter compatibility
    now_naive = now.replace(tzinfo=None) if now.tzinfo else now
    
    anchor_str = task.last_success_at or task.created_at
    try:
        anchor = datetime.fromisoformat(anchor_str).replace(tzinfo=None)
    except Exception:
        anchor = now_naive - timedelta(hours=task.catchup_window_hours)

    window_start = now_naive - timedelta(hours=task.catchup_window_hours)
    if anchor < window_start:
        anchor = window_start

    try:
        cron = croniter(cron_expr, anchor)
    except Exception:
        log.warning("Invalid cron expression %r for task %s", cron_expr, task.task_id)
        return []

    mode = task.schedule.get("mode", "daily")
    slots: list[DueSlot] = []
    safety = 0
    while safety < 500:
        safety += 1
        nxt = cron.get_next(datetime)
        if nxt > now_naive:
            break
        key = make_idempotency_key(task.task_id, nxt, mode)
        if not has_successful_run(key):
            slots.append(
                DueSlot(
                    task_id=task.task_id,
                    scheduled_for=nxt,
                    idempotency_key=key,
                )
            )

    if not slots:
        return []

    if task.catchup_policy == "LATEST_ONLY":
        return slots[-1:]
    # ALL_MISSED — cap to max_catchup_runs
    return slots[-task.max_catchup_runs :]


def _compute_interval_slots(task: TaskDescriptor, now: datetime) -> list[DueSlot]:
    """Compute missed slots for interval-based schedules.
    
    Note: Uses naive datetime for consistent arithmetic.
    """
    sched = task.schedule
    interval_days = max(1, sched.get("interval_days", 1))
    sched_time = sched.get("time", "")
    if not sched_time or ":" not in sched_time:
        return []
    hh, mm = int(sched_time.split(":")[0]), int(sched_time.split(":")[1])

    # Convert now to naive for consistent arithmetic
    now_naive = now.replace(tzinfo=None) if now.tzinfo else now
    
    anchor_str = task.last_success_at or task.created_at
    try:
        anchor = datetime.fromisoformat(anchor_str).replace(tzinfo=None)
    except Exception:
        anchor = now_naive - timedelta(hours=task.catchup_window_hours)

    window_start = now_naive - timedelta(hours=task.catchup_window_hours)
    cursor = anchor.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if cursor <= anchor:
        cursor += timedelta(days=interval_days)

    mode = "interval"
    slots: list[DueSlot] = []
    safety = 0
    while cursor <= now_naive and safety < 500:
        safety += 1
        if cursor >= window_start:
            key = make_idempotency_key(task.task_id, cursor, mode)
            if not has_successful_run(key):
                slots.append(
                    DueSlot(
                        task_id=task.task_id,
                        scheduled_for=cursor,
                        idempotency_key=key,
                    )
                )
        cursor += timedelta(days=interval_days)

    if not slots:
        return []
    if task.catchup_policy == "LATEST_ONLY":
        return slots[-1:]
    return slots[-task.max_catchup_runs :]


# ── SchedulerService ───────────────────────────────────────────────────


class SchedulerService:
    """Central service that checks all tasks for due slots and dispatches
    compensating executions.

    The actual execution logic (running the agent, saving reports, etc.) is
    delegated to *executor* callbacks registered via ``register_executor``.
    """

    def __init__(self, max_concurrent: int = 2):
        self._executors: dict[str, Callable] = {}
        self._task_loaders: list[Callable[[], list[TaskDescriptor]]] = []
        self._global_sem = threading.Semaphore(max_concurrent)
        self._task_locks: dict[str, threading.Lock] = {}
        self._task_locks_guard = threading.Lock()

    # ── registration ───────────────────────────────────────────────────

    def register_executor(
        self, kind: str, fn: Callable[[TaskDescriptor, DueSlot, str], None]
    ) -> None:
        """Register a callback that knows how to execute a task of *kind*.

        Signature: fn(task_descriptor, due_slot, trigger) -> None
        """
        self._executors[kind] = fn

    def register_task_loader(self, fn: Callable[[], list[TaskDescriptor]]) -> None:
        """Register a callable that returns current TaskDescriptors."""
        self._task_loaders.append(fn)

    # ── trigger entry points ───────────────────────────────────────────

    def on_app_start(self) -> None:
        log.info("[scheduler] catch-up check on startup")
        self.run_due_checks(trigger="startup")

    def on_resume(self) -> None:
        log.info("[scheduler] catch-up check on resume")
        self.run_due_checks(trigger="resume")

    def tick(self) -> None:
        self.run_due_checks(trigger="tick")

    # ── core logic ─────────────────────────────────────────────────────

    def run_due_checks(self, trigger: str = "tick") -> None:
        _ensure_task_runs_table()
        now = now_local()
        tasks = self._load_all_tasks()

        for task in tasks:
            if task.schedule.get("enabled") is False:
                continue
            slots = compute_due_slots(task, now)
            for slot in slots:
                self._dispatch(task, slot, trigger)

    def _load_all_tasks(self) -> list[TaskDescriptor]:
        all_tasks: list[TaskDescriptor] = []
        for loader in self._task_loaders:
            try:
                all_tasks.extend(loader())
            except Exception as exc:
                log.error("[scheduler] task loader error: %s", exc)
        return all_tasks

    def _get_task_lock(self, task_id: str) -> threading.Lock:
        with self._task_locks_guard:
            if task_id not in self._task_locks:
                self._task_locks[task_id] = threading.Lock()
            return self._task_locks[task_id]

    def _dispatch(self, task: TaskDescriptor, slot: DueSlot, trigger: str) -> None:
        kind = task.extra.get("kind", "custom")
        executor = self._executors.get(kind)
        if not executor:
            log.warning("[scheduler] no executor for kind=%r task=%s", kind, task.task_id)
            return

        task_lock = self._get_task_lock(task.task_id)
        if not task_lock.acquire(blocking=False):
            log.debug("[scheduler] task %s already running, skipping", task.task_id)
            return

        def _run():
            try:
                if not self._global_sem.acquire(timeout=5):
                    log.warning("[scheduler] concurrency limit reached, deferring %s", task.task_id)
                    return
                try:
                    rid = record_run_start(
                        task.task_id,
                        slot.idempotency_key,
                        slot.scheduled_for.isoformat(),
                        trigger,
                    )
                    if rid is None:
                        log.debug(
                            "[scheduler] idempotency check: %s already recorded",
                            slot.idempotency_key,
                        )
                        return
                    try:
                        executor(task, slot, trigger)
                        record_run_finish(slot.idempotency_key, success=True)
                    except Exception as exc:
                        log.error("[scheduler] task %s failed: %s", task.task_id, exc)
                        record_run_finish(slot.idempotency_key, success=False, error=str(exc))
                finally:
                    self._global_sem.release()
            finally:
                task_lock.release()

        threading.Thread(target=_run, daemon=True, name=f"sched-{task.task_id}").start()

    def trigger_now(self, task_id: str) -> tuple[bool, str]:
        """Manually trigger a task by its ID. Returns (success, message)."""
        tasks = self._load_all_tasks()
        task = next((t for t in tasks if t.task_id == task_id), None)
        if task is None:
            return False, f"task {task_id} not found"

        now = now_local()
        slot = DueSlot(
            task_id=task_id,
            scheduled_for=now,
            idempotency_key=f"manual_{task_id}_{now.strftime('%Y%m%d_%H%M%S')}",
        )
        self._dispatch(task, slot, trigger="manual")
        return True, "triggered"


# Module-level singleton
scheduler_service = SchedulerService()
