"""Zephyr RTC capability skeleton."""

from __future__ import annotations

from typing import Any

from ..base import RTCCapabilityContract
from ._base import ZephyrCapabilityMixin


class ZephyrRTCCapability(ZephyrCapabilityMixin, RTCCapabilityContract):
    """Zephyr RTC capability skeleton for future Zephyr MCU backend."""

    def list_devices(self) -> list[str]:
        """List RTC devices in the system."""
        raise self._not_implemented("list_devices")

    def device_exists(self, device: str) -> bool:
        """Check if RTC device exists.

        Args:
            device: RTC device path.
        """
        raise self._not_implemented("device_exists")

    def resolve_bound_interface(self, declared: list[str] | None = None) -> str | None:
        """Resolve bound RTC interface.

        Args:
            declared: List of declared interfaces, optional.
        """
        raise self._not_implemented("resolve_bound_interface")

    def read_time(self, device: str | None = None) -> dict[str, Any]:
        """Read RTC device time.

        Args:
            device: RTC device path, optional.
        """
        raise self._not_implemented("read_time")
