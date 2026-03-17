"""Typed configuration errors used by the loading and resolving pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ConfigError(Exception):
    error_type: str
    message: str
    field_path: str | None = None
    source: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        Exception.__init__(self, self.__str__())

    def __str__(self) -> str:
        segments = [f"[{self.error_type}]", self.message]
        if self.field_path:
            segments.append(f"field={self.field_path}")
        if self.source:
            segments.append(f"source={self.source}")
        return " ".join(segments)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_type": self.error_type,
            "message": self.message,
            "field_path": self.field_path,
            "source": self.source,
            "details": dict(self.details),
        }


class ConfigFileNotFoundError(ConfigError):
    def __init__(
        self, message: str, *, field_path: str | None = None, source: str | None = None
    ) -> None:
        super().__init__(
            "file_not_found", message, field_path=field_path, source=source
        )


class SchemaValidationError(ConfigError):
    def __init__(
        self, message: str, *, field_path: str | None = None, source: str | None = None
    ) -> None:
        super().__init__(
            "schema_invalid", message, field_path=field_path, source=source
        )


class TemplateResolutionError(ConfigError):
    def __init__(
        self, message: str, *, field_path: str | None = None, source: str | None = None
    ) -> None:
        super().__init__(
            "template_unresolved", message, field_path=field_path, source=source
        )


class OverrideNotAllowedError(ConfigError):
    def __init__(
        self, message: str, *, field_path: str | None = None, source: str | None = None
    ) -> None:
        super().__init__(
            "override_not_allowed", message, field_path=field_path, source=source
        )


class ProfileNotSupportedError(ConfigError):
    def __init__(
        self, message: str, *, field_path: str | None = None, source: str | None = None
    ) -> None:
        super().__init__(
            "profile_not_supported", message, field_path=field_path, source=source
        )
