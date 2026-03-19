"""Minimal adapter abstractions for platform capabilities."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class CommandResult:
    """Command execution result dataclass."""

    return_code: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0

    @property
    def success(self) -> bool:
        """Check if command executed successfully.

        Returns:
            True if return code is 0, False otherwise.
        """
        return self.return_code == 0


class PlatformAdapter(ABC):
    """Base platform adapter class.

    Defines generic interfaces for platform-specific operations.
    """

    def __init__(self, *, config: dict[str, Any] | None = None) -> None:
        """Initialize platform adapter.

        Args:
            config: Configuration dictionary, optional.
        """
        self.config = dict(config or {})

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Get platform name.

        Returns:
            Platform name string.
        """
        raise NotImplementedError

    @abstractmethod
    def execute(
        self,
        command: str | Sequence[str],
        *,
        timeout: int | None = None,
        shell: bool | None = None,
    ) -> CommandResult:
        """Execute system command.

        Args:
            command: Command to execute.
            timeout: Timeout in seconds, optional.
            shell: Whether to use shell execution, optional.

        Returns:
            CommandResult containing execution result.
        """
        raise NotImplementedError

    @abstractmethod
    def get_system_info(self) -> dict[str, Any]:
        """Get system information.

        Returns:
            Dictionary containing system information.
        """
        raise NotImplementedError

    # These hooks intentionally stay protected. They represent host filesystem
    # access used by Linux-style capability implementations rather than the
    # platform-agnostic adapter contract consumed by the execution layer.
    def _path_exists(self, path: str | Path) -> bool:
        """Check if path exists (internal method).

        Args:
            path: Path to check.

        Returns:
            True if path exists, False otherwise.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not expose filesystem path checks"
        )

    def _read_text(self, path: str | Path, *, encoding: str = "utf-8") -> str:
        """Read file text content (internal method).

        Args:
            path: File path.
            encoding: File encoding, defaults to utf-8.

        Returns:
            File text content.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not expose filesystem text reads"
        )

    def _list_paths(self, pattern: str) -> list[str]:
        """List file paths matching pattern (internal method).

        Args:
            pattern: Filename pattern.

        Returns:
            List of matching paths.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not expose filesystem path discovery"
        )
