"""Minimal adapter abstractions for platform capabilities."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


@dataclass(slots=True)
class CommandResult:
    return_code: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0

    @property
    def success(self) -> bool:
        return self.return_code == 0


class PlatformAdapter(ABC):
    def __init__(self, *, config: dict[str, Any] | None = None) -> None:
        self.config = dict(config or {})

    @property
    @abstractmethod
    def platform_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def execute(self, command: str | Sequence[str], *, timeout: int | None = None, shell: bool | None = None) -> CommandResult:
        raise NotImplementedError

    @abstractmethod
    def get_system_info(self) -> dict[str, Any]:
        raise NotImplementedError

    # These hooks intentionally stay protected. They represent host filesystem
    # access used by Linux-style capability implementations rather than the
    # platform-agnostic adapter contract consumed by the execution layer.
    def _path_exists(self, path: str | Path) -> bool:
        raise NotImplementedError(f"{self.__class__.__name__} does not expose filesystem path checks")

    def _read_text(self, path: str | Path, *, encoding: str = "utf-8") -> str:
        raise NotImplementedError(f"{self.__class__.__name__} does not expose filesystem text reads")

    def _list_paths(self, pattern: str) -> list[str]:
        raise NotImplementedError(f"{self.__class__.__name__} does not expose filesystem path discovery")
