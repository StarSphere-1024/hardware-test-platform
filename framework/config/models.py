"""Strongly typed configuration models for the first delivery phase."""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any


def to_plain_data(value: Any) -> Any:
    if is_dataclass(value):
        return {
            item.name: to_plain_data(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: to_plain_data(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_plain_data(item) for item in value]
    if isinstance(value, tuple):
        return [to_plain_data(item) for item in value]
    return value


@dataclass(slots=True)
class SerializableModel:
    def to_dict(self) -> dict[str, Any]:
        return to_plain_data(self)


@dataclass(slots=True)
class ProductConfig(SerializableModel):
    sku: str | None = None
    stage: str | None = None
    default_board_profile: str | None = None


@dataclass(slots=True)
class InterfaceBinding(SerializableModel):
    items: list[str] = field(default_factory=list)
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_config(cls, value: Any) -> InterfaceBinding:
        if isinstance(value, list):
            items = [item for item in value if isinstance(item, str)]
            return cls(
                items=items,
            )
        if isinstance(value, dict):
            raw_items = value.get("items")
            items = (
                [item for item in raw_items if isinstance(item, str)]
                if isinstance(raw_items, list)
                else []
            )
            description = value.get("description")
            return cls(
                items=items,
                description=description if isinstance(description, str) else None,
                metadata=dict(value.get("metadata", {}))
                if isinstance(value.get("metadata"), dict)
                else {},
            )
        raise TypeError(f"unsupported interface binding value: {value!r}")


@dataclass(slots=True)
class RuntimeDefaults(SerializableModel):
    default_timeout: int = 60
    default_retry: int = 0
    default_retry_interval: int = 0
    default_resource_lock_quarantine_seconds: float = 5.0


@dataclass(slots=True)
class ObservabilityConfig(SerializableModel):
    report_enabled: bool = True
    dashboard_enabled: bool = False
    dashboard_auto_exit_on_success_seconds: int | None = 3
    dashboard_auto_exit_on_failure_seconds: int | None = None


@dataclass(slots=True)
class GlobalConfig(SerializableModel):
    product: ProductConfig
    runtime: RuntimeDefaults = field(default_factory=RuntimeDefaults)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GlobalConfig:
        product_data = dict(data["product"])
        product = ProductConfig(
            default_board_profile=product_data.get(
                "default_board_profile", product_data.get("board_profile")
            ),
        )
        return cls(
            product=product,
            runtime=RuntimeDefaults(**data.get("runtime", {})),
            observability=ObservabilityConfig(**data.get("observability", {})),
        )


@dataclass(slots=True)
class BoardProfile(SerializableModel):
    profile_name: str
    platform: str
    product: ProductConfig
    supported_cases: list[str] = field(default_factory=list)
    interfaces: dict[str, InterfaceBinding] = field(default_factory=dict)
    capabilities: dict[str, Any] = field(default_factory=dict)
    tools_required: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BoardProfile:
        product_data = dict(data["product"])
        return cls(
            profile_name=data["profile_name"],
            platform=data["platform"],
            product=ProductConfig(
                sku=product_data["sku"],
                stage=product_data["stage"],
            ),
            supported_cases=list(data.get("supported_cases", [])),
            interfaces={
                key: InterfaceBinding.from_config(value)
                for key, value in data.get("interfaces", {}).items()
            },
            capabilities=dict(data.get("capabilities", {})),
            tools_required=list(data.get("tools_required", [])),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(slots=True)
class FunctionInvocationSpec(SerializableModel):
    name: str
    enabled: bool = True
    params: dict[str, Any] = field(default_factory=dict)
    expect: dict[str, Any] | None = None
    timeout: int | None = None
    retry: int | None = None
    retry_interval: int | None = None
    resource_lock_quarantine_seconds: float | None = None
    required_capabilities: list[str] = field(default_factory=list)
    resources: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FunctionInvocationSpec:
        return cls(
            name=data["name"],
            enabled=data.get("enabled", True),
            params=dict(data.get("params", {})),
            expect=dict(data["expect"]) if data.get("expect") is not None else None,
            timeout=data.get("timeout"),
            retry=data.get("retry"),
            retry_interval=data.get("retry_interval"),
            resource_lock_quarantine_seconds=data.get(
                "resource_lock_quarantine_seconds"
            ),
            required_capabilities=list(data.get("required_capabilities", [])),
            resources=list(data.get("resources", [])),
            tags=list(data.get("tags", [])),
        )


@dataclass(slots=True)
class CaseSpec(SerializableModel):
    case_name: str
    module: str
    board_profile: str | None = None
    description: str | None = None
    functions: list[FunctionInvocationSpec] = field(default_factory=list)
    execution: str = "sequential"
    timeout: int | None = None
    retry: int | None = None
    retry_interval: int | None = None
    resource_lock_quarantine_seconds: float | None = None
    stop_on_failure: bool | None = None
    required_interfaces: dict[str, Any] = field(default_factory=dict)
    resources: list[str] = field(default_factory=list)
    precheck: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CaseSpec:
        return cls(
            case_name=data["case_name"],
            module=data["module"],
            board_profile=data.get("board_profile"),
            description=data.get("description"),
            functions=[
                FunctionInvocationSpec.from_dict(item)
                for item in data.get("functions", [])
            ],
            execution=data.get("execution", "sequential"),
            timeout=data.get("timeout"),
            retry=data.get("retry"),
            retry_interval=data.get("retry_interval"),
            resource_lock_quarantine_seconds=data.get(
                "resource_lock_quarantine_seconds"
            ),
            stop_on_failure=data.get("stop_on_failure"),
            required_interfaces=dict(data.get("required_interfaces", {})),
            resources=list(data.get("resources", [])),
            precheck=data.get("precheck", True),
        )


@dataclass(slots=True)
class FixtureSpec(SerializableModel):
    fixture_name: str
    board_profile: str | None = None
    description: str | None = None
    cases: list[str] = field(default_factory=list)
    execution: str = "sequential"
    timeout: int | None = None
    retry: int | None = None
    retry_interval: int | None = None
    resource_lock_quarantine_seconds: float | None = None
    stop_on_failure: bool = False
    loop: bool = False
    loop_count: int | None = None
    loop_interval: int | None = None
    report_enabled: bool | None = None
    sn_required: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FixtureSpec:
        return cls(
            fixture_name=data["fixture_name"],
            board_profile=data.get("board_profile"),
            description=data.get("description"),
            cases=list(data.get("cases", [])),
            execution=data.get("execution", "sequential"),
            timeout=data.get("timeout"),
            retry=data.get("retry"),
            retry_interval=data.get("retry_interval"),
            resource_lock_quarantine_seconds=data.get(
                "resource_lock_quarantine_seconds"
            ),
            stop_on_failure=data.get("stop_on_failure", False),
            loop=data.get("loop", False),
            loop_count=data.get("loop_count"),
            loop_interval=data.get("loop_interval"),
            report_enabled=data.get("report_enabled"),
            sn_required=data.get("sn_required", False),
        )


@dataclass(slots=True)
class ResolvedExecutionConfig(SerializableModel):
    request: dict[str, Any]
    global_config: GlobalConfig
    board_profile: BoardProfile
    fixture: FixtureSpec | None
    cases: list[CaseSpec]
    resolved_runtime: dict[str, Any]
    resolved_interfaces: dict[str, Any]
    capability_requirements: list[str]
    config_sources: dict[str, Any]
