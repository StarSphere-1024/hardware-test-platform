"""Minimal UART loopback function backed by the platform serial capability."""

from __future__ import annotations

from typing import Any

__test__ = False


def test_uart_loopback(
    port: str,
    payload: str,
    baudrate: int = 115200,
    timeout: int = 5,
    capability_registry: dict[str, Any] | None = None,
    execution_context: Any | None = None,
) -> dict[str, Any]:
    registry = capability_registry or getattr(execution_context, "capability_registry", None) or {}
    serial = registry.get("serial")
    if serial is None:
        return {
            "code": -2,
            "message": "serial capability is not available",
            "details": {"port": port, "payload": payload},
        }

    result = serial.loopback_test(port, payload=payload, baudrate=baudrate, timeout=timeout)
    success = bool(result.get("success", False))
    return {
        "code": 0 if success else -1,
        "status": "passed" if success else "failed",
        "message": result.get("message") or ("uart loopback ok" if success else "uart loopback failed"),
        "details": {
            "port": port,
            "payload": payload,
            "received": result.get("received"),
            "error_type": result.get("error_type"),
        },
        "metrics": {
            "duration_ms": result.get("duration_ms", 0),
            "payload_size": len(payload.encode("utf-8")),
        },
    }
