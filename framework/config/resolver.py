"""Resolve raw configuration assets into a single executable config object."""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

from .errors import OverrideNotAllowedError, ProfileNotSupportedError, TemplateResolutionError
from .loader import ConfigLoader
from .models import BoardProfile, CaseSpec, FixtureSpec, FunctionInvocationSpec, GlobalConfig, ResolvedExecutionConfig

_ALLOWED_OVERRIDES = {
    "board_profile",
    "execution",
    "loop",
    "loop_count",
    "loop_interval",
    "report_enabled",
    "resource_lock_quarantine_seconds",
    "retry",
    "retry_interval",
    "sn_required",
    "stop_on_failure",
    "timeout",
}
_TEMPLATE_PATTERN = re.compile(r"\$\{([^{}]+)\}")


class ConfigResolver:
    def __init__(self, workspace_root: str | Path) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.loader = ConfigLoader(self.workspace_root)

    def resolve_fixture(
        self,
        fixture_path: str | Path,
        *,
        global_config_path: str | Path | None = None,
        board_profile: str | None = None,
        cli_overrides: dict[str, Any] | None = None,
        request: dict[str, Any] | None = None,
    ) -> ResolvedExecutionConfig:
        overrides = self._validate_overrides(cli_overrides)
        global_config, global_source = self.loader.load_global_config(global_config_path)
        fixture, fixture_source = self.loader.load_fixture(fixture_path)
        board_profile_name = overrides.get("board_profile") or board_profile or fixture.board_profile or global_config.product.default_board_profile
        board, board_source = self.loader.load_board_profile(
            profile_name=board_profile_name
        )

        case_sources: dict[str, str] = {}
        raw_cases: list[CaseSpec] = []
        fixture_dir = Path(fixture_source).parent
        for case_ref in fixture.cases:
            case_spec, case_source = self.loader.load_case(case_ref, base_dir=fixture_dir)
            self._assert_case_board_compatible(board.profile_name, fixture, case_spec, case_source)
            self._assert_case_supported(board, case_spec, case_source)
            raw_cases.append(case_spec)
            case_sources[case_spec.case_name] = case_source

        resolved_interfaces = self._build_resolved_interfaces(board)
        context = self._build_template_context(global_config, board, resolved_interfaces)
        resolved_runtime, runtime_sources = self._resolve_fixture_runtime(global_config, fixture, overrides)
        resolved_cases, case_trace = self._resolve_cases(raw_cases, context, fixture, global_config, overrides)
        capability_requirements = self._collect_capability_requirements(resolved_cases)

        return ResolvedExecutionConfig(
            request=request or {"kind": "fixture", "fixture_path": str(fixture_path)},
            global_config=global_config,
            board_profile=board,
            fixture=fixture,
            cases=resolved_cases,
            resolved_runtime=resolved_runtime,
            resolved_interfaces=resolved_interfaces,
            capability_requirements=capability_requirements,
            config_sources={
                "global_config": global_source,
                "board_profile": board_source,
                "fixture": fixture_source,
                "cases": {name: case_sources[name] for name in case_sources},
                "runtime": runtime_sources,
                "case_runtime": case_trace,
            },
        )

    def resolve_case(
        self,
        case_path: str | Path,
        *,
        global_config_path: str | Path | None = None,
        board_profile: str | None = None,
        cli_overrides: dict[str, Any] | None = None,
        request: dict[str, Any] | None = None,
    ) -> ResolvedExecutionConfig:
        overrides = self._validate_overrides(cli_overrides)
        global_config, global_source = self.loader.load_global_config(global_config_path)
        case_spec, case_source = self.loader.load_case(case_path)
        board_profile_name = overrides.get("board_profile") or board_profile or case_spec.board_profile or global_config.product.default_board_profile
        board, board_source = self.loader.load_board_profile(
            profile_name=board_profile_name
        )
        self._assert_case_board_compatible(board.profile_name, None, case_spec, case_source)
        self._assert_case_supported(board, case_spec, case_source)
        resolved_interfaces = self._build_resolved_interfaces(board)
        context = self._build_template_context(global_config, board, resolved_interfaces)
        resolved_cases, case_trace = self._resolve_cases([case_spec], context, None, global_config, overrides)
        resolved_runtime, runtime_sources = self._resolve_case_only_runtime(global_config, case_spec, overrides)
        capability_requirements = self._collect_capability_requirements(resolved_cases)

        return ResolvedExecutionConfig(
            request=request or {"kind": "case", "case_path": str(case_path)},
            global_config=global_config,
            board_profile=board,
            fixture=None,
            cases=resolved_cases,
            resolved_runtime=resolved_runtime,
            resolved_interfaces=resolved_interfaces,
            capability_requirements=capability_requirements,
            config_sources={
                "global_config": global_source,
                "board_profile": board_source,
                "cases": {case_spec.case_name: case_source},
                "runtime": runtime_sources,
                "case_runtime": case_trace,
            },
        )

    def _validate_overrides(self, cli_overrides: dict[str, Any] | None) -> dict[str, Any]:
        overrides = dict(cli_overrides or {})
        unsupported = sorted(set(overrides) - _ALLOWED_OVERRIDES)
        if unsupported:
            raise OverrideNotAllowedError(
                f"unsupported CLI override keys: {', '.join(unsupported)}",
                field_path=unsupported[0],
            )
        return overrides

    def _assert_case_supported(self, board: BoardProfile, case_spec: CaseSpec, case_source: str) -> None:
        if board.supported_cases and case_spec.case_name not in board.supported_cases:
            raise ProfileNotSupportedError(
                f"case '{case_spec.case_name}' is not allowed by board profile '{board.profile_name}'",
                field_path="supported_cases",
                source=case_source,
            )

    def _assert_case_board_compatible(
        self,
        resolved_board_profile: str,
        fixture: FixtureSpec | None,
        case_spec: CaseSpec,
        case_source: str,
    ) -> None:
        if fixture is not None and fixture.board_profile and case_spec.board_profile and fixture.board_profile != case_spec.board_profile:
            raise ProfileNotSupportedError(
                f"case '{case_spec.case_name}' declares board profile '{case_spec.board_profile}' but fixture '{fixture.fixture_name}' declares '{fixture.board_profile}'",
                field_path="board_profile",
                source=case_source,
            )
        if case_spec.board_profile and case_spec.board_profile != resolved_board_profile:
            raise ProfileNotSupportedError(
                f"case '{case_spec.case_name}' declares board profile '{case_spec.board_profile}' but resolved board profile is '{resolved_board_profile}'",
                field_path="board_profile",
                source=case_source,
            )

    def _build_resolved_interfaces(self, board: BoardProfile) -> dict[str, Any]:
        resolved: dict[str, Any] = {}
        for name, binding in board.interfaces.items():
            bound = binding.items[0] if binding.items else None
            resolved[name] = {
                "name": name,
                "bound": bound,
                "declared": list(binding.items),
                "description": binding.description,
                "metadata": copy.deepcopy(binding.metadata),
                "source": "board_profile",
            }
        return resolved

    def _build_template_context(
        self,
        global_config: GlobalConfig,
        board: BoardProfile,
        resolved_interfaces: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "product": board.product.to_dict(),
            "runtime": global_config.runtime.to_dict(),
            "observability": global_config.observability.to_dict(),
            "interfaces": copy.deepcopy(board.to_dict().get("interfaces", {})),
            "capabilities": copy.deepcopy(board.capabilities),
            "metadata": copy.deepcopy(board.metadata),
            "resolved": {"interfaces": copy.deepcopy(resolved_interfaces)},
        }

    def _resolve_fixture_runtime(
        self,
        global_config: GlobalConfig,
        fixture: FixtureSpec,
        overrides: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
        runtime: dict[str, Any] = {}
        sources: dict[str, dict[str, Any]] = {}
        values = {
            "execution": [("default", "sequential"), ("fixture", fixture.execution), ("cli", overrides.get("execution"))],
            "timeout": [
                ("global", global_config.runtime.default_timeout),
                ("fixture", fixture.timeout),
                ("cli", overrides.get("timeout")),
            ],
            "retry": [
                ("global", global_config.runtime.default_retry),
                ("fixture", fixture.retry),
                ("cli", overrides.get("retry")),
            ],
            "retry_interval": [
                ("global", global_config.runtime.default_retry_interval),
                ("fixture", fixture.retry_interval),
                ("cli", overrides.get("retry_interval")),
            ],
            "resource_lock_quarantine_seconds": [
                ("global", global_config.runtime.default_resource_lock_quarantine_seconds),
                ("fixture", fixture.resource_lock_quarantine_seconds),
                ("cli", overrides.get("resource_lock_quarantine_seconds")),
            ],
            "stop_on_failure": [("default", False), ("fixture", fixture.stop_on_failure), ("cli", overrides.get("stop_on_failure"))],
            "loop": [("default", False), ("fixture", fixture.loop), ("cli", overrides.get("loop"))],
            "loop_count": [("default", None), ("fixture", fixture.loop_count), ("cli", overrides.get("loop_count"))],
            "loop_interval": [("default", None), ("fixture", fixture.loop_interval), ("cli", overrides.get("loop_interval"))],
            "report_enabled": [
                ("global", global_config.observability.report_enabled),
                ("fixture", fixture.report_enabled),
                ("cli", overrides.get("report_enabled")),
            ],
            "sn_required": [("default", False), ("fixture", fixture.sn_required), ("cli", overrides.get("sn_required"))],
        }
        for key, chain in values.items():
            runtime[key], sources[key] = self._choose_value(chain)
        return runtime, sources

    def _resolve_case_only_runtime(
        self,
        global_config: GlobalConfig,
        case_spec: CaseSpec,
        overrides: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
        runtime: dict[str, Any] = {}
        sources: dict[str, dict[str, Any]] = {}
        values = {
            "execution": [("default", "sequential"), ("case", case_spec.execution), ("cli", overrides.get("execution"))],
            "timeout": [
                ("global", global_config.runtime.default_timeout),
                ("case", case_spec.timeout),
                ("cli", overrides.get("timeout")),
            ],
            "retry": [
                ("global", global_config.runtime.default_retry),
                ("case", case_spec.retry),
                ("cli", overrides.get("retry")),
            ],
            "retry_interval": [
                ("global", global_config.runtime.default_retry_interval),
                ("case", case_spec.retry_interval),
                ("cli", overrides.get("retry_interval")),
            ],
            "resource_lock_quarantine_seconds": [
                ("global", global_config.runtime.default_resource_lock_quarantine_seconds),
                ("case", case_spec.resource_lock_quarantine_seconds),
                ("cli", overrides.get("resource_lock_quarantine_seconds")),
            ],
            "stop_on_failure": [("default", False), ("case", case_spec.stop_on_failure), ("cli", overrides.get("stop_on_failure"))],
        }
        for key, chain in values.items():
            runtime[key], sources[key] = self._choose_value(chain)
        return runtime, sources

    def _resolve_cases(
        self,
        cases: list[CaseSpec],
        context: dict[str, Any],
        fixture: FixtureSpec | None,
        global_config: GlobalConfig,
        overrides: dict[str, Any],
    ) -> tuple[list[CaseSpec], dict[str, Any]]:
        resolved_cases: list[CaseSpec] = []
        trace: dict[str, Any] = {}
        for case_spec in cases:
            functions: list[FunctionInvocationSpec] = []
            function_trace: dict[str, Any] = {}
            case_timeout, case_timeout_source = self._choose_value(
                [
                    ("global", global_config.runtime.default_timeout),
                    ("fixture", fixture.timeout if fixture else None),
                    ("case", case_spec.timeout),
                    ("cli", overrides.get("timeout")),
                ]
            )
            case_retry, case_retry_source = self._choose_value(
                [
                    ("global", global_config.runtime.default_retry),
                    ("fixture", fixture.retry if fixture else None),
                    ("case", case_spec.retry),
                    ("cli", overrides.get("retry")),
                ]
            )
            case_retry_interval, case_retry_interval_source = self._choose_value(
                [
                    ("global", global_config.runtime.default_retry_interval),
                    ("fixture", fixture.retry_interval if fixture else None),
                    ("case", case_spec.retry_interval),
                    ("cli", overrides.get("retry_interval")),
                ]
            )
            case_resource_lock_quarantine_seconds, case_resource_lock_quarantine_source = self._choose_value(
                [
                    ("global", global_config.runtime.default_resource_lock_quarantine_seconds),
                    ("fixture", fixture.resource_lock_quarantine_seconds if fixture else None),
                    ("case", case_spec.resource_lock_quarantine_seconds),
                    ("cli", overrides.get("resource_lock_quarantine_seconds")),
                ]
            )
            case_execution, case_execution_source = self._choose_value(
                [("default", "sequential"), ("fixture", fixture.execution if fixture else None), ("case", case_spec.execution), ("cli", overrides.get("execution"))]
            )
            case_stop_on_failure, case_stop_on_failure_source = self._choose_value(
                [("default", False), ("fixture", fixture.stop_on_failure if fixture else None), ("case", case_spec.stop_on_failure), ("cli", overrides.get("stop_on_failure"))]
            )
            case_resources, case_resources_template_sources = self._resolve_templates(
                list(case_spec.resources),
                context,
                field_path=f"cases.{case_spec.case_name}.resources",
            )

            for index, function in enumerate(case_spec.functions):
                timeout, timeout_source = self._choose_value(
                    [
                        ("global", global_config.runtime.default_timeout),
                        ("fixture", fixture.timeout if fixture else None),
                        ("case", case_spec.timeout),
                        ("function", function.timeout),
                        ("cli", overrides.get("timeout")),
                    ]
                )
                retry, retry_source = self._choose_value(
                    [
                        ("global", global_config.runtime.default_retry),
                        ("fixture", fixture.retry if fixture else None),
                        ("case", case_spec.retry),
                        ("function", function.retry),
                        ("cli", overrides.get("retry")),
                    ]
                )
                retry_interval, retry_interval_source = self._choose_value(
                    [
                        ("global", global_config.runtime.default_retry_interval),
                        ("fixture", fixture.retry_interval if fixture else None),
                        ("case", case_spec.retry_interval),
                        ("function", function.retry_interval),
                        ("cli", overrides.get("retry_interval")),
                    ]
                )
                resource_lock_quarantine_seconds, resource_lock_quarantine_source = self._choose_value(
                    [
                        ("global", global_config.runtime.default_resource_lock_quarantine_seconds),
                        ("fixture", fixture.resource_lock_quarantine_seconds if fixture else None),
                        ("case", case_spec.resource_lock_quarantine_seconds),
                        ("function", function.resource_lock_quarantine_seconds),
                        ("cli", overrides.get("resource_lock_quarantine_seconds")),
                    ]
                )
                params, template_sources = self._resolve_templates(
                    function.params,
                    context,
                    field_path=f"cases.{case_spec.case_name}.functions[{index}].params",
                )
                function_resources, function_resource_template_sources = self._resolve_templates(
                    list(function.resources),
                    context,
                    field_path=f"cases.{case_spec.case_name}.functions[{index}].resources",
                )
                effective_resources, resource_source = self._resolve_function_resources(
                    case_spec=case_spec,
                    case_resources=case_resources,
                    function=function,
                    function_resources=function_resources,
                    resolved_interfaces=context.get("resolved", {}).get("interfaces", {}),
                )
                functions.append(
                    FunctionInvocationSpec(
                        name=function.name,
                        enabled=function.enabled,
                        params=params,
                        expect=copy.deepcopy(function.expect),
                        timeout=timeout,
                        retry=retry,
                        retry_interval=retry_interval,
                        resource_lock_quarantine_seconds=resource_lock_quarantine_seconds,
                        required_capabilities=list(function.required_capabilities),
                        resources=effective_resources,
                        tags=list(function.tags),
                    )
                )
                function_trace[f"{function.name}#{index}"] = {
                    "timeout": timeout_source,
                    "retry": retry_source,
                    "retry_interval": retry_interval_source,
                    "resource_lock_quarantine_seconds": resource_lock_quarantine_source,
                    "templates": template_sources,
                    "resource_templates": function_resource_template_sources,
                    "resources": {"source": resource_source, "value": copy.deepcopy(effective_resources)},
                }

            resolved_cases.append(
                CaseSpec(
                    case_name=case_spec.case_name,
                    module=case_spec.module,
                    board_profile=case_spec.board_profile,
                    description=case_spec.description,
                    functions=functions,
                    execution=case_execution,
                    timeout=case_timeout,
                    retry=case_retry,
                    retry_interval=case_retry_interval,
                    resource_lock_quarantine_seconds=case_resource_lock_quarantine_seconds,
                    stop_on_failure=case_stop_on_failure,
                    required_interfaces=copy.deepcopy(case_spec.required_interfaces),
                    resources=list(case_resources),
                    precheck=case_spec.precheck,
                )
            )
            trace[case_spec.case_name] = {
                "execution": case_execution_source,
                "timeout": case_timeout_source,
                "retry": case_retry_source,
                "retry_interval": case_retry_interval_source,
                "resource_lock_quarantine_seconds": case_resource_lock_quarantine_source,
                "stop_on_failure": case_stop_on_failure_source,
                "resource_templates": case_resources_template_sources,
                "resources": {"source": "case" if case_resources else "derived", "value": copy.deepcopy(case_resources)},
                "functions": function_trace,
            }
        return resolved_cases, trace

    def _resolve_function_resources(
        self,
        *,
        case_spec: CaseSpec,
        case_resources: list[str],
        function: FunctionInvocationSpec,
        function_resources: list[str],
        resolved_interfaces: dict[str, Any],
    ) -> tuple[list[str], str]:
        if function_resources:
            return self._dedupe_strings(function_resources), "function"
        if case_resources:
            return self._dedupe_strings(case_resources), "case"
        return self._derive_resources(case_spec=case_spec, function=function, resolved_interfaces=resolved_interfaces), "derived"

    def _derive_resources(
        self,
        *,
        case_spec: CaseSpec,
        function: FunctionInvocationSpec,
        resolved_interfaces: dict[str, Any],
    ) -> list[str]:
        resources: list[str] = []
        for interface_name in case_spec.required_interfaces:
            resolved_interface = resolved_interfaces.get(interface_name, {})
            bound = resolved_interface.get("bound")
            if isinstance(bound, str) and bound:
                resources.append(f"interface:{interface_name}:{bound}")
            else:
                resources.append(f"interface:{interface_name}")
        for capability_name in function.required_capabilities:
            resources.append(f"capability:{capability_name}")
        return self._dedupe_strings(resources)

    def _dedupe_strings(self, values: list[Any]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            if not isinstance(value, str):
                continue
            normalized = value.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
        return ordered

    def _resolve_templates(self, value: Any, context: dict[str, Any], *, field_path: str) -> tuple[Any, dict[str, str]]:
        if isinstance(value, dict):
            resolved: dict[str, Any] = {}
            sources: dict[str, str] = {}
            for key, item in value.items():
                next_value, nested_sources = self._resolve_templates(item, context, field_path=f"{field_path}.{key}")
                resolved[key] = next_value
                sources.update(nested_sources)
            return resolved, sources
        if isinstance(value, list):
            resolved_list: list[Any] = []
            sources: dict[str, str] = {}
            for index, item in enumerate(value):
                next_value, nested_sources = self._resolve_templates(item, context, field_path=f"{field_path}[{index}]")
                resolved_list.append(next_value)
                sources.update(nested_sources)
            return resolved_list, sources
        if not isinstance(value, str):
            return value, {}

        matches = list(_TEMPLATE_PATTERN.finditer(value))
        if not matches:
            return value, {}

        if len(matches) == 1 and matches[0].span() == (0, len(value)):
            token = matches[0].group(1).strip()
            return copy.deepcopy(self._lookup_context(token, context, field_path)), {field_path: token}

        result = value
        sources: dict[str, str] = {}
        for match in matches:
            token = match.group(1).strip()
            replacement = self._lookup_context(token, context, field_path)
            if isinstance(replacement, (dict, list)):
                raise TemplateResolutionError(
                    "template expands to a non-scalar value inside a string",
                    field_path=field_path,
                )
            result = result.replace(match.group(0), str(replacement))
            sources[field_path] = token
        return result, sources

    def _lookup_context(self, path: str, context: dict[str, Any], field_path: str) -> Any:
        current: Any = context
        for segment in path.split("."):
            if not isinstance(current, dict) or segment not in current:
                raise TemplateResolutionError(
                    f"unable to resolve template path '{path}'",
                    field_path=field_path,
                )
            current = current[segment]
        return current

    def _collect_capability_requirements(self, cases: list[CaseSpec]) -> list[str]:
        requirements: set[str] = set()
        for case_spec in cases:
            requirements.update(case_spec.required_interfaces.keys())
            for function in case_spec.functions:
                requirements.update(function.required_capabilities)
        return sorted(requirements)

    def _choose_value(self, chain: list[tuple[str, Any]]) -> tuple[Any, dict[str, Any]]:
        selected_source = "default"
        selected_value: Any = None
        for source, value in chain:
            if value is not None:
                selected_source = source
                selected_value = value
        return selected_value, {"source": selected_source, "value": copy.deepcopy(selected_value)}
