"""Linux serial capability implementation."""

from __future__ import annotations

import time
from typing import Any

from ..base import SerialCapabilityContract


class LinuxSerialCapability(SerialCapabilityContract):
    def list_ports(self) -> list[str]:
        ports: list[str] = []
        for pattern in ("/dev/ttyS*", "/dev/ttyUSB*", "/dev/ttyACM*"):
            ports.extend(self.adapter._list_paths(pattern))
        return sorted(set(ports))

    def resolve_primary(self, candidates: list[str] | None = None) -> str | None:
        preferred = candidates or self._interface_candidates("uart")
        available = set(self.list_ports())
        for candidate in preferred:
            if candidate in available:
                return candidate
        return None

    def port_exists(self, port: str) -> bool:
        return self.adapter._path_exists(port)

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
                "port": port,
                "payload": payload,
                "received": None,
                "matched": False,
                "baudrate": baudrate,
                "error_type": "device_not_found",
                "message": f"serial port not found: {port}",
            }

        try:
            import serial  # type: ignore
        except ImportError:
            return {
                "success": False,
                "port": port,
                "payload": payload,
                "received": None,
                "matched": False,
                "baudrate": baudrate,
                "error_type": "missing_dependency",
                "message": "pyserial is not installed",
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
                "port": port,
                "payload": payload,
                "received": None,
                "matched": False,
                "baudrate": baudrate,
                "error_type": "io_error",
                "message": str(error),
            }

        matched = received == encoded
        return {
            "success": matched,
            "port": port,
            "payload": payload,
            "received": received.decode("utf-8", errors="replace"),
            "matched": matched,
            "baudrate": baudrate,
            "error_type": None if matched else "payload_mismatch",
            "message": "loopback ok" if matched else "loopback mismatch",
            "duration_ms": int((time.perf_counter() - started_at) * 1000),
        }

    def _interface_candidates(self, name: str) -> list[str]:
        value = self.board_profile.get("interfaces", {}).get(name, [])
        if isinstance(value, list):
            return [item for item in value if isinstance(item, str)]
        if isinstance(value, dict):
            candidates = value.get("items")
            if candidates is None:
                candidates = value.get("candidates", [])
            primary = value.get("primary")
            items = [item for item in candidates if isinstance(item, str)]
            if isinstance(primary, str) and primary not in items:
                return [primary, *items]
            return items
        return []