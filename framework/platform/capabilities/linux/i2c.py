"""Linux I2C capability implementation."""

from __future__ import annotations

from ..base import I2CCapabilityContract


class LinuxI2CCapability(I2CCapabilityContract):
    def list_buses(self) -> list[str]:
        return sorted(self.adapter._list_paths("/dev/i2c-*"))

    def bus_exists(self, bus: str) -> bool:
        return self.adapter._path_exists(bus)

    def resolve_bound_interface(self, declared: list[str] | None = None) -> str | None:
        preferred = declared or self._declared_interfaces("i2c")
        available = set(self.list_buses())
        for candidate in preferred:
            if candidate in available:
                return candidate
        return None

    def scan_buses(self, buses: list[str] | None = None) -> dict[str, Any]:
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
            "error_type": None if success else ("device_not_found" if selected_buses else "no_bus_selected"),
            "message": (
                f"i2c scan ok, buses={len(selected_buses)}"
                if success
                else ("i2c scan failed" if selected_buses else "i2c bus not found")
            ),
        }

    def _declared_interfaces(self, name: str) -> list[str]:
        value = self.board_profile.get("interfaces", {}).get(name, [])
        if isinstance(value, list):
            return [item for item in value if isinstance(item, str)]
        if isinstance(value, dict):
            items = value.get("items")
            return [item for item in items if isinstance(item, str)] if isinstance(items, list) else []
        return []