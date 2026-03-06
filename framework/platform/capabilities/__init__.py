"""Capability providers for the platform layer."""

from .gpio import GPIOCapability
from .i2c import I2CCapability
from .network import NetworkCapability
from .rtc import RTCCapability
from .serial import SerialCapability
from .system_info import SystemInfoCapability

__all__ = [
    "GPIOCapability",
    "I2CCapability",
    "NetworkCapability",
    "RTCCapability",
    "SerialCapability",
    "SystemInfoCapability",
]
