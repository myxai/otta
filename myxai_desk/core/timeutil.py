"""Time utilities — timezone-aware helpers for consistent datetime handling.

This module provides a single source of truth for local timezone to avoid
hardcoding timezone(timedelta(hours=8)) across the codebase.

All timestamp generation, UI display, and date-based keys should use these
utilities to ensure consistent behavior across different user timezones.
"""

from __future__ import annotations

from datetime import datetime, timezone

# Auto-detect local timezone from system
# This works on all platforms and respects user's system timezone settings
LOCAL_TZ = datetime.now().astimezone().tzinfo


def now_local() -> datetime:
    """Return current time in local timezone (timezone-aware)."""
    return datetime.now(LOCAL_TZ)


def now_utc() -> datetime:
    """Return current time in UTC (timezone-aware)."""
    return datetime.now(timezone.utc)


def to_local(dt: datetime) -> datetime:
    """Convert a datetime to local timezone.
    
    If the input is naive (no timezone), it will be treated as UTC.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(LOCAL_TZ)


def to_utc(dt: datetime) -> datetime:
    """Convert a datetime to UTC.
    
    If the input is naive (no timezone), it will be treated as local time.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(timezone.utc)


def local_date_str(dt: datetime | None = None, fmt: str = "%Y-%m-%d") -> str:
    """Return local calendar date string (YYYY-MM-DD by default).
    
    This should be used for:
    - UI display of dates
    - Date-based filenames (reports, trash, etc.)
    - Date-based keys for daily tasks
    
    Args:
        dt: datetime to format (defaults to now)
        fmt: strftime format string
    """
    if dt is None:
        dt = now_local()
    elif dt.tzinfo is None:
        dt = to_local(dt)
    elif dt.tzinfo != LOCAL_TZ:
        dt = to_local(dt)
    return dt.strftime(fmt)


def local_datetime_str(dt: datetime | None = None, fmt: str = "%Y%m%d_%H%M%S") -> str:
    """Return local datetime string (YYYYmmdd_HHMMSS by default).
    
    This should be used for:
    - Timestamp-based filenames
    - Audit log timestamps for display
    
    Args:
        dt: datetime to format (defaults to now)
        fmt: strftime format string
    """
    if dt is None:
        dt = now_local()
    elif dt.tzinfo is None:
        dt = to_local(dt)
    elif dt.tzinfo != LOCAL_TZ:
        dt = to_local(dt)
    return dt.strftime(fmt)


def utc_isoformat(dt: datetime | None = None) -> str:
    """Return UTC ISO format string for storage.
    
    This should be used for:
    - Database storage (created_at, last_run, scheduled_for, etc.)
    - API responses
    - Cross-system timestamp exchange
    
    Args:
        dt: datetime to format (defaults to now)
    """
    if dt is None:
        return now_utc().isoformat()
    return to_utc(dt).isoformat()


def local_isoformat(dt: datetime | None = None) -> str:
    """Return local timezone ISO format string.
    
    Use this for user-facing timestamps that should preserve timezone info.
    For storage, prefer utc_isoformat() for consistency.
    
    Args:
        dt: datetime to format (defaults to now)
    """
    if dt is None:
        return now_local().isoformat()
    return to_local(dt).isoformat()
