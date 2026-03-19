"""Shared helpers for Zephyr capability skeletons."""

from __future__ import annotations

from ..base import CapabilityBase


class ZephyrCapabilityMixin(CapabilityBase):
    """Zephyr capability mixin providing helper methods for unimplemented exceptions."""

    def _not_implemented(self, operation: str) -> NotImplementedError:
        """Create a NotImplementedError.

        Args:
            operation: Operation name.

        Returns:
            NotImplementedError instance.
        """
        return NotImplementedError(
            f"{self.__class__.__name__}.{operation} requires a Zephyr adapter "
            "and transport-specific implementation"
        )
