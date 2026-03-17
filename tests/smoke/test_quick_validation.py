from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from framework.cli.run_fixture import main as run_fixture_main


REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _patch_quick_validation_capabilities(
    monkeypatch, *, eth_success: bool = True
) -> None:
    from framework.platform.capabilities import (
        GPIOCapability,
        I2CCapability,
        NetworkCapability,
        RTCCapability,
        SerialCapability,
    )

    def fake_ping(self, target_ip, *, interface=None, count=1, timeout=5):
        return {
            "success": eth_success,
            "target": target_ip,
            "interface": interface,
            "return_code": 0 if eth_success else 1,
            "stdout": (
                "1 packets transmitted, 1 received, 0% packet loss\n"
                "rtt min/avg/max/mdev = 0.010/0.321/1.000/0.100 ms\n"
                if eth_success
                else "1 packets transmitted, 0 received, 100% packet loss\n"
            ),
            "stderr": "" if eth_success else "ping timeout",
            "packet_loss": 0.0 if eth_success else 100.0,
            "avg_latency_ms": 0.321 if eth_success else 0.0,
            "message": (
                f"icmp probe to {target_ip} via {interface or 'auto'} ok"
                if eth_success
                else f"icmp probe to {target_ip} via {interface or 'auto'} failed"
            ),
            "error_type": None if eth_success else "probe_failed",
            "duration_ms": 5,
        }

    def fake_loopback(self, port, *, payload, baudrate=115200, timeout=5):
        return {
            "success": True,
            "port": port,
            "payload": payload,
            "message": "loopback ok",
            "received": payload,
            "matched": True,
            "baudrate": baudrate,
            "error_type": None,
            "duration_ms": 4,
        }

    def fake_read_time(self, device=None):
        return {
            "success": True,
            "device": device or "/dev/rtc0",
            "datetime": datetime(2026, 3, 6, 12, 0, 0, tzinfo=timezone.utc),
            "time_iso": "2026-03-06T12:00:00+00:00",
            "source": "hwclock",
            "raw": "2026-03-06 12:00:00",
            "message": f"rtc read ok on {device or '/dev/rtc0'}",
        }

    def fake_describe_pin(self, physical_pin):
        return {
            "physical_pin": physical_pin,
            "logical_pin": 51,
            "chip_count": 1,
            "chips": ["/dev/gpiochip0"],
            "available": True,
            "success": True,
            "error_type": None,
            "message": f"gpio mapping ok for physical pin {physical_pin}",
        }

    def fake_scan_buses(self, buses=None):
        bus_list = buses or ["/dev/i2c-0", "/dev/i2c-2"]
        return {
            "success": True,
            "requested_buses": list(bus_list),
            "bus_count": len(bus_list),
            "buses": [{"bus": item, "exists": True} for item in bus_list],
            "error_type": None,
            "message": f"i2c scan ok, buses={len(bus_list)}",
        }

    monkeypatch.setattr(NetworkCapability, "ping", fake_ping)
    monkeypatch.setattr(SerialCapability, "loopback_test", fake_loopback)
    monkeypatch.setattr(RTCCapability, "read_time", fake_read_time)
    monkeypatch.setattr(GPIOCapability, "describe_pin", fake_describe_pin)
    monkeypatch.setattr(I2CCapability, "scan_buses", fake_scan_buses)


def _run_quick_validation(
    tmp_path: Path, capsys, *, stop_on_failure: bool = False
) -> tuple[int, dict[str, object]]:
    return _run_fixture(
        tmp_path,
        capsys,
        config="fixtures/linux_host_pc.json",
        stop_on_failure=stop_on_failure,
    )


def _run_fixture(
    tmp_path: Path,
    capsys,
    *,
    config: str,
    stop_on_failure: bool = False,
) -> tuple[int, dict[str, object]]:
    argv = [
        "--workspace-root",
        str(REPO_ROOT),
        "--artifacts-root",
        str(tmp_path / "artifacts"),
        "--config",
        config,
    ]
    if stop_on_failure:
        argv.append("--stop-on-failure")
    exit_code = run_fixture_main(argv)
    payload = json.loads(capsys.readouterr().out)
    return exit_code, payload


def _build_precheck_failure_workspace(workspace_root: Path) -> None:
    _write_json(
        workspace_root / "config" / "global_config.json",
        {
            "product": {"default_board_profile": "rk3576_missing_eth"},
            "runtime": {
                "default_timeout": 60,
                "default_retry": 1,
                "default_retry_interval": 3,
            },
            "observability": {
                "report_enabled": True,
                "dashboard_enabled": True,
            },
        },
    )
    _write_json(
        workspace_root / "config" / "boards" / "rk3576_missing_eth.json",
        {
            "profile_name": "rk3576_missing_eth",
            "platform": "linux",
            "product": {"sku": "RK3576_EVB", "stage": "DVT"},
            "supported_cases": ["eth_case", "uart_case"],
            "interfaces": {
                "uart": ["/dev/ttyS0"],
            },
            "capabilities": {
                "serial": {"loopback": True},
            },
            "metadata": {
                "vendor": "Seeed",
                "board_family": "rk3576",
            },
        },
    )
    _write_json(
        workspace_root / "cases" / "eth_case.json",
        {
            "case_name": "eth_case",
            "module": "network",
            "description": "ETH case used for precheck failure smoke.",
            "execution": "sequential",
            "required_interfaces": {
                "eth": {
                    "required": True,
                    "select": "auto",
                }
            },
            "functions": [
                {
                    "name": "test_eth_ping",
                    "params": {
                        "interface": "missing",
                        "target_ip": "192.168.1.100",
                    },
                }
            ],
        },
    )
    _write_json(
        workspace_root / "cases" / "uart_case.json",
        {
            "case_name": "uart_case",
            "module": "uart",
            "description": "UART case used for aborted smoke.",
            "execution": "sequential",
            "required_interfaces": {
                "uart": {
                    "required": True,
                    "select": "auto",
                }
            },
            "functions": [
                {
                    "name": "test_uart_loopback",
                    "params": {
                        "port": "/dev/ttyS0",
                        "payload": "smoke",
                    },
                }
            ],
        },
    )
    _write_json(
        workspace_root / "fixtures" / "precheck_failure.json",
        {
            "fixture_name": "precheck_failure",
            "description": "Fixture for required_interfaces precheck smoke.",
            "cases": [
                "cases/eth_case.json",
                "cases/uart_case.json",
            ],
            "execution": "sequential",
            "stop_on_failure": True,
            "report_enabled": True,
            "timeout": 120,
            "retry": 1,
            "retry_interval": 1,
        },
    )


def test_quick_validation_fixture_smoke(tmp_path: Path, monkeypatch, capsys) -> None:
    _patch_quick_validation_capabilities(monkeypatch)

    exit_code, payload = _run_quick_validation(tmp_path, capsys)
    snapshot_path = Path(payload["snapshot_path"])
    event_log_path = Path(payload["event_log_path"])
    log_path = Path(payload["log_path"])
    report_paths = [Path(item) for item in payload["report_paths"]]

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert len(payload["result"]["children"]) == 4
    assert [
        case_result["children"][0]["name"]
        for case_result in payload["result"]["children"]
    ] == [
        "test_eth_ping",
        "test_uart_loopback",
        "test_rtc_read",
        "test_i2c_scan",
    ]
    assert snapshot_path.exists()
    assert event_log_path.exists()
    assert log_path.exists()
    assert len(report_paths) == 2
    assert all(path.exists() for path in report_paths)

    snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot_payload["fixture"]["name"] == "linux_host_pc"
    assert snapshot_payload["current_status"] == "passed"
    assert snapshot_payload["counters"]["passed"] >= 4

    event_lines = event_log_path.read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in event_lines]
    event_types = [entry["event"]["event_type"] for entry in events]
    assert len(event_lines) >= 12
    assert "plan_created" in event_types
    assert "task_started" in event_types
    assert "task_finished" in event_types
    assert "report_generated" in event_types

    json_report = next(path for path in report_paths if path.suffix == ".json")
    report_payload = json.loads(json_report.read_text(encoding="utf-8"))
    assert report_payload["request"]["target_name"] == "fixtures/linux_host_pc.json"
    assert (
        report_payload["config_snapshot"]["fixture"]["fixture_name"] == "linux_host_pc"
    )
    assert report_payload["result_snapshot"]["current_status"] == "passed"
    assert report_payload["metadata"]["event_count"] == len(event_lines) - 1


def test_quick_validation_fixture_stop_on_failure_smoke(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    _patch_quick_validation_capabilities(monkeypatch, eth_success=False)

    exit_code, payload = _run_quick_validation(tmp_path, capsys, stop_on_failure=True)
    snapshot_path = Path(payload["snapshot_path"])
    event_log_path = Path(payload["event_log_path"])
    report_paths = [Path(item) for item in payload["report_paths"]]

    assert exit_code == 1
    assert payload["status"] == "aborted"
    case_results = payload["result"]["children"]
    assert len(case_results) == 4
    assert case_results[0]["name"] == "eth_case"
    assert case_results[0]["status"] == "failed"
    assert case_results[0]["children"][0]["name"] == "test_eth_ping"
    assert case_results[0]["children"][0]["status"] == "failed"
    assert all(case_result["status"] == "aborted" for case_result in case_results[1:])
    assert all(
        case_result["message"] == "aborted by stop_on_failure"
        for case_result in case_results[1:]
    )

    snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot_payload["fixture"]["name"] == "linux_host_pc"
    assert snapshot_payload["current_status"] == "aborted"
    assert snapshot_payload["counters"]["failed"] >= 1
    assert snapshot_payload["counters"]["aborted"] >= 1

    event_lines = event_log_path.read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in event_lines]
    task_started = [
        entry for entry in events if entry["event"]["event_type"] == "task_started"
    ]
    task_finished = [
        entry for entry in events if entry["event"]["event_type"] == "task_finished"
    ]
    task_retried = [
        entry for entry in events if entry["event"]["event_type"] == "task_retried"
    ]
    assert len(task_started) == 5
    assert len(task_finished) == 3
    assert len(task_retried) == 2
    assert task_started[0]["event"]["task_type"] == "fixture"
    assert task_started[1]["event"]["task_type"] == "case"
    assert all(entry["event"]["task_type"] == "function" for entry in task_started[2:])
    assert all(entry["event"]["task_name"] == "test_eth_ping" for entry in task_retried)
    assert task_finished[-1]["event"]["status_after"] == "aborted"

    json_report = next(path for path in report_paths if path.suffix == ".json")
    report_payload = json.loads(json_report.read_text(encoding="utf-8"))
    assert report_payload["result_snapshot"]["current_status"] == "aborted"
    assert report_payload["root_result"]["status"] == "aborted"
    assert report_payload["root_result"]["children"][0]["status"] == "failed"
    assert all(
        child["status"] == "aborted"
        for child in report_payload["root_result"]["children"][1:]
    )


def test_fixture_precheck_failure_smoke(tmp_path: Path, capsys) -> None:
    workspace_root = tmp_path / "workspace"
    _build_precheck_failure_workspace(workspace_root)

    exit_code = run_fixture_main(
        [
            "--workspace-root",
            str(workspace_root),
            "--artifacts-root",
            str(tmp_path / "artifacts"),
            "--config",
            "fixtures/precheck_failure.json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    snapshot_path = Path(payload["snapshot_path"])
    event_log_path = Path(payload["event_log_path"])
    report_paths = [Path(item) for item in payload["report_paths"]]

    assert exit_code == 1
    assert payload["status"] == "aborted"
    case_results = payload["result"]["children"]
    assert [case_result["name"] for case_result in case_results] == [
        "eth_case",
        "uart_case",
    ]
    assert case_results[0]["status"] == "failed"
    assert case_results[0]["message"] == "missing required interfaces: eth"
    assert case_results[0]["children"] == []
    assert case_results[1]["status"] == "aborted"
    assert case_results[1]["message"] == "aborted by stop_on_failure"

    snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot_payload["fixture"]["name"] == "precheck_failure"
    assert snapshot_payload["current_status"] == "aborted"
    assert snapshot_payload["counters"]["failed"] >= 1
    assert snapshot_payload["counters"]["aborted"] >= 1

    event_lines = event_log_path.read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in event_lines]
    task_started = [
        entry for entry in events if entry["event"]["event_type"] == "task_started"
    ]
    task_finished = [
        entry for entry in events if entry["event"]["event_type"] == "task_finished"
    ]
    assert len(task_started) == 2
    assert len(task_finished) == 2
    assert all(entry["event"]["task_type"] != "function" for entry in task_started)
    assert task_finished[0]["event"]["task_name"] == "eth_case"
    assert task_finished[0]["event"]["status_after"] == "failed"
    assert task_finished[1]["event"]["task_name"] == "precheck_failure"
    assert task_finished[1]["event"]["status_after"] == "aborted"

    json_report = next(path for path in report_paths if path.suffix == ".json")
    report_payload = json.loads(json_report.read_text(encoding="utf-8"))
    assert report_payload["request"]["target_name"] == "fixtures/precheck_failure.json"
    assert (
        report_payload["config_snapshot"]["fixture"]["fixture_name"]
        == "precheck_failure"
    )
    assert report_payload["result_snapshot"]["current_status"] == "aborted"
    assert report_payload["root_result"]["children"][0]["details"][
        "missing_interfaces"
    ] == ["eth"]


def test_parallel_fixture_smoke(tmp_path: Path, monkeypatch, capsys) -> None:
    _patch_quick_validation_capabilities(monkeypatch)

    exit_code, payload = _run_fixture(
        tmp_path,
        capsys,
        config="fixtures/linux_host_pc_parallel.json",
    )
    snapshot_path = Path(payload["snapshot_path"])
    event_log_path = Path(payload["event_log_path"])

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert payload["result"]["name"] == "linux_host_pc_parallel"
    assert [case_result["name"] for case_result in payload["result"]["children"]] == [
        "eth_case",
        "uart_case",
    ]

    snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot_payload["fixture"]["name"] == "linux_host_pc_parallel"
    assert snapshot_payload["current_status"] == "passed"

    event_lines = event_log_path.read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in event_lines]
    task_started = [
        entry for entry in events if entry["event"]["event_type"] == "task_started"
    ]
    case_started = [
        entry for entry in task_started if entry["event"]["task_type"] == "case"
    ]
    assert len(case_started) == 2
    assert {entry["event"]["task_name"] for entry in case_started} == {
        "eth_case",
        "uart_case",
    }
