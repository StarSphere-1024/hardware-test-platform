from __future__ import annotations

import json
from pathlib import Path

import pytest

from framework.config.errors import OverrideNotAllowedError, ProfileNotSupportedError, SchemaValidationError
from framework.config.resolver import ConfigResolver
from framework.config.validator import validate_fixture_data


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_fixture_resolution_builds_resolved_execution_config() -> None:
    resolver = ConfigResolver(REPO_ROOT)

    resolved = resolver.resolve_fixture("fixtures/linux_host_pc.json")

    assert resolved.fixture is not None
    assert resolved.fixture.fixture_name == "linux_host_pc"
    assert resolved.global_config.product.default_board_profile == "linux_host_pc"
    assert resolved.board_profile.platform == "linux"
    assert resolved.board_profile.profile_name == "linux_host_pc"
    assert resolved.board_profile.product.sku == "LINUX_HOST_PC"
    assert resolved.board_profile.product.stage == "DEV"
    assert resolved.resolved_interfaces["eth"]["selected"] == "eno1"
    assert resolved.resolved_interfaces["eth"]["selected"] == "eno1"
    assert resolved.resolved_interfaces["eth"]["source"] == "board_profile"
    assert resolved.resolved_interfaces["eth"]["items"][0] == "eno1"
    assert resolved.resolved_interfaces["i2c"]["selected"] == "/dev/i2c-0"
    assert len(resolved.cases) == 4
    assert resolved.cases[0].functions[0].params["interface"] == "eno1"
    assert resolved.cases[1].functions[0].params["port"] == "/dev/ttyUSB0"
    assert resolved.cases[2].functions[0].params["rtc_device"] == "/dev/rtc0"
    assert resolved.cases[3].functions[0].params["bus"] == "/dev/i2c-0"
    assert resolved.resolved_runtime["timeout"] == 300
    assert resolved.config_sources["runtime"]["timeout"]["source"] == "fixture"
    assert resolved.config_sources["case_runtime"]["uart_case"]["functions"]["test_uart_loopback#0"]["timeout"]["source"] == "function"


def test_fixture_board_profile_overrides_global_default() -> None:
    resolver = ConfigResolver(REPO_ROOT)

    resolved = resolver.resolve_fixture("fixtures/rk3576_smoke.json")

    assert resolved.fixture is not None
    assert resolved.fixture.board_profile == "rk3576"
    assert resolved.board_profile.profile_name == "rk3576"
    assert resolved.board_profile.product.sku == "RK3576_EVB"
    assert resolved.board_profile.product.stage == "DVT"


def test_case_board_profile_overrides_global_default() -> None:
    resolver = ConfigResolver(REPO_ROOT)

    resolved = resolver.resolve_case("cases/rk3576/uart_case.json")

    assert resolved.cases[0].board_profile == "rk3576"
    assert resolved.board_profile.profile_name == "rk3576"


def test_case_resolution_falls_back_to_default_board_profile() -> None:
    resolver = ConfigResolver(REPO_ROOT)

    resolved = resolver.resolve_case("cases/linux_host_pc/eth_case.json")

    assert resolved.global_config.product.default_board_profile == "linux_host_pc"
    assert resolved.board_profile.profile_name == "linux_host_pc"


def test_fixture_resolution_rejects_mismatched_case_board_profile(tmp_path: Path) -> None:
    fixture_path = tmp_path / "fixture.json"
    case_path = tmp_path / "case.json"

    fixture_path.write_text(
        json.dumps(
            {
                "fixture_name": "mismatch_fixture",
                "board_profile": "rk3576",
                "cases": ["case.json"],
            }
        ),
        encoding="utf-8",
    )
    case_path.write_text(
        json.dumps(
            {
                "case_name": "mismatch_case",
                "module": "uart",
                "board_profile": "linux_host_pc",
                "functions": [{"name": "test_uart_loopback"}],
            }
        ),
        encoding="utf-8",
    )

    resolver = ConfigResolver(REPO_ROOT)

    with pytest.raises(ProfileNotSupportedError):
        resolver.resolve_fixture(fixture_path)


def test_cli_override_wins_for_runtime_fields() -> None:
    resolver = ConfigResolver(REPO_ROOT)

    resolved = resolver.resolve_fixture(
        "fixtures/linux_host_pc.json",
        cli_overrides={"timeout": 120, "report_enabled": False},
    )

    assert resolved.resolved_runtime["timeout"] == 120
    assert resolved.resolved_runtime["report_enabled"] is False
    assert resolved.config_sources["runtime"]["timeout"]["source"] == "cli"
    assert resolved.cases[0].functions[0].timeout == 120


def test_invalid_override_is_rejected() -> None:
    resolver = ConfigResolver(REPO_ROOT)

    with pytest.raises(OverrideNotAllowedError):
        resolver.resolve_fixture("fixtures/linux_host_pc.json", cli_overrides={"unsupported": True})


def test_fixture_validation_rejects_invalid_loop_configuration() -> None:
    invalid_fixture = json.loads((REPO_ROOT / "fixtures" / "linux_host_pc.json").read_text(encoding="utf-8"))
    invalid_fixture["loop"] = True
    invalid_fixture["loop_count"] = 0

    with pytest.raises(SchemaValidationError):
        validate_fixture_data(invalid_fixture, source="tests")
