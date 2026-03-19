"""Linux GPIO capability implementation."""

from __future__ import annotations

from typing import Any

from ..base import GPIOCapabilityContract


class LinuxGPIOCapability(GPIOCapabilityContract):
    """Linux GPIO capability implementation based on Linux GPIO subsystem."""

    def list_chips(self) -> list[str]:
        """List GPIO chips in the system.

        Returns:
            Sorted list of GPIO chip paths.
        """
        return sorted(self.adapter._list_paths("/dev/gpiochip*"))

    def chip_exists(self, chip: str) -> bool:
        """Check if GPIO chip exists.

        Args:
            chip: GPIO chip path.

        Returns:
            True if chip exists, False otherwise.
        """
        return self.adapter._path_exists(chip)

    def physical_to_logical(self, pin: int) -> int | None:
        """Convert physical pin number to logical pin number.

        Args:
            pin: Physical pin number.

        Returns:
            Logical pin number, or None if conversion fails.
        """
        mapping = self.board_profile.get("metadata", {}).get("gpio_mapping", {})
        if not isinstance(mapping, dict) or not mapping:
            mapping = self.board_profile.get("gpio", {}).get("physical_to_logical", {})
        if not isinstance(mapping, dict):
            return None
        value = mapping.get(str(pin), mapping.get(pin))
        return int(value) if value is not None else None

    def describe_pin(self, physical_pin: int) -> dict[str, Any]:
        """Describe pin information.

        Args:
            physical_pin: Physical pin number.

        Returns:
            Dictionary containing pin information including logical pin, chip info,
            and availability.
        """
        logical_pin = self.physical_to_logical(physical_pin)
        chips = self.list_chips()
        available = logical_pin is not None and bool(chips)
        return {
            "physical_pin": physical_pin,
            "logical_pin": logical_pin,
            "chip_count": len(chips),
            "chips": chips,
            "available": available,
            "success": available,
            "error_type": None
            if available
            else ("mapping_not_found" if logical_pin is None else "device_not_found"),
            "message": (
                f"gpio mapping ok for physical pin {physical_pin}"
                if available
                else f"gpio mapping unavailable for physical pin {physical_pin}"
            ),
        }
