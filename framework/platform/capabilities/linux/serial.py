"""Linux serial capability implementation."""

from __future__ import annotations

import time
from typing import Any

from ..base import SerialCapabilityContract


class LinuxSerialCapability(SerialCapabilityContract):
    """Linux serial capability implementation.

    Supports device enumeration and loopback tests.
    """

    def list_ports(self) -> list[str]:
        """List serial devices in the system.

        Returns:
            Sorted list of serial device paths.
        """
        ports: list[str] = []
        for pattern in ("/dev/ttyS*", "/dev/ttyUSB*", "/dev/ttyACM*"):
            ports.extend(self.adapter._list_paths(pattern))
        return sorted(set(ports))

    def resolve_bound_interface(self, declared: list[str] | None = None) -> str | None:
        """Resolve bound serial interface.

        Args:
            declared: List of declared interfaces, optional.

        Returns:
            Bound interface path, or None if not found.
        """
        preferred = declared or self._declared_interfaces("uart")
        available = set(self.list_ports())
        for candidate in preferred:
            if candidate in available:
                return candidate
        return None

    def port_exists(self, port: str) -> bool:
        """Check if serial device exists.

        Args:
            port: Serial device path.

        Returns:
            True if device exists, False otherwise.
        """
        return self.adapter._path_exists(port)

    def loopback_test(
        self,
        port: str,
        *,
        payload: str,
        baudrate: int = 115200,
        timeout: int = 5,
    ) -> dict[str, Any]:
        """Execute serial loopback test.

        Args:
            port: Serial device path.
            payload: Test payload data.
            baudrate: Baud rate, defaults to 115200.
            timeout: Timeout in seconds, defaults to 5.

        Returns:
            Dictionary containing loopback test results including sent
            and received data.
        """
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

    def _declared_interfaces(self, name: str) -> list[str]:
        """Get declared interfaces from board profile.

        Args:
            name: Interface name.

        Returns:
            List of declared interface paths.
        """
        value = self.board_profile.get("interfaces", {}).get(name, [])
        if isinstance(value, list):
            return [item for item in value if isinstance(item, str)]
        if isinstance(value, dict):
            items = value.get("items")
            return (
                [item for item in items if isinstance(item, str)]
                if isinstance(items, list)
                else []
            )
        return []
