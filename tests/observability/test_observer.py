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
        "fixtures/quick_validation.json",
        request={"kind": "fixture", "request_id": "req-obs-001", "fixture_path": "fixtures/quick_validation.json"},
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
        "test_eth_ping": lambda interface, target_ip: {"code": 0, "message": f"ping {target_ip} via {interface}", "details": {"interface": interface}},
        "test_uart_loopback": lambda port, baudrate, payload: {"code": 0, "message": f"loopback ok on {port}", "details": {"payload": payload}},
        "test_rtc_read": lambda rtc_device: {"code": 0, "message": f"rtc ok on {rtc_device}", "details": {"rtc_device": rtc_device}},
        "test_gpio_mapping": lambda physical_pin: {"code": 0, "message": f"gpio ok on {physical_pin}", "details": {"physical_pin": physical_pin}},
        "test_i2c_scan": lambda bus, scan_all: {"code": 0, "message": f"i2c ok on {bus}", "details": {"bus": bus, "scan_all": scan_all}},
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
    assert snapshot_payload["fixture"]["name"] == "quick_validation"
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
