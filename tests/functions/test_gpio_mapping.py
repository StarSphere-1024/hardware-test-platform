from __future__ import annotations

from functions.gpio.test_gpio_mapping import test_gpio_mapping as gpio_mapping_function


class _FakeGPIOCapability:
    def __init__(self) -> None:
        self.calls = []

    def describe_pin(self, physical_pin):
        self.calls.append(physical_pin)
        return {
            "physical_pin": physical_pin,
            "logical_pin": 51,
            "chip_count": 1,
            "chips": ["/dev/gpiochip0"],
            "available": True,
            "success": True,
            "error_type": None,
            "message": f"gpio mapping ok for physical pin {physical_pin}",
        }


def test_gpio_mapping_uses_gpio_capability() -> None:
    capability = _FakeGPIOCapability()

    result = gpio_mapping_function(
        physical_pin=7, capability_registry={"gpio": capability}
    )

    assert result["code"] == 0
    assert result["status"] == "passed"
    assert result["details"]["logical_pin"] == 51
    assert result["details"]["chip_count"] == 1
    assert result["message"] == "gpio mapping ok for physical pin 7"
    assert capability.calls == [7]
