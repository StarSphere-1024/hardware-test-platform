"""Zephyr RTC capability skeleton."""

from __future__ import annotations

from typing import Any

from ..base import RTCCapabilityContract
from ._base import ZephyrCapabilityMixin


class ZephyrRTCCapability(ZephyrCapabilityMixin, RTCCapabilityContract):
    def list_devices(self) -> list[str]:
        raise self._not_implemented("list_devices")

    def device_exists(self, device: str) -> bool:
        raise self._not_implemented("device_exists")

    def resolve_primary(self, candidates: list[str] | None = None) -> str | None:
        raise self._not_implemented("resolve_primary")

    def read_time(self, device: str | None = None) -> dict[str, Any]:
        raise self._not_implemented("read_time")