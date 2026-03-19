"""Typed configuration errors used by the loading and resolving pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ConfigError(Exception):
    """Base class for configuration errors."""

    error_type: str
    message: str
    field_path: str | None = None
    source: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Initialize exception message."""
        Exception.__init__(self, self.__str__())

    def __str__(self) -> str:
        """Return formatted error message.

        Returns:
            Formatted error message string.
        """
        segments = [f"[{self.error_type}]", self.message]
        if self.field_path:
            segments.append(f"field={self.field_path}")
        if self.source:
            segments.append(f"source={self.source}")
        return " ".join(segments)

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary format.

        Returns:
            Dictionary containing error information.
        """
        return {
            "error_type": self.error_type,
            "message": self.message,
            "field_path": self.field_path,
            "source": self.source,
            "details": dict(self.details),
        }


class ConfigFileNotFoundError(ConfigError):
    """Configuration file not found error."""

    def __init__(
        self, message: str, *, field_path: str | None = None, source: str | None = None
    ) -> None:
        """Initialize configuration not found error.

        Args:
            message: Error message.
            field_path: Related field path.
            source: Configuration source.
        """
        super().__init__(
            "file_not_found", message, field_path=field_path, source=source
        )


class SchemaValidationError(ConfigError):
    """Configuration schema validation error."""

    def __init__(
        self, message: str, *, field_path: str | None = None, source: str | None = None
    ) -> None:
        """Initialize schema validation error.

        Args:
            message: Error message.
            field_path: Related field path.
            source: Configuration source.
        """
        super().__init__(
            "schema_invalid", message, field_path=field_path, source=source
        )


class TemplateResolutionError(ConfigError):
    """Template resolution error."""

    def __init__(
        self, message: str, *, field_path: str | None = None, source: str | None = None
    ) -> None:
        """Initialize template resolution error.

        Args:
            message: Error message.
            field_path: Related field path.
            source: Configuration source.
        """
        super().__init__(
            "template_unresolved", message, field_path=field_path, source=source
        )


class OverrideNotAllowedError(ConfigError):
    """Override not allowed error."""

    def __init__(
        self, message: str, *, field_path: str | None = None, source: str | None = None
    ) -> None:
        """Initialize override not allowed error.

        Args:
            message: Error message.
            field_path: Related field path.
            source: Configuration source.
        """
        super().__init__(
            "override_not_allowed", message, field_path=field_path, source=source
        )


class ProfileNotSupportedError(ConfigError):
    """Board profile not supported error."""

    def __init__(
        self, message: str, *, field_path: str | None = None, source: str | None = None
    ) -> None:
        """Initialize board profile not supported error.

        Args:
            message: Error message.
            field_path: Related field path.
            source: Configuration source.
        """
        super().__init__(
            "profile_not_supported", message, field_path=field_path, source=source
        )
