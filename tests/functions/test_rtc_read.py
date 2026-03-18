from __future__ import annotations

from datetime import UTC, datetime

from functions.rtc.test_rtc_read import test_rtc_read as rtc_read_function


class _FakeRTCCapability:
    def __init__(self) -> None:
        self.calls = []

    def read_time(self, device=None):
        self.calls.append(device)
        return {
            "success": True,
            "device": device or "/dev/rtc0",
            "datetime": datetime(2026, 3, 6, 12, 0, 0, tzinfo=UTC),
            "time_iso": "2026-03-06T12:00:00+00:00",
            "source": "hwclock",
            "raw": "2026-03-06 12:00:00",
            "message": f"rtc read ok on {device or '/dev/rtc0'}",
        }


def test_rtc_read_uses_rtc_capability() -> None:
    capability = _FakeRTCCapability()

    result = rtc_read_function(
        rtc_device="/dev/rtc0", capability_registry={"rtc": capability}
    )

    assert result["code"] == 0
    assert result["status"] == "passed"
    assert result["details"]["rtc_device"] == "/dev/rtc0"
    assert result["details"]["source"] == "hwclock"
    assert result["details"]["time"].startswith("2026-03-06T12:00:00")
    assert capability.calls == ["/dev/rtc0"]
