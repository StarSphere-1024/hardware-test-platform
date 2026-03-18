"""Sequential scheduler for fixture, case and function task graphs."""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import UTC, datetime
from typing import Any

from framework.domain.execution import ExecutionContext, ExecutionPlan, ExecutionTask
from framework.domain.results import ExecutionResult, ResultStatus

from .errors import TaskExecutionError, UnsupportedExecutionModeError
from .function_executor import FunctionExecutor
from .policies import (
    aggregate_status,
    normalize_status,
    should_retry,
    summarize_children,
)
from .resource_locks import ResourceLockManager

DEFAULT_RESOURCE_QUARANTINE_SECONDS = 5.0


class Scheduler:
    def __init__(self, function_executor: FunctionExecutor) -> None:
        self.function_executor = function_executor
        self._resource_lock_managers: dict[int, ResourceLockManager] = {}
        self._runtime_state_lock = threading.Lock()

    def run(self, plan: ExecutionPlan, context: ExecutionContext) -> ExecutionResult:
        if plan.root_task.execution_mode not in {"sequential", "parallel"}:
            raise UnsupportedExecutionModeError(
                f"unsupported root execution mode: {plan.root_task.execution_mode}"
            )

        observer = self._observer_from_context(context)
        logger = self._logger_from_context(context)

        logger.debug(
            "Scheduler.run: starting execution for plan %s with mode %s",
            plan.plan_id,
            plan.root_task.execution_mode,
        )

        children_by_parent: dict[str, list[ExecutionTask]] = defaultdict(list)
        for task in plan.tasks:
            if task.parent_task_id is not None:
                children_by_parent[task.parent_task_id].append(task)
        for child_tasks in children_by_parent.values():
            child_tasks.sort(key=lambda item: item.task_id)

        context.runtime_state.setdefault("completed_tasks", [])
        context.runtime_state.setdefault("attempts", {})

        if observer is not None:
            observer.on_plan_created(plan)

        root_result = self._execute_task(
            plan.root_task, children_by_parent, context, plan.plan_id
        )
        if observer is not None:
            observer.on_execution_finished(root_result, plan=plan, context=context)

        logger.debug(
            "Scheduler.run: completed execution for plan %s with status %s",
            plan.plan_id,
            root_result.status,
        )
        return root_result

    def _execute_task(
        self,
        task: ExecutionTask,
        children_by_parent: dict[str, list[ExecutionTask]],
        context: ExecutionContext,
        plan_id: str,
    ) -> ExecutionResult:
        logger = self._logger_from_context(context)

        if task.task_type == "function":
            logger.debug(
                "Scheduler._execute_task: executing function task %s (%s)",
                task.task_id,
                task.name,
            )
            return self._execute_function_task(task, context, plan_id)

        if task.execution_mode not in {"sequential", "parallel"}:
            raise UnsupportedExecutionModeError(

                    f"unsupported task execution mode: {task.task_id} "
                    f"-> {task.execution_mode}"

            )

        observer = self._observer_from_context(context)
        if observer is not None:
            observer.on_task_started(task, plan_id=plan_id)

        logger.debug(
            "Scheduler._execute_task: starting container task %s (%s) with %d children",
            task.task_id,
            task.name,
            len(children_by_parent.get(task.task_id, [])),
        )

        started_at = datetime.now(UTC)
        started_perf = time.perf_counter()

        if task.task_type == "case":
            precheck_result = self._run_case_precheck(task, context)
            if precheck_result is not None:
                logger.debug(
                    "Scheduler._execute_task: case %s failed precheck", task.task_id
                )
                if observer is not None:
                    observer.on_task_finished(task, precheck_result, plan_id=plan_id)
                return precheck_result

        child_tasks = children_by_parent.get(task.task_id, [])
        if task.execution_mode == "parallel":
            child_results = self._execute_children_parallel(
                task, child_tasks, children_by_parent, context, plan_id
            )
        else:
            child_results = self._execute_children_sequential(
                task, child_tasks, children_by_parent, context, plan_id
            )

        finished_at = datetime.now(UTC)
        status = aggregate_status(child_results)
        summary = summarize_children(child_results)
        message = self._build_container_message(task.task_type, summary)
        result = ExecutionResult(
            task_id=task.task_id,
            task_type=task.task_type,
            name=task.name,
            status=status,
            message=message,
            details={"summary": summary},
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=int((time.perf_counter() - started_perf) * 1000),
            children=child_results,
        )
        self._mark_task_completed(context, task.task_id)
        if observer is not None:
            observer.on_task_finished(task, result, plan_id=plan_id)
        return result

    def _execute_function_task(
        self, task: ExecutionTask, context: ExecutionContext, plan_id: str
    ) -> ExecutionResult:
        logger = self._logger_from_context(context)
        retry_policy = task.retry_policy
        max_retries = retry_policy.max_retries if retry_policy else 0
        retry_interval = retry_policy.interval_seconds if retry_policy else 0
        observer = self._observer_from_context(context)
        resource_lock_manager = self._resource_lock_manager(context)
        resources = self._resolve_task_resources(task)

        logger.debug(
            "Scheduler._execute_function_task: "
            "task %s (%s) with max_retries=%d, resources=%s",
            task.task_id,
            task.name,
            max_retries,
            resources,
        )

        last_result: ExecutionResult | None = None
        for attempt in range(max_retries + 1):
            self._set_attempt(context, task.task_id, attempt)
            if observer is not None:
                observer.on_task_started(
                    task,
                    plan_id=plan_id,
                    attempt=attempt + 1,
                    status_before="retrying" if attempt > 0 else "pending",
                )
            lock_info: dict[str, object] = {"resources": list(resources), "wait_ms": 0}
            release_info: dict[str, object] | None = None
            result: ExecutionResult | None = None
            if resources:
                logger.debug(
                    "Scheduler._execute_function_task: "
                    "attempting resource lock acquisition for "
                    "task %s, attempt %d",
                    task.task_id,
                    attempt + 1,
                )
                lock_info = resource_lock_manager.acquire(
                    resources,
                    owner_task_id=task.task_id,
                    owner_attempt=attempt + 1,
                    timeout_seconds=task.timeout,
                )
                if not lock_info.get("acquired"):
                    logger.debug(
                        "Scheduler._execute_function_task: "
                        "resource lock acquisition failed for task %s: %s",
                        task.task_id,
                        lock_info.get("reason"),
                    )
                    result = self._build_resource_lock_failure(task, lock_info)
                    result.retry_count = attempt
                    last_result = result
                    self._attach_lock_details(result, lock_info, release_info=None)
                    if not should_retry(result.status, attempt, max_retries):
                        self._mark_task_completed(context, task.task_id)
                        if observer is not None:
                            observer.on_task_finished(task, result, plan_id=plan_id)
                        return result
                    if observer is not None:
                        observer.on_task_retried(
                            task,
                            plan_id=plan_id,
                            current_attempt=attempt + 1,
                            next_attempt=attempt + 2,
                            retry_interval_seconds=retry_interval,
                            last_result=result,
                        )
                    if retry_interval > 0:
                        time.sleep(retry_interval)
                    continue

            try:
                logger.debug(
                    "Scheduler._execute_function_task: "
                    "executing function %s (attempt %d)",
                    task.task_id,
                    attempt + 1,
                )
                result = self.function_executor.execute(task, context)
            finally:
                if resources and lock_info.get("acquired"):
                    release_status = (
                        normalize_status(result.status)
                        if result is not None
                        else ResultStatus.FAILED.value
                    )
                    quarantine_seconds = (
                        self._resource_quarantine_seconds(task, context)
                        if release_status == ResultStatus.TIMEOUT.value
                        else 0
                    )
                    logger.debug(
                        "Scheduler._execute_function_task: "
                        "releasing resources for task %s, "
                        "quarantine=%ds, reason=%s",
                        task.task_id,
                        quarantine_seconds,
                        release_status,
                    )
                    release_info = resource_lock_manager.release(
                        resources,
                        owner_task_id=task.task_id,
                        release_reason=release_status,
                        quarantine_seconds=quarantine_seconds,
                    )

            if result is None:
                raise TaskExecutionError(
                    f"function task did not produce a result: {task.task_id}"
                )
            result.retry_count = attempt
            last_result = result
            self._attach_lock_details(result, lock_info, release_info)
            if not should_retry(result.status, attempt, max_retries):
                logger.debug(
                    "Scheduler._execute_function_task: "
                    "task %s completed with status %s",
                    task.task_id,
                    result.status,
                )
                self._mark_task_completed(context, task.task_id)
                if observer is not None:
                    observer.on_task_finished(task, result, plan_id=plan_id)
                return result
            logger.debug(
                "Scheduler._execute_function_task: "
                "task %s will be retried (attempt %d of %d)",
                task.task_id,
                attempt + 1,
                max_retries + 1,
            )
            if observer is not None:
                observer.on_task_retried(
                    task,
                    plan_id=plan_id,
                    current_attempt=attempt + 1,
                    next_attempt=attempt + 2,
                    retry_interval_seconds=retry_interval,
                    last_result=result,
                )
            if retry_interval > 0:
                time.sleep(retry_interval)

        if last_result is None:
            raise TaskExecutionError(
                f"function task did not produce a result: {task.task_id}"
            )
        self._mark_task_completed(context, task.task_id)
        if observer is not None:
            observer.on_task_finished(task, last_result, plan_id=plan_id)
        return last_result

    def _execute_children_sequential(
        self,
        task: ExecutionTask,
        child_tasks: list[ExecutionTask],
        children_by_parent: dict[str, list[ExecutionTask]],
        context: ExecutionContext,
        plan_id: str,
    ) -> list[ExecutionResult]:
        child_results: list[ExecutionResult] = []
        for child_task in child_tasks:
            child_result = self._execute_task(
                child_task, children_by_parent, context, plan_id
            )
            child_results.append(child_result)
            if (
                task.stop_on_failure
                and normalize_status(child_result.status) != ResultStatus.PASSED.value
            ):
                for remaining_task in child_tasks[len(child_results) :]:
                    child_results.append(
                        self._build_aborted_result(
                            remaining_task, "aborted by stop_on_failure"
                        )
                    )
                break
        return child_results

    def _execute_children_parallel(
        self,
        task: ExecutionTask,
        child_tasks: list[ExecutionTask],
        children_by_parent: dict[str, list[ExecutionTask]],
        context: ExecutionContext,
        plan_id: str,
    ) -> list[ExecutionResult]:
        if not child_tasks:
            return []

        ordered_ids = [child.task_id for child in child_tasks]
        pending = {child.task_id: child for child in child_tasks}
        results_by_task_id: dict[str, ExecutionResult] = {}
        in_flight: dict[Future[ExecutionResult], ExecutionTask] = {}
        scheduler_completed: set[str] = set(self._completed_tasks(context))
        stop_submitting = False

        with ThreadPoolExecutor(
            max_workers=len(child_tasks), thread_name_prefix="fixture-scheduler"
        ) as executor:
            while pending or in_flight:
                if not stop_submitting:
                    ready_tasks = [
                        child
                        for child in child_tasks
                        if child.task_id in pending
                        and self._dependencies_satisfied(child, scheduler_completed)
                    ]
                    for ready_task in ready_tasks:
                        in_flight[
                            executor.submit(
                                self._execute_task,
                                ready_task,
                                children_by_parent,
                                context,
                                plan_id,
                            )
                        ] = ready_task
                        pending.pop(ready_task.task_id, None)

                if not in_flight:
                    if pending:
                        if stop_submitting:
                            break
                        unresolved = ", ".join(sorted(pending))
                        raise TaskExecutionError(
                            "parallel scheduling stalled, "
                            f"unresolved dependencies: {unresolved}"
                        )
                    break

                done, _ = wait(in_flight.keys(), return_when=FIRST_COMPLETED)
                for future in done:
                    child_task = in_flight.pop(future)
                    child_result = future.result()
                    results_by_task_id[child_task.task_id] = child_result
                    scheduler_completed.add(child_task.task_id)
                    if (
                        task.stop_on_failure
                        and normalize_status(child_result.status)
                        != ResultStatus.PASSED.value
                    ):
                        stop_submitting = True

            if stop_submitting and pending:
                for task_id, pending_task in pending.items():
                    results_by_task_id[task_id] = self._build_aborted_result(
                        pending_task, "aborted by stop_on_failure"
                    )

        return [
            results_by_task_id[task_id]
            for task_id in ordered_ids
            if task_id in results_by_task_id
        ]

    def _run_case_precheck(
        self, task: ExecutionTask, context: ExecutionContext
    ) -> ExecutionResult | None:
        payload = task.payload
        if not payload.get("precheck", True):
            return None
        required_interfaces = payload.get("required_interfaces", {})
        missing = [
            name
            for name, request in required_interfaces.items()
            if request.get("required", False)
            and name not in context.resolved_config.resolved_interfaces
        ]
        if not missing:
            return None

        started_at = datetime.now(UTC)
        finished_at = datetime.now(UTC)
        return ExecutionResult(
            task_id=task.task_id,
            task_type=task.task_type,
            name=task.name,
            status=ResultStatus.FAILED,
            code=-1,
            message=f"missing required interfaces: {', '.join(sorted(missing))}",
            details={"missing_interfaces": sorted(missing)},
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=0,
            children=[],
        )

    def _build_aborted_result(
        self, task: ExecutionTask, message: str
    ) -> ExecutionResult:
        timestamp = datetime.now(UTC)
        return ExecutionResult(
            task_id=task.task_id,
            task_type=task.task_type,
            name=task.name,
            status=ResultStatus.ABORTED,
            message=message,
            started_at=timestamp,
            finished_at=timestamp,
            duration_ms=0,
        )

    def _build_container_message(self, task_type: str, summary: dict[str, int]) -> str:
        if not summary:
            return f"{task_type} completed with no child tasks"
        ordered = ", ".join(f"{key}={value}" for key, value in sorted(summary.items()))
        return f"{task_type} completed: {ordered}"

    def _observer_from_context(self, context: ExecutionContext) -> Any:
        return context.runtime_state.get("observability")

    def _logger_from_context(self, context: ExecutionContext) -> Any:
        observer = context.runtime_state.get("observability")
        if observer is not None and hasattr(observer, "logger"):
            return observer.logger
        import logging

        return logging.getLogger("hardware_test_platform.scheduler")

    def _completed_tasks(self, context: ExecutionContext) -> list[str]:
        with self._runtime_state_lock:
            return list(context.runtime_state.get("completed_tasks", []))

    def _mark_task_completed(self, context: ExecutionContext, task_id: str) -> None:
        with self._runtime_state_lock:
            context.runtime_state.setdefault("completed_tasks", []).append(task_id)

    def _set_attempt(
        self, context: ExecutionContext, task_id: str, attempt: int
    ) -> None:
        with self._runtime_state_lock:
            context.runtime_state.setdefault("attempts", {})[task_id] = attempt

    def _dependencies_satisfied(
        self, task: ExecutionTask, completed_task_ids: set[str]
    ) -> bool:
        return all(dependency in completed_task_ids for dependency in task.dependencies)

    def _resource_lock_manager(self, context: ExecutionContext) -> ResourceLockManager:
        context_key = id(context)
        manager = self._resource_lock_managers.get(context_key)
        if manager is None:
            manager = ResourceLockManager(context.resource_locks)
            self._resource_lock_managers[context_key] = manager
        return manager

    def _resource_quarantine_seconds(
        self, task: ExecutionTask, context: ExecutionContext
    ) -> float:
        value = task.payload.get("resource_lock_quarantine_seconds")
        if value is None:
            value = context.resolved_config.resolved_runtime.get(
                "resource_lock_quarantine_seconds"
            )
        if value is None:
            value = context.runtime_state.get("resource_lock_quarantine_seconds")
        if isinstance(value, (int, float)):
            return max(float(value), 0.0)
        return DEFAULT_RESOURCE_QUARANTINE_SECONDS

    def _resolve_task_resources(self, task: ExecutionTask) -> list[str]:
        raw_resources = task.payload.get("resources")
        if isinstance(raw_resources, list):
            return sorted(
                {
                    resource.strip()
                    for resource in raw_resources
                    if isinstance(resource, str) and resource.strip()
                }
            )
        raw_capabilities = task.payload.get("required_capabilities", [])
        if not isinstance(raw_capabilities, list):
            return []
        return sorted(
            {
                f"capability:{name.strip()}"
                for name in raw_capabilities
                if isinstance(name, str) and name.strip()
            }
        )

    def _build_resource_lock_failure(
        self, task: ExecutionTask, lock_info: dict[str, Any]
    ) -> ExecutionResult:
        timestamp = datetime.now(UTC)
        reason = str(lock_info.get("reason") or "timeout")
        blocked_resource = lock_info.get("blocked_resource")
        if reason == "quarantine":
            message = f"resource '{blocked_resource}' is quarantined"
        elif reason == "locked":
            message = f"resource '{blocked_resource}' is already locked"
        else:
            message = "resource lock acquisition timed out"
        return ExecutionResult(
            task_id=task.task_id,
            task_type=task.task_type,
            name=task.name,
            status=ResultStatus.TIMEOUT,
            code=1,
            message=message,
            started_at=timestamp,
            finished_at=timestamp,
            duration_ms=0,
            details={"resources": list(lock_info.get("resources", []))},
        )

    def _attach_lock_details(
        self,
        result: ExecutionResult,
        lock_info: dict[str, Any],
        release_info: dict[str, Any] | None,
    ) -> None:
        result.details = dict(result.details)
        result.details["resource_lock"] = {
            "resources": list(lock_info.get("resources", [])),
            "wait_ms": int(lock_info.get("wait_ms", 0) or 0),
            "acquired": bool(lock_info.get("acquired", False)),
            "blocked_resource": lock_info.get("blocked_resource"),
            "blocked_reason": lock_info.get("reason"),
            "release_reason": release_info.get("release_reason")
            if release_info
            else None,
            "quarantine_until": release_info.get("quarantine_until")
            if release_info
            else None,
        }
