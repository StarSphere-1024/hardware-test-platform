"""Capability contracts shared across platform-specific implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..adapters.base import PlatformAdapter


class CapabilityBase(ABC):
    name: str

    def __init__(self, adapter: PlatformAdapter, board_profile: dict[str, Any] | None = None) -> None:
        self.adapter = adapter
        self.board_profile = dict(board_profile or {})


class NetworkCapabilityContract(CapabilityBase):
    name = "network"

    @abstractmethod
    def list_interfaces(self, *, include_loopback: bool = False) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def resolve_primary(self, candidates: list[str] | None = None) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def ping(self, target_ip: str, *, interface: str | None = None, count: int = 1, timeout: int = 5) -> dict[str, Any]:
        raise NotImplementedError


class SerialCapabilityContract(CapabilityBase):
    name = "serial"

    @abstractmethod
    def list_ports(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def resolve_primary(self, candidates: list[str] | None = None) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def port_exists(self, port: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def loopback_test(
        self,
        port: str,
        *,
        payload: str,
        baudrate: int = 115200,
        timeout: int = 5,
    ) -> dict[str, Any]:
        raise NotImplementedError


class GPIOCapabilityContract(CapabilityBase):
    name = "gpio"

    @abstractmethod
    def list_chips(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def chip_exists(self, chip: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def physical_to_logical(self, pin: int) -> int | None:
        raise NotImplementedError

    @abstractmethod
    def describe_pin(self, physical_pin: int) -> dict[str, Any]:
        raise NotImplementedError


class I2CCapabilityContract(CapabilityBase):
    name = "i2c"

    @abstractmethod
    def list_buses(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def bus_exists(self, bus: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def resolve_primary(self, candidates: list[str] | None = None) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def scan_buses(self, buses: list[str] | None = None) -> dict[str, Any]:
        raise NotImplementedError


class RTCCapabilityContract(CapabilityBase):
    name = "rtc"

    @abstractmethod
    def list_devices(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def device_exists(self, device: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def resolve_primary(self, candidates: list[str] | None = None) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def read_time(self, device: str | None = None) -> dict[str, Any]:
        raise NotImplementedError


class SystemInfoCapabilityContract(CapabilityBase):
    name = "system_info"

    @abstractmethod
    def collect(self) -> dict[str, Any]:
        raise NotImplementedError