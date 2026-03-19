"""Zephyr GPIO capability skeleton."""

from __future__ import annotations

from typing import Any

from ..base import GPIOCapabilityContract
from ._base import ZephyrCapabilityMixin


class ZephyrGPIOCapability(ZephyrCapabilityMixin, GPIOCapabilityContract):
    """Zephyr GPIO capability skeleton for future Zephyr MCU backend."""

    def list_chips(self) -> list[str]:
        """List GPIO chips in the system."""
        raise self._not_implemented("list_chips")

    def chip_exists(self, chip: str) -> bool:
        """Check if GPIO chip exists.

        Args:
            chip: GPIO chip path.
        """
        raise self._not_implemented("chip_exists")

    def physical_to_logical(self, pin: int) -> int | None:
        """Convert physical pin number to logical pin number.

        Args:
            pin: Physical pin number.
        """
        raise self._not_implemented("physical_to_logical")

    def describe_pin(self, physical_pin: int) -> dict[str, Any]:
        """Describe pin information.

        Args:
            physical_pin: Physical pin number.
        """
        raise self._not_implemented("describe_pin")
