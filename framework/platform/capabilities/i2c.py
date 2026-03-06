"""Linux I2C capability."""

from __future__ import annotations

from typing import Any

from ..adapters.base import PlatformAdapter


class I2CCapability:
    name = "i2c"

    def __init__(self, adapter: PlatformAdapter, board_profile: dict[str, Any] | None = None) -> None:
        self.adapter = adapter
        self.board_profile = dict(board_profile or {})

    def list_buses(self) -> list[str]:
        return sorted(self.adapter.list_paths("/dev/i2c-*"))

    def bus_exists(self, bus: str) -> bool:
        return self.adapter.path_exists(bus)

    def resolve_primary(self, candidates: list[str] | None = None) -> str | None:
        preferred = candidates or self.board_profile.get("interfaces", {}).get("i2c", [])
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
        return {
            "success": bool(selected_buses),
            "bus_count": len(selected_buses),
            "buses": summary,
        }
