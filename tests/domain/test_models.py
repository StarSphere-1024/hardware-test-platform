from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from framework.config.resolver import ConfigResolver
from framework.domain.events import EventRecord, EventStatus, EventType, ExecutionEvent
from framework.domain.execution import ArtifactDirectories, ExecutionContext, ExecutionPlan, ExecutionTask, RetryPolicy
from framework.domain.requests import ExecutionRequest
from framework.domain.results import DashboardSnapshot, ExecutionResult, ReportArtifact, ResultSnapshot, ResultStatus


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_execution_request_is_json_serializable() -> None:
    request = ExecutionRequest(
        request_id="req-001",
        target_type="fixture",
        target_name="fixtures/quick_validation.json",
        cli_overrides={"timeout": 120},
        board_profile="rk3576",
        operator="tester",
        trigger_source="cli",
    )

    payload = request.to_dict()

    assert payload["target_type"] == "fixture"
    assert payload["cli_overrides"]["timeout"] == 120
    json.dumps(payload)


def test_execution_context_serializes_with_resolved_config() -> None:
    resolver = ConfigResolver(REPO_ROOT)
    resolved_config = resolver.resolve_fixture("fixtures/quick_validation.json")
    root_task = ExecutionTask(
        task_id="fixture.quick_validation",
        task_type="fixture",
        name="quick_validation",
        execution_mode="sequential",
        payload={"fixture": resolved_config.fixture.to_dict() if resolved_config.fixture else None},
        timeout=resolved_config.resolved_runtime["timeout"],
        retry_policy=RetryPolicy(
            max_retries=resolved_config.resolved_runtime["retry"],
            interval_seconds=resolved_config.resolved_runtime["retry_interval"],
        ),
    )
    plan = ExecutionPlan(
        plan_id="plan-001",
        root_task=root_task,
        tasks=[root_task],
        execution_policy={"mode": "sequential"},
        resource_requirements={"interfaces": ["eth", "uart"]},
    )
    context = ExecutionContext(
        request_id="req-001",
        plan_id=plan.plan_id,
        resolved_config=resolved_config,
        adapter_registry={"platform": resolved_config.board_profile.platform},
        capability_registry={"network": True, "serial": True},
        runtime_state={"loop_index": 0, "completed_tasks": []},
        artifacts_dir=ArtifactDirectories(
            logs_dir=REPO_ROOT / "logs",
            tmp_dir=REPO_ROOT / "tmp",
            reports_dir=REPO_ROOT / "reports",
        ),
    )

    payload = context.to_dict()

    assert payload["resolved_config"]["cases"][0]["functions"][0]["params"]["interface"] == "end0"
    assert payload["artifacts_dir"]["tmp_dir"].endswith("tmp")
    json.dumps(plan.to_dict())
    json.dumps(payload)


def test_execution_result_snapshot_and_dashboard_are_serializable() -> None:
    started_at = datetime(2026, 3, 6, 12, 0, 0, tzinfo=timezone.utc)
    finished_at = datetime(2026, 3, 6, 12, 0, 1, tzinfo=timezone.utc)
    child = ExecutionResult(
        task_id="function.eth.1",
        task_type="function",
        name="test_eth_ping",
        status=ResultStatus.PASSED,
        code=0,
        message="ping ok",
        details={"interface": "end0"},
        metrics={"avg_latency_ms": 1.2},
        artifacts=[ReportArtifact(artifact_type="json", uri="reports/eth.json", content_type="application/json")],
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=1000,
    )
    parent = ExecutionResult(
        task_id="case.eth",
        task_type="case",
        name="eth_case",
        status=ResultStatus.PASSED,
        message="case ok",
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=1000,
        children=[child],
    )
    snapshot = ResultSnapshot(
        request_id="req-001",
        plan_id="plan-001",
        updated_at=finished_at,
        status_summary={"passed": 2},
        runtime_state={"completed_tasks": ["function.eth.1", "case.eth"]},
        results=[parent],
    )
    dashboard = DashboardSnapshot(
        request_id="req-001",
        plan_id="plan-001",
        updated_at=finished_at,
        overall_status="passed",
        task_counts={"passed": 2, "failed": 0},
        latest_message="eth_case passed",
    )

    result_payload = parent.to_dict()
    snapshot_payload = snapshot.to_dict()
    dashboard_payload = dashboard.to_dict()

    assert result_payload["children"][0]["status"] == "passed"
    assert snapshot_payload["results"][0]["children"][0]["artifacts"][0]["artifact_type"] == "json"
    assert dashboard_payload["overall_status"] == "passed"
    json.dumps(snapshot_payload)
    json.dumps(dashboard_payload)


def test_execution_event_record_is_json_serializable() -> None:
    timestamp = datetime(2026, 3, 6, 12, 0, 0, tzinfo=timezone.utc)
    event = ExecutionEvent(
        event_id="evt-001",
        request_id="req-001",
        plan_id="plan-001",
        event_type=EventType.TASK_STARTED,
        status=EventStatus.INFO,
        task_id="function.eth.1",
        task_type="function",
        timestamp=timestamp,
        message="starting test_eth_ping",
        payload={"attempt": 1},
    )
    record = EventRecord(
        sequence=1,
        event=event,
        stored_at=timestamp,
        storage_metadata={"stream": "events/request-001.jsonl"},
    )

    payload = record.to_dict()

    assert payload["event"]["event_type"] == "task_started"
    assert payload["event"]["status"] == "info"
    json.dumps(payload)
