from __future__ import annotations

from framework.platform.capabilities.base import (
    GPIOCapabilityContract,
    I2CCapabilityContract,
    NetworkCapabilityContract,
    RTCCapabilityContract,
    SerialCapabilityContract,
    SystemInfoCapabilityContract,
)
from framework.platform.capabilities.zephyr import (
    ZephyrGPIOCapability,
    ZephyrI2CCapability,
    ZephyrNetworkCapability,
    ZephyrRTCCapability,
    ZephyrSerialCapability,
    ZephyrSystemInfoCapability,
)


def test_zephyr_capability_skeletons_are_exported_with_expected_contracts() -> None:
    assert issubclass(ZephyrNetworkCapability, NetworkCapabilityContract)
    assert issubclass(ZephyrSerialCapability, SerialCapabilityContract)
    assert issubclass(ZephyrGPIOCapability, GPIOCapabilityContract)
    assert issubclass(ZephyrI2CCapability, I2CCapabilityContract)
    assert issubclass(ZephyrRTCCapability, RTCCapabilityContract)
    assert issubclass(ZephyrSystemInfoCapability, SystemInfoCapabilityContract)