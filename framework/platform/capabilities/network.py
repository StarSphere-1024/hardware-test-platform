"""Linux network capability."""

from __future__ import annotations

import re
from typing import Any

from ..adapters.base import PlatformAdapter


class NetworkCapability:
    name = "network"

    def __init__(self, adapter: PlatformAdapter, board_profile: dict[str, Any] | None = None) -> None:
        self.adapter = adapter
        self.board_profile = dict(board_profile or {})

    def list_interfaces(self, *, include_loopback: bool = False) -> list[str]:
        interfaces = [path.rsplit("/", 1)[-1] for path in self.adapter._list_paths("/sys/class/net/*")]
        if include_loopback:
            return interfaces
        return [name for name in interfaces if name != "lo"]

    def resolve_primary(self, candidates: list[str] | None = None) -> str | None:
        preferred = candidates or self.board_profile.get("interfaces", {}).get("eth", [])
        available = set(self.list_interfaces(include_loopback=True))
        for candidate in preferred:
            if candidate in available:
                return candidate
        return None

    def ping(self, target_ip: str, *, interface: str | None = None, count: int = 1, timeout: int = 5) -> dict[str, Any]:
        command = ["ping", "-c", str(count), "-W", str(timeout)]
        if interface:
            command.extend(["-I", interface])
        command.append(target_ip)
        result = self.adapter.execute(command, timeout=max(timeout * count, timeout + 1))
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        packet_loss = self._parse_packet_loss(stdout)
        avg_latency_ms = self._parse_average_latency(stdout)
        return {
            "success": result.success,
            "target": target_ip,
            "interface": interface,
            "return_code": result.return_code,
            "stdout": stdout,
            "stderr": stderr,
            "packet_loss": packet_loss,
            "avg_latency_ms": avg_latency_ms,
            "error_type": None if result.success else "probe_failed",
            "message": (
                f"icmp probe to {target_ip} via {interface or 'auto'} ok"
                if result.success
                else f"icmp probe to {target_ip} via {interface or 'auto'} failed"
            ),
            "duration_ms": result.duration_ms,
        }

    def _parse_packet_loss(self, output: str) -> float:
        match = re.search(r"([\d.]+)%\s+packet loss", output)
        if match:
            return float(match.group(1))
        return 100.0 if output else 0.0

    def _parse_average_latency(self, output: str) -> float:
        match = re.search(r"(?:rtt|round-trip) min/avg/max(?:/mdev)? = [\d.]+/([\d.]+)/", output)
        if match:
            return float(match.group(1))
        return 0.0
