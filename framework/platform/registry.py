"""Adapter and capability registry for platform assembly."""

from __future__ import annotations

from typing import Any

from framework.config.models import BoardProfile

from .adapters.base import PlatformAdapter
from .adapters.linux import LinuxAdapter
from .capabilities.base import CapabilityBase
from .capabilities.linux import (
    LinuxGPIOCapability,
    LinuxI2CCapability,
    LinuxNetworkCapability,
    LinuxRTCCapability,
    LinuxSerialCapability,
    LinuxSystemInfoCapability,
)


class PlatformRegistry:
    """Platform registry.

    Manages adapter and capability registration and creation.
    """

    def __init__(self) -> None:
        """Initialize platform registry with default adapters and capabilities."""
        self._adapter_factories: dict[str, type[PlatformAdapter]] = {
            "linux": LinuxAdapter
        }
        self._capability_factories_by_platform: dict[
            str, dict[str, type[CapabilityBase]]
        ] = {
            "linux": {
                "network": LinuxNetworkCapability,
                "serial": LinuxSerialCapability,
                "gpio": LinuxGPIOCapability,
                "i2c": LinuxI2CCapability,
                "rtc": LinuxRTCCapability,
                "system_info": LinuxSystemInfoCapability,
            }
        }

    def register_adapter(
        self, platform_name: str, adapter_cls: type[PlatformAdapter]
    ) -> None:
        """Register platform adapter.

        Args:
            platform_name: Platform name.
            adapter_cls: Adapter class.
        """
        self._adapter_factories[platform_name] = adapter_cls

    def register_capability(
        self, platform_name: str, name: str, capability_cls: type[CapabilityBase]
    ) -> None:
        """Register platform capability.

        Args:
            platform_name: Platform name.
            name: Capability name.
            capability_cls: Capability class.
        """
        self._capability_factories_by_platform.setdefault(platform_name, {})[name] = (
            capability_cls
        )

    def create_adapter(
        self, board_profile: BoardProfile, *, config: dict[str, Any] | None = None
    ) -> PlatformAdapter:
        """Create platform adapter instance.

        Args:
            board_profile: Board profile configuration.
            config: Configuration dictionary, optional.

        Returns:
            Platform adapter instance.

        Raises:
            KeyError: When platform is not supported.
        """
        if board_profile.platform not in self._adapter_factories:
            raise KeyError(f"unsupported platform adapter: {board_profile.platform}")
        return self._adapter_factories[board_profile.platform](config=config)

    def create_capability_registry(
        self, adapter: PlatformAdapter, board_profile: BoardProfile
    ) -> dict[str, Any]:
        """Create capability registry.

        Args:
            adapter: Platform adapter instance.
            board_profile: Board profile configuration.

        Returns:
            Capability registry dictionary.

        Raises:
            KeyError: When capability platform is not supported.
        """
        capability_factories = self._capability_factories_by_platform.get(
            board_profile.platform
        )
        if capability_factories is None:
            raise KeyError(f"unsupported capability platform: {board_profile.platform}")
        board_payload = board_profile.to_dict()
        registry = {
            name: capability_cls(adapter, board_payload)
            for name, capability_cls in capability_factories.items()
        }
        return registry

    def create_runtime_registries(
        self, board_profile: BoardProfile, *, config: dict[str, Any] | None = None
    ) -> tuple[dict[str, PlatformAdapter], dict[str, Any]]:
        """Create runtime registries.

        Args:
            board_profile: Board profile configuration.
            config: Configuration dictionary, optional.

        Returns:
            Tuple containing adapter registry and capability registry.
        """
        adapter = self.create_adapter(board_profile, config=config)
        adapters = {board_profile.platform: adapter}
        capabilities = self.create_capability_registry(adapter, board_profile)
        return adapters, capabilities
