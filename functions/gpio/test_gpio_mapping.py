"""Minimal GPIO mapping validation backed by the platform gpio capability."""

from __future__ import annotations

from typing import Any

__test__ = False


def test_gpio_mapping(
    physical_pin: int,
    capability_registry: dict[str, Any] | None = None,
    execution_context: Any | None = None,
) -> dict[str, Any]:
    """Validate GPIO mapping for a physical pin.

    Args:
        physical_pin: Physical pin number to validate.
        capability_registry: Registry of available capabilities.
        execution_context: Execution context with injected capabilities.

    Returns:
        Dictionary with code, status, message, and details about the GPIO mapping.
    """
    registry = (
        capability_registry
        or getattr(execution_context, "capability_registry", None)
        or {}
    )
    gpio = registry.get("gpio")
    if gpio is None:
        return {
            "code": -2,
            "message": "gpio capability is not available",
            "details": {"physical_pin": physical_pin},
        }

    description = gpio.describe_pin(physical_pin)
    success = bool(description.get("success", description.get("available", False)))
    return {
        "code": 0 if success else -1,
        "status": "passed" if success else "failed",
        "message": description.get("message")
        or (
            f"gpio mapping ok for physical pin {physical_pin}"
            if success
            else f"gpio mapping unavailable for physical pin {physical_pin}"
        ),
        "details": description,
    }
