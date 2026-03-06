"""CLI entrypoint for fixture execution."""

from __future__ import annotations

from typing import Any, Callable

from framework.execution.fixture_runner import FixtureRunner

from .common import (
    CLIError,
    build_execution_request,
    build_fixture_resolved_config,
    create_base_parser,
    execute_plan,
    payload_exit_code,
    print_payload,
)


def main(argv: list[str] | None = None, *, function_registry: dict[str, Callable[..., Any]] | None = None) -> int:
    parser = create_base_parser("Execute a fixture configuration")
    parser.add_argument("--config", required=True, help="fixture config path")
    args = parser.parse_args(argv)
    try:
        request = build_execution_request(args, target_type="fixture", target_name=args.config)
        resolved_config = build_fixture_resolved_config(args, request)
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
        )
        print_payload(payload)
        return payload_exit_code(payload)
    except CLIError as error:
        print_payload(error.payload)
        return error.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
