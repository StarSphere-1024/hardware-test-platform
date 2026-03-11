"""Minimal Ethernet ping function backed by the platform capability registry."""

from __future__ import annotations

from typing import Any

__test__ = False


def test_eth_ping(
    target_ip: str,
    interface: str | None = None,
    count: int = 1,
    timeout: int = 5,
    capability_registry: dict[str, Any] | None = None,
    execution_context: Any | None = None,
) -> dict[str, Any]:
    registry = capability_registry or getattr(execution_context, "capability_registry", None) or {}
    network = registry.get("network")
    if network is None:
        return {
            "code": -2,
            "message": "network capability is not available",
            "details": {"target_ip": target_ip, "interface": interface},
        }

    selected_interface = interface or network.resolve_primary()
    ping_result = network.ping(target_ip, interface=selected_interface, count=count, timeout=timeout)
    stdout = ping_result.get("stdout", "")
    packet_loss = float(ping_result.get("packet_loss", 0.0))
    avg_latency_ms = float(ping_result.get("avg_latency_ms", 0.0))
    success = bool(ping_result.get("success", False))

    return {
        "code": 0 if success else -1,
        "status": "passed" if success else "failed",
        "message": (
            f"ping {target_ip} via {selected_interface or 'auto'} ok"
            if success
            else f"ping {target_ip} via {selected_interface or 'auto'} failed"
        ),
        "details": {
            "success": success,
            "target_ip": target_ip,
            "interface": ping_result.get("interface", selected_interface),
            "packet_loss": packet_loss,
            "stdout": stdout,
            "stderr": ping_result.get("stderr", ""),
            "error_type": ping_result.get("error_type"),
        },
        "metrics": {
            "packet_loss": packet_loss,
            "avg_latency_ms": avg_latency_ms,
        },
    }
