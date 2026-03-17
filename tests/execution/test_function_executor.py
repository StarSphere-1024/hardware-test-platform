from __future__ import annotations

import time
from pathlib import Path

from framework.config.resolver import ConfigResolver
from framework.domain.execution import (
    ArtifactDirectories,
    ExecutionContext,
    ExecutionTask,
)
from framework.domain.results import ResultStatus
from framework.execution.function_executor import FunctionExecutor


REPO_ROOT = Path(__file__).resolve().parents[2]


def _build_context():
    resolver = ConfigResolver(REPO_ROOT)
    resolved_config = resolver.resolve_fixture("fixtures/linux_host_pc.json")
    return ExecutionContext(
        request_id="req-function-timeout",
        plan_id="plan.function-timeout",
        resolved_config=resolved_config,
        runtime_state={},
        artifacts_dir=ArtifactDirectories(
            logs_dir=REPO_ROOT / "logs",
            tmp_dir=REPO_ROOT / "tmp",
            reports_dir=REPO_ROOT / "reports",
        ),
    )


def test_function_executor_returns_timeout_without_waiting_for_worker_completion() -> (
    None
):
    def blocking_function(delay: float) -> dict[str, object]:
        time.sleep(delay)
        return {"code": 0, "message": "done"}

    executor = FunctionExecutor({"blocking_function": blocking_function})
    task = ExecutionTask(
        task_id="function.blocking_function",
        task_type="function",
        name="blocking_function",
        timeout=0,
        payload={"function_name": "blocking_function", "params": {"delay": 0.5}},
    )

    started = time.perf_counter()
    result = executor.execute(task, _build_context())
    elapsed = time.perf_counter() - started

    assert result.status == ResultStatus.TIMEOUT
    assert result.code == 1
    assert elapsed < 0.2
    assert (
        result.details["residual_risk"]["kind"]
        == "timeout_background_execution_unknown"
    )
    assert (
        "worker could be confirmed stopped"
        in result.details["residual_risk"]["message"]
    )


def test_function_executor_fails_when_expect_rules_are_not_met() -> None:
    executor = FunctionExecutor(
        {
            "loopback_function": lambda: {
                "code": 0,
                "status": "passed",
                "message": "loopback ok",
                "details": {"received": "wrong-payload"},
            }
        }
    )
    task = ExecutionTask(
        task_id="function.loopback_function",
        task_type="function",
        name="loopback_function",
        payload={
            "function_name": "loopback_function",
            "params": {},
            "expect": {
                "pass_policy": "all",
                "rules": [
                    {
                        "field": "received",
                        "operator": "eq",
                        "value": "phase-a",
                        "message": "uart must echo the configured payload",
                    }
                ],
            },
        },
    )

    result = executor.execute(task, _build_context())

    assert result.status == ResultStatus.FAILED
    assert result.code == -1
    assert result.message == "uart must echo the configured payload"
    assert result.details["expectation_results"][0]["passed"] is False


def test_function_executor_preserves_success_when_expect_rules_are_met() -> None:
    executor = FunctionExecutor(
        {
            "rtc_function": lambda: {
                "code": 0,
                "status": "passed",
                "message": "rtc read ok",
                "details": {"time": "2026-03-10T10:00:00+00:00"},
            }
        }
    )
    task = ExecutionTask(
        task_id="function.rtc_function",
        task_type="function",
        name="rtc_function",
        payload={
            "function_name": "rtc_function",
            "params": {},
            "expect": {
                "pass_policy": "all",
                "rules": [
                    {
                        "field": "time",
                        "operator": "non_empty",
                        "message": "rtc must return a timestamp",
                    }
                ],
            },
        },
    )

    result = executor.execute(task, _build_context())

    assert result.status == ResultStatus.PASSED
    assert result.code == 0
    assert result.details["expectation_results"][0]["passed"] is True
