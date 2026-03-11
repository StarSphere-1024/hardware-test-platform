"""Zephyr capability skeletons.

These classes define the module layout and public names for a future Zephyr MCU
backend. They intentionally raise ``NotImplementedError`` until a Zephyr
adapter and transport bindings are introduced.
"""

from .gpio import ZephyrGPIOCapability
from .i2c import ZephyrI2CCapability
from .network import ZephyrNetworkCapability
from .rtc import ZephyrRTCCapability
from .serial import ZephyrSerialCapability
from .system_info import ZephyrSystemInfoCapability

__all__ = [
	"ZephyrGPIOCapability",
	"ZephyrI2CCapability",
	"ZephyrNetworkCapability",
	"ZephyrRTCCapability",
	"ZephyrSerialCapability",
	"ZephyrSystemInfoCapability",
]