"""Adapter and capability registry for platform assembly."""

from __future__ import annotations

from typing import Any

from framework.config.models import BoardProfile

from .adapters.base import PlatformAdapter
from .adapters.linux import LinuxAdapter
from .capabilities import (
    GPIOCapability,
    I2CCapability,
    NetworkCapability,
    RTCCapability,
    SerialCapability,
    SystemInfoCapability,
)


class PlatformRegistry:
    def __init__(self) -> None:
        self._adapter_factories: dict[str, type[PlatformAdapter]] = {"linux": LinuxAdapter}
        self._capability_factories: dict[str, type] = {
            "network": NetworkCapability,
            "serial": SerialCapability,
            "gpio": GPIOCapability,
            "i2c": I2CCapability,
            "rtc": RTCCapability,
            "system_info": SystemInfoCapability,
        }

    def register_adapter(self, platform_name: str, adapter_cls: type[PlatformAdapter]) -> None:
        self._adapter_factories[platform_name] = adapter_cls

    def register_capability(self, name: str, capability_cls: type) -> None:
        self._capability_factories[name] = capability_cls

    def create_adapter(self, board_profile: BoardProfile, *, config: dict[str, Any] | None = None) -> PlatformAdapter:
        if board_profile.platform not in self._adapter_factories:
            raise KeyError(f"unsupported platform adapter: {board_profile.platform}")
        return self._adapter_factories[board_profile.platform](config=config)

    def create_capability_registry(self, adapter: PlatformAdapter, board_profile: BoardProfile) -> dict[str, Any]:
        board_payload = board_profile.to_dict()
        registry = {
            name: capability_cls(adapter, board_payload)
            for name, capability_cls in self._capability_factories.items()
        }
        return registry

    def create_runtime_registries(self, board_profile: BoardProfile, *, config: dict[str, Any] | None = None) -> tuple[dict[str, PlatformAdapter], dict[str, Any]]:
        adapter = self.create_adapter(board_profile, config=config)
        adapters = {board_profile.platform: adapter}
        capabilities = self.create_capability_registry(adapter, board_profile)
        return adapters, capabilities
