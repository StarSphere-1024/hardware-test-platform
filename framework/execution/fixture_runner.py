"""Build fixture-level execution plans from resolved configuration."""

from __future__ import annotations

from framework.config.models import ResolvedExecutionConfig
from framework.domain.execution import ExecutionPlan, ExecutionTask, RetryPolicy

from .case_runner import CaseRunner


class FixtureRunner:
    def __init__(self) -> None:
        self.case_runner = CaseRunner()

    def build_plan(self, resolved_config: ResolvedExecutionConfig) -> ExecutionPlan:
        fixture_name = resolved_config.fixture.fixture_name if resolved_config.fixture else "adhoc_case"
        root_task = ExecutionTask(
            task_id=f"fixture.{fixture_name}",
            task_type="fixture",
            name=fixture_name,
            execution_mode=resolved_config.resolved_runtime.get("execution", "sequential"),
            timeout=resolved_config.resolved_runtime.get("timeout"),
            retry_policy=RetryPolicy(
                max_retries=resolved_config.resolved_runtime.get("retry", 0),
                interval_seconds=resolved_config.resolved_runtime.get("retry_interval", 0),
            ),
            stop_on_failure=bool(resolved_config.resolved_runtime.get("stop_on_failure", False)),
            payload={
                "fixture": resolved_config.fixture.to_dict() if resolved_config.fixture else None,
                "request": dict(resolved_config.request),
            },
        )

        tasks: list[ExecutionTask] = [root_task]
        previous_case_task_id: str | None = None
        for index, case_spec in enumerate(resolved_config.cases):
            case_task, function_tasks = self.case_runner.build_case_task(
                case_spec,
                parent_task_id=root_task.task_id,
                index=index,
            )
            if previous_case_task_id and root_task.execution_mode == "sequential":
                case_task.dependencies.append(previous_case_task_id)
            previous_case_task_id = case_task.task_id
            tasks.append(case_task)
            tasks.extend(function_tasks)

        plan_resources = sorted(
            {
                resource
                for task in tasks
                if task.task_type == "function"
                for resource in task.payload.get("resources", [])
                if isinstance(resource, str) and resource
            }
        )

        return ExecutionPlan(
            plan_id=f"plan.{fixture_name}",
            root_task=root_task,
            tasks=tasks,
            execution_policy={
                "mode": root_task.execution_mode,
                "stop_on_failure": root_task.stop_on_failure,
                "timeout": root_task.timeout,
            },
            resource_requirements={
                "capabilities": list(resolved_config.capability_requirements),
                "resources": plan_resources,
            },
        )
