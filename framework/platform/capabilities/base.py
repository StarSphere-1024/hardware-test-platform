"""Capability contracts shared across platform-specific implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..adapters.base import PlatformAdapter


class CapabilityBase(ABC):
    """Base capability class.

    Defines generic interfaces for platform-specific capabilities.
    """

    name: str

    def __init__(
        self, adapter: PlatformAdapter, board_profile: dict[str, Any] | None = None
    ) -> None:
        """Initialize capability base class.

        Args:
            adapter: Platform adapter instance.
            board_profile: Board profile configuration, optional.
        """
        self.adapter = adapter
        self.board_profile = dict(board_profile or {})


class NetworkCapabilityContract(CapabilityBase):
    """Network capability contract.

    Defines abstract interfaces for network interfaces and connectivity tests.
    """

    name = "network"

    @abstractmethod
    def list_interfaces(self, *, include_loopback: bool = False) -> list[str]:
        """List network interfaces in the system.

        Args:
            include_loopback: Whether to include loopback interface, defaults to False.

        Returns:
            List of network interface names.
        """
        raise NotImplementedError

    @abstractmethod
    def resolve_bound_interface(self, declared: list[str] | None = None) -> str | None:
        """Resolve bound network interface.

        Args:
            declared: List of declared interfaces, optional.

        Returns:
            Bound interface name, or None if not found.
        """
        raise NotImplementedError

    @abstractmethod
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

        Returns:
            Dictionary containing ping test results.
        """
        raise NotImplementedError


class SerialCapabilityContract(CapabilityBase):
    """Serial capability contract.

    Defines abstract interfaces for serial communication tests.
    """

    name = "serial"

    @abstractmethod
    def list_ports(self) -> list[str]:
        """List serial devices in the system.

        Returns:
            List of serial device paths.
        """
        raise NotImplementedError

    @abstractmethod
    def resolve_bound_interface(self, declared: list[str] | None = None) -> str | None:
        """Resolve bound serial interface.

        Args:
            declared: List of declared interfaces, optional.

        Returns:
            Bound interface path, or None if not found.
        """
        raise NotImplementedError

    @abstractmethod
    def port_exists(self, port: str) -> bool:
        """Check if serial device exists.

        Args:
            port: Serial device path.

        Returns:
            True if device exists, False otherwise.
        """
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
        """Execute serial loopback test.

        Args:
            port: Serial device path.
            payload: Test payload data.
            baudrate: Baud rate, defaults to 115200.
            timeout: Timeout in seconds, defaults to 5.

        Returns:
            Dictionary containing loopback test results.
        """
        raise NotImplementedError


class GPIOCapabilityContract(CapabilityBase):
    """GPIO capability contract.

    Defines abstract interfaces for general-purpose input/output pin tests.
    """

    name = "gpio"

    @abstractmethod
    def list_chips(self) -> list[str]:
        """List GPIO chips in the system.

        Returns:
            List of GPIO chip paths.
        """
        raise NotImplementedError

    @abstractmethod
    def chip_exists(self, chip: str) -> bool:
        """Check if GPIO chip exists.

        Args:
            chip: GPIO chip path.

        Returns:
            True if chip exists, False otherwise.
        """
        raise NotImplementedError

    @abstractmethod
    def physical_to_logical(self, pin: int) -> int | None:
        """Convert physical pin number to logical pin number.

        Args:
            pin: Physical pin number.

        Returns:
            Logical pin number, or None if conversion fails.
        """
        raise NotImplementedError

    @abstractmethod
    def describe_pin(self, physical_pin: int) -> dict[str, Any]:
        """Describe pin information.

        Args:
            physical_pin: Physical pin number.

        Returns:
            Dictionary containing pin information.
        """
        raise NotImplementedError


class I2CCapabilityContract(CapabilityBase):
    """I2C capability contract.

    Defines abstract interfaces for I2C bus scanning and tests.
    """

    name = "i2c"

    @abstractmethod
    def list_buses(self) -> list[str]:
        """List I2C buses in the system.

        Returns:
            List of I2C bus paths.
        """
        raise NotImplementedError

    @abstractmethod
    def bus_exists(self, bus: str) -> bool:
        """Check if I2C bus exists.

        Args:
            bus: I2C bus path.

        Returns:
            True if bus exists, False otherwise.
        """
        raise NotImplementedError

    @abstractmethod
    def resolve_bound_interface(self, declared: list[str] | None = None) -> str | None:
        """Resolve bound I2C interface.

        Args:
            declared: List of declared interfaces, optional.

        Returns:
            Bound interface path, or None if not found.
        """
        raise NotImplementedError

    @abstractmethod
    def scan_buses(self, buses: list[str] | None = None) -> dict[str, Any]:
        """Scan I2C buses.

        Args:
            buses: List of buses to scan, optional.

        Returns:
            Dictionary containing scan results.
        """
        raise NotImplementedError


class RTCCapabilityContract(CapabilityBase):
    """RTC capability contract.

    Defines abstract interfaces for real-time clock reading and tests.
    """

    name = "rtc"

    @abstractmethod
    def list_devices(self) -> list[str]:
        """List RTC devices in the system.

        Returns:
            List of RTC device paths.
        """
        raise NotImplementedError

    @abstractmethod
    def device_exists(self, device: str) -> bool:
        """Check if RTC device exists.

        Args:
            device: RTC device path.

        Returns:
            True if device exists, False otherwise.
        """
        raise NotImplementedError

    @abstractmethod
    def resolve_bound_interface(self, declared: list[str] | None = None) -> str | None:
        """Resolve bound RTC interface.

        Args:
            declared: List of declared interfaces, optional.

        Returns:
            Bound interface path, or None if not found.
        """
        raise NotImplementedError

    @abstractmethod
    def read_time(self, device: str | None = None) -> dict[str, Any]:
        """Read RTC device time.

        Args:
            device: RTC device path, optional.

        Returns:
            Dictionary containing time information.
        """
        raise NotImplementedError


class SystemInfoCapabilityContract(CapabilityBase):
    """System info capability contract.

    Defines abstract interfaces for system information collection.
    """

    name = "system_info"

    @abstractmethod
    def collect(self) -> dict[str, Any]:
        """Collect system information.

        Returns:
            Dictionary containing system information.
        """
        raise NotImplementedError
