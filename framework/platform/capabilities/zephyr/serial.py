"""Zephyr serial capability skeleton."""

from __future__ import annotations

from typing import Any

from ..base import SerialCapabilityContract
from ._base import ZephyrCapabilityMixin


class ZephyrSerialCapability(ZephyrCapabilityMixin, SerialCapabilityContract):
    def list_ports(self) -> list[str]:
        raise self._not_implemented("list_ports")

    def resolve_primary(self, candidates: list[str] | None = None) -> str | None:
        raise self._not_implemented("resolve_primary")

    def port_exists(self, port: str) -> bool:
        raise self._not_implemented("port_exists")

    def loopback_test(
        self,
        port: str,
        *,
        payload: str,
        baudrate: int = 115200,
        timeout: int = 5,
    ) -> dict[str, Any]:
        raise self._not_implemented("loopback_test")