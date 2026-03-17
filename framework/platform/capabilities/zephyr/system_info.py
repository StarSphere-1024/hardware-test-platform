"""Zephyr system-info capability skeleton."""

from __future__ import annotations

from typing import Any

from ..base import SystemInfoCapabilityContract
from ._base import ZephyrCapabilityMixin


class ZephyrSystemInfoCapability(ZephyrCapabilityMixin, SystemInfoCapabilityContract):
    def collect(self) -> dict[str, Any]:
        raise self._not_implemented("collect")
