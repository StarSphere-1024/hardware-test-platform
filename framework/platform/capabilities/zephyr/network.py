"""Zephyr network capability skeleton."""

from __future__ import annotations

from typing import Any

from ..base import NetworkCapabilityContract
from ._base import ZephyrCapabilityMixin


class ZephyrNetworkCapability(ZephyrCapabilityMixin, NetworkCapabilityContract):
    """Zephyr network capability skeleton for future Zephyr MCU backend."""

    def list_interfaces(self, *, include_loopback: bool = False) -> list[str]:
        """List network interfaces in the system.

        Args:
            include_loopback: Whether to include loopback interface, defaults to False.
        """
        raise self._not_implemented("list_interfaces")

    def resolve_bound_interface(self, declared: list[str] | None = None) -> str | None:
        """Resolve bound network interface.

        Args:
            declared: List of declared interfaces, optional.
        """
        raise self._not_implemented("resolve_bound_interface")

    def ping(
        self,
        target_ip: str,
        *,
        interface: str | None = None,
        count: int = 1,
        timeout: int = 5,
    ) -> dict[str, Any]:
        """Execute ICMP ping test.

        Args:
            target_ip: Target IP address.
            interface: Network interface to use, optional.
            count: Number of ping packets, defaults to 1.
            timeout: Timeout in seconds, defaults to 5.
        """
        raise self._not_implemented("ping")
