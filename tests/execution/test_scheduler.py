from __future__ import annotations

import copy
import threading
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
        plan_id="plan.linux_host_pc",
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
    resolved_config = resolver.resolve_fixture("fixtures/linux_host_pc.json")

    plan = FixtureRunner().build_plan(resolved_config)

    assert plan.root_task.task_type == "fixture"
    assert plan.root_task.name == "linux_host_pc"
    assert len(plan.tasks) == 9
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
    ]
    assert plan.tasks[1].dependencies == []
    assert plan.tasks[3].dependencies == [plan.tasks[1].task_id]
    assert plan.resource_requirements["resources"] == [
        "interface:eth:eno1",
        "interface:i2c:/dev/i2c-0",
        "interface:rtc:/dev/rtc0",
        "interface:uart:/dev/ttyUSB0",
    ]


def test_scheduler_runs_fixture_sequentially_and_aggregates_results() -> None:
    resolver = ConfigResolver(REPO_ROOT)
    resolved_config = resolver.resolve_fixture("fixtures/linux_host_pc.json")
    plan = FixtureRunner().build_plan(resolved_config)

    registry = {
        "test_eth_ping": lambda interface, target_ip: {
            "code": 0,
            "message": f"ping {target_ip} via {interface}",
            "details": {"interface": interface, "target_ip": target_ip, "success": True},
            "metrics": {"avg_latency_ms": 1.5},
        },
        "test_uart_loopback": lambda port, baudrate, payload: {
            "code": 0,
            "message": f"loopback ok on {port}",
            "details": {"port": port, "baudrate": baudrate, "payload": payload, "received": payload},
        },
        "test_rtc_read": lambda rtc_device: {
            "code": 0,
            "message": f"rtc ok on {rtc_device}",
            "details": {"rtc_device": rtc_device, "time": "2026-03-12T10:00:00+00:00"},
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
            "metrics": {"bus_count": 1},
        },
    }

    result = Scheduler(FunctionExecutor(registry)).run(plan, _build_context(resolved_config))

    assert result.status == ResultStatus.PASSED
    assert len(result.children) == 4
    assert result.children[0].children[0].status == ResultStatus.PASSED
    assert result.children[1].children[0].details["port"] == "/dev/ttyUSB0"
    assert result.children[3].children[0].details["bus"] == "/dev/i2c-0"
    assert result.children[0].children[0].details["resource_lock"]["acquired"] is True
    assert result.children[0].children[0].details["resource_lock"]["resources"] == ["interface:eth:eno1"]


def test_scheduler_retries_failed_function_until_success() -> None:
    resolver = ConfigResolver(REPO_ROOT)
    resolved_config = resolver.resolve_fixture("fixtures/linux_host_pc.json")
    flaky_case = copy.deepcopy(resolved_config.cases[0])
    flaky_case.functions[0].retry = 2
    flaky_case.functions[0].retry_interval = 0
    resolved_config.cases = [flaky_case]
    resolved_config.fixture.cases = ["cases/linux_host_pc/eth_case.json"]
    plan = FixtureRunner().build_plan(resolved_config)

    attempts = {"count": 0}

    def flaky_test(interface, target_ip):
        attempts["count"] += 1
        if attempts["count"] < 3:
            return {"code": -1, "message": "temporary failure"}
        return {
            "code": 0,
            "message": f"recovered via {interface}",
            "details": {"target_ip": target_ip, "success": True},
        }

    result = Scheduler(FunctionExecutor({"test_eth_ping": flaky_test})).run(plan, _build_context(resolved_config))
    function_result = result.children[0].children[0]

    assert result.status == ResultStatus.PASSED
    assert function_result.retry_count == 2
    assert attempts["count"] == 3


def test_scheduler_marks_timeout_and_honors_stop_on_failure() -> None:
    resolver = ConfigResolver(REPO_ROOT)
    resolved_config = resolver.resolve_fixture("fixtures/linux_host_pc.json")
    timeout_case = copy.deepcopy(resolved_config.cases[0])
    timeout_case.stop_on_failure = True
    timeout_case.functions[0].timeout = 0
    timeout_case.functions.append(
        copy.deepcopy(timeout_case.functions[0])
    )
    timeout_case.functions[1].name = "test_eth_second"
    timeout_case.functions[1].timeout = 1
    resolved_config.cases = [timeout_case]
    resolved_config.fixture.cases = ["cases/linux_host_pc/eth_case.json"]
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
    assert case_result.children[0].details["resource_lock"]["quarantine_until"] is not None


def test_scheduler_waits_for_quarantined_resource_before_running() -> None:
    resolver = ConfigResolver(REPO_ROOT)
    resolved_config = resolver.resolve_fixture("fixtures/linux_host_pc.json")
    resolved_config.cases = [copy.deepcopy(resolved_config.cases[0])]
    resolved_config.fixture.cases = ["cases/linux_host_pc/eth_case.json"]
    resolved_config.cases[0].functions[0].resource_lock_quarantine_seconds = 0.01
    plan = FixtureRunner().build_plan(resolved_config)
    context = _build_context(resolved_config)

    scheduler = Scheduler(
        FunctionExecutor(
            {
                "test_eth_ping": lambda interface, target_ip: {
                    "code": 0,
                    "message": f"ping {target_ip} via {interface}",
                    "details": {"success": True},
                }
            }
        )
    )
    manager = scheduler._resource_lock_manager(context)
    manager.release(
        ["interface:eth:eno1"],
        owner_task_id="seed-task",
        release_reason="timeout",
        quarantine_seconds=0.01,
    )

    started = time.perf_counter()
    result = scheduler.run(plan, context)
    elapsed = time.perf_counter() - started

    assert result.status == ResultStatus.PASSED
    assert elapsed >= 0.01
    assert result.children[0].children[0].details["resource_lock"]["wait_ms"] >= 1


def test_scheduler_releases_resource_owner_after_timeout() -> None:
    resolver = ConfigResolver(REPO_ROOT)
    resolved_config = resolver.resolve_fixture("fixtures/linux_host_pc.json")
    resolved_config.cases = [copy.deepcopy(resolved_config.cases[0])]
    resolved_config.fixture.cases = ["cases/linux_host_pc/eth_case.json"]
    resolved_config.cases[0].functions[0].timeout = 0
    resolved_config.cases[0].functions[0].resource_lock_quarantine_seconds = 0.02
    plan = FixtureRunner().build_plan(resolved_config)
    context = _build_context(resolved_config)

    result = Scheduler(FunctionExecutor({"test_eth_ping": lambda interface, target_ip: time.sleep(0.05)})).run(plan, context)
    entry = context.resource_locks["interface:eth:eno1"]

    assert result.status == ResultStatus.TIMEOUT
    assert entry["owner_task_id"] is None
    assert entry["last_release_reason"] == "timeout"
    assert entry["quarantine_until"] is not None


def test_scheduler_runs_parallel_cases_when_resources_do_not_conflict() -> None:
    resolver = ConfigResolver(REPO_ROOT)
    resolved_config = resolver.resolve_fixture("fixtures/linux_host_pc.json")
    resolved_config.fixture.execution = "parallel"
    resolved_config.resolved_runtime["execution"] = "parallel"
    resolved_config.cases = [copy.deepcopy(resolved_config.cases[0]), copy.deepcopy(resolved_config.cases[1])]
    resolved_config.fixture.cases = ["cases/linux_host_pc/eth_case.json", "cases/linux_host_pc/uart_case.json"]
    plan = FixtureRunner().build_plan(resolved_config)

    start_times: dict[str, float] = {}
    start_lock = threading.Lock()
    both_started = threading.Event()

    def eth_runner(interface, target_ip):
        with start_lock:
            start_times["eth"] = time.perf_counter()
            if len(start_times) == 2:
                both_started.set()
        both_started.wait(0.3)
        time.sleep(0.05)
        return {"code": 0, "message": "eth ok", "details": {"success": True}}

    def uart_runner(port, baudrate, payload):
        with start_lock:
            start_times["uart"] = time.perf_counter()
            if len(start_times) == 2:
                both_started.set()
        both_started.wait(0.3)
        time.sleep(0.05)
        return {"code": 0, "message": "uart ok", "details": {"received": payload}}

    registry = {"test_eth_ping": eth_runner, "test_uart_loopback": uart_runner}

    started = time.perf_counter()
    result = Scheduler(FunctionExecutor(registry)).run(plan, _build_context(resolved_config))
    elapsed = time.perf_counter() - started

    assert result.status == ResultStatus.PASSED
    assert set(start_times) == {"eth", "uart"}
    assert abs(start_times["eth"] - start_times["uart"]) < 0.1
    assert elapsed < 0.2


def test_scheduler_serializes_parallel_cases_that_share_resource() -> None:
    resolver = ConfigResolver(REPO_ROOT)
    resolved_config = resolver.resolve_fixture("fixtures/linux_host_pc.json")
    resolved_config.fixture.execution = "parallel"
    resolved_config.resolved_runtime["execution"] = "parallel"
    first_case = copy.deepcopy(resolved_config.cases[0])
    second_case = copy.deepcopy(resolved_config.cases[1])
    first_case.functions[0].resources = ["shared:serial-bus"]
    second_case.functions[0].resources = ["shared:serial-bus"]
    resolved_config.cases = [first_case, second_case]
    resolved_config.fixture.cases = ["cases/linux_host_pc/eth_case.json", "cases/linux_host_pc/uart_case.json"]
    plan = FixtureRunner().build_plan(resolved_config)

    def slow_eth(interface, target_ip):
        time.sleep(0.2)
        return {"code": 0, "message": "eth ok", "details": {"success": True}}

    def slow_uart(port, baudrate, payload):
        time.sleep(0.2)
        return {"code": 0, "message": "uart ok", "details": {"received": payload}}

    started = time.perf_counter()
    result = Scheduler(FunctionExecutor({"test_eth_ping": slow_eth, "test_uart_loopback": slow_uart})).run(
        plan,
        _build_context(resolved_config),
    )
    elapsed = time.perf_counter() - started

    assert result.status == ResultStatus.PASSED
    assert elapsed >= 0.35


def test_scheduler_parallel_stop_on_failure_preserves_in_flight_tasks() -> None:
    resolver = ConfigResolver(REPO_ROOT)
    resolved_config = resolver.resolve_fixture("fixtures/linux_host_pc.json")
    parallel_case = copy.deepcopy(resolved_config.cases[0])
    parallel_case.execution = "parallel"
    parallel_case.stop_on_failure = True

    failing_function = copy.deepcopy(parallel_case.functions[0])
    failing_function.name = "test_eth_fail_fast"
    failing_function.retry = 0
    failing_function.retry_interval = 0
    failing_function.expect = {}
    slow_function = copy.deepcopy(parallel_case.functions[0])
    slow_function.name = "test_eth_slow_success"
    slow_function.retry = 0
    slow_function.retry_interval = 0
    slow_function.expect = {}
    dependent_function = copy.deepcopy(parallel_case.functions[0])
    dependent_function.name = "test_eth_dependent"
    dependent_function.retry = 0
    dependent_function.retry_interval = 0
    dependent_function.expect = {}
    parallel_case.functions = [failing_function, slow_function, dependent_function]

    resolved_config.cases = [parallel_case]
    resolved_config.fixture.cases = ["cases/linux_host_pc/eth_case.json"]
    plan = FixtureRunner().build_plan(resolved_config)

    started: list[str] = []
    start_lock = threading.Lock()
    slow_started = threading.Event()

    def fail_fast(interface, target_ip):
        with start_lock:
            started.append("fail")
        slow_started.wait(0.2)
        return {"code": -1, "message": f"forced failure via {interface}", "details": {"target_ip": target_ip}}

    def slow_success(interface, target_ip):
        with start_lock:
            started.append("slow")
        slow_started.set()
        time.sleep(0.05)
        return {"code": 0, "message": f"slow success via {interface}", "details": {"target_ip": target_ip}}

    registry = {
        "test_eth_fail_fast": fail_fast,
        "test_eth_slow_success": slow_success,
        "test_eth_dependent": lambda interface, target_ip: {"code": 0, "message": "should not run"},
    }

    dependent_task = next(task for task in plan.tasks if task.name == "test_eth_dependent")
    failing_task = next(task for task in plan.tasks if task.name == "test_eth_fail_fast")
    dependent_task.dependencies = [failing_task.task_id]

    result = Scheduler(FunctionExecutor(registry)).run(plan, _build_context(resolved_config))
    case_result = result.children[0]

    assert result.status == ResultStatus.ABORTED
    assert case_result.status == ResultStatus.ABORTED
    assert started == ["fail", "slow"] or started == ["slow", "fail"]
    assert [child.status for child in case_result.children] == [ResultStatus.FAILED, ResultStatus.PASSED, ResultStatus.ABORTED]
    assert case_result.children[2].message == "aborted by stop_on_failure"


def test_scheduler_parallel_timeout_does_not_cancel_in_flight_tasks() -> None:
    resolver = ConfigResolver(REPO_ROOT)
    resolved_config = resolver.resolve_fixture("fixtures/linux_host_pc.json")
    parallel_case = copy.deepcopy(resolved_config.cases[0])
    parallel_case.execution = "parallel"
    parallel_case.stop_on_failure = True

    timeout_function = copy.deepcopy(parallel_case.functions[0])
    timeout_function.name = "test_eth_timeout"
    timeout_function.timeout = 0
    timeout_function.resource_lock_quarantine_seconds = 0.02
    timeout_function.retry = 0
    timeout_function.retry_interval = 0
    timeout_function.expect = {}
    slow_function = copy.deepcopy(parallel_case.functions[0])
    slow_function.name = "test_eth_parallel_success"
    slow_function.retry = 0
    slow_function.retry_interval = 0
    slow_function.expect = {}
    dependent_function = copy.deepcopy(parallel_case.functions[0])
    dependent_function.name = "test_eth_timeout_dependent"
    dependent_function.retry = 0
    dependent_function.retry_interval = 0
    dependent_function.expect = {}
    parallel_case.functions = [timeout_function, slow_function, dependent_function]

    resolved_config.cases = [parallel_case]
    resolved_config.fixture.cases = ["cases/linux_host_pc/eth_case.json"]
    plan = FixtureRunner().build_plan(resolved_config)

    timeout_task = next(task for task in plan.tasks if task.name == "test_eth_timeout")
    dependent_task = next(task for task in plan.tasks if task.name == "test_eth_timeout_dependent")
    dependent_task.dependencies = [timeout_task.task_id]

    started = threading.Event()

    def blocking_timeout(interface, target_ip):
        started.set()
        time.sleep(0.05)
        return {"code": 0, "message": f"unexpected success via {interface}", "details": {"target_ip": target_ip}}

    def slow_success(interface, target_ip):
        started.wait(0.2)
        time.sleep(0.05)
        return {"code": 0, "message": f"slow success via {interface}", "details": {"target_ip": target_ip}}

    registry = {
        "test_eth_timeout": blocking_timeout,
        "test_eth_parallel_success": slow_success,
        "test_eth_timeout_dependent": lambda interface, target_ip: {"code": 0, "message": "should not run"},
    }

    result = Scheduler(FunctionExecutor(registry)).run(plan, _build_context(resolved_config))
    case_result = result.children[0]

    assert result.status == ResultStatus.TIMEOUT
    assert case_result.status == ResultStatus.TIMEOUT
    assert [child.status for child in case_result.children] == [ResultStatus.TIMEOUT, ResultStatus.PASSED, ResultStatus.ABORTED]
    assert case_result.children[0].details["resource_lock"]["quarantine_until"] is not None
    assert case_result.children[0].details["residual_risk"]["kind"] == "timeout_background_execution_unknown"


def test_scheduler_parallel_shared_resource_conflict_aborts_unsubmitted_dependents() -> None:
    resolver = ConfigResolver(REPO_ROOT)
    resolved_config = resolver.resolve_fixture("fixtures/linux_host_pc.json")
    parallel_case = copy.deepcopy(resolved_config.cases[0])
    parallel_case.execution = "parallel"
    parallel_case.stop_on_failure = True

    locked_function = copy.deepcopy(parallel_case.functions[0])
    locked_function.name = "test_eth_locked_one"
    locked_function.timeout = 0
    locked_function.resources = ["shared:eth-bus"]
    locked_function.retry = 0
    locked_function.retry_interval = 0
    locked_function.expect = {}
    blocked_function = copy.deepcopy(parallel_case.functions[0])
    blocked_function.name = "test_eth_locked_two"
    blocked_function.timeout = 0
    blocked_function.resources = ["shared:eth-bus"]
    blocked_function.retry = 0
    blocked_function.retry_interval = 0
    blocked_function.expect = {}
    dependent_function = copy.deepcopy(parallel_case.functions[0])
    dependent_function.name = "test_eth_locked_dependent"
    dependent_function.retry = 0
    dependent_function.retry_interval = 0
    dependent_function.expect = {}
    parallel_case.functions = [locked_function, blocked_function, dependent_function]

    resolved_config.cases = [parallel_case]
    resolved_config.fixture.cases = ["cases/linux_host_pc/eth_case.json"]
    plan = FixtureRunner().build_plan(resolved_config)
    context = _build_context(resolved_config)
    scheduler = Scheduler(
        FunctionExecutor(
            {
                "test_eth_locked_one": lambda interface, target_ip: {"code": 0, "message": "should not run"},
                "test_eth_locked_two": lambda interface, target_ip: {"code": 0, "message": "should not run"},
                "test_eth_locked_dependent": lambda interface, target_ip: {"code": 0, "message": "should not run"},
            }
        )
    )

    first_task = next(task for task in plan.tasks if task.name == "test_eth_locked_one")
    second_task = next(task for task in plan.tasks if task.name == "test_eth_locked_two")
    dependent_task = next(task for task in plan.tasks if task.name == "test_eth_locked_dependent")
    dependent_task.dependencies = [first_task.task_id]

    scheduler._resource_lock_manager(context).acquire(
        ["shared:eth-bus"],
        owner_task_id="seed-owner",
        owner_attempt=1,
        timeout_seconds=1,
    )
    result = scheduler.run(plan, context)
    case_result = result.children[0]

    assert result.status == ResultStatus.TIMEOUT
    assert case_result.status == ResultStatus.TIMEOUT
    assert [child.status for child in case_result.children] == [ResultStatus.TIMEOUT, ResultStatus.TIMEOUT, ResultStatus.ABORTED]
    assert case_result.children[0].details["resource_lock"]["acquired"] is False
    assert case_result.children[1].details["resource_lock"]["acquired"] is False
    assert case_result.children[0].details["resource_lock"]["blocked_reason"] == "locked"
    assert case_result.children[1].details["resource_lock"]["blocked_reason"] == "locked"


def test_scheduler_parallel_dependency_chain_aborts_unsubmitted_descendants_after_failure() -> None:
    resolver = ConfigResolver(REPO_ROOT)
    resolved_config = resolver.resolve_fixture("fixtures/linux_host_pc.json")
    parallel_case = copy.deepcopy(resolved_config.cases[0])
    parallel_case.execution = "parallel"
    parallel_case.stop_on_failure = True

    first_function = copy.deepcopy(parallel_case.functions[0])
    first_function.name = "test_eth_chain_first"
    first_function.retry = 0
    first_function.retry_interval = 0
    first_function.expect = {}
    second_function = copy.deepcopy(parallel_case.functions[0])
    second_function.name = "test_eth_chain_second"
    second_function.retry = 0
    second_function.retry_interval = 0
    second_function.expect = {}
    third_function = copy.deepcopy(parallel_case.functions[0])
    third_function.name = "test_eth_chain_third"
    third_function.retry = 0
    third_function.retry_interval = 0
    third_function.expect = {}
    parallel_case.functions = [first_function, second_function, third_function]

    resolved_config.cases = [parallel_case]
    resolved_config.fixture.cases = ["cases/linux_host_pc/eth_case.json"]
    plan = FixtureRunner().build_plan(resolved_config)

    first_task = next(task for task in plan.tasks if task.name == "test_eth_chain_first")
    second_task = next(task for task in plan.tasks if task.name == "test_eth_chain_second")
    third_task = next(task for task in plan.tasks if task.name == "test_eth_chain_third")
    second_task.dependencies = [first_task.task_id]
    third_task.dependencies = [second_task.task_id]

    registry = {
        "test_eth_chain_first": lambda interface, target_ip: {"code": 0, "message": "first ok", "details": {"target_ip": target_ip}},
        "test_eth_chain_second": lambda interface, target_ip: {"code": -1, "message": "second failed", "details": {"target_ip": target_ip}},
        "test_eth_chain_third": lambda interface, target_ip: {"code": 0, "message": "should not run"},
    }

    result = Scheduler(FunctionExecutor(registry)).run(plan, _build_context(resolved_config))
    case_result = result.children[0]

    assert result.status == ResultStatus.ABORTED
    assert case_result.status == ResultStatus.ABORTED
    assert [child.status for child in case_result.children] == [ResultStatus.PASSED, ResultStatus.FAILED, ResultStatus.ABORTED]
    assert case_result.children[2].message == "aborted by stop_on_failure"
