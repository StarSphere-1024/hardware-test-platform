from __future__ import annotations

import copy
import time
from pathlib import Path

from framework.config.resolver import ConfigResolver
from framework.domain.execution import ArtifactDirectories, ExecutionContext
from framework.domain.results import ResultStatus
from framework.execution.fixture_runner import FixtureRunner
from framework.execution.function_executor import FunctionExecutor
from framework.execution.scheduler import Scheduler


REPO_ROOT = Path(__file__).resolve().parents[2]


def _build_context(resolved_config):
    return ExecutionContext(
        request_id="req-exec-001",
        plan_id="plan.quick_validation",
        resolved_config=resolved_config,
        runtime_state={},
        artifacts_dir=ArtifactDirectories(
            logs_dir=REPO_ROOT / "logs",
            tmp_dir=REPO_ROOT / "tmp",
            reports_dir=REPO_ROOT / "reports",
        ),
    )


def test_fixture_runner_builds_execution_plan_from_resolved_config() -> None:
    resolver = ConfigResolver(REPO_ROOT)
    resolved_config = resolver.resolve_fixture("fixtures/quick_validation.json")

    plan = FixtureRunner().build_plan(resolved_config)

    assert plan.root_task.task_type == "fixture"
    assert plan.root_task.name == "quick_validation"
    assert len(plan.tasks) == 11
    assert [task.task_type for task in plan.tasks] == [
        "fixture",
        "case",
        "function",
        "case",
        "function",
        "case",
        "function",
        "case",
        "function",
        "case",
        "function",
    ]
    assert plan.tasks[1].dependencies == []
    assert plan.tasks[3].dependencies == [plan.tasks[1].task_id]


def test_scheduler_runs_fixture_sequentially_and_aggregates_results() -> None:
    resolver = ConfigResolver(REPO_ROOT)
    resolved_config = resolver.resolve_fixture("fixtures/quick_validation.json")
    plan = FixtureRunner().build_plan(resolved_config)

    registry = {
        "test_eth_ping": lambda interface, target_ip: {
            "code": 0,
            "message": f"ping {target_ip} via {interface}",
            "details": {"interface": interface, "target_ip": target_ip},
            "metrics": {"avg_latency_ms": 1.5},
        },
        "test_uart_loopback": lambda port, baudrate, payload: {
            "code": 0,
            "message": f"loopback ok on {port}",
            "details": {"port": port, "baudrate": baudrate, "payload": payload},
        },
        "test_rtc_read": lambda rtc_device: {
            "code": 0,
            "message": f"rtc ok on {rtc_device}",
            "details": {"rtc_device": rtc_device},
        },
        "test_gpio_mapping": lambda physical_pin: {
            "code": 0,
            "message": f"gpio ok on pin {physical_pin}",
            "details": {"physical_pin": physical_pin, "logical_pin": 51},
        },
        "test_i2c_scan": lambda bus, scan_all: {
            "code": 0,
            "message": f"i2c ok on {bus}",
            "details": {"bus": bus, "scan_all": scan_all},
        },
    }

    result = Scheduler(FunctionExecutor(registry)).run(plan, _build_context(resolved_config))

    assert result.status == ResultStatus.PASSED
    assert len(result.children) == 5
    assert result.children[0].children[0].status == ResultStatus.PASSED
    assert result.children[1].children[0].details["port"] == "/dev/ttyS0"
    assert result.children[4].children[0].details["bus"] == "/dev/i2c-0"


def test_scheduler_retries_failed_function_until_success() -> None:
    resolver = ConfigResolver(REPO_ROOT)
    resolved_config = resolver.resolve_fixture("fixtures/quick_validation.json")
    flaky_case = copy.deepcopy(resolved_config.cases[0])
    flaky_case.functions[0].retry = 2
    flaky_case.functions[0].retry_interval = 0
    resolved_config.cases = [flaky_case]
    resolved_config.fixture.cases = ["cases/eth_case.json"]
    plan = FixtureRunner().build_plan(resolved_config)

    attempts = {"count": 0}

    def flaky_test(interface, target_ip):
        attempts["count"] += 1
        if attempts["count"] < 3:
            return {"code": -1, "message": "temporary failure"}
        return {"code": 0, "message": f"recovered via {interface}", "details": {"target_ip": target_ip}}

    result = Scheduler(FunctionExecutor({"test_eth_ping": flaky_test})).run(plan, _build_context(resolved_config))
    function_result = result.children[0].children[0]

    assert result.status == ResultStatus.PASSED
    assert function_result.retry_count == 2
    assert attempts["count"] == 3


def test_scheduler_marks_timeout_and_honors_stop_on_failure() -> None:
    resolver = ConfigResolver(REPO_ROOT)
    resolved_config = resolver.resolve_fixture("fixtures/quick_validation.json")
    timeout_case = copy.deepcopy(resolved_config.cases[0])
    timeout_case.stop_on_failure = True
    timeout_case.functions[0].timeout = 0
    timeout_case.functions.append(
        copy.deepcopy(timeout_case.functions[0])
    )
    timeout_case.functions[1].name = "test_eth_second"
    timeout_case.functions[1].timeout = 1
    resolved_config.cases = [timeout_case]
    resolved_config.fixture.cases = ["cases/eth_case.json"]
    plan = FixtureRunner().build_plan(resolved_config)

    def slow_test(interface, target_ip):
        time.sleep(0.05)
        return {"code": 0, "message": f"slow success on {interface}", "details": {"target_ip": target_ip}}

    registry = {
        "test_eth_ping": slow_test,
        "test_eth_second": lambda interface, target_ip: {"code": 0, "message": "should not run"},
    }

    result = Scheduler(FunctionExecutor(registry)).run(plan, _build_context(resolved_config))
    case_result = result.children[0]

    assert result.status == ResultStatus.TIMEOUT
    assert case_result.children[0].status == ResultStatus.TIMEOUT
    assert case_result.children[1].status == ResultStatus.ABORTED
