"""Background system metrics collection for dashboard display."""

from __future__ import annotations

import contextlib
import json
import threading
import time
from pathlib import Path
from typing import Any

try:
    import psutil
except ImportError:  # pragma: no cover - runtime fallback only
    psutil = None


class SystemMonitor:
    def __init__(
        self,
        output_dir: str = "tmp",
        output_file: str = "system_monitor.json",
        refresh_interval: float = 2.0,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_file = self.output_dir / output_file
        self.refresh_interval = refresh_interval
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._last_data: dict[str, Any] = {}

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
            self._thread = None

    def collect(self) -> dict[str, Any]:
        data = {
            "timestamp": time.time(),
            "cpu": self._get_cpu_info(),
            "memory": self._get_memory_info(),
            "storage": self._get_storage_info(),
            "platform": self._get_platform_info(),
        }
        with self._lock:
            self._last_data = data
        return data

    def get_latest(self) -> dict[str, Any]:
        with self._lock:
            return self._last_data.copy()

    def _run_loop(self) -> None:
        while self._running:
            with contextlib.suppress(Exception):
                self._write(self.collect())
            if self._stop_event.wait(timeout=self.refresh_interval):
                break

    def _write(self, data: dict[str, Any]) -> None:
        self.output_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _get_cpu_info(self) -> dict[str, Any]:
        if psutil is None:
            return {
                "usage_percent": None,
                "frequency_mhz": None,
                "temperature": None,
                "cores": None,
            }
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_freq = psutil.cpu_freq()
        return {
            "usage_percent": round(cpu_percent, 1),
            "frequency_mhz": round(float(cpu_freq.current), 1)
            if cpu_freq and cpu_freq.current
            else None,
            "temperature": self._get_cpu_temperature(),
            "cores": psutil.cpu_count(logical=True),
        }

    def _get_cpu_temperature(self) -> float | None:
        if psutil is None:
            return None
        try:
            sensors = psutil.sensors_temperatures()
        except Exception:
            sensors = {}
        if sensors:
            for sensor_list in sensors.values():
                if sensor_list:
                    return round(float(sensor_list[0].current), 1)
        thermal_path = Path("/sys/class/thermal/thermal_zone0/temp")
        if thermal_path.exists():
            try:
                return round(
                    int(thermal_path.read_text(encoding="utf-8").strip()) / 1000.0, 1
                )
            except (OSError, ValueError):
                return None
        return None

    def _get_memory_info(self) -> dict[str, Any]:
        if psutil is None:
            return {
                "used_mb": None,
                "available_mb": None,
                "total_mb": None,
                "usage_percent": None,
            }
        memory = psutil.virtual_memory()
        return {
            "used_mb": round(memory.used / (1024 * 1024), 1),
            "available_mb": round(memory.available / (1024 * 1024), 1),
            "total_mb": round(memory.total / (1024 * 1024), 1),
            "usage_percent": round(memory.percent, 1),
        }

    def _get_storage_info(self) -> dict[str, Any]:
        if psutil is None:
            return {
                "used_gb": None,
                "free_gb": None,
                "total_gb": None,
                "usage_percent": None,
            }
        usage = psutil.disk_usage("/")
        return {
            "used_gb": round(usage.used / (1024 * 1024 * 1024), 1),
            "free_gb": round(usage.free / (1024 * 1024 * 1024), 1),
            "total_gb": round(usage.total / (1024 * 1024 * 1024), 1),
            "usage_percent": round(usage.percent, 1),
        }

    def _get_platform_info(self) -> dict[str, str]:
        import platform

        return {
            "system": platform.system(),
            "machine": platform.machine(),
            "processor": platform.processor() or "unknown",
        }


_monitor: SystemMonitor | None = None


def get_monitor() -> SystemMonitor:
    global _monitor
    if _monitor is None:
        _monitor = SystemMonitor()
    return _monitor


def start_monitoring(
    output_dir: str = "tmp", refresh_interval: float = 2.0
) -> SystemMonitor:
    global _monitor
    if _monitor is None or str(_monitor.output_dir) != str(Path(output_dir)):
        if _monitor is not None:
            _monitor.stop()
        _monitor = SystemMonitor(
            output_dir=output_dir, refresh_interval=refresh_interval
        )
    _monitor.start()
    return _monitor


def stop_monitoring() -> None:
    global _monitor
    if _monitor is not None:
        _monitor.stop()
