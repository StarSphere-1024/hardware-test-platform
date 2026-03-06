"""Sequential scheduler for fixture, case and function task graphs."""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime, timezone

from framework.domain.execution import ExecutionContext, ExecutionPlan, ExecutionTask
from framework.domain.results import ExecutionResult, ResultStatus

from .errors import TaskExecutionError, UnsupportedExecutionModeError
from .function_executor import FunctionExecutor
from .policies import aggregate_status, normalize_status, should_retry, summarize_children


class Scheduler:
    def __init__(self, function_executor: FunctionExecutor) -> None:
        self.function_executor = function_executor

    def run(self, plan: ExecutionPlan, context: ExecutionContext) -> ExecutionResult:
        if plan.root_task.execution_mode != "sequential":
            raise UnsupportedExecutionModeError("only sequential fixture execution is implemented in phase C")

        task_index = {task.task_id: task for task in plan.tasks}
        children_by_parent: dict[str, list[ExecutionTask]] = defaultdict(list)
        for task in plan.tasks:
            if task.parent_task_id is not None:
                children_by_parent[task.parent_task_id].append(task)
        for child_tasks in children_by_parent.values():
            child_tasks.sort(key=lambda item: item.task_id)

        context.runtime_state.setdefault("completed_tasks", [])
        context.runtime_state.setdefault("attempts", {})

        observer = self._observer_from_context(context)
        if observer is not None:
            observer.on_plan_created(plan)

        root_result = self._execute_task(plan.root_task, children_by_parent, context, plan.plan_id)
        if observer is not None:
            observer.on_execution_finished(root_result, plan=plan, context=context)
        return root_result

    def _execute_task(
        self,
        task: ExecutionTask,
        children_by_parent: dict[str, list[ExecutionTask]],
        context: ExecutionContext,
        plan_id: str,
    ) -> ExecutionResult:
        if task.task_type == "function":
            return self._execute_function_task(task, context, plan_id)

        if task.execution_mode != "sequential":
            raise UnsupportedExecutionModeError(f"only sequential task execution is implemented: {task.task_id}")

        observer = self._observer_from_context(context)
        if observer is not None:
            observer.on_task_started(task, plan_id=plan_id)

        started_at = datetime.now(timezone.utc)
        started_perf = time.perf_counter()

        if task.task_type == "case":
            precheck_result = self._run_case_precheck(task, context)
            if precheck_result is not None:
                if observer is not None:
                    observer.on_task_finished(task, precheck_result, plan_id=plan_id)
                return precheck_result

        child_results: list[ExecutionResult] = []
        for child_task in children_by_parent.get(task.task_id, []):
            child_result = self._execute_task(child_task, children_by_parent, context, plan_id)
            child_results.append(child_result)
            if task.stop_on_failure and normalize_status(child_result.status) != ResultStatus.PASSED.value:
                for remaining_task in children_by_parent.get(task.task_id, [])[len(child_results):]:
                    child_results.append(self._build_aborted_result(remaining_task, "aborted by stop_on_failure"))
                break

        finished_at = datetime.now(timezone.utc)
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
        context.runtime_state["completed_tasks"].append(task.task_id)
        if observer is not None:
            observer.on_task_finished(task, result, plan_id=plan_id)
        return result

    def _execute_function_task(self, task: ExecutionTask, context: ExecutionContext, plan_id: str) -> ExecutionResult:
        retry_policy = task.retry_policy
        max_retries = retry_policy.max_retries if retry_policy else 0
        retry_interval = retry_policy.interval_seconds if retry_policy else 0
        observer = self._observer_from_context(context)

        last_result: ExecutionResult | None = None
        for attempt in range(max_retries + 1):
            context.runtime_state["attempts"][task.task_id] = attempt
            if observer is not None:
                observer.on_task_started(
                    task,
                    plan_id=plan_id,
                    attempt=attempt + 1,
                    status_before="retrying" if attempt > 0 else "pending",
                )
            result = self.function_executor.execute(task, context)
            result.retry_count = attempt
            last_result = result
            if not should_retry(result.status, attempt, max_retries):
                context.runtime_state["completed_tasks"].append(task.task_id)
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

        if last_result is None:
            raise TaskExecutionError(f"function task did not produce a result: {task.task_id}")
        context.runtime_state["completed_tasks"].append(task.task_id)
        if observer is not None:
            observer.on_task_finished(task, last_result, plan_id=plan_id)
        return last_result

    def _run_case_precheck(self, task: ExecutionTask, context: ExecutionContext) -> ExecutionResult | None:
        payload = task.payload
        if not payload.get("precheck", True):
            return None
        required_interfaces = payload.get("required_interfaces", {})
        missing = [name for name, request in required_interfaces.items() if request.get("required", False) and name not in context.resolved_config.resolved_interfaces]
        if not missing:
            return None

        started_at = datetime.now(timezone.utc)
        finished_at = datetime.now(timezone.utc)
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

    def _build_aborted_result(self, task: ExecutionTask, message: str) -> ExecutionResult:
        timestamp = datetime.now(timezone.utc)
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

    def _observer_from_context(self, context: ExecutionContext):
        return context.runtime_state.get("observability")
