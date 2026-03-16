from __future__ import annotations

import json
from pathlib import Path

from framework.config.resolver import ConfigResolver
from framework.domain.execution import ArtifactDirectories, ExecutionContext
from framework.execution.fixture_runner import FixtureRunner
from framework.execution.function_executor import FunctionExecutor
from framework.execution.scheduler import Scheduler
from framework.observability import EventStore, ExecutionObserver, ReportGenerator, ResultStore, UnifiedLogger


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_scheduler_writes_events_snapshots_logs_and_reports(tmp_path: Path) -> None:
    resolver = ConfigResolver(REPO_ROOT)
    resolved = resolver.resolve_fixture(
        "fixtures/linux_host_pc.json",
        request={"kind": "fixture", "request_id": "req-obs-001", "fixture_path": "fixtures/linux_host_pc.json"},
    )
    plan = FixtureRunner().build_plan(resolved)

    result_store = ResultStore(tmp_path / "tmp")
    event_store = EventStore(tmp_path / "logs" / "events")
    report_generator = ReportGenerator(tmp_path / "reports")
    logger = UnifiedLogger(tmp_path / "logs")
    observer = ExecutionObserver(
        resolved_config=resolved,
        result_store=result_store,
        event_store=event_store,
        report_generator=report_generator,
        logger=logger,
    )

    context = ExecutionContext(
        request_id="req-obs-001",
        plan_id=plan.plan_id,
        resolved_config=resolved,
        runtime_state={"observability": observer},
        artifacts_dir=ArtifactDirectories(
            logs_dir=tmp_path / "logs",
            tmp_dir=tmp_path / "tmp",
            reports_dir=tmp_path / "reports",
        ),
    )

    registry = {
        "test_eth_ping": lambda interface, target_ip: {
            "code": 0,
            "message": f"ping {target_ip} via {interface}",
            "details": {"interface": interface, "success": True},
        },
        "test_uart_loopback": lambda port, baudrate, payload: {
            "code": 0,
            "message": f"loopback ok on {port}",
            "details": {"payload": payload, "received": payload},
        },
        "test_rtc_read": lambda rtc_device: {
            "code": 0,
            "message": f"rtc ok on {rtc_device}",
            "details": {"rtc_device": rtc_device, "time": "2026-03-10T10:00:00+00:00"},
        },
        "test_i2c_scan": lambda bus, scan_all: {
            "code": 0,
            "message": f"i2c ok on {bus}",
            "details": {"bus": bus, "scan_all": scan_all},
            "metrics": {"bus_count": 1},
        },
    }
    root_result = Scheduler(FunctionExecutor(registry)).run(plan, context)

    snapshot_path = result_store.snapshot_path("req-obs-001")
    event_log_path = event_store.event_log_path("req-obs-001")
    log_path = tmp_path / "logs" / "req-obs-001.log"
    reports = sorted((tmp_path / "reports").glob("*"))

    assert root_result.artifacts
    assert snapshot_path.exists()
    assert event_log_path.exists()
    assert log_path.exists()
    assert len(reports) == 2

    snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot_payload["current_status"] == "passed"
    assert snapshot_payload["fixture"]["name"] == "linux_host_pc"
    assert snapshot_payload["counters"]["passed"] >= 1

    lines = event_log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 12
    events = [json.loads(line) for line in lines]
    event_types = [entry["event"]["event_type"] for entry in events]
    assert "plan_created" in event_types
    assert "task_started" in event_types
    assert "task_finished" in event_types
    assert "report_generated" in event_types
    assert [entry["sequence"] for entry in events] == list(range(1, len(events) + 1))

    report_json = [item for item in reports if item.suffix == ".json"][0]
    report_payload = json.loads(report_json.read_text(encoding="utf-8"))
    assert report_payload["result_snapshot"]["current_status"] == "passed"
    assert report_payload["metadata"]["event_count"] == len(events) - 1


def test_observer_writes_live_case_summaries_before_fixture_finishes(tmp_path: Path) -> None:
    resolver = ConfigResolver(REPO_ROOT)
    resolved = resolver.resolve_fixture(
        "fixtures/linux_host_pc.json",
        request={"kind": "fixture", "request_id": "req-obs-live-001", "fixture_path": "fixtures/linux_host_pc.json"},
    )
    plan = FixtureRunner().build_plan(resolved)

    observer = ExecutionObserver(
        resolved_config=resolved,
        result_store=ResultStore(tmp_path / "tmp"),
        event_store=EventStore(tmp_path / "logs" / "events"),
        report_generator=ReportGenerator(tmp_path / "reports"),
        logger=UnifiedLogger(tmp_path / "logs"),
    )

    fixture_task = plan.root_task
    case_task = next(task for task in plan.tasks if task.task_type == "case")
    function_task = next(task for task in plan.tasks if task.parent_task_id == case_task.task_id and task.task_type == "function")

    observer.on_plan_created(plan)
    observer.on_task_started(fixture_task, plan_id=plan.plan_id)
    observer.on_task_started(case_task, plan_id=plan.plan_id)
    observer.on_task_started(function_task, plan_id=plan.plan_id, attempt=1, status_before="pending")

    snapshot_payload = json.loads((tmp_path / "tmp" / "req-obs-live-001_snapshot.json").read_text(encoding="utf-8"))

    assert snapshot_payload["current_status"] == "running"
    assert snapshot_payload["cases"]
    assert snapshot_payload["cases"][0]["name"] == "eth_case"
    assert snapshot_payload["cases"][0]["status"] == "running"
    assert snapshot_payload["cases"][0]["summary"]["running"] == 1


def test_observer_and_report_preserve_timeout_residual_risk(tmp_path: Path) -> None:
    resolver = ConfigResolver(REPO_ROOT)
    resolved = resolver.resolve_fixture(
        "fixtures/linux_host_pc.json",
        request={"kind": "fixture", "request_id": "req-obs-timeout-001", "fixture_path": "fixtures/linux_host_pc.json"},
    )
    resolved.cases = [resolved.cases[0]]
    resolved.fixture.cases = ["cases/linux_host_pc/eth_case.json"]
    resolved.cases[0].functions[0].timeout = 0
    plan = FixtureRunner().build_plan(resolved)

    result_store = ResultStore(tmp_path / "tmp")
    event_store = EventStore(tmp_path / "logs" / "events")
    report_generator = ReportGenerator(tmp_path / "reports")
    logger = UnifiedLogger(tmp_path / "logs")
    observer = ExecutionObserver(
        resolved_config=resolved,
        result_store=result_store,
        event_store=event_store,
        report_generator=report_generator,
        logger=logger,
    )
    context = ExecutionContext(
        request_id="req-obs-timeout-001",
        plan_id=plan.plan_id,
        resolved_config=resolved,
        runtime_state={"observability": observer},
        artifacts_dir=ArtifactDirectories(
            logs_dir=tmp_path / "logs",
            tmp_dir=tmp_path / "tmp",
            reports_dir=tmp_path / "reports",
        ),
    )

    def blocking_timeout(interface, target_ip):
        return_value = {"interface": interface, "target_ip": target_ip}
        import time

        time.sleep(0.05)
        return {"code": 0, "message": "unexpected success", "details": return_value}

    root_result = Scheduler(FunctionExecutor({"test_eth_ping": blocking_timeout})).run(plan, context)

    snapshot_payload = json.loads(result_store.snapshot_path("req-obs-timeout-001").read_text(encoding="utf-8"))
    event_lines = event_store.event_log_path("req-obs-timeout-001").read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in event_lines]
    report_json = next(item for item in (tmp_path / "reports").glob("*.json"))
    report_text = next(item for item in (tmp_path / "reports").glob("*.report"))
    report_payload = json.loads(report_json.read_text(encoding="utf-8"))

    function_result = root_result.children[0].children[0]
    assert function_result.status == "timeout"
    assert function_result.details["residual_risk"]["kind"] == "timeout_background_execution_unknown"
    assert snapshot_payload["results"][0]["children"][0]["children"][0]["details"]["residual_risk"]["kind"] == "timeout_background_execution_unknown"

    timeout_event = next(
        entry["event"]
        for entry in events
        if entry["event"]["event_type"] == "task_finished" and entry["event"].get("task_name") == "test_eth_ping"
    )
    assert timeout_event["payload"]["residual_risk"]["kind"] == "timeout_background_execution_unknown"
    assert report_payload["root_result"]["children"][0]["children"][0]["details"]["residual_risk"]["kind"] == "timeout_background_execution_unknown"
    assert "Residual Risks:" in report_text.read_text(encoding="utf-8")
    assert "test_eth_ping: timeout returned before the worker could be confirmed stopped" in report_text.read_text(encoding="utf-8")
