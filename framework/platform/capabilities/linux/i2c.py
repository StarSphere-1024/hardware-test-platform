"""Linux I2C capability implementation."""

from __future__ import annotations

from typing import Any

from ..base import I2CCapabilityContract


class LinuxI2CCapability(I2CCapabilityContract):
    """Linux I2C capability implementation.

    Supports bus scanning and device detection.
    """

    def list_buses(self) -> list[str]:
        """List I2C buses in the system.

        Returns:
            Sorted list of I2C bus paths.
        """
        return sorted(self.adapter._list_paths("/dev/i2c-*"))

    def bus_exists(self, bus: str) -> bool:
        """Check if I2C bus exists.

        Args:
            bus: I2C bus path.

        Returns:
            True if bus exists, False otherwise.
        """
        return self.adapter._path_exists(bus)

    def resolve_bound_interface(self, declared: list[str] | None = None) -> str | None:
        """Resolve bound I2C interface.

        Args:
            declared: List of declared interfaces, optional.

        Returns:
            Bound interface path, or None if not found.
        """
        preferred = declared or self._declared_interfaces("i2c")
        available = set(self.list_buses())
        for candidate in preferred:
            if candidate in available:
                return candidate
        return None

    def scan_buses(self, buses: list[str] | None = None) -> dict[str, Any]:
        """Scan I2C buses.

        Args:
            buses: List of buses to scan, optional.

        Returns:
            Dictionary containing scan results including bus status and success flag.
        """
        selected_buses = buses or self.list_buses()
        summary = []
        for bus in selected_buses:
            summary.append(
                {
                    "bus": bus,
                    "exists": self.bus_exists(bus),
                }
            )
        success = bool(selected_buses) and all(item["exists"] for item in summary)
        return {
            "success": success,
            "requested_buses": list(selected_buses),
            "bus_count": len(selected_buses),
            "buses": summary,
            "error_type": None
            if success
            else ("device_not_found" if selected_buses else "no_bus_selected"),
            "message": (
                f"i2c scan ok, buses={len(selected_buses)}"
                if success
                else ("i2c scan failed" if selected_buses else "i2c bus not found")
            ),
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
