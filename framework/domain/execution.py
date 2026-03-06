"""Execution plan and runtime context models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from framework.config.models import ResolvedExecutionConfig

from ._serialization import SerializableModel

_TASK_TYPES = {"fixture", "case", "function"}
_EXECUTION_MODES = {"sequential", "parallel"}


@dataclass(slots=True)
class RetryPolicy(SerializableModel):
    max_retries: int = 0
    interval_seconds: int = 0


@dataclass(slots=True)
class ExecutionTask(SerializableModel):
    task_id: str
    task_type: str
    name: str
    execution_mode: str = "sequential"
    payload: dict[str, Any] = field(default_factory=dict)
    parent_task_id: str | None = None
    timeout: int | None = None
    retry_policy: RetryPolicy | None = None
    stop_on_failure: bool = False
    dependencies: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.task_id:
            raise ValueError("task_id must not be empty")
        if self.task_type not in _TASK_TYPES:
            raise ValueError(f"task_type must be one of {sorted(_TASK_TYPES)}")
        if not self.name:
            raise ValueError("name must not be empty")
        if self.execution_mode not in _EXECUTION_MODES:
            raise ValueError(f"execution_mode must be one of {sorted(_EXECUTION_MODES)}")


@dataclass(slots=True)
class ExecutionPlan(SerializableModel):
    plan_id: str
    root_task: ExecutionTask
    tasks: list[ExecutionTask] = field(default_factory=list)
    execution_policy: dict[str, Any] = field(default_factory=dict)
    resource_requirements: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.plan_id:
            raise ValueError("plan_id must not be empty")
        if not self.tasks:
            self.tasks = [self.root_task]
        task_ids = {task.task_id for task in self.tasks}
        if self.root_task.task_id not in task_ids:
            self.tasks.insert(0, self.root_task)


@dataclass(slots=True)
class ArtifactDirectories(SerializableModel):
    logs_dir: Path
    tmp_dir: Path
    reports_dir: Path


@dataclass(slots=True)
class ExecutionContext(SerializableModel):
    request_id: str
    plan_id: str
    resolved_config: ResolvedExecutionConfig
    adapter_registry: dict[str, Any] = field(default_factory=dict)
    capability_registry: dict[str, Any] = field(default_factory=dict)
    runtime_state: dict[str, Any] = field(default_factory=dict)
    resource_locks: dict[str, Any] = field(default_factory=dict)
    artifacts_dir: ArtifactDirectories | None = None
