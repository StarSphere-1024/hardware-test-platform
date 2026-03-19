"""Linux system information capability implementation."""

from __future__ import annotations

from typing import Any

from ..base import SystemInfoCapabilityContract


class LinuxSystemInfoCapability(SystemInfoCapabilityContract):
    """Linux system information capability implementation.

    Collects system hardware and software information.
    """

    def collect(self) -> dict[str, Any]:
        """Collect system information.

        Returns:
            Dictionary containing system information including board profile info.
        """
        info = self.adapter.get_system_info()
        info["board_profile"] = self.board_profile.get("profile_name")
        info["declared_platform"] = self.board_profile.get("platform")
        return info
