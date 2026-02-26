"""System information utilities for status page."""
from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("myxai.system_info")

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    log.warning("psutil not available, system monitoring will be unavailable")


def get_system_monitor() -> dict[str, Any]:
    """Get real-time system monitoring data (CPU, Memory, Disk, Network)."""
    if not PSUTIL_AVAILABLE:
        return {"available": False}

    try:
        # Use blocking=True with 0.1s interval to get instant CPU reading
        cpu = psutil.cpu_percent(interval=0.1, percpu=False)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        net = psutil.net_io_counters()
        return {
            "available": True,
            "cpu_percent": cpu,
            "memory": {
                "percent": mem.percent,
                "used_gb": round(mem.used / (1024 ** 3), 2),
                "total_gb": round(mem.total / (1024 ** 3), 2),
            },
            "disk": {
                "percent": disk.percent,
                "used_gb": round(disk.used / (1024 ** 3), 2),
                "total_gb": round(disk.total / (1024 ** 3), 2),
            },
            "network": {
                "bytes_sent": net.bytes_sent,
                "bytes_recv": net.bytes_recv,
            },
        }
    except Exception:
        log.exception("Failed to get system monitor data")
        return {"available": False}

