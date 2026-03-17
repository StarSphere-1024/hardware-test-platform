"""Capability contracts and public exports for the platform layer."""

from .base import (
    CapabilityBase,
    GPIOCapabilityContract,
    I2CCapabilityContract,
    NetworkCapabilityContract,
    RTCCapabilityContract,
    SerialCapabilityContract,
    SystemInfoCapabilityContract,
)
from .linux import (
    LinuxGPIOCapability as GPIOCapability,
    LinuxI2CCapability as I2CCapability,
    LinuxNetworkCapability as NetworkCapability,
    LinuxRTCCapability as RTCCapability,
    LinuxSerialCapability as SerialCapability,
    LinuxSystemInfoCapability as SystemInfoCapability,
)

__all__ = [
    "CapabilityBase",
    "GPIOCapability",
    "GPIOCapabilityContract",
    "I2CCapability",
    "I2CCapabilityContract",
    "NetworkCapability",
    "NetworkCapabilityContract",
    "RTCCapability",
    "RTCCapabilityContract",
    "SerialCapability",
    "SerialCapabilityContract",
    "SystemInfoCapability",
    "SystemInfoCapabilityContract",
]
