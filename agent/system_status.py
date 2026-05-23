"""
System performance status helpers for the Web UI.
"""
from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import time
from functools import lru_cache


def get_system_status() -> dict:
    """Return best-effort CPU, memory, GPU, and temperature metrics."""
    psutil = _try_psutil()
    now = time.time()

    return {
        "timestamp": now,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor() or platform.machine(),
            "hostname": platform.node(),
            "uptime_seconds": _uptime_seconds(psutil, now),
        },
        "cpu": _cpu_status(psutil),
        "memory": _memory_status(psutil),
        "gpu": _gpu_status(),
        "temperature": _temperature_status(psutil),
        "battery": _battery_status(psutil),
    }


def _try_psutil():
    try:
        import psutil  # type: ignore
    except Exception:
        return None
    return psutil


def _cpu_status(psutil) -> dict:
    load_avg = os.getloadavg() if hasattr(os, "getloadavg") else None
    logical = os.cpu_count()

    if psutil:
        return {
            "available": True,
            "percent": psutil.cpu_percent(interval=0.05),
            "per_cpu_percent": psutil.cpu_percent(interval=None, percpu=True),
            "count_logical": logical,
            "count_physical": psutil.cpu_count(logical=False),
            "load_average": load_avg,
        }

    return {
        "available": bool(load_avg),
        "percent": None,
        "per_cpu_percent": [],
        "count_logical": logical,
        "count_physical": None,
        "load_average": load_avg,
        "note": "Install psutil for CPU utilization percent.",
    }


def _memory_status(psutil) -> dict:
    if psutil:
        virtual = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return {
            "available": True,
            "total_bytes": virtual.total,
            "available_bytes": virtual.available,
            "used_bytes": virtual.used,
            "percent": virtual.percent,
            "swap_total_bytes": swap.total,
            "swap_used_bytes": swap.used,
            "swap_percent": swap.percent,
        }

    mac_memory = _mac_memory_status()
    if mac_memory:
        return mac_memory

    return {
        "available": False,
        "total_bytes": None,
        "available_bytes": None,
        "used_bytes": None,
        "percent": None,
        "note": "Install psutil for memory metrics.",
    }


def _gpu_status() -> dict:
    nvidia = _nvidia_gpu_status()
    if nvidia["available"]:
        return nvidia

    apple = _apple_gpu_status()
    if apple["available"]:
        return apple

    return {
        "available": False,
        "devices": [],
        "note": "GPU utilization is available with nvidia-smi. Apple/Integrated GPU live utilization may not be exposed.",
    }


def _temperature_status(psutil) -> dict:
    if psutil and hasattr(psutil, "sensors_temperatures"):
        try:
            sensors = psutil.sensors_temperatures(fahrenheit=False)
        except Exception:
            sensors = {}

        entries = []
        for source, readings in sensors.items():
            for reading in readings:
                current = getattr(reading, "current", None)
                if current is None:
                    continue
                entries.append({
                    "source": source,
                    "label": getattr(reading, "label", "") or source,
                    "current_c": current,
                    "high_c": getattr(reading, "high", None),
                    "critical_c": getattr(reading, "critical", None),
                })

        if entries:
            return {"available": True, "sensors": entries}

    osx_temp = _osx_cpu_temp()
    if osx_temp is not None:
        return {
            "available": True,
            "sensors": [{"source": "osx-cpu-temp", "label": "CPU", "current_c": osx_temp}],
        }

    return {
        "available": False,
        "sensors": [],
        "note": "Temperature sensors are platform-dependent. On macOS, install osx-cpu-temp for CPU temperature.",
    }


def _battery_status(psutil) -> dict:
    if not psutil or not hasattr(psutil, "sensors_battery"):
        return {"available": False}
    try:
        battery = psutil.sensors_battery()
    except Exception:
        battery = None
    if not battery:
        return {"available": False}
    return {
        "available": True,
        "percent": battery.percent,
        "plugged": battery.power_plugged,
        "seconds_left": battery.secsleft,
    }


def _uptime_seconds(psutil, now: float) -> float | None:
    if not psutil:
        return None
    try:
        return max(0.0, now - psutil.boot_time())
    except Exception:
        return None


def _nvidia_gpu_status() -> dict:
    if not shutil.which("nvidia-smi"):
        return {"available": False, "devices": []}

    query = (
        "name,utilization.gpu,memory.total,memory.used,temperature.gpu,power.draw"
    )
    cmd = [
        "nvidia-smi",
        f"--query-gpu={query}",
        "--format=csv,noheader,nounits",
    ]
    output = _run_command(cmd)
    if not output:
        return {"available": False, "devices": []}

    devices = []
    for line in output.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 6:
            continue
        devices.append({
            "name": parts[0],
            "utilization_percent": _to_float(parts[1]),
            "memory_total_mb": _to_float(parts[2]),
            "memory_used_mb": _to_float(parts[3]),
            "temperature_c": _to_float(parts[4]),
            "power_watts": _to_float(parts[5]),
        })

    return {"available": bool(devices), "vendor": "nvidia", "devices": devices}


@lru_cache(maxsize=1)
def _apple_gpu_status() -> dict:
    if platform.system() != "Darwin":
        return {"available": False, "devices": []}

    output = _run_command(["system_profiler", "SPDisplaysDataType"])
    if not output:
        return {"available": False, "devices": []}

    devices = []
    current = None
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if line.endswith(":") and not line.startswith(("Displays:", "Graphics/Displays:")):
            if current:
                devices.append(current)
            current = {"name": line[:-1]}
        elif current and line.startswith("Chipset Model:"):
            current["name"] = line.split(":", 1)[1].strip()
        elif current and line.startswith("VRAM"):
            current["memory"] = line.split(":", 1)[1].strip()
        elif current and line.startswith("Metal Support:"):
            current["metal"] = line.split(":", 1)[1].strip()

    if current:
        devices.append(current)

    return {
        "available": bool(devices),
        "vendor": "apple_or_integrated",
        "devices": devices,
        "note": "Live utilization is not available from system_profiler.",
    }


def _mac_memory_status() -> dict | None:
    if platform.system() != "Darwin":
        return None

    vm_stat = _run_command(["vm_stat"])
    if not vm_stat:
        return None

    page_size = _mac_page_size(vm_stat)
    if not page_size:
        return None

    pages = {}
    for line in vm_stat.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        pages[key.strip()] = _to_float(value.strip().strip("."))

    total = _to_float(_run_command(["sysctl", "-n", "hw.memsize"]))
    if not total:
        total_page_keys = (
            "Pages free",
            "Pages active",
            "Pages inactive",
            "Pages speculative",
            "Pages wired down",
            "Pages occupied by compressor",
        )
        total_pages = sum(pages.get(key, 0) or 0 for key in total_page_keys)
        total = total_pages * page_size if total_pages else None
    if not total:
        return None

    free = pages.get("Pages free", 0) + pages.get("Pages speculative", 0)
    inactive = pages.get("Pages inactive", 0)
    available = (free + inactive) * page_size
    used = max(0, total - available)
    percent = round((used / total) * 100, 1) if total else None

    return {
        "available": True,
        "total_bytes": total,
        "available_bytes": available,
        "used_bytes": used,
        "percent": percent,
        "note": "Memory from macOS sysctl/vm_stat fallback. Install psutil for richer metrics.",
    }


def _mac_page_size(vm_stat: str) -> float | None:
    match = re.search(r"page size of (\d+) bytes", vm_stat)
    if match:
        return _to_float(match.group(1))
    return _to_float(_run_command(["sysctl", "-n", "hw.pagesize"]))


def _osx_cpu_temp() -> float | None:
    if not shutil.which("osx-cpu-temp"):
        return None
    output = _run_command(["osx-cpu-temp"])
    if not output:
        return None
    return _to_float(output.replace("°C", "").replace("C", "").strip())


def _run_command(args: list[str]) -> str:
    try:
        result = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _to_float(value) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None
