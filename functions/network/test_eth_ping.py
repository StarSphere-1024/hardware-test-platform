"""Minimal Ethernet ping function backed by the platform capability registry."""

from __future__ import annotations

import re
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
    packet_loss = _parse_packet_loss(stdout)
    avg_latency_ms = _parse_average_latency(stdout)
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
            "interface": selected_interface,
            "packet_loss": packet_loss,
            "stdout": stdout,
            "stderr": ping_result.get("stderr", ""),
        },
        "metrics": {
            "packet_loss": packet_loss,
            "avg_latency_ms": avg_latency_ms,
        },
    }


def _parse_packet_loss(output: str) -> float:
    match = re.search(r"([\d.]+)%\s+packet loss", output)
    if match:
        return float(match.group(1))
    return 100.0 if output else 0.0


def _parse_average_latency(output: str) -> float:
    match = re.search(r"(?:rtt|round-trip) min/avg/max(?:/mdev)? = [\d.]+/([\d.]+)/", output)
    if match:
        return float(match.group(1))
    return 0.0
