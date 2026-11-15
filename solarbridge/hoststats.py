"""Local host metrics for the «09 / PC MASTER POLL» section and the master heartbeat.

Read-only: /proc, /sys, shutil.disk_usage and (on Raspberry Pi only)
`vcgencmd get_throttled`. Best effort by design: any read failure leaves the
field as None instead of raising, and machines without /proc (Windows, macOS)
simply miss the kernel-derived fields — the dashboard hides them.

A small TTL cache keeps the frequent calls (every /api/current plus the 15 s
heartbeat) cheap: /proc reads cost microseconds, while vcgencmd spawns a
subprocess and is therefore refreshed no more than once per cache interval.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

DEFAULT_INTERVAL = 10.0
VCGENCMD_CANDIDATES = ("/usr/bin/vcgencmd", "/opt/vc/bin/vcgencmd")


class DiskGuard:
    """Free-disk watchdog for the master storage path.

    When the free share of the watched filesystem drops below
    min_free_percent, `paused` flips to True: the poller then stops writing
    samples to its own database (data on receivers keeps flowing via the
    forwarder's live passthrough) and the dashboard shows a warning. 0
    disables the guard entirely."""

    def __init__(self, watch_dir: Path | None, min_free_percent: float) -> None:
        self.watch_dir = Path(watch_dir) if watch_dir else None
        self.min_free_percent = max(0.0, float(min_free_percent))

    def status(self) -> dict[str, Any]:
        free_percent: float | None = None
        try:
            usage = shutil.disk_usage(str(self.watch_dir) if self.watch_dir else ".")
            if usage.total > 0:
                free_percent = round(usage.free / usage.total * 100.0, 1)
        except OSError:
            pass
        paused = (
            self.min_free_percent > 0
            and free_percent is not None
            and free_percent < self.min_free_percent
        )
        return {
            "free_percent": free_percent,
            "min_free_percent": self.min_free_percent,
            "paused": paused,
        }


class HostStats:
    """TTL-cached provider of local machine metrics."""

    def __init__(self, watch_dir: Path | None = None, interval: float = DEFAULT_INTERVAL) -> None:
        self.watch_dir = Path(watch_dir) if watch_dir else None
        self.interval = max(1.0, float(interval))
        self._lock = threading.Lock()
        self._cache: dict[str, Any] | None = None
        self._cache_at = 0.0

    def snapshot(self) -> dict[str, Any]:
        now = time.monotonic()
        with self._lock:
            if self._cache is not None and now - self._cache_at < self.interval:
                return dict(self._cache)
            stats = self._read()
            self._cache = stats
            self._cache_at = now
            return stats

    # ------------------------------------------------------------------ reads

    def _read(self) -> dict[str, Any]:
        stats: dict[str, Any] = {
            "cpu_temp_c": _cpu_temp(),
            "load_1m": None,
            "load_5m": None,
            "load_15m": None,
            "mem_total_mb": None,
            "mem_used_percent": None,
            "disk_total_gb": None,
            "disk_used_percent": None,
            "uptime_s": None,
            "throttled": None,
            "throttled_raw": None,
        }
        _proc_loadavg(stats)
        _proc_meminfo(stats)
        _proc_uptime(stats)
        _disk_usage(stats, self.watch_dir)
        _throttled_flag(stats)
        return stats


def _read_text(path: str) -> str | None:
    try:
        with open(path, encoding="ascii") as handle:
            return handle.read()
    except OSError:
        return None


def _cpu_temp() -> float | None:
    for path in ("/sys/class/thermal/thermal_zone0/temp", "/sys/class/hwmon/hwmon0/temp1_input"):
        text = _read_text(path)
        if not text:
            continue
        try:
            return round(int(text.strip()) / 1000.0, 1)
        except ValueError:
            continue
    return None


def _proc_loadavg(stats: dict[str, Any]) -> None:
    text = _read_text("/proc/loadavg")
    if not text:
        return
    parts = text.split()
    try:
        stats["load_1m"] = float(parts[0])
        stats["load_5m"] = float(parts[1])
        stats["load_15m"] = float(parts[2])
    except (IndexError, ValueError):
        pass


def _proc_meminfo(stats: dict[str, Any]) -> None:
    text = _read_text("/proc/meminfo")
    if not text:
        return
    values: dict[str, int] = {}
    for line in text.splitlines():
        key, _, rest = line.partition(":")
        if key not in {"MemTotal", "MemAvailable"}:
            continue
        try:
            values[key] = int(rest.strip().split()[0])  # kB
        except (IndexError, ValueError):
            continue
    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    if total:
        stats["mem_total_mb"] = round(total / 1024, 1)
        if available:
            stats["mem_used_percent"] = round(max(0.0, (total - available) / total * 100.0), 1)


def _proc_uptime(stats: dict[str, Any]) -> None:
    text = _read_text("/proc/uptime")
    if not text:
        return
    try:
        stats["uptime_s"] = round(float(text.split()[0]), 1)
    except (IndexError, ValueError):
        pass


def _disk_usage(stats: dict[str, Any], watch_dir: Path | None) -> None:
    try:
        usage = shutil.disk_usage(str(watch_dir) if watch_dir else ".")
    except OSError:
        return
    if usage.total > 0:
        stats["disk_total_gb"] = round(usage.total / 1024**3, 1)
        stats["disk_used_percent"] = round(usage.used / usage.total * 100.0, 1)


def _throttled_flag(stats: dict[str, Any]) -> None:
    """Raspberry Pi power/clock health via vcgencmd (absent elsewhere).

    Bit 0 under-voltage now, 1 frequency capped now, 2 throttled now;
    bits 16-18 the same events in the past.
    """
    binary = next((Path(path) for path in VCGENCMD_CANDIDATES if Path(path).exists()), None)
    if binary is None:
        return
    try:
        result = subprocess.run(
            [str(binary), "get_throttled"], capture_output=True, text=True, timeout=2.0
        )
    except (OSError, subprocess.SubprocessError):
        return
    text = (result.stdout or "").strip()
    marker = "throttled="
    if marker not in text:
        return
    raw = text.split(marker, 1)[1].split()[0]
    try:
        value = int(raw, 16) if raw.startswith("0x") else int(raw)
    except ValueError:
        return
    stats["throttled_raw"] = f"0x{value:08x}"
    stats["throttled"] = bool(value & 0b111) or bool(value & (0b111 << 16))
