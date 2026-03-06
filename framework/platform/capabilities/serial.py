"""Linux serial capability."""

from __future__ import annotations

import time
from typing import Any

from ..adapters.base import PlatformAdapter


class SerialCapability:
    name = "serial"

    def __init__(self, adapter: PlatformAdapter, board_profile: dict[str, Any] | None = None) -> None:
        self.adapter = adapter
        self.board_profile = dict(board_profile or {})

    def list_ports(self) -> list[str]:
        ports: list[str] = []
        for pattern in ("/dev/ttyS*", "/dev/ttyUSB*", "/dev/ttyACM*"):
            ports.extend(self.adapter.list_paths(pattern))
        return sorted(set(ports))

    def resolve_primary(self, candidates: list[str] | None = None) -> str | None:
        preferred = candidates or self.board_profile.get("interfaces", {}).get("uart", [])
        available = set(self.list_ports())
        for candidate in preferred:
            if candidate in available:
                return candidate
        return None

    def port_exists(self, port: str) -> bool:
        return self.adapter.path_exists(port)

    def loopback_test(
        self,
        port: str,
        *,
        payload: str,
        baudrate: int = 115200,
        timeout: int = 5,
    ) -> dict[str, Any]:
        if not self.port_exists(port):
            return {
                "success": False,
                "error_type": "device_not_found",
                "message": f"serial port not found: {port}",
                "payload": payload,
            }

        try:
            import serial  # type: ignore
        except ImportError:
            return {
                "success": False,
                "error_type": "missing_dependency",
                "message": "pyserial is not installed",
                "payload": payload,
            }

        started_at = time.perf_counter()
        encoded = payload.encode("utf-8")
        try:
            with serial.Serial(port, baudrate=baudrate, timeout=timeout) as handle:
                handle.write(encoded)
                handle.flush()
                time.sleep(min(0.1, timeout))
                received = handle.read(len(encoded))
        except Exception as error:
            return {
                "success": False,
                "error_type": "io_error",
                "message": str(error),
                "payload": payload,
            }

        return {
            "success": received == encoded,
            "message": "loopback ok" if received == encoded else "loopback mismatch",
            "payload": payload,
            "received": received.decode("utf-8", errors="replace"),
            "duration_ms": int((time.perf_counter() - started_at) * 1000),
        }
