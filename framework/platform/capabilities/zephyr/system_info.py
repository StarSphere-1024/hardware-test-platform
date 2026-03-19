"""Zephyr system-info capability skeleton."""

from __future__ import annotations

from typing import Any

from ..base import SystemInfoCapabilityContract
from ._base import ZephyrCapabilityMixin


class ZephyrSystemInfoCapability(ZephyrCapabilityMixin, SystemInfoCapabilityContract):
    """Zephyr system information capability skeleton for future Zephyr MCU backend."""

    def collect(self) -> dict[str, Any]:
        """Collect system information."""
        raise self._not_implemented("collect")
