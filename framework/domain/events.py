"""Execution event models used by stores and reporters."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from ._serialization import SerializableModel


class EventType(str, Enum):
    """Execution event types."""

    REQUEST_RECEIVED = "request_received"
    PLAN_CREATED = "plan_created"
    TASK_STARTED = "task_started"
    TASK_FINISHED = "task_finished"
    TASK_RETRIED = "task_retried"
    SNAPSHOT_UPDATED = "snapshot_updated"
    REPORT_GENERATED = "report_generated"
    EXECUTION_FAILED = "execution_failed"


class EventStatus(str, Enum):
    """Event status."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


@dataclass(slots=True)
class ExecutionEvent(SerializableModel):
    """Execution event model."""

    event_id: str
    request_id: str
    plan_id: str
    event_type: EventType | str
    timestamp: datetime
    status: EventStatus | str = EventStatus.INFO
    task_id: str | None = None
    task_type: str | None = None
    task_name: str | None = None
    parent_task_id: str | None = None
    attempt: int | None = None
    status_before: str | None = None
    status_after: str | None = None
    message: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EventRecord(SerializableModel):
    """Event record model."""

    sequence: int
    event: ExecutionEvent
    stored_at: datetime
    storage_metadata: dict[str, Any] = field(default_factory=dict)
