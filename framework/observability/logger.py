"""Unified logging and execution observation helpers."""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from framework.config.models import ResolvedExecutionConfig
from framework.domain.events import EventStatus, EventType, ExecutionEvent
from framework.domain.execution import ExecutionContext, ExecutionPlan, ExecutionTask
from framework.domain.results import ExecutionResult, ResultSnapshot, ResultStatus
from framework.execution.policies import normalize_status, summarize_children

from .event_store import EventStore
from .report_generator import ReportGenerator
from .result_store import ResultStore


class UnifiedLogger:
    """Unified logger creating separate log files for each request."""

    def __init__(self, logs_dir: str | Path = "logs", verbose_level: int = 0) -> None:
        """Initialize unified logger.

        Args:
            logs_dir: Directory for log files
            verbose_level: Verbosity level (0=INFO, 1+=DEBUG)
        """
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.verbose_level = verbose_level
        self._loggers: dict[str, logging.Logger] = {}

    def get_logger(self, request_id: str) -> logging.Logger:
        """Get or create a logger for the given request ID.

        Args:
            request_id: Unique request identifier

        Returns:
            Configured logger instance
        """
        if request_id in self._loggers:
            return self._loggers[request_id]
        logger = logging.getLogger(f"hardware_test_platform.{request_id}")
        log_level = logging.DEBUG if self.verbose_level >= 1 else logging.INFO
        logger.setLevel(log_level)
        logger.propagate = False
        if not logger.handlers:
            handler = logging.FileHandler(
                self.logs_dir / f"{request_id}.log", encoding="utf-8"
            )
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s %(message)s")
            )
            logger.addHandler(handler)
        self._loggers[request_id] = logger
        return logger


class ExecutionObserver:
    """Execution observer for recording events, snapshots, and reports.

    Tracks task states, collects events, writes result snapshots, and generates
    final reports.
    """

    def __init__(
        self,
        *,
        resolved_config: ResolvedExecutionConfig,
        result_store: ResultStore,
        event_store: EventStore,
        report_generator: ReportGenerator,
        logger: UnifiedLogger,
    ) -> None:
        """Initialize ExecutionObserver.

        Args:
            resolved_config: Resolved execution configuration.
            result_store: Result store.
            event_store: Event store.
            report_generator: Report generator.
            logger: Unified logger.
        """
        self.resolved_config = resolved_config
        self.result_store = result_store
        self.event_store = event_store
        self.report_generator = report_generator
        self.logger = logger.get_logger(
            str(
                resolved_config.request.get(
                    "request_id", resolved_config.request.get("kind", "request")
                )
            )
        )
        self.plan_tasks: dict[str, ExecutionTask] = {}
        self.task_states: dict[str, str] = {}
        self.task_results: dict[str, ExecutionResult] = {}
        self.task_started_at: dict[str, datetime] = {}
        self.latest_snapshot: ResultSnapshot | None = None
        self._lock = threading.RLock()

    @property
    def request_id(self) -> str:
        """Get the current request ID.

        Returns:
            Unique request identifier.
        """
        return str(
            self.resolved_config.request.get(
                "request_id", self.resolved_config.request.get("kind", "request")
            )
        )

    def on_plan_created(self, plan: ExecutionPlan) -> None:
        """Handle plan created event.

        Args:
            plan: Created execution plan object.
        """
        with self._lock:
            self.plan_tasks = {task.task_id: task for task in plan.tasks}
            self._append_event(
                event_type=EventType.PLAN_CREATED,
                status=EventStatus.INFO,
                message="execution plan created",
                payload={
                    "target_type": self.resolved_config.request.get("kind", "fixture"),
                    "target_name": (
                        self.resolved_config.request.get("fixture_path")
                        or self.resolved_config.request.get("case_path")
                    ),
                    "selected_board_profile": (
                        self.resolved_config.board_profile.profile_name
                    ),
                    "resolved_case_count": len(self.resolved_config.cases),
                },
                plan_id=plan.plan_id,
            )

    def on_task_started(
        self,
        task: ExecutionTask,
        *,
        plan_id: str,
        attempt: int | None = None,
        status_before: str | None = None,
    ) -> None:
        """Handle task started event.

        Args:
            task: Task that started executing.
            plan_id: Execution plan ID.
            attempt: Current attempt number.
            status_before: Status before task started.
        """
        with self._lock:
            self.task_states[task.task_id] = ResultStatus.RUNNING.value
            self.task_started_at.setdefault(task.task_id, datetime.now(UTC))
            self._append_event(
                event_type=EventType.TASK_STARTED,
                status=EventStatus.INFO,
                message=f"task started: {task.name}",
                plan_id=plan_id,
                task=task,
                attempt=attempt,
                status_before=status_before,
                status_after=ResultStatus.RUNNING.value,
                payload={
                    "timeout": task.timeout,
                    "dependencies": list(task.dependencies),
                    "resolved_interfaces": self.resolved_config.resolved_interfaces,
                },
            )
            self._write_snapshot(plan_id)

    def on_task_retried(
        self,
        task: ExecutionTask,
        *,
        plan_id: str,
        current_attempt: int,
        next_attempt: int,
        retry_interval_seconds: int,
        last_result: ExecutionResult,
    ) -> None:
        """Handle task retried event.

        Args:
            task: Task being retried.
            plan_id: Execution plan ID.
            current_attempt: Current attempt number.
            next_attempt: Next attempt number.
            retry_interval_seconds: Retry interval in seconds.
            last_result: Previous execution result.
        """
        with self._lock:
            self.task_states[task.task_id] = "retrying"
            self._append_event(
                event_type=EventType.TASK_RETRIED,
                status=EventStatus.WARNING,
                message=f"task retrying: {task.name}",
                plan_id=plan_id,
                task=task,
                attempt=current_attempt,
                status_before=normalize_status(last_result.status),
                status_after="retrying",
                payload={
                    "current_attempt": current_attempt,
                    "next_attempt": next_attempt,
                    "retry_interval_seconds": retry_interval_seconds,
                    "last_error_message": last_result.message,
                },
            )
            self._write_snapshot(plan_id)

    def on_task_finished(
        self, task: ExecutionTask, result: ExecutionResult, *, plan_id: str
    ) -> None:
        """Handle task finished event.

        Args:
            task: Completed task.
            result: Task execution result.
            plan_id: Execution plan ID.
        """
        with self._lock:
            normalized = normalize_status(result.status)
            self.task_states[task.task_id] = normalized
            self.task_results[task.task_id] = result
            residual_risk = (
                result.details.get("residual_risk")
                if isinstance(result.details, dict)
                else None
            )
            status = (
                EventStatus.SUCCESS
                if normalized == "passed"
                else EventStatus.ERROR
                if normalized in {"failed", "timeout", "aborted"}
                else EventStatus.INFO
            )
            self._append_event(
                event_type=EventType.TASK_FINISHED,
                status=status,
                message=result.message or f"task finished: {task.name}",
                plan_id=plan_id,
                task=task,
                attempt=(result.retry_count + 1)
                if task.task_type == "function"
                else None,
                status_before=ResultStatus.RUNNING.value,
                status_after=normalized,
                payload={
                    "code": result.code,
                    "duration_ms": result.duration_ms,
                    "summary": result.details.get("summary")
                    if isinstance(result.details, dict)
                    else None,
                    "residual_risk": residual_risk,
                },
            )
            self._write_snapshot(
                plan_id, root_result=result if task.task_type == "fixture" else None
            )

    def on_execution_finished(
        self,
        root_result: ExecutionResult,
        *,
        plan: ExecutionPlan,
        context: ExecutionContext,
    ) -> list[str]:
        """Handle execution finished event, generating reports and snapshots.

        Args:
            root_result: Root execution result.
            plan: Execution plan.
            context: Execution context.

        Returns:
            List of generated artifact URIs.
        """
        with self._lock:
            snapshot = self._write_snapshot(
                plan.plan_id,
                root_result=root_result,
                runtime_state=context.runtime_state,
            )
            events = self.event_store.read(self.request_id)
            artifacts = self.report_generator.generate(
                root_result=root_result,
                snapshot=snapshot,
                resolved_config=self.resolved_config,
                events=events,
            )
            root_result.artifacts.extend(artifacts)
            self._append_event(
                event_type=EventType.REPORT_GENERATED,
                status=EventStatus.SUCCESS,
                message="report generated",
                plan_id=plan.plan_id,
                task=root_result_to_task(root_result),
                status_before=normalize_status(root_result.status),
                status_after=normalize_status(root_result.status),
                payload={"artifacts": [artifact.to_dict() for artifact in artifacts]},
            )
            self._write_snapshot(
                plan.plan_id,
                root_result=root_result,
                runtime_state=context.runtime_state,
            )
            return [artifact.uri for artifact in artifacts]

    def _write_snapshot(
        self,
        plan_id: str,
        *,
        root_result: ExecutionResult | None = None,
        runtime_state: dict[str, Any] | None = None,
    ) -> ResultSnapshot:
        """Write a result snapshot.

        Args:
            plan_id: Execution plan ID.
            root_result: Root execution result.
            runtime_state: Runtime state.

        Returns:
            Written result snapshot.
        """
        counters = self._build_counters()
        fixture_summary = self._build_fixture_summary(root_result)
        case_summaries = self._build_case_summaries(root_result)
        snapshot = ResultSnapshot(
            request_id=self.request_id,
            plan_id=plan_id,
            updated_at=datetime.now(UTC),
            current_status=fixture_summary.get(
                "status", self._infer_current_status(counters)
            ),
            fixture=fixture_summary,
            cases=case_summaries,
            counters=counters,
            status_summary=dict(counters),
            runtime_state=self._sanitize_runtime_state(runtime_state or {}),
            results=[root_result]
            if root_result is not None
            else list(self.task_results.values()),
        )
        self.result_store.write_snapshot(snapshot)
        self.latest_snapshot = snapshot
        return snapshot

    def _build_counters(self) -> dict[str, int]:
        """Build task status counters.

        Returns:
            Dictionary containing task counts by status.
        """
        counters: dict[str, int] = {}
        for status in self.task_states.values():
            counters[status] = counters.get(status, 0) + 1
        return counters

    def _build_fixture_summary(
        self, root_result: ExecutionResult | None
    ) -> dict[str, Any]:
        """Build fixture summary.

        Args:
            root_result: Root execution result.

        Returns:
            Fixture summary dictionary.
        """
        if root_result is None:
            return {}
        return {
            "task_id": root_result.task_id,
            "name": root_result.name,
            "status": normalize_status(root_result.status),
            "message": root_result.message,
        }

    def _build_case_summaries(
        self, root_result: ExecutionResult | None
    ) -> list[dict[str, Any]]:
        """Build case summaries.

        Args:
            root_result: Root execution result.

        Returns:
            List of case summary dictionaries.
        """
        case_summaries: list[dict[str, Any]] = []
        if root_result is None:
            for task in self.plan_tasks.values():
                if task.task_type != "case":
                    continue
                case_result = self.task_results.get(task.task_id)
                if case_result is not None:
                    case_summaries.append(
                        self._build_case_summary_from_result(case_result)
                    )
                    continue

                child_statuses = self._collect_child_statuses(task.task_id)
                inferred_status = self._infer_task_status(task.task_id, child_statuses)
                case_summaries.append(
                    self._build_case_summary_from_task(
                        task, inferred_status, child_statuses
                    )
                )
            return case_summaries
        for child in root_result.children:
            if child.task_type != "case":
                continue
            case_summaries.append(self._build_case_summary_from_result(child))
        return case_summaries

    def _build_case_summary_from_result(
        self, case_result: ExecutionResult
    ) -> dict[str, Any]:
        """Build case summary from execution result.

        Args:
            case_result: Case execution result.

        Returns:
            Case summary dictionary.
        """
        return {
            "task_id": case_result.task_id,
            "name": case_result.name,
            "status": normalize_status(case_result.status),
            "message": case_result.message,
            "summary": summarize_children(case_result.children),
            "started_at": case_result.started_at,
            "duration_ms": case_result.duration_ms,
        }

    def _build_case_summary_from_task(
        self,
        task: ExecutionTask,
        inferred_status: str,
        child_statuses: list[str],
    ) -> dict[str, Any]:
        """Build case summary from task.

        Args:
            task: Execution task.
            inferred_status: Inferred status.
            child_statuses: List of child task statuses.

        Returns:
            Case summary dictionary.
        """
        started_at = self.task_started_at.get(task.task_id)
        duration_ms = None
        if started_at is not None and inferred_status == ResultStatus.RUNNING.value:
            duration_ms = int(
                (datetime.now(UTC) - started_at).total_seconds() * 1000
            )
        return {
            "task_id": task.task_id,
            "name": task.name,
            "status": inferred_status,
            "message": self._infer_case_message(
                task.name, inferred_status, child_statuses
            ),
            "summary": self._summarize_statuses(child_statuses),
            "started_at": started_at,
            "duration_ms": duration_ms,
        }

    def _collect_child_statuses(self, parent_task_id: str) -> list[str]:
        """Collect child task statuses.

        Args:
            parent_task_id: Parent task ID.

        Returns:
            List of child task statuses.
        """
        child_statuses: list[str] = []
        for task in self.plan_tasks.values():
            if task.parent_task_id != parent_task_id:
                continue
            result = self.task_results.get(task.task_id)
            if result is not None:
                child_statuses.append(normalize_status(result.status))
                continue
            state = self.task_states.get(task.task_id)
            if state is not None:
                child_statuses.append(state)
        return child_statuses

    def _infer_task_status(self, task_id: str, child_statuses: list[str]) -> str:
        """Infer task status from child statuses.

        Args:
            task_id: Task ID.
            child_statuses: List of child task statuses.

        Returns:
            Inferred task status.
        """
        direct_state = self.task_states.get(task_id)
        if direct_state is not None:
            if direct_state == "retrying":
                return ResultStatus.RUNNING.value
            if direct_state != "pending":
                return direct_state

        if any(
            status in {ResultStatus.RUNNING.value, "retrying"}
            for status in child_statuses
        ):
            return ResultStatus.RUNNING.value
        for terminal in ("failed", "timeout", "aborted"):
            if terminal in child_statuses:
                return terminal
        if child_statuses and all(status == "passed" for status in child_statuses):
            return "passed"
        if child_statuses and all(status == "skipped" for status in child_statuses):
            return "skipped"
        return "pending"

    def _summarize_statuses(self, statuses: list[str]) -> dict[str, int]:
        """Summarize status list.

        Args:
            statuses: List of statuses.

        Returns:
            Status count dictionary.
        """
        summary: dict[str, int] = {}
        for status in statuses:
            normalized = ResultStatus.RUNNING.value if status == "retrying" else status
            summary[normalized] = summary.get(normalized, 0) + 1
        return summary

    def _infer_case_message(
        self, case_name: str, status: str, child_statuses: list[str]
    ) -> str:
        """Infer case message.

        Args:
            case_name: Case name.
            status: Status.
            child_statuses: List of child task statuses.

        Returns:
            Case status message.
        """
        if child_statuses:
            summary = self._summarize_statuses(child_statuses)
            ordered = ", ".join(
                f"{key}={value}" for key, value in sorted(summary.items())
            )
            if status == ResultStatus.RUNNING.value:
                return f"case running: {ordered}"
            if status == "pending":
                return f"case pending: {case_name}"
            return f"case in progress: {ordered}"
        if status == ResultStatus.RUNNING.value:
            return f"case running: {case_name}"
        if status == "pending":
            return f"case pending: {case_name}"
        return f"case status: {status}"

    def _infer_current_status(self, counters: dict[str, int]) -> str:
        """Infer current overall status.

        Args:
            counters: Status counters.

        Returns:
            Current status string.
        """
        if counters.get(ResultStatus.RUNNING.value) or counters.get("retrying"):
            return ResultStatus.RUNNING.value
        for terminal in ("failed", "timeout", "aborted"):
            if counters.get(terminal):
                return terminal
        if counters.get("passed"):
            return "passed"
        if counters.get("skipped"):
            return "skipped"
        return "pending"

    def _sanitize_runtime_state(self, runtime_state: dict[str, Any]) -> dict[str, Any]:
        """Sanitize runtime state.

        Args:
            runtime_state: Raw runtime state.

        Returns:
            Sanitized runtime state dictionary.
        """
        sanitized: dict[str, Any] = {}
        for key, value in runtime_state.items():
            if key == "observability":
                continue
            sanitized[key] = value
        return sanitized

    def _append_event(
        self,
        *,
        event_type: EventType,
        status: EventStatus,
        message: str,
        plan_id: str,
        task: ExecutionTask | None = None,
        attempt: int | None = None,
        status_before: str | None = None,
        status_after: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Append an event to the event store.

        Args:
            event_type: Event type.
            status: Event status.
            message: Event message.
            plan_id: Execution plan ID.
            task: Associated task.
            attempt: Attempt number.
            status_before: Status before event.
            status_after: Status after event.
            payload: Additional event data.
        """
        event = ExecutionEvent(
            event_id=str(uuid.uuid4()),
            request_id=self.request_id,
            plan_id=plan_id,
            event_type=event_type,
            timestamp=datetime.now(UTC),
            status=status,
            task_id=task.task_id if task else None,
            task_type=task.task_type if task else None,
            task_name=task.name if task else None,
            parent_task_id=task.parent_task_id if task else None,
            attempt=attempt,
            status_before=status_before,
            status_after=status_after,
            message=message,
            payload=dict(payload or {}),
        )
        self.event_store.append(event, source="scheduler")
        self.logger.info("%s %s %s", event.event_type, event.task_id or "-", message)


def root_result_to_task(result: ExecutionResult) -> ExecutionTask:
    """Convert an execution result to a task object.

    Args:
        result: Execution result object.

    Returns:
        Corresponding task object.
    """
    return ExecutionTask(
        task_id=result.task_id,
        task_type=result.task_type,
        name=result.name,
        execution_mode="sequential",
        payload={},
    )
