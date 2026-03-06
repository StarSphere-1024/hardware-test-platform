"""Result and snapshot models shared by execution and observability layers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from ._serialization import SerializableModel


class ResultStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"
    ABORTED = "aborted"


@dataclass(slots=True)
class ReportArtifact(SerializableModel):
    artifact_type: str
    uri: str
    content_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutionResult(SerializableModel):
    task_id: str
    task_type: str
    name: str
    status: ResultStatus | str
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    code: int | None = None
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float | int] = field(default_factory=dict)
    artifacts: list[ReportArtifact] = field(default_factory=list)
    retry_count: int = 0
    children: list["ExecutionResult"] = field(default_factory=list)


@dataclass(slots=True)
class ResultSnapshot(SerializableModel):
    request_id: str
    plan_id: str
    updated_at: datetime
    current_status: str = "pending"
    fixture: dict[str, Any] = field(default_factory=dict)
    cases: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)
    status_summary: dict[str, int] = field(default_factory=dict)
    runtime_state: dict[str, Any] = field(default_factory=dict)
    results: list[ExecutionResult] = field(default_factory=list)


@dataclass(slots=True)
class DashboardSnapshot(SerializableModel):
    request_id: str
    plan_id: str
    updated_at: datetime
    overall_status: str
    task_counts: dict[str, int] = field(default_factory=dict)
    latest_message: str | None = None
