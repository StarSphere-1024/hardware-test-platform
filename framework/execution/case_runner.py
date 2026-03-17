"""Build case-level execution tasks from resolved configuration."""

from __future__ import annotations

from framework.config.models import CaseSpec, FunctionInvocationSpec
from framework.domain.execution import ExecutionTask, RetryPolicy


class CaseRunner:
    def build_case_task(
        self, case_spec: CaseSpec, *, parent_task_id: str | None = None, index: int = 0
    ) -> tuple[ExecutionTask, list[ExecutionTask]]:
        case_task_id = f"case.{index}.{case_spec.case_name}"
        case_task = ExecutionTask(
            task_id=case_task_id,
            task_type="case",
            parent_task_id=parent_task_id,
            name=case_spec.case_name,
            execution_mode=case_spec.execution,
            timeout=case_spec.timeout,
            retry_policy=RetryPolicy(
                max_retries=case_spec.retry or 0,
                interval_seconds=case_spec.retry_interval or 0,
            ),
            stop_on_failure=bool(case_spec.stop_on_failure),
            payload={
                "case": case_spec.to_dict(),
                "required_interfaces": dict(case_spec.required_interfaces),
                "resources": list(case_spec.resources),
                "resource_lock_quarantine_seconds": case_spec.resource_lock_quarantine_seconds,
                "precheck": case_spec.precheck,
            },
        )

        function_tasks: list[ExecutionTask] = []
        previous_task_id: str | None = None
        for function_index, function_spec in enumerate(case_spec.functions):
            if not function_spec.enabled:
                continue
            dependency_task_id = (
                previous_task_id if case_spec.execution == "sequential" else None
            )
            function_tasks.append(
                self._build_function_task(
                    function_spec,
                    case_name=case_spec.case_name,
                    parent_task_id=case_task_id,
                    task_index=function_index,
                    previous_task_id=dependency_task_id,
                )
            )
            previous_task_id = function_tasks[-1].task_id

        return case_task, function_tasks

    def _build_function_task(
        self,
        function_spec: FunctionInvocationSpec,
        *,
        case_name: str,
        parent_task_id: str,
        task_index: int,
        previous_task_id: str | None,
    ) -> ExecutionTask:
        return ExecutionTask(
            task_id=f"function.{case_name}.{task_index}.{function_spec.name}",
            task_type="function",
            parent_task_id=parent_task_id,
            name=function_spec.name,
            execution_mode="sequential",
            timeout=function_spec.timeout,
            retry_policy=RetryPolicy(
                max_retries=function_spec.retry or 0,
                interval_seconds=function_spec.retry_interval or 0,
            ),
            stop_on_failure=False,
            dependencies=[previous_task_id] if previous_task_id else [],
            payload={
                "function_name": function_spec.name,
                "params": dict(function_spec.params),
                "expect": dict(function_spec.expect or {}),
                "required_capabilities": list(function_spec.required_capabilities),
                "resources": list(function_spec.resources),
                "resource_lock_quarantine_seconds": function_spec.resource_lock_quarantine_seconds,
                "tags": list(function_spec.tags),
            },
        )
