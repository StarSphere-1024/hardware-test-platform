"""Execution request models for CLI and runner entrypoints."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ._serialization import SerializableModel

_TARGET_TYPES = {"function", "case", "fixture"}


@dataclass(slots=True)
class ExecutionRequest(SerializableModel):
    request_id: str
    target_type: str
    target_name: str
    cli_overrides: dict[str, Any] = field(default_factory=dict)
    board_profile: str | None = None
    sn: str | None = None
    operator: str | None = None
    trigger_source: str | None = None

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ValueError("request_id must not be empty")
        if self.target_type not in _TARGET_TYPES:
            raise ValueError(f"target_type must be one of {sorted(_TARGET_TYPES)}")
        if not self.target_name:
            raise ValueError("target_name must not be empty")
