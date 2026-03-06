"""Platform adapters and capabilities."""

from .adapters import CommandResult, LinuxAdapter, PlatformAdapter
from .registry import PlatformRegistry

__all__ = ["CommandResult", "LinuxAdapter", "PlatformAdapter", "PlatformRegistry"]
