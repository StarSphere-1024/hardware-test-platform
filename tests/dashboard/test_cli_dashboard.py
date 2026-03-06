from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from framework.dashboard.cli_dashboard import CLIDashboard, DashboardDataSource


REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def test_dashboard_collects_current_snapshot_state(tmp_path: Path) -> None:
    request_id = "req-dash-001"
    artifacts_root = tmp_path / "artifacts"
    _write_json(
        artifacts_root / "tmp" / f"{request_id}_snapshot.json",
        {
            "request_id": request_id,
            "plan_id": "plan.quick_validation",
            "updated_at": datetime(2026, 3, 6, 12, 0, 0, tzinfo=timezone.utc).isoformat(),
            "current_status": "aborted",
            "fixture": {"name": "quick_validation", "status": "aborted"},
            "cases": [
                {"name": "eth_case", "status": "failed", "message": "ping failed", "summary": {"failed": 1}},
                {"name": "uart_case", "status": "aborted", "message": "aborted by stop_on_failure", "summary": {"aborted": 1}},
            ],
            "counters": {"failed": 1, "aborted": 1},
            "status_summary": {"failed": 1, "aborted": 1},
            "runtime_state": {},
            "results": [],
        },
    )
    _write_jsonl(
        artifacts_root / "logs" / "events" / f"{request_id}.jsonl",
        [
            {
                "sequence": 1,
                "stored_at": datetime(2026, 3, 6, 12, 0, 0, tzinfo=timezone.utc).isoformat(),
                "storage_metadata": {"source": "scheduler"},
                "event": {"event_id": "evt-1", "request_id": request_id, "plan_id": "plan.quick_validation", "event_type": "task_retried", "timestamp": datetime(2026, 3, 6, 12, 0, 0, tzinfo=timezone.utc).isoformat(), "status": "warning", "task_name": "test_eth_ping", "message": "retrying"},
            }
        ],
    )
    _write_json(
        artifacts_root / "tmp" / "system_monitor.json",
        {
            "cpu": {"usage_percent": 23.0, "temperature": 48.0, "frequency_mhz": 1800},
            "memory": {"used_mb": 512, "total_mb": 2048, "usage_percent": 25.0},
            "storage": {"used_gb": 8, "total_gb": 32, "usage_percent": 25.0},
        },
    )
    (artifacts_root / "logs" / f"{request_id}.log").parent.mkdir(parents=True, exist_ok=True)
    (artifacts_root / "logs" / f"{request_id}.log").write_text("line-1\nline-2\n", encoding="utf-8")
    (artifacts_root / "reports").mkdir(parents=True, exist_ok=True)
    (artifacts_root / "reports" / f"RK3576_{request_id}_aborted.report.json").write_text("{}", encoding="utf-8")

    dashboard = CLIDashboard(
        workspace_root=REPO_ROOT,
        tmp_dir=artifacts_root / "tmp",
        logs_dir=artifacts_root / "logs",
        reports_dir=artifacts_root / "reports",
        request_id=request_id,
        fixture_name="quick_validation",
    )

    state = dashboard._collect_state()
    layout = dashboard.render_once()

    assert state["current_status"] == "aborted"
    assert state["fail_count"] == 1
    assert state["aborted_count"] == 1
    assert state["retry_count"] == 1
    assert state["sys_info"]["cpu"]["usage_percent"] == 23.0
    assert layout is not None


def test_dashboard_data_source_selects_latest_snapshot_when_request_is_omitted(tmp_path: Path) -> None:
    tmp_dir = tmp_path / "tmp"
    logs_dir = tmp_path / "logs"
    reports_dir = tmp_path / "reports"
    older = tmp_dir / "req-old_snapshot.json"
    newer = tmp_dir / "req-new_snapshot.json"
    _write_json(older, {"request_id": "req-old", "fixture": {"name": "old"}, "cases": []})
    _write_json(newer, {"request_id": "req-new", "fixture": {"name": "new"}, "cases": []})

    source = DashboardDataSource(workspace_root=REPO_ROOT, tmp_dir=tmp_dir, logs_dir=logs_dir, reports_dir=reports_dir)

    snapshot = source.read_snapshot()

    assert snapshot["request_id"] == "req-new"