"""Zephyr I2C capability skeleton."""

from __future__ import annotations

from typing import Any

from ..base import I2CCapabilityContract
from ._base import ZephyrCapabilityMixin


class ZephyrI2CCapability(ZephyrCapabilityMixin, I2CCapabilityContract):
    """Zephyr I2C capability skeleton for future Zephyr MCU backend."""

    def list_buses(self) -> list[str]:
        """List I2C buses in the system."""
        raise self._not_implemented("list_buses")

    def bus_exists(self, bus: str) -> bool:
        """Check if I2C bus exists.

        Args:
            bus: I2C bus path.
        """
        raise self._not_implemented("bus_exists")

    def resolve_bound_interface(self, declared: list[str] | None = None) -> str | None:
        """Resolve bound I2C interface.

        Args:
            declared: List of declared interfaces, optional.
        """
        raise self._not_implemented("resolve_bound_interface")

    def scan_buses(self, buses: list[str] | None = None) -> dict[str, Any]:
        """Scan I2C buses.

        Args:
            buses: List of buses to scan, optional.
        """
        raise self._not_implemented("scan_buses")
