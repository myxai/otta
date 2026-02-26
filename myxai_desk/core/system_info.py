"""System information utilities for status page."""
from __future__ import annotations

import logging
import platform
import socket
from typing import Any

log = logging.getLogger("myxai.system_info")

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    log.warning("psutil not available, system info will be limited")


def get_system_info() -> dict[str, Any]:
    """Collect system information including device, OS, CPU, GPU, memory, storage, network."""
    info = {}
    
    # Basic system info
    info["hostname"] = socket.gethostname()
    info["platform"] = platform.system()
    info["platform_release"] = platform.release()
    info["platform_version"] = platform.version()
    info["architecture"] = platform.machine()
    info["processor"] = platform.processor()
    
    # Python info
    info["python_version"] = platform.python_version()
    
    if not PSUTIL_AVAILABLE:
        info["psutil_available"] = False
        return info
    
    info["psutil_available"] = True
    
    try:
        # CPU info
        info["cpu"] = {
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
            "max_frequency": getattr(psutil.cpu_freq(), "max", 0) if psutil.cpu_freq() else 0,
            "current_frequency": getattr(psutil.cpu_freq(), "current", 0) if psutil.cpu_freq() else 0,
            "usage_percent": psutil.cpu_percent(interval=0.1),
        }
    except Exception:
        log.debug("Failed to get CPU info", exc_info=True)
        info["cpu"] = {}
    
    try:
        # Memory info
        mem = psutil.virtual_memory()
        info["memory"] = {
            "total": mem.total,
            "available": mem.available,
            "used": mem.used,
            "percent": mem.percent,
        }
    except Exception:
        log.debug("Failed to get memory info", exc_info=True)
        info["memory"] = {}
    
    try:
        # Disk info
        disk = psutil.disk_usage("/")
        info["disk"] = {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent,
        }
    except Exception:
        log.debug("Failed to get disk info", exc_info=True)
        info["disk"] = {}
    
    try:
        # Network info
        net_io = psutil.net_io_counters()
        info["network"] = {
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv,
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv,
        }
        
        # Network interfaces
        addrs = psutil.net_if_addrs()
        interfaces = []
        for iface_name, iface_addrs in addrs.items():
            for addr in iface_addrs:
                if addr.family == socket.AF_INET:  # IPv4
                    interfaces.append({
                        "name": iface_name,
                        "address": addr.address,
                    })
                    break
        info["network"]["interfaces"] = interfaces
    except Exception:
        log.debug("Failed to get network info", exc_info=True)
        info["network"] = {}
    
    try:
        # GPU info (basic detection, detailed info would require platform-specific tools)
        # For now, we'll just indicate if we can detect GPU presence
        gpu_info = []
        
        # Try nvidia-smi for NVIDIA GPUs
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        parts = [p.strip() for p in line.split(",")]
                        if len(parts) >= 3:
                            gpu_info.append({
                                "vendor": "NVIDIA",
                                "name": parts[0],
                                "driver": parts[1],
                                "memory": parts[2],
                            })
        except Exception:
            pass
        
        info["gpu"] = gpu_info if gpu_info else None
    except Exception:
        log.debug("Failed to get GPU info", exc_info=True)
        info["gpu"] = None
    
    try:
        # Boot time
        info["boot_time"] = psutil.boot_time()
    except Exception:
        log.debug("Failed to get boot time", exc_info=True)
        info["boot_time"] = None
    
    return info


def format_bytes(bytes_value: int | float) -> str:
    """Format bytes to human-readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"


def format_frequency(mhz: float) -> str:
    """Format CPU frequency to human-readable string."""
    if mhz >= 1000:
        return f"{mhz / 1000:.2f} GHz"
    return f"{mhz:.0f} MHz"
