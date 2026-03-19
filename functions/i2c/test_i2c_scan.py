"""Minimal I2C scan function backed by the platform i2c capability."""

from __future__ import annotations

from typing import Any

__test__ = False


def test_i2c_scan(
    bus: str | None = None,
    scan_all: bool = False,
    capability_registry: dict[str, Any] | None = None,
    execution_context: Any | None = None,
) -> dict[str, Any]:
    """Scan I2C buses for connected devices.

    Args:
        bus: Specific I2C bus to scan, or None for default.
        scan_all: If True, scan all available I2C buses.
        capability_registry: Registry of available capabilities.
        execution_context: Execution context with injected capabilities.

    Returns:
        Dictionary with code, status, message, details, and metrics about the I2C scan.
    """
    registry = (
        capability_registry
        or getattr(execution_context, "capability_registry", None)
        or {}
    )
    i2c = registry.get("i2c")
    if i2c is None:
        return {
            "code": -2,
            "message": "i2c capability is not available",
            "details": {"bus": bus, "scan_all": scan_all},
        }

    buses = None if scan_all else ([bus] if bus else None)
    result = i2c.scan_buses(buses)
    success = bool(result.get("success", False))
    return {
        "code": 0 if success else -1,
        "status": "passed" if success else "failed",
        "message": result.get("message")
        or (
            f"i2c scan ok, buses={result.get('bus_count', 0)}"
            if success
            else "i2c scan failed"
        ),
        "details": {
            "requested_bus": bus,
            "scan_all": scan_all,
            "requested_buses": result.get("requested_buses", buses or []),
            "buses": result.get("buses", []),
            "error_type": result.get("error_type"),
        },
        "metrics": {
            "bus_count": result.get("bus_count", 0),
        },
    }
