"""Platform adapter implementations."""

from .base import CommandResult, PlatformAdapter
from .linux import LinuxAdapter

__all__ = ["CommandResult", "PlatformAdapter", "LinuxAdapter"]
