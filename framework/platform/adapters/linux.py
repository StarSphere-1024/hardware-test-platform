"""Linux local platform adapter implementation."""

from __future__ import annotations

import platform
import shlex
import socket
import subprocess
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .base import CommandResult, PlatformAdapter


class LinuxAdapter(PlatformAdapter):
    @property
    def platform_name(self) -> str:
        return "linux"

    def execute(
        self,
        command: str | Sequence[str],
        *,
        timeout: int | None = None,
        shell: bool | None = None,
    ) -> CommandResult:
        started_at = time.perf_counter()
        if isinstance(command, str):
            use_shell = True if shell is None else shell
            args: str | Sequence[str] = command if use_shell else shlex.split(command)
        else:
            use_shell = False if shell is None else shell
            args = list(command)

        try:
            completed = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=use_shell,
                check=False,
            )
            return CommandResult(
                return_code=completed.returncode,
                stdout=completed.stdout or "",
                stderr=completed.stderr or "",
                duration_ms=int((time.perf_counter() - started_at) * 1000),
            )
        except subprocess.TimeoutExpired as error:
            return CommandResult(
                return_code=124,
                stdout=(error.stdout or "") if isinstance(error.stdout, str) else "",
                stderr=(error.stderr or "") if isinstance(error.stderr, str) else "",
                duration_ms=int((time.perf_counter() - started_at) * 1000),
            )
        except FileNotFoundError as error:
            return CommandResult(
                return_code=127,
                stderr=str(error),
                duration_ms=int((time.perf_counter() - started_at) * 1000),
            )

    def _path_exists(self, path: str | Path) -> bool:
        return Path(path).exists()

    def _read_text(self, path: str | Path, *, encoding: str = "utf-8") -> str:
        return Path(path).read_text(encoding=encoding)

    def _list_paths(self, pattern: str) -> list[str]:
        return sorted(str(p) for p in Path().glob(pattern))

    def get_system_info(self) -> dict[str, Any]:
        info = {
            "platform": self.platform_name,
            "hostname": socket.gethostname(),
            "machine": platform.machine(),
            "kernel": platform.release(),
            "python_version": platform.python_version(),
        }
        model_path = Path("/proc/device-tree/model")
        if model_path.exists():
            info["device_model"] = model_path.read_text(
                encoding="utf-8", errors="ignore"
            ).strip("\x00\n")
        os_release = Path("/etc/os-release")
        if os_release.exists():
            for line in os_release.read_text(
                encoding="utf-8", errors="ignore"
            ).splitlines():
                if line.startswith("PRETTY_NAME="):
                    info["os"] = line.split("=", 1)[1].strip().strip('"')
                    break
        return info
