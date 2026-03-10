"""Shared CLI helpers for building requests and executing plans."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import sys
import threading
import uuid
from pathlib import Path
from typing import Any, Callable

from framework.config.loader import ConfigLoader
from framework.config.models import CaseSpec, FunctionInvocationSpec, ResolvedExecutionConfig
from framework.config.resolver import ConfigResolver
from framework.domain.execution import ArtifactDirectories, ExecutionContext, ExecutionPlan, ExecutionTask, RetryPolicy
from framework.domain.requests import ExecutionRequest
from framework.execution.fixture_runner import FixtureRunner
from framework.execution.function_executor import FunctionExecutor
from framework.execution.scheduler import Scheduler
from framework.observability import EventStore, ExecutionObserver, ReportGenerator, ResultStore, UnifiedLogger
from framework.platform.registry import PlatformRegistry


class CLIError(Exception):
    def __init__(self, message: str, *, exit_code: int = 2, payload: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.payload = dict(payload or {"error": message})


def _looks_like_workspace_root(candidate: Path) -> bool:
    return (
        (candidate / "framework").is_dir()
        and (candidate / "config").is_dir()
        and ((candidate / "cases").is_dir() or (candidate / "fixtures").is_dir())
    )


def _iter_workspace_root_candidates(args: argparse.Namespace) -> list[Path]:
    origins: list[Path] = [Path.cwd().resolve()]
    for attr_name in ("config", "global_config"):
        value = getattr(args, attr_name, None)
        if not value:
            continue
        candidate = Path(value)
        if candidate.is_absolute():
            origins.append((candidate if candidate.is_dir() else candidate.parent).resolve())

    seen: set[Path] = set()
    ordered: list[Path] = []
    for origin in origins:
        for candidate in (origin, *origin.parents):
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            ordered.append(resolved)
    return ordered


def _root_matches_cli_paths(candidate: Path, args: argparse.Namespace) -> bool:
    for attr_name in ("config", "global_config"):
        value = getattr(args, attr_name, None)
        if not value:
            continue
        path = Path(value)
        if path.is_absolute():
            if not path.exists():
                return False
            continue
        cwd_candidate = (Path.cwd() / path).resolve()
        workspace_candidate = (candidate / path).resolve()
        if cwd_candidate.exists() or workspace_candidate.exists():
            continue
        return False
    return True


def resolve_workspace_root(args: argparse.Namespace) -> Path:
    explicit_root = getattr(args, "workspace_root", None)
    if explicit_root not in (None, ""):
        return Path(explicit_root).resolve()

    matched_workspaces: list[Path] = []
    for candidate in _iter_workspace_root_candidates(args):
        if not _looks_like_workspace_root(candidate):
            continue
        matched_workspaces.append(candidate)
        if _root_matches_cli_paths(candidate, args):
            return candidate

    if matched_workspaces:
        return matched_workspaces[0]
    return Path.cwd().resolve()


def _normalize_path_arg(value: str | None, *, workspace_root: Path) -> str | None:
    if not value:
        return value
    candidate = Path(value)
    if candidate.is_absolute():
        return str(candidate.resolve())

    cwd_candidate = (Path.cwd() / candidate).resolve()
    workspace_candidate = (workspace_root / candidate).resolve()
    if cwd_candidate.exists() and not workspace_candidate.exists():
        return str(cwd_candidate)
    return value


def normalize_cli_args(args: argparse.Namespace) -> argparse.Namespace:
    workspace_root = resolve_workspace_root(args)
    args.workspace_root = str(workspace_root)
    if hasattr(args, "config"):
        args.config = _normalize_path_arg(getattr(args, "config", None), workspace_root=workspace_root)
    args.global_config = _normalize_path_arg(getattr(args, "global_config", None), workspace_root=workspace_root)
    return args


def create_base_parser(description: str, *, include_board_profile: bool = False) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--request-id", default=None, help="explicit request id used for logs/tmp/reports correlation")
    parser.add_argument("--workspace-root", default=None, help="workspace root used for config resolution; auto-detected when omitted")
    parser.add_argument("--artifacts-root", default=None, help="output root for logs/tmp/reports")
    parser.add_argument("--global-config", default=None, help="override global config path")
    if include_board_profile:
        parser.add_argument("--board-profile", default=None, help="explicit board profile name")
    parser.add_argument("--sn", default=None, help="serial number")
    parser.add_argument("--operator", default=None, help="operator name")
    parser.add_argument("--trigger-source", default="cli", help="request trigger source")
    parser.add_argument("--timeout", type=int, default=None, help="override timeout seconds")
    parser.add_argument("--retry", type=int, default=None, help="override retry count")
    parser.add_argument("--retry-interval", type=int, default=None, help="override retry interval seconds")
    parser.add_argument("--execution", choices=["sequential", "parallel"], default=None, help="override execution mode")
    parser.add_argument("--stop-on-failure", action="store_true", help="stop on first failure")
    parser.add_argument("--report-enabled", dest="report_enabled", action="store_true", default=None, help="force report generation")
    parser.add_argument("--no-report", dest="report_enabled", action="store_false", help="disable report generation")
    parser.add_argument("--dashboard", action="store_true", help="attach terminal dashboard during execution")
    parser.add_argument("--dashboard-refresh", type=float, default=1.0, help="dashboard refresh interval in seconds")
    parser.add_argument("--dashboard-no-monitor", action="store_true", help="disable system monitoring in attached dashboard")
    parser.add_argument("--dashboard-keep-open", action="store_true", help="keep dashboard open after execution until manual quit")
    return parser


def cli_overrides_from_args(args: argparse.Namespace) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for key in ("timeout", "retry", "retry_interval", "execution", "report_enabled"):
        value = getattr(args, key)
        if value is not None:
            overrides[key] = value
    if args.stop_on_failure:
        overrides["stop_on_failure"] = True
    return overrides


def build_execution_request(args: argparse.Namespace, *, target_type: str, target_name: str) -> ExecutionRequest:
    return ExecutionRequest(
        request_id=args.request_id or f"req-{uuid.uuid4().hex[:12]}",
        target_type=target_type,
        target_name=target_name,
        cli_overrides=cli_overrides_from_args(args),
        board_profile=getattr(args, "board_profile", None),
        sn=args.sn,
        operator=args.operator,
        trigger_source=args.trigger_source,
    )


def build_fixture_resolved_config(args: argparse.Namespace, request: ExecutionRequest) -> ResolvedExecutionConfig:
    resolver = ConfigResolver(Path(args.workspace_root).resolve())
    return resolver.resolve_fixture(
        args.config,
        global_config_path=args.global_config,
        board_profile=getattr(args, "board_profile", None),
        cli_overrides=request.cli_overrides,
        request=request.to_dict(),
    )


def build_case_resolved_config(args: argparse.Namespace, request: ExecutionRequest) -> ResolvedExecutionConfig:
    resolver = ConfigResolver(Path(args.workspace_root).resolve())
    return resolver.resolve_case(
        args.config,
        global_config_path=args.global_config,
        board_profile=getattr(args, "board_profile", None),
        cli_overrides=request.cli_overrides,
        request=request.to_dict(),
    )


def build_function_resolved_config(
    args: argparse.Namespace,
    request: ExecutionRequest,
    *,
    function_name: str,
    params: dict[str, Any],
) -> ResolvedExecutionConfig:
    workspace_root = Path(args.workspace_root).resolve()
    loader = ConfigLoader(workspace_root)
    global_config, global_source = loader.load_global_config(args.global_config)
    board_profile_name = getattr(args, "board_profile", None) or global_config.product.default_board_profile
    board_profile, board_source = loader.load_board_profile(profile_name=board_profile_name)

    timeout = args.timeout if args.timeout is not None else global_config.runtime.default_timeout
    retry = args.retry if args.retry is not None else global_config.runtime.default_retry
    retry_interval = args.retry_interval if args.retry_interval is not None else global_config.runtime.default_retry_interval
    report_enabled = args.report_enabled if args.report_enabled is not None else global_config.observability.report_enabled

    function_spec = FunctionInvocationSpec(
        name=function_name,
        params=params,
        timeout=timeout,
        retry=retry,
        retry_interval=retry_interval,
    )
    case_spec = CaseSpec(
        case_name=f"{function_name}_case",
        module="adhoc",
        functions=[function_spec],
        execution="sequential",
        timeout=timeout,
        retry=retry,
        retry_interval=retry_interval,
        stop_on_failure=True,
        precheck=False,
    )
    resolved_interfaces = {
        name: {"primary": candidates[0] if candidates else None, "candidates": list(candidates)}
        for name, candidates in board_profile.interfaces.items()
    }
    return ResolvedExecutionConfig(
        request=request.to_dict(),
        global_config=global_config,
        board_profile=board_profile,
        fixture=None,
        cases=[case_spec],
        resolved_runtime={
            "execution": "sequential",
            "timeout": timeout,
            "retry": retry,
            "retry_interval": retry_interval,
            "stop_on_failure": True,
            "report_enabled": report_enabled,
        },
        resolved_interfaces=resolved_interfaces,
        capability_requirements=[],
        config_sources={
            "global_config": global_source,
            "board_profile": board_source,
            "runtime": {
                "timeout": {"source": "cli" if args.timeout is not None else "global", "value": timeout},
                "retry": {"source": "cli" if args.retry is not None else "global", "value": retry},
                "retry_interval": {"source": "cli" if args.retry_interval is not None else "global", "value": retry_interval},
            },
        },
    )


def build_function_plan(resolved_config: ResolvedExecutionConfig, *, function_name: str, params: dict[str, Any]) -> ExecutionPlan:
    runtime = resolved_config.resolved_runtime
    root_task = ExecutionTask(
        task_id=f"function.{function_name}",
        task_type="function",
        name=function_name,
        execution_mode="sequential",
        timeout=runtime.get("timeout"),
        retry_policy=RetryPolicy(
            max_retries=runtime.get("retry", 0),
            interval_seconds=runtime.get("retry_interval", 0),
        ),
        payload={"function_name": function_name, "params": params},
    )
    return ExecutionPlan(
        plan_id=f"plan.{function_name}",
        root_task=root_task,
        tasks=[root_task],
        execution_policy={"mode": "sequential", "timeout": root_task.timeout},
    )


def load_callable(callable_path: str) -> tuple[str, Callable[..., Any]]:
    if ":" in callable_path:
        module_name, attr_name = callable_path.split(":", 1)
    elif "." in callable_path:
        module_name, attr_name = callable_path.rsplit(".", 1)
    else:
        raise CLIError("callable path must be in module:function format", exit_code=2)
    module = importlib.import_module(module_name)
    function = getattr(module, attr_name, None)
    if function is None or not callable(function):
        raise CLIError(f"callable not found: {callable_path}", exit_code=2)
    return attr_name, function


def discover_workspace_functions(workspace_root: str | Path, function_names: set[str]) -> dict[str, Callable[..., Any]]:
    registry: dict[str, Callable[..., Any]] = {}
    functions_root = Path(workspace_root).resolve() / "functions"
    if not functions_root.exists():
        return registry

    for function_name in function_names:
        matches = sorted(functions_root.rglob(f"{function_name}.py"))
        if not matches:
            continue
        module_path = matches[0]
        module_name = f"workspace_function_{function_name}_{uuid.uuid4().hex[:8]}"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        candidate = getattr(module, function_name, None)
        if callable(candidate):
            registry[function_name] = candidate
    return registry


def parse_json_params(raw: str | None) -> dict[str, Any]:
    if raw in (None, "", "null"):
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise CLIError(f"invalid JSON params: {error.msg}", exit_code=2) from error
    if not isinstance(payload, dict):
        raise CLIError("--params must decode to an object", exit_code=2)
    return payload


def execute_plan(
    *,
    resolved_config: ResolvedExecutionConfig,
    plan: ExecutionPlan,
    workspace_root: str | Path,
    artifacts_root: str | Path | None,
    function_registry: dict[str, Callable[..., Any]] | None = None,
    dashboard_enabled: bool = False,
    dashboard_refresh_interval: float = 1.0,
    dashboard_start_monitor: bool = True,
    dashboard_keep_open: bool = False,
) -> dict[str, Any]:
    workspace = Path(workspace_root).resolve()
    outputs_root = Path(artifacts_root).resolve() if artifacts_root else workspace
    logs_dir = outputs_root / "logs"
    tmp_dir = outputs_root / "tmp"
    reports_dir = outputs_root / "reports"
    logs_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    adapters, capabilities = PlatformRegistry().create_runtime_registries(resolved_config.board_profile)
    observer = ExecutionObserver(
        resolved_config=resolved_config,
        result_store=ResultStore(tmp_dir),
        event_store=EventStore(logs_dir / "events"),
        report_generator=ReportGenerator(reports_dir),
        logger=UnifiedLogger(logs_dir),
    )
    context = ExecutionContext(
        request_id=str(resolved_config.request["request_id"]),
        plan_id=plan.plan_id,
        resolved_config=resolved_config,
        adapter_registry=adapters,
        capability_registry=capabilities,
        runtime_state={"observability": observer},
        artifacts_dir=ArtifactDirectories(logs_dir=logs_dir, tmp_dir=tmp_dir, reports_dir=reports_dir),
    )

    registry = dict(function_registry or {})
    missing_function_names = {
        task.payload.get("function_name")
        for task in plan.tasks
        if task.task_type == "function" and task.payload.get("function_name") not in registry
    }
    registry.update(discover_workspace_functions(workspace, {name for name in missing_function_names if isinstance(name, str)}))

    root_result, dashboard_meta = _run_scheduler(
        registry=registry,
        plan=plan,
        context=context,
        workspace_root=workspace,
        outputs_root=outputs_root,
        dashboard_enabled=dashboard_enabled,
        dashboard_refresh_interval=dashboard_refresh_interval,
        dashboard_start_monitor=dashboard_start_monitor,
        dashboard_keep_open=dashboard_keep_open,
    )
    payload = {
        "request_id": context.request_id,
        "plan_id": plan.plan_id,
        "status": str(root_result.status.value if hasattr(root_result.status, "value") else root_result.status),
        "result": root_result.to_dict(),
        "snapshot_path": str(observer.result_store.snapshot_path(context.request_id)),
        "event_log_path": str(observer.event_store.event_log_path(context.request_id)),
        "report_paths": [artifact.uri for artifact in root_result.artifacts],
        "log_path": str(logs_dir / f"{context.request_id}.log"),
    }
    if dashboard_meta is not None:
        payload["dashboard"] = dashboard_meta
    return payload


def _run_scheduler(
    *,
    registry: dict[str, Callable[..., Any]],
    plan: ExecutionPlan,
    context: ExecutionContext,
    workspace_root: Path,
    outputs_root: Path,
    dashboard_enabled: bool,
    dashboard_refresh_interval: float,
    dashboard_start_monitor: bool,
    dashboard_keep_open: bool,
):
    scheduler = Scheduler(FunctionExecutor(registry))
    if not dashboard_enabled:
        return scheduler.run(plan, context), None

    result_box: dict[str, Any] = {}
    error_box: dict[str, BaseException] = {}

    def _worker() -> None:
        try:
            result_box["result"] = scheduler.run(plan, context)
        except BaseException as error:  # pragma: no cover - surfaced after join
            error_box["error"] = error

    worker = threading.Thread(target=_worker, name=f"dashboard-exec-{context.request_id}", daemon=True)
    worker.start()
    observability_config = context.resolved_config.global_config.observability
    dashboard_meta = _attach_dashboard(
        request_id=context.request_id,
        fixture_name=str(context.resolved_config.fixture.fixture_name if context.resolved_config.fixture else ""),
        workspace_root=workspace_root,
        outputs_root=outputs_root,
        refresh_interval=dashboard_refresh_interval,
        start_monitor=dashboard_start_monitor,
        keep_open=dashboard_keep_open,
        success_exit_linger_seconds=observability_config.dashboard_auto_exit_on_success_seconds,
        failure_exit_linger_seconds=observability_config.dashboard_auto_exit_on_failure_seconds,
    )
    worker.join()

    error = error_box.get("error")
    if error is not None:
        raise error
    return result_box["result"], dashboard_meta


def _attach_dashboard(
    *,
    request_id: str,
    fixture_name: str,
    workspace_root: Path,
    outputs_root: Path,
    refresh_interval: float,
    start_monitor: bool,
    keep_open: bool,
    success_exit_linger_seconds: float | None,
    failure_exit_linger_seconds: float | None,
) -> dict[str, Any]:
    metadata = {
        "enabled": True,
        "request_id": request_id,
        "fixture": fixture_name,
        "mode": "attached",
        "artifacts_root": str(outputs_root),
        "attached": False,
    }
    if keep_open:
        success_exit_linger_seconds = None
        failure_exit_linger_seconds = None
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        metadata["reason"] = "non-interactive terminal"
        return metadata

    try:
        from framework.dashboard import run_dashboard

        run_dashboard(
            workspace_root=workspace_root,
            artifacts_root=outputs_root,
            fixture_name=fixture_name,
            request_id=request_id,
            refresh_interval=refresh_interval,
            start_monitor=start_monitor,
            auto_exit=success_exit_linger_seconds is not None or failure_exit_linger_seconds is not None,
            success_exit_linger_seconds=success_exit_linger_seconds,
            failure_exit_linger_seconds=failure_exit_linger_seconds,
        )
        metadata["attached"] = True
        metadata["auto_exit"] = success_exit_linger_seconds is not None or failure_exit_linger_seconds is not None
        metadata["success_exit_linger_seconds"] = success_exit_linger_seconds
        metadata["failure_exit_linger_seconds"] = failure_exit_linger_seconds
    except Exception as error:  # pragma: no cover - dashboard should not fail execution
        metadata["reason"] = str(error)
    return metadata


def print_payload(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def payload_exit_code(payload: dict[str, Any]) -> int:
    return 0 if payload.get("status") == "passed" else 1
