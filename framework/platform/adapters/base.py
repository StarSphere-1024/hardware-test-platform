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
    def path_exists(self, path: str | Path) -> bool:
        raise NotImplementedError

    @abstractmethod
    def read_text(self, path: str | Path, *, encoding: str = "utf-8") -> str:
        raise NotImplementedError

    @abstractmethod
    def list_paths(self, pattern: str) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def get_system_info(self) -> dict[str, Any]:
        raise NotImplementedError
