from __future__ import annotations

from functions.i2c.test_i2c_scan import test_i2c_scan as i2c_scan_function


class _FakeI2CCapability:
    def __init__(self) -> None:
        self.calls = []

    def scan_buses(self, buses=None):
        self.calls.append(buses)
        bus_list = buses or ["/dev/i2c-0", "/dev/i2c-2"]
        return {
            "success": True,
            "requested_buses": list(bus_list),
            "bus_count": len(bus_list),
            "buses": [{"bus": item, "exists": True} for item in bus_list],
            "error_type": None,
            "message": f"i2c scan ok, buses={len(bus_list)}",
        }


def test_i2c_scan_uses_i2c_capability() -> None:
    capability = _FakeI2CCapability()

    result = i2c_scan_function(bus="/dev/i2c-0", scan_all=False, capability_registry={"i2c": capability})

    assert result["code"] == 0
    assert result["status"] == "passed"
    assert result["metrics"]["bus_count"] == 1
    assert result["details"]["requested_buses"] == ["/dev/i2c-0"]
    assert result["details"]["buses"][0]["bus"] == "/dev/i2c-0"
    assert capability.calls == [["/dev/i2c-0"]]
