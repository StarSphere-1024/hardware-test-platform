"""Shared helpers for Zephyr capability skeletons."""

from __future__ import annotations

from ..base import CapabilityBase


class ZephyrCapabilityMixin(CapabilityBase):
    def _not_implemented(self, operation: str) -> NotImplementedError:
        return NotImplementedError(
            f"{self.__class__.__name__}.{operation} requires a Zephyr adapter and transport-specific implementation"
        )