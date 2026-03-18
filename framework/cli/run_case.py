"""CLI entrypoint for case execution."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from framework.config.errors import ConfigError, SchemaValidationError
from framework.execution.fixture_runner import FixtureRunner

from .common import (
    CLIError,
    build_case_resolved_config,
    build_execution_request,
    create_base_parser,
    execute_plan,
    normalize_cli_args,
    payload_exit_code,
    print_payload,
)


def _build_fixture_misuse_hint(args: argparse.Namespace) -> str | None:
    """Return a friendly hint when a fixture config is passed to run_case."""

    config_path = Path(args.config)
    if "fixtures" in config_path.parts:
        return (
            f"detected fixture config '{args.config}', "
            "use: python -m framework.cli.run_fixture --config {args.config}"
        )

    if config_path.suffix.lower() != ".json":
        return None

    source_path = Path(args.workspace_root).resolve() / config_path
    if not source_path.exists():
        return None

    try:
        data = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if isinstance(data, dict) and "fixture_name" in data and "case_name" not in data:
        return (
            f"detected fixture config '{args.config}', "
            "use: python -m framework.cli.run_fixture --config {args.config}"
        )
    return None


def main(
    argv: list[str] | None = None,
    *,
    function_registry: dict[str, Callable[..., Any]] | None = None,
) -> int:
    parser = create_base_parser("Execute a case configuration")
    parser.add_argument("--config", required=True, help="case config path")
    args = parser.parse_args(argv)
    args = normalize_cli_args(args)
    try:
        request = build_execution_request(
            args, target_type="case", target_name=args.config
        )
        resolved_config = build_case_resolved_config(args, request)
        plan = FixtureRunner().build_plan(resolved_config)
        payload = execute_plan(
            resolved_config=resolved_config,
            plan=plan,
            workspace_root=args.workspace_root,
            artifacts_root=args.artifacts_root,
            function_registry=function_registry,
            dashboard_enabled=args.dashboard,
            dashboard_refresh_interval=args.dashboard_refresh,
            dashboard_start_monitor=not args.dashboard_no_monitor,
            dashboard_keep_open=args.dashboard_keep_open,
            verbose_level=1 if args.verbose else 0,
        )
        print_payload(payload)
        return payload_exit_code(payload)
    except ConfigError as error:
        payload = {"error": str(error)}
        if isinstance(error, SchemaValidationError) and error.field_path == "case_name":
            hint = _build_fixture_misuse_hint(args)
            if hint:
                payload["hint"] = hint
        print_payload(payload)
        return 2
    except CLIError as error:
        print_payload(error.payload)
        return error.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
