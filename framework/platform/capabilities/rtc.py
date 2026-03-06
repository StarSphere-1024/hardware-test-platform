"""Linux RTC capability."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..adapters.base import PlatformAdapter


class RTCCapability:
    name = "rtc"

    def __init__(self, adapter: PlatformAdapter, board_profile: dict[str, Any] | None = None) -> None:
        self.adapter = adapter
        self.board_profile = dict(board_profile or {})

    def list_devices(self) -> list[str]:
        devices = self.adapter.list_paths("/dev/rtc*")
        return sorted([path for path in devices if path != "/dev/rtc"] + (["/dev/rtc"] if "/dev/rtc" in devices else []))

    def device_exists(self, device: str) -> bool:
        return self.adapter.path_exists(device)

    def resolve_primary(self, candidates: list[str] | None = None) -> str | None:
        preferred = candidates or self.board_profile.get("interfaces", {}).get("rtc", [])
        for candidate in preferred:
            if self.adapter.path_exists(candidate):
                return candidate
        return None

    def read_time(self, device: str | None = None) -> dict[str, Any]:
        rtc_device = device or self.resolve_primary()
        if not rtc_device:
            return {
                "success": False,
                "error_type": "device_not_found",
                "message": "rtc device not found",
            }

        result = self.adapter.execute(["hwclock", f"--rtc={rtc_device}", "--show"], timeout=5)
        if result.success and result.stdout.strip():
            parsed = self._parse_hwclock_output(result.stdout)
            if parsed is not None:
                return {
                    "success": True,
                    "device": rtc_device,
                    "datetime": parsed,
                    "source": "hwclock",
                    "raw": result.stdout.strip(),
                }

        sysfs_name = rtc_device.split("/")[-1]
        for candidate in (
            f"/sys/class/rtc/{sysfs_name}/since_epoch",
            "/sys/class/rtc/rtc0/since_epoch",
        ):
            if self.adapter.path_exists(candidate):
                raw = self.adapter.read_text(candidate).strip().split(".")[0]
                epoch = int(raw)
                return {
                    "success": True,
                    "device": rtc_device,
                    "datetime": datetime.fromtimestamp(epoch, tz=timezone.utc),
                    "source": "sysfs",
                    "raw": raw,
                }

        return {
            "success": False,
            "device": rtc_device,
            "error_type": "read_failed",
            "message": result.stderr.strip() or "unable to read rtc time",
        }

    def _parse_hwclock_output(self, output: str) -> datetime | None:
        first_line = output.strip().splitlines()[0] if output.strip() else ""
        head = first_line.split(".")[0].strip()
        for pattern in ("%Y-%m-%d %H:%M:%S", "%a %d %b %Y %I:%M:%S %p %Z"):
            try:
                parsed = datetime.strptime(head, pattern)
                return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
            except ValueError:
                continue
        return None
