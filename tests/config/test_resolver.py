from __future__ import annotations

import json
from pathlib import Path

import pytest

from framework.config.errors import OverrideNotAllowedError, SchemaValidationError
from framework.config.resolver import ConfigResolver
from framework.config.validator import validate_fixture_data


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_fixture_resolution_builds_resolved_execution_config() -> None:
    resolver = ConfigResolver(REPO_ROOT)

    resolved = resolver.resolve_fixture("fixtures/quick_validation.json")

    assert resolved.fixture is not None
    assert resolved.fixture.fixture_name == "quick_validation"
    assert resolved.global_config.product.board_profile == "rk3576"
    assert resolved.board_profile.platform == "linux"
    assert resolved.resolved_interfaces["eth"]["primary"] == "end0"
    assert resolved.resolved_interfaces["i2c"]["primary"] == "/dev/i2c-0"
    assert len(resolved.cases) == 5
    assert resolved.cases[0].functions[0].params["interface"] == "end0"
    assert resolved.cases[1].functions[0].params["port"] == "/dev/ttyS0"
    assert resolved.cases[2].functions[0].params["rtc_device"] == "/dev/rtc0"
    assert resolved.cases[4].functions[0].params["bus"] == "/dev/i2c-0"
    assert resolved.resolved_runtime["timeout"] == 300
    assert resolved.config_sources["runtime"]["timeout"]["source"] == "fixture"
    assert resolved.config_sources["case_runtime"]["uart_case"]["functions"]["test_uart_loopback#0"]["timeout"]["source"] == "function"


def test_cli_override_wins_for_runtime_fields() -> None:
    resolver = ConfigResolver(REPO_ROOT)

    resolved = resolver.resolve_fixture(
        "fixtures/quick_validation.json",
        cli_overrides={"timeout": 120, "report_enabled": False},
    )

    assert resolved.resolved_runtime["timeout"] == 120
    assert resolved.resolved_runtime["report_enabled"] is False
    assert resolved.config_sources["runtime"]["timeout"]["source"] == "cli"
    assert resolved.cases[0].functions[0].timeout == 120


def test_invalid_override_is_rejected() -> None:
    resolver = ConfigResolver(REPO_ROOT)

    with pytest.raises(OverrideNotAllowedError):
        resolver.resolve_fixture("fixtures/quick_validation.json", cli_overrides={"unsupported": True})


def test_fixture_validation_rejects_invalid_loop_configuration() -> None:
    invalid_fixture = json.loads((REPO_ROOT / "fixtures" / "quick_validation.json").read_text(encoding="utf-8"))
    invalid_fixture["loop"] = True
    invalid_fixture["loop_count"] = 0

    with pytest.raises(SchemaValidationError):
        validate_fixture_data(invalid_fixture, source="tests")
