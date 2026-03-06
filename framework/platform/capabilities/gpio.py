"""Linux GPIO capability."""

from __future__ import annotations

from typing import Any

from ..adapters.base import PlatformAdapter


class GPIOCapability:
    name = "gpio"

    def __init__(self, adapter: PlatformAdapter, board_profile: dict[str, Any] | None = None) -> None:
        self.adapter = adapter
        self.board_profile = dict(board_profile or {})

    def list_chips(self) -> list[str]:
        return sorted(self.adapter.list_paths("/dev/gpiochip*"))

    def chip_exists(self, chip: str) -> bool:
        return self.adapter.path_exists(chip)

    def physical_to_logical(self, pin: int) -> int | None:
        mapping = self.board_profile.get("metadata", {}).get("gpio_mapping", {})
        if not isinstance(mapping, dict) or not mapping:
            mapping = self.board_profile.get("gpio", {}).get("physical_to_logical", {})
        if not isinstance(mapping, dict):
            return None
        value = mapping.get(str(pin), mapping.get(pin))
        return int(value) if value is not None else None

    def describe_pin(self, physical_pin: int) -> dict[str, Any]:
        logical_pin = self.physical_to_logical(physical_pin)
        chips = self.list_chips()
        return {
            "physical_pin": physical_pin,
            "logical_pin": logical_pin,
            "chip_count": len(chips),
            "chips": chips,
            "available": logical_pin is not None and bool(chips),
        }
