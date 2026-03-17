"""Zephyr GPIO capability skeleton."""

from __future__ import annotations

from typing import Any

from ..base import GPIOCapabilityContract
from ._base import ZephyrCapabilityMixin


class ZephyrGPIOCapability(ZephyrCapabilityMixin, GPIOCapabilityContract):
    def list_chips(self) -> list[str]:
        raise self._not_implemented("list_chips")

    def chip_exists(self, chip: str) -> bool:
        raise self._not_implemented("chip_exists")

    def physical_to_logical(self, pin: int) -> int | None:
        raise self._not_implemented("physical_to_logical")

    def describe_pin(self, physical_pin: int) -> dict[str, Any]:
        raise self._not_implemented("describe_pin")
