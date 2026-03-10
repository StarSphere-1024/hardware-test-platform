from __future__ import annotations

import json
from pathlib import Path

import pytest

import framework.cli.common as cli_common
from framework.cli.run_case import main as run_case_main
from framework.cli.run_fixture import main as run_fixture_main
from framework.cli.run_function import main as run_function_main


REPO_ROOT = Path(__file__).resolve().parents[2]


def _mock_function_registry() -> dict[str, object]:
    return {
        "test_eth_ping": lambda interface, target_ip: {
            "code": 0,
            "message": f"ping {target_ip} via {interface}",
            "details": {"success": True, "interface": interface, "target_ip": target_ip},
            "metrics": {"packet_loss": 0.0},
        },
        "test_uart_loopback": lambda port, baudrate, payload: {
            "code": 0,
            "message": f"loopback ok on {port}",
            "details": {"received": payload, "port": port},
        },
        "test_rtc_read": lambda rtc_device: {
            "code": 0,
            "message": f"rtc ok on {rtc_device}",
            "details": {"time": "2026-03-10T10:00:00+00:00", "rtc_device": rtc_device},
        },
        "test_gpio_mapping": lambda physical_pin: {
            "code": 0,
            "message": f"gpio ok on {physical_pin}",
            "details": {"available": True, "physical_pin": physical_pin},
        },
        "test_i2c_scan": lambda bus, scan_all: {
            "code": 0,
            "message": f"i2c ok on {bus}",
            "metrics": {"bus_count": 1},
            "details": {"requested_bus": bus, "scan_all": scan_all},
        },
    }


def test_run_fixture_cli_executes_fixture_and_prints_paths(tmp_path: Path, capsys) -> None:
    exit_code = run_fixture_main(
        [
            "--workspace-root",
            str(REPO_ROOT),
            "--artifacts-root",
            str(tmp_path),
            "--config",
            "fixtures/linux_host_pc.json",
        ],
        function_registry=_mock_function_registry(),
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["snapshot_path"]).exists()
    assert Path(payload["event_log_path"]).exists()
    assert len(payload["report_paths"]) == 2


def test_run_fixture_cli_can_attach_dashboard(tmp_path: Path, monkeypatch, capsys) -> None:
    attached: dict[str, object] = {}

    def fake_attach_dashboard(**kwargs):
        attached.update(kwargs)
        return {
            "enabled": True,
            "attached": True,
            "request_id": kwargs["request_id"],
            "fixture": kwargs["fixture_name"],
            "mode": "attached",
            "artifacts_root": str(kwargs["outputs_root"]),
            "auto_exit": True,
            "success_exit_linger_seconds": kwargs["success_exit_linger_seconds"],
            "failure_exit_linger_seconds": kwargs["failure_exit_linger_seconds"],
        }

    monkeypatch.setattr(cli_common, "_attach_dashboard", fake_attach_dashboard)

    exit_code = run_fixture_main(
        [
            "--workspace-root",
            str(REPO_ROOT),
            "--artifacts-root",
            str(tmp_path),
            "--config",
            "fixtures/linux_host_pc.json",
            "--dashboard",
        ],
        function_registry=_mock_function_registry(),
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["dashboard"]["attached"] is True
    assert attached["request_id"] == payload["request_id"]
    assert attached["fixture_name"] == "linux_host_pc"
    assert attached["success_exit_linger_seconds"] is None
    assert attached["failure_exit_linger_seconds"] is None


def test_run_fixture_cli_auto_discovers_real_eth_and_uart_functions(tmp_path: Path, monkeypatch, capsys) -> None:
    from datetime import datetime, timezone

    from framework.platform.capabilities.gpio import GPIOCapability
    from framework.platform.capabilities.i2c import I2CCapability
    from framework.platform.capabilities.network import NetworkCapability
    from framework.platform.capabilities.rtc import RTCCapability
    from framework.platform.capabilities.serial import SerialCapability

    def fake_ping(self, target_ip, *, interface=None, count=1, timeout=5):
        return {
            "success": True,
            "return_code": 0,
            "stdout": "1 packets transmitted, 1 received, 0% packet loss\nrtt min/avg/max/mdev = 0.010/0.321/1.000/0.100 ms\n",
            "stderr": "",
            "duration_ms": 5,
        }

    def fake_loopback(self, port, *, payload, baudrate=115200, timeout=5):
        return {
            "success": True,
            "message": "loopback ok",
            "received": payload,
            "duration_ms": 4,
        }

    def fake_read_time(self, device=None):
        return {
            "success": True,
            "device": device or "/dev/rtc0",
            "datetime": datetime(2026, 3, 6, 12, 0, 0, tzinfo=timezone.utc),
            "source": "hwclock",
            "raw": "2026-03-06 12:00:00",
        }

    def fake_describe_pin(self, physical_pin):
        return {
            "physical_pin": physical_pin,
            "logical_pin": 51,
            "chip_count": 1,
            "chips": ["/dev/gpiochip0"],
            "available": True,
        }

    def fake_scan_buses(self, buses=None):
        bus_list = buses or ["/dev/i2c-0", "/dev/i2c-2"]
        return {
            "success": True,
            "bus_count": len(bus_list),
            "buses": [{"bus": item, "exists": True} for item in bus_list],
        }

    monkeypatch.setattr(NetworkCapability, "ping", fake_ping)
    monkeypatch.setattr(SerialCapability, "loopback_test", fake_loopback)
    monkeypatch.setattr(RTCCapability, "read_time", fake_read_time)
    monkeypatch.setattr(GPIOCapability, "describe_pin", fake_describe_pin)
    monkeypatch.setattr(I2CCapability, "scan_buses", fake_scan_buses)

    exit_code = run_fixture_main(
        [
            "--workspace-root",
            str(REPO_ROOT),
            "--artifacts-root",
            str(tmp_path / "artifacts"),
            "--config",
            "fixtures/linux_host_pc.json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    case_results = payload["result"]["children"]
    assert len(case_results) == 4
    assert case_results[0]["children"][0]["name"] == "test_eth_ping"
    assert case_results[1]["children"][0]["name"] == "test_uart_loopback"
    assert case_results[1]["children"][0]["message"] == "loopback ok"
    assert case_results[2]["children"][0]["name"] == "test_rtc_read"
    assert case_results[3]["children"][0]["name"] == "test_i2c_scan"


def test_run_case_cli_executes_case_request(tmp_path: Path, capsys) -> None:
    exit_code = run_case_main(
        [
            "--workspace-root",
            str(REPO_ROOT),
            "--artifacts-root",
            str(tmp_path),
            "--config",
            "cases/linux_host_pc/eth_case.json",
            "--timeout",
            "15",
        ],
        function_registry={
            "test_eth_ping": lambda interface, target_ip: {
                "code": 0,
                "message": f"ping {target_ip} via {interface}",
                "details": {"success": True, "interface": interface, "target_ip": target_ip},
                "metrics": {"packet_loss": 0.0},
            }
        },
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["result"]["name"] == "adhoc_case"
    assert payload["result"]["children"][0]["children"][0]["message"].startswith("ping")


def test_run_case_cli_auto_discovers_real_eth_function(tmp_path: Path, monkeypatch, capsys) -> None:
    from framework.platform.capabilities.network import NetworkCapability

    def fake_ping(self, target_ip, *, interface=None, count=1, timeout=5):
        return {
            "success": True,
            "return_code": 0,
            "stdout": "1 packets transmitted, 1 received, 0% packet loss\nrtt min/avg/max/mdev = 0.010/0.321/1.000/0.100 ms\n",
            "stderr": "",
            "duration_ms": 5,
        }

    monkeypatch.setattr(NetworkCapability, "ping", fake_ping)

    exit_code = run_case_main(
        [
            "--workspace-root",
            str(REPO_ROOT),
            "--artifacts-root",
            str(tmp_path / "artifacts"),
            "--config",
            "cases/linux_host_pc/eth_case.json",
            "--timeout",
            "15",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert payload["result"]["children"][0]["children"][0]["message"].startswith("ping 192.168.100.1 via")
    assert payload["result"]["children"][0]["children"][0]["metrics"]["avg_latency_ms"] == 0.321


def test_run_case_cli_auto_discovers_real_rtc_function(tmp_path: Path, monkeypatch, capsys) -> None:
    from datetime import datetime, timezone

    from framework.platform.capabilities.rtc import RTCCapability

    def fake_read_time(self, device=None):
        return {
            "success": True,
            "device": device or "/dev/rtc0",
            "datetime": datetime(2026, 3, 6, 12, 0, 0, tzinfo=timezone.utc),
            "source": "hwclock",
            "raw": "2026-03-06 12:00:00",
        }

    monkeypatch.setattr(RTCCapability, "read_time", fake_read_time)

    exit_code = run_case_main(
        [
            "--workspace-root",
            str(REPO_ROOT),
            "--artifacts-root",
            str(tmp_path / "artifacts"),
            "--config",
            "cases/linux_host_pc/rtc_case.json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert payload["result"]["children"][0]["children"][0]["name"] == "test_rtc_read"
    assert payload["result"]["children"][0]["children"][0]["details"]["source"] == "hwclock"


def test_run_case_cli_auto_discovers_real_gpio_function(tmp_path: Path, monkeypatch, capsys) -> None:
    from framework.platform.capabilities.gpio import GPIOCapability

    def fake_describe_pin(self, physical_pin):
        return {
            "physical_pin": physical_pin,
            "logical_pin": 51,
            "chip_count": 1,
            "chips": ["/dev/gpiochip0"],
            "available": True,
        }

    monkeypatch.setattr(GPIOCapability, "describe_pin", fake_describe_pin)

    exit_code = run_case_main(
        [
            "--workspace-root",
            str(REPO_ROOT),
            "--artifacts-root",
            str(tmp_path / "artifacts"),
            "--config",
            "cases/rk3576/gpio_case.json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert payload["result"]["children"][0]["children"][0]["name"] == "test_gpio_mapping"
    assert payload["result"]["children"][0]["children"][0]["details"]["logical_pin"] == 51


def test_run_case_cli_auto_discovers_real_i2c_function(tmp_path: Path, monkeypatch, capsys) -> None:
    from framework.platform.capabilities.i2c import I2CCapability

    def fake_scan_buses(self, buses=None):
        bus_list = buses or ["/dev/i2c-0", "/dev/i2c-2"]
        return {
            "success": True,
            "bus_count": len(bus_list),
            "buses": [{"bus": item, "exists": True} for item in bus_list],
        }

    monkeypatch.setattr(I2CCapability, "scan_buses", fake_scan_buses)

    exit_code = run_case_main(
        [
            "--workspace-root",
            str(REPO_ROOT),
            "--artifacts-root",
            str(tmp_path / "artifacts"),
            "--config",
            "cases/linux_host_pc/i2c_case.json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert payload["result"]["children"][0]["children"][0]["name"] == "test_i2c_scan"
    assert payload["result"]["children"][0]["children"][0]["metrics"]["bus_count"] >= 1


def test_run_function_cli_imports_callable_and_executes(tmp_path: Path, monkeypatch, capsys) -> None:
    module_path = tmp_path / "sample_funcs.py"
    module_path.write_text(
        "def ping_once(target_ip, count=1):\n"
        "    return {'code': 0, 'message': f'ping {target_ip} x{count}', 'details': {'target_ip': target_ip, 'count': count}}\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    exit_code = run_function_main(
        [
            "--workspace-root",
            str(REPO_ROOT),
            "--artifacts-root",
            str(tmp_path / "artifacts"),
            "--callable",
            "sample_funcs:ping_once",
            "--params",
            '{"target_ip": "127.0.0.1", "count": 2}',
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["result"]["name"] == "ping_once"
    assert payload["result"]["details"]["target_ip"] == "127.0.0.1"


def test_run_function_cli_rejects_invalid_params_json(capsys) -> None:
    exit_code = run_function_main(
        [
            "--workspace-root",
            str(REPO_ROOT),
            "--callable",
            "missing.module:function",
            "--params",
            "not-json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert "error" in payload


def test_run_case_cli_rejects_board_profile_argument(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc_info:
        run_case_main(
            [
                "--workspace-root",
                str(REPO_ROOT),
                "--artifacts-root",
                str(tmp_path),
                "--config",
                "cases/linux_host_pc/eth_case.json",
                "--board-profile",
                "linux_host_pc",
            ]
        )

    assert exc_info.value.code == 2


def test_run_case_cli_reports_hint_when_fixture_config_passed(capsys) -> None:
    exit_code = run_case_main(
        [
            "--workspace-root",
            str(REPO_ROOT),
            "--config",
            "fixtures/rk3576_smoke.json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert "hint" in payload
    assert "run_fixture" in payload["hint"]
    assert "fixtures/rk3576_smoke.json" in payload["hint"]


def test_run_fixture_cli_rejects_board_profile_argument(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc_info:
        run_fixture_main(
            [
                "--workspace-root",
                str(REPO_ROOT),
                "--artifacts-root",
                str(tmp_path),
                "--config",
                "fixtures/linux_host_pc.json",
                "--board-profile",
                "linux_host_pc",
            ]
        )

    assert exc_info.value.code == 2
