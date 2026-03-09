from __future__ import annotations

import time
from pathlib import Path

from framework.config.resolver import ConfigResolver
from framework.domain.execution import ArtifactDirectories, ExecutionContext, ExecutionTask
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


def test_function_executor_returns_timeout_without_waiting_for_worker_completion() -> None:
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