from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rich.console import Console

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
            "plan_id": "plan.linux_host_pc",
            "updated_at": datetime(2026, 3, 6, 12, 0, 0, tzinfo=timezone.utc).isoformat(),
            "current_status": "aborted",
            "fixture": {"name": "linux_host_pc", "status": "aborted"},
            "cases": [
                {
                    "name": "eth_case",
                    "status": "failed",
                    "message": "ping failed",
                    "summary": {"failed": 1},
                    "started_at": datetime(2026, 3, 6, 11, 59, 30, tzinfo=timezone.utc).isoformat(),
                    "duration_ms": 12000,
                },
                {
                    "name": "uart_case",
                    "status": "aborted",
                    "message": "aborted by stop_on_failure",
                    "summary": {"aborted": 1},
                    "started_at": datetime(2026, 3, 6, 11, 59, 42, tzinfo=timezone.utc).isoformat(),
                    "duration_ms": 0,
                },
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
                "stored_at": datetime(
                    2026, 3, 6, 12, 0, 0, tzinfo=timezone.utc
                ).isoformat(),
                "storage_metadata": {"source": "scheduler"},
                "event": {
                    "event_id": "evt-1",
                    "request_id": request_id,
                    "plan_id": "plan.linux_host_pc",
                    "event_type": "task_retried",
                    "timestamp": datetime(
                        2026, 3, 6, 12, 0, 0, tzinfo=timezone.utc
                    ).isoformat(),
                    "status": "warning",
                    "task_name": "test_eth_ping",
                    "message": "retrying",
                },
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
        fixture_name="linux_host_pc",
    )

    state = dashboard._collect_state()
    layout = dashboard.render_once()

    assert state["current_status"] == "aborted"
    assert state["fail_count"] == 1
    assert state["timeout_count"] == 0
    assert state["aborted_count"] == 1
    assert state["completed_count"] == 2
    assert state["wait_count"] == 0
    assert state["retry_count"] == 1
    assert state["sys_info"]["cpu"]["usage_percent"] == 23.0
    assert layout is not None


def test_dashboard_module_table_shows_case_runtime(tmp_path: Path) -> None:
    dashboard = CLIDashboard(workspace_root=REPO_ROOT, tmp_dir=tmp_path / "tmp", logs_dir=tmp_path / "logs", reports_dir=tmp_path / "reports")

    panel = dashboard._create_module_table(
        [
            {
                "name": "eth_case",
                "status": "running",
                "summary": {"running": 1},
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
            {
                "name": "uart_case",
                "status": "passed",
                "summary": {"passed": 1},
                "duration_ms": 65000,
            },
        ]
    )
    console = Console(record=True, force_terminal=False, width=120)
    console.print(panel)
    rendered = console.export_text(clear=False)

    assert "Runtime" in rendered
    assert "00:01:05" in rendered


def test_dashboard_runtime_prefers_live_running_elapsed_over_stale_duration() -> None:
    dashboard = CLIDashboard(workspace_root=REPO_ROOT)

    runtime_text = dashboard._case_runtime_display(
        {
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": 0,
        }
    )

    assert runtime_text == "0s"


def test_dashboard_runtime_formats_short_durations_with_milliseconds() -> None:
    dashboard = CLIDashboard(workspace_root=REPO_ROOT)

    assert dashboard._format_completed_duration(345) == "345ms"
    assert dashboard._format_completed_duration(1500) == "1.5s"


def test_dashboard_running_runtime_is_quantized_to_whole_seconds() -> None:
    dashboard = CLIDashboard(workspace_root=REPO_ROOT)

    assert dashboard._format_running_duration(250) == "0s"
    assert dashboard._format_running_duration(1250) == "1s"


def test_dashboard_running_runtime_uses_monotonic_baseline(monkeypatch) -> None:
    dashboard = CLIDashboard(workspace_root=REPO_ROOT)
    started_at = datetime(2026, 3, 12, 10, 0, 0, tzinfo=timezone.utc)
    case = {
        "name": "eth_case",
        "status": "running",
        "started_at": started_at.isoformat(),
        "duration_ms": 0,
    }

    class FakeDateTime(datetime):
        current = started_at

        @classmethod
        def now(cls, tz=None):
            value = cls.current
            return value if tz is None else value.astimezone(tz)

    monotonic_values = iter([100.0, 101.9])
    monkeypatch.setattr("framework.dashboard.cli_dashboard.time.monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr("framework.dashboard.cli_dashboard.datetime", FakeDateTime)

    FakeDateTime.current = started_at + timedelta(milliseconds=1200)
    assert dashboard._case_runtime_display(case) == "1s"

    FakeDateTime.current = started_at + timedelta(milliseconds=200)
    assert dashboard._case_runtime_display(case) == "3s"


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


def test_dashboard_auto_exit_policy_uses_success_and_failure_delays() -> None:
    dashboard = CLIDashboard(
        workspace_root=REPO_ROOT,
        success_exit_linger_seconds=3.0,
        failure_exit_linger_seconds=None,
        auto_exit=True,
    )

    assert dashboard._linger_seconds_for_status("passed") == 3.0
    assert dashboard._linger_seconds_for_status("skipped") == 3.0
    assert dashboard._linger_seconds_for_status("failed") is None
    assert dashboard._linger_seconds_for_status("aborted") is None


def test_dashboard_recent_failures_prefers_failed_function_messages(tmp_path: Path) -> None:
    request_id = "req-dash-failures"
    artifacts_root = tmp_path / "artifacts"
    _write_json(
        artifacts_root / "tmp" / f"{request_id}_snapshot.json",
        {
            "request_id": request_id,
            "plan_id": "plan.rk3576_smoke",
            "updated_at": datetime(2026, 3, 10, 10, 0, 0, tzinfo=timezone.utc).isoformat(),
            "current_status": "failed",
            "fixture": {"name": "rk3576_smoke", "status": "failed"},
            "cases": [
                {"name": "eth_case", "status": "failed", "message": "case completed: failed=1", "summary": {"failed": 1}},
                {"name": "uart_case", "status": "timeout", "message": "case completed: timeout=1", "summary": {"timeout": 1}},
            ],
            "counters": {"failed": 1, "timeout": 1},
            "status_summary": {"failed": 1, "timeout": 1},
            "runtime_state": {},
            "results": [
                {
                    "task_id": "fixture.0.rk3576_smoke",
                    "task_type": "fixture",
                    "name": "rk3576_smoke",
                    "status": "failed",
                    "children": [
                        {
                            "task_id": "case.0.eth_case",
                            "task_type": "case",
                            "name": "eth_case",
                            "status": "failed",
                            "message": "case completed: failed=1",
                            "children": [
                                {
                                    "task_id": "function.eth.0.test_eth_ping",
                                    "task_type": "function",
                                    "name": "test_eth_ping",
                                    "status": "failed",
                                    "message": "ethernet peer must be reachable",
                                }
                            ],
                        },
                        {
                            "task_id": "case.1.uart_case",
                            "task_type": "case",
                            "name": "uart_case",
                            "status": "timeout",
                            "message": "case completed: timeout=1",
                            "children": [
                                {
                                    "task_id": "function.uart.0.test_uart_loopback",
                                    "task_type": "function",
                                    "name": "test_uart_loopback",
                                    "status": "timeout",
                                    "message": "function 'test_uart_loopback' timed out after 5s",
                                }
                            ],
                        },
                    ],
                }
            ],
        },
    )

    dashboard = CLIDashboard(
        workspace_root=REPO_ROOT,
        tmp_dir=artifacts_root / "tmp",
        logs_dir=artifacts_root / "logs",
        reports_dir=artifacts_root / "reports",
        request_id=request_id,
        fixture_name="rk3576_smoke",
    )

    state = dashboard._collect_state()
    panel = dashboard._create_recent_failures_panel(state)
    rendered = str(panel.renderable)

    assert "eth_case / test_eth_ping: ethernet peer must be reachable" in rendered
    assert "uart_case / test_uart_loopback: function 'test_uart_loopback' timed out after 5s" in rendered
    assert "case completed: failed=1" not in rendered


def test_dashboard_counts_timeout_cases_as_completed(tmp_path: Path) -> None:
    request_id = "req-dash-timeout-count"
    artifacts_root = tmp_path / "artifacts"
    _write_json(
        artifacts_root / "tmp" / f"{request_id}_snapshot.json",
        {
            "request_id": request_id,
            "plan_id": "plan.rk3576_smoke",
            "updated_at": datetime(2026, 3, 10, 10, 0, 0, tzinfo=timezone.utc).isoformat(),
            "current_status": "timeout",
            "fixture": {"name": "rk3576_smoke", "status": "timeout"},
            "cases": [
                {"name": "eth_case", "status": "failed", "message": "failed", "summary": {"failed": 1}},
                {"name": "uart_case", "status": "timeout", "message": "timeout", "summary": {"timeout": 1}},
                {"name": "rtc_case", "status": "passed", "message": "passed", "summary": {"passed": 1}},
                {"name": "i2c_case", "status": "passed", "message": "passed", "summary": {"passed": 1}},
                {"name": "gpio_case", "status": "passed", "message": "passed", "summary": {"passed": 1}},
            ],
            "counters": {"failed": 1, "timeout": 1, "passed": 3},
            "status_summary": {"failed": 1, "timeout": 1, "passed": 3},
            "runtime_state": {},
            "results": [],
        },
    )

    dashboard = CLIDashboard(
        workspace_root=REPO_ROOT,
        tmp_dir=artifacts_root / "tmp",
        logs_dir=artifacts_root / "logs",
        reports_dir=artifacts_root / "reports",
        request_id=request_id,
        fixture_name="rk3576_smoke",
    )

    state = dashboard._collect_state()

    assert state["total"] == 5
    assert state["completed_count"] == 5
    assert state["timeout_count"] == 1
    assert state["wait_count"] == 0
