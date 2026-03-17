"""Zephyr I2C capability skeleton."""

from __future__ import annotations

from typing import Any

from ..base import I2CCapabilityContract
from ._base import ZephyrCapabilityMixin


class ZephyrI2CCapability(ZephyrCapabilityMixin, I2CCapabilityContract):
    def list_buses(self) -> list[str]:
        raise self._not_implemented("list_buses")

    def bus_exists(self, bus: str) -> bool:
        raise self._not_implemented("bus_exists")

    def resolve_bound_interface(self, declared: list[str] | None = None) -> str | None:
        raise self._not_implemented("resolve_bound_interface")

    def scan_buses(self, buses: list[str] | None = None) -> dict[str, Any]:
        raise self._not_implemented("scan_buses")
