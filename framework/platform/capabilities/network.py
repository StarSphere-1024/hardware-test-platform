"""Linux network capability."""

from __future__ import annotations

from typing import Any

from ..adapters.base import PlatformAdapter


class NetworkCapability:
    name = "network"

    def __init__(self, adapter: PlatformAdapter, board_profile: dict[str, Any] | None = None) -> None:
        self.adapter = adapter
        self.board_profile = dict(board_profile or {})

    def list_interfaces(self, *, include_loopback: bool = False) -> list[str]:
        interfaces = [path.rsplit("/", 1)[-1] for path in self.adapter.list_paths("/sys/class/net/*")]
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
        return {
            "success": result.success,
            "return_code": result.return_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_ms": result.duration_ms,
        }
