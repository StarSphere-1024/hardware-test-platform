"""Linux system information capability implementation."""

from __future__ import annotations

from typing import Any

from ..base import SystemInfoCapabilityContract


class LinuxSystemInfoCapability(SystemInfoCapabilityContract):
    def collect(self) -> dict[str, Any]:
        info = self.adapter.get_system_info()
        info["board_profile"] = self.board_profile.get("profile_name")
        info["declared_platform"] = self.board_profile.get("platform")
        return info
