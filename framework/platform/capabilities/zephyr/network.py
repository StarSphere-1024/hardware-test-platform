"""Zephyr network capability skeleton."""

from __future__ import annotations

from typing import Any

from ..base import NetworkCapabilityContract
from ._base import ZephyrCapabilityMixin


class ZephyrNetworkCapability(ZephyrCapabilityMixin, NetworkCapabilityContract):
    def list_interfaces(self, *, include_loopback: bool = False) -> list[str]:
        raise self._not_implemented("list_interfaces")

    def resolve_primary(self, candidates: list[str] | None = None) -> str | None:
        raise self._not_implemented("resolve_primary")

    def ping(self, target_ip: str, *, interface: str | None = None, count: int = 1, timeout: int = 5) -> dict[str, Any]:
        raise self._not_implemented("ping")