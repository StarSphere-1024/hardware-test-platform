"""Linux RTC capability implementation."""

from __future__ import annotations

from datetime import datetime, timezone

from ..base import RTCCapabilityContract


class LinuxRTCCapability(RTCCapabilityContract):
    def list_devices(self) -> list[str]:
        devices = self.adapter._list_paths("/dev/rtc*")
        return sorted([path for path in devices if path != "/dev/rtc"] + (["/dev/rtc"] if "/dev/rtc" in devices else []))

    def device_exists(self, device: str) -> bool:
        return self.adapter._path_exists(device)

    def resolve_primary(self, candidates: list[str] | None = None) -> str | None:
        preferred = candidates or self._interface_candidates("rtc")
        for candidate in preferred:
            if self.adapter._path_exists(candidate):
                return candidate
        return None

    def read_time(self, device: str | None = None) -> dict[str, Any]:
        rtc_device = device or self.resolve_primary()
        if not rtc_device:
            return {
                "success": False,
                "device": device,
                "datetime": None,
                "time_iso": None,
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
                    "time_iso": parsed.isoformat(),
                    "source": "hwclock",
                    "raw": result.stdout.strip(),
                    "message": f"rtc read ok on {rtc_device}",
                }

        sysfs_name = rtc_device.split("/")[-1]
        for candidate in (
            f"/sys/class/rtc/{sysfs_name}/since_epoch",
            "/sys/class/rtc/rtc0/since_epoch",
        ):
            if self.adapter._path_exists(candidate):
                raw = self.adapter._read_text(candidate).strip().split(".")[0]
                epoch = int(raw)
                parsed = datetime.fromtimestamp(epoch, tz=timezone.utc)
                return {
                    "success": True,
                    "device": rtc_device,
                    "datetime": parsed,
                    "time_iso": parsed.isoformat(),
                    "source": "sysfs",
                    "raw": raw,
                    "message": f"rtc read ok on {rtc_device}",
                }

        return {
            "success": False,
            "device": rtc_device,
            "datetime": None,
            "time_iso": None,
            "error_type": "read_failed",
            "message": result.stderr.strip() or "unable to read rtc time",
        }

    def _interface_candidates(self, name: str) -> list[str]:
        value = self.board_profile.get("interfaces", {}).get(name, [])
        if isinstance(value, list):
            return [item for item in value if isinstance(item, str)]
        if isinstance(value, dict):
            candidates = value.get("items")
            if candidates is None:
                candidates = value.get("candidates", [])
            primary = value.get("primary")
            items = [item for item in candidates if isinstance(item, str)]
            if isinstance(primary, str) and primary not in items:
                return [primary, *items]
            return items
        return []

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