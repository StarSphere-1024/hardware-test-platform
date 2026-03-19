"""Zephyr serial capability skeleton."""

from __future__ import annotations

from typing import Any

from ..base import SerialCapabilityContract
from ._base import ZephyrCapabilityMixin


class ZephyrSerialCapability(ZephyrCapabilityMixin, SerialCapabilityContract):
    """Zephyr serial capability skeleton for future Zephyr MCU backend."""

    def list_ports(self) -> list[str]:
        """List serial devices in the system."""
        raise self._not_implemented("list_ports")

    def resolve_bound_interface(self, declared: list[str] | None = None) -> str | None:
        """Resolve bound serial interface.

        Args:
            declared: List of declared interfaces, optional.
        """
        raise self._not_implemented("resolve_bound_interface")

    def port_exists(self, port: str) -> bool:
        """Check if serial device exists.

        Args:
            port: Serial device path.
        """
        raise self._not_implemented("port_exists")

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
        """
        raise self._not_implemented("loopback_test")
