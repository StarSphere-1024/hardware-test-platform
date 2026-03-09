"""CLI entrypoint for single function execution."""

from __future__ import annotations

from typing import Any, Callable

from .common import (
    CLIError,
    build_execution_request,
    build_function_plan,
    build_function_resolved_config,
    create_base_parser,
    execute_plan,
    load_callable,
    parse_json_params,
    payload_exit_code,
    print_payload,
)


def main(argv: list[str] | None = None, *, function_registry: dict[str, Callable[..., Any]] | None = None) -> int:
    parser = create_base_parser("Execute a single function callable", include_board_profile=True)
    parser.add_argument("--callable", required=True, help="python callable path in module:function format")
    parser.add_argument("--params", default="{}", help="JSON object params for callable")
    args = parser.parse_args(argv)
    try:
        params = parse_json_params(args.params)
        function_name, callable_obj = load_callable(args.callable)
        registry = dict(function_registry or {})
        registry[function_name] = callable_obj
        request = build_execution_request(args, target_type="function", target_name=args.callable)
        resolved_config = build_function_resolved_config(args, request, function_name=function_name, params=params)
        plan = build_function_plan(resolved_config, function_name=function_name, params=params)
        payload = execute_plan(
            resolved_config=resolved_config,
            plan=plan,
            workspace_root=args.workspace_root,
            artifacts_root=args.artifacts_root,
            function_registry=registry,
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
