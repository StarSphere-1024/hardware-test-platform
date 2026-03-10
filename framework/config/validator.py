"""Schema validation helpers for configuration assets."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .errors import SchemaValidationError

_EXECUTION_VALUES = {"sequential", "parallel"}


def _ensure_mapping(value: Any, *, field_path: str, source: str | None) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SchemaValidationError("expected object", field_path=field_path, source=source)
    return value


def _require_field(mapping: Mapping[str, Any], key: str, *, field_path: str, source: str | None) -> Any:
    if key not in mapping:
        raise SchemaValidationError("missing required field", field_path=field_path, source=source)
    return mapping[key]


def _require_string(mapping: Mapping[str, Any], key: str, *, field_path: str, source: str | None) -> str:
    value = _require_field(mapping, key, field_path=field_path, source=source)
    if not isinstance(value, str) or not value.strip():
        raise SchemaValidationError("expected non-empty string", field_path=field_path, source=source)
    return value


def _optional_string(mapping: Mapping[str, Any], key: str, *, field_path: str, source: str | None) -> None:
    value = mapping.get(key)
    if value is not None and not isinstance(value, str):
        raise SchemaValidationError("expected string", field_path=field_path, source=source)


def _optional_bool(mapping: Mapping[str, Any], key: str, *, field_path: str, source: str | None) -> None:
    value = mapping.get(key)
    if value is not None and not isinstance(value, bool):
        raise SchemaValidationError("expected bool", field_path=field_path, source=source)


def _optional_int(mapping: Mapping[str, Any], key: str, *, field_path: str, source: str | None) -> None:
    value = mapping.get(key)
    if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
        raise SchemaValidationError("expected int", field_path=field_path, source=source)


def _optional_nullable_int(mapping: Mapping[str, Any], key: str, *, field_path: str, source: str | None) -> None:
    value = mapping.get(key)
    if value is None:
        return
    if not isinstance(value, int) or isinstance(value, bool):
        raise SchemaValidationError("expected int or null", field_path=field_path, source=source)


def _optional_list_of_strings(mapping: Mapping[str, Any], key: str, *, field_path: str, source: str | None) -> None:
    value = mapping.get(key)
    if value is None:
        return
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise SchemaValidationError("expected list of strings", field_path=field_path, source=source)


def _validate_execution(mapping: Mapping[str, Any], key: str, *, field_path: str, source: str | None) -> None:
    value = mapping.get(key)
    if value is not None and value not in _EXECUTION_VALUES:
        raise SchemaValidationError(
            f"expected one of {sorted(_EXECUTION_VALUES)}",
            field_path=field_path,
            source=source,
        )


def validate_global_config_data(data: Any, *, source: str | None = None) -> None:
    root = _ensure_mapping(data, field_path="global_config", source=source)
    product = _ensure_mapping(_require_field(root, "product", field_path="product", source=source), field_path="product", source=source)
    _optional_string(product, "default_board_profile", field_path="product.default_board_profile", source=source)
    _optional_string(product, "board_profile", field_path="product.board_profile", source=source)

    runtime = root.get("runtime")
    if runtime is not None:
        runtime_mapping = _ensure_mapping(runtime, field_path="runtime", source=source)
        _optional_int(runtime_mapping, "default_timeout", field_path="runtime.default_timeout", source=source)
        _optional_int(runtime_mapping, "default_retry", field_path="runtime.default_retry", source=source)
        _optional_int(runtime_mapping, "default_retry_interval", field_path="runtime.default_retry_interval", source=source)

    observability = root.get("observability")
    if observability is not None:
        observability_mapping = _ensure_mapping(observability, field_path="observability", source=source)
        _optional_bool(observability_mapping, "report_enabled", field_path="observability.report_enabled", source=source)
        _optional_bool(observability_mapping, "dashboard_enabled", field_path="observability.dashboard_enabled", source=source)
        _optional_nullable_int(
            observability_mapping,
            "dashboard_auto_exit_on_success_seconds",
            field_path="observability.dashboard_auto_exit_on_success_seconds",
            source=source,
        )
        _optional_nullable_int(
            observability_mapping,
            "dashboard_auto_exit_on_failure_seconds",
            field_path="observability.dashboard_auto_exit_on_failure_seconds",
            source=source,
        )


def validate_board_profile_data(data: Any, *, source: str | None = None) -> None:
    root = _ensure_mapping(data, field_path="board_profile", source=source)
    _require_string(root, "profile_name", field_path="profile_name", source=source)
    _require_string(root, "platform", field_path="platform", source=source)
    product = _ensure_mapping(_require_field(root, "product", field_path="product", source=source), field_path="product", source=source)
    _require_string(product, "sku", field_path="product.sku", source=source)
    _require_string(product, "stage", field_path="product.stage", source=source)
    _optional_list_of_strings(root, "supported_cases", field_path="supported_cases", source=source)
    _optional_list_of_strings(root, "tools_required", field_path="tools_required", source=source)

    interfaces = root.get("interfaces")
    if interfaces is not None:
        interfaces_mapping = _ensure_mapping(interfaces, field_path="interfaces", source=source)
        for name, candidates in interfaces_mapping.items():
            if not isinstance(name, str):
                raise SchemaValidationError("expected string key", field_path="interfaces", source=source)
            if not isinstance(candidates, list) or any(not isinstance(item, str) for item in candidates):
                raise SchemaValidationError("expected list of strings", field_path=f"interfaces.{name}", source=source)

    for key in ("capabilities", "metadata"):
        value = root.get(key)
        if value is not None:
            _ensure_mapping(value, field_path=key, source=source)


def validate_case_data(data: Any, *, source: str | None = None) -> None:
    root = _ensure_mapping(data, field_path="case", source=source)
    _require_string(root, "case_name", field_path="case_name", source=source)
    _require_string(root, "module", field_path="module", source=source)
    _optional_string(root, "board_profile", field_path="board_profile", source=source)
    _validate_execution(root, "execution", field_path="execution", source=source)
    _optional_string(root, "description", field_path="description", source=source)

    for key in ("timeout", "retry", "retry_interval"):
        _optional_int(root, key, field_path=key, source=source)
    for key in ("stop_on_failure", "precheck"):
        _optional_bool(root, key, field_path=key, source=source)

    functions = _require_field(root, "functions", field_path="functions", source=source)
    if not isinstance(functions, list) or not functions:
        raise SchemaValidationError("expected non-empty list", field_path="functions", source=source)
    for index, item in enumerate(functions):
        item_path = f"functions[{index}]"
        function_mapping = _ensure_mapping(item, field_path=item_path, source=source)
        _require_string(function_mapping, "name", field_path=f"{item_path}.name", source=source)
        _optional_bool(function_mapping, "enabled", field_path=f"{item_path}.enabled", source=source)
        for key in ("timeout", "retry", "retry_interval"):
            _optional_int(function_mapping, key, field_path=f"{item_path}.{key}", source=source)
        for key in ("params", "expect"):
            value = function_mapping.get(key)
            if value is not None:
                _ensure_mapping(value, field_path=f"{item_path}.{key}", source=source)
        _optional_list_of_strings(
            function_mapping,
            "required_capabilities",
            field_path=f"{item_path}.required_capabilities",
            source=source,
        )
        _optional_list_of_strings(function_mapping, "tags", field_path=f"{item_path}.tags", source=source)

    required_interfaces = root.get("required_interfaces")
    if required_interfaces is not None:
        _ensure_mapping(required_interfaces, field_path="required_interfaces", source=source)


def validate_fixture_data(data: Any, *, source: str | None = None) -> None:
    root = _ensure_mapping(data, field_path="fixture", source=source)
    _require_string(root, "fixture_name", field_path="fixture_name", source=source)
    _optional_string(root, "board_profile", field_path="board_profile", source=source)
    _validate_execution(root, "execution", field_path="execution", source=source)
    _optional_string(root, "description", field_path="description", source=source)

    cases = _require_field(root, "cases", field_path="cases", source=source)
    if not isinstance(cases, list) or not cases or any(not isinstance(item, str) or not item for item in cases):
        raise SchemaValidationError("expected non-empty list of case references", field_path="cases", source=source)

    for key in ("timeout", "retry", "retry_interval", "loop_count", "loop_interval"):
        _optional_int(root, key, field_path=key, source=source)
    for key in ("stop_on_failure", "loop", "report_enabled", "sn_required"):
        _optional_bool(root, key, field_path=key, source=source)

    if root.get("loop") and not root.get("loop_count"):
        raise SchemaValidationError(
            "loop_count must be greater than 0 when loop=true",
            field_path="loop_count",
            source=source,
        )
