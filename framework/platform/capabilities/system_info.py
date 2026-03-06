"""System information capability."""

from __future__ import annotations

from typing import Any

from ..adapters.base import PlatformAdapter


class SystemInfoCapability:
    name = "system_info"

    def __init__(self, adapter: PlatformAdapter, board_profile: dict[str, Any] | None = None) -> None:
        self.adapter = adapter
        self.board_profile = dict(board_profile or {})

    def collect(self) -> dict[str, Any]:
        info = self.adapter.get_system_info()
        info["board_profile"] = self.board_profile.get("profile_name")
        info["declared_platform"] = self.board_profile.get("platform")
        return info
