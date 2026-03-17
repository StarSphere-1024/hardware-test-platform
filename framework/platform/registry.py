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
    def __init__(self) -> None:
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
        self._adapter_factories[platform_name] = adapter_cls

    def register_capability(
        self, platform_name: str, name: str, capability_cls: type[CapabilityBase]
    ) -> None:
        self._capability_factories_by_platform.setdefault(platform_name, {})[name] = (
            capability_cls
        )

    def create_adapter(
        self, board_profile: BoardProfile, *, config: dict[str, Any] | None = None
    ) -> PlatformAdapter:
        if board_profile.platform not in self._adapter_factories:
            raise KeyError(f"unsupported platform adapter: {board_profile.platform}")
        return self._adapter_factories[board_profile.platform](config=config)

    def create_capability_registry(
        self, adapter: PlatformAdapter, board_profile: BoardProfile
    ) -> dict[str, Any]:
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
        adapter = self.create_adapter(board_profile, config=config)
        adapters = {board_profile.platform: adapter}
        capabilities = self.create_capability_registry(adapter, board_profile)
        return adapters, capabilities
