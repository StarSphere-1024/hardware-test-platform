"""Minimal RTC read function backed by the platform rtc capability."""

from __future__ import annotations

from typing import Any

__test__ = False


def test_rtc_read(
    rtc_device: str | None = None,
    capability_registry: dict[str, Any] | None = None,
    execution_context: Any | None = None,
) -> dict[str, Any]:
    registry = (
        capability_registry
        or getattr(execution_context, "capability_registry", None)
        or {}
    )
    rtc = registry.get("rtc")
    if rtc is None:
        return {
            "code": -2,
            "message": "rtc capability is not available",
            "details": {"rtc_device": rtc_device},
        }

    result = rtc.read_time(rtc_device)
    success = bool(result.get("success", False))
    time_iso = result.get("time_iso")
    if time_iso is None:
        dt_value = result.get("datetime")
        time_iso = dt_value.isoformat() if hasattr(dt_value, "isoformat") else None
    return {
        "code": 0 if success else -1,
        "status": "passed" if success else "failed",
        "message": result.get("message")
        or (f"rtc read ok on {result.get('device')}" if success else "rtc read failed"),
        "details": {
            "rtc_device": result.get("device", rtc_device),
            "time": time_iso,
            "source": result.get("source"),
            "raw": result.get("raw"),
            "error_type": result.get("error_type"),
        },
    }
