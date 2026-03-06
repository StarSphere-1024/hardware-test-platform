"""Configuration loading and resolution utilities."""

from .errors import (
    ConfigError,
    ConfigFileNotFoundError,
    OverrideNotAllowedError,
    ProfileNotSupportedError,
    SchemaValidationError,
    TemplateResolutionError,
)
from .loader import ConfigLoader
from .models import (
    BoardProfile,
    CaseSpec,
    FixtureSpec,
    FunctionInvocationSpec,
    GlobalConfig,
    ResolvedExecutionConfig,
)
from .resolver import ConfigResolver

__all__ = [
    "BoardProfile",
    "CaseSpec",
    "ConfigError",
    "ConfigFileNotFoundError",
    "ConfigLoader",
    "ConfigResolver",
    "FixtureSpec",
    "FunctionInvocationSpec",
    "GlobalConfig",
    "OverrideNotAllowedError",
    "ProfileNotSupportedError",
    "ResolvedExecutionConfig",
    "SchemaValidationError",
    "TemplateResolutionError",
]
