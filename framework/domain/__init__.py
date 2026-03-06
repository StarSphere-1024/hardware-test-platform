"""Domain contracts used by configuration, execution and observability layers."""

from .events import EventRecord, EventStatus, EventType, ExecutionEvent
from .execution import ArtifactDirectories, ExecutionContext, ExecutionPlan, ExecutionTask, RetryPolicy
from .requests import ExecutionRequest
from .results import DashboardSnapshot, ExecutionResult, ReportArtifact, ResultSnapshot, ResultStatus
from .specs import CaseSpec, FixtureSpec, FunctionInvocationSpec

__all__ = [
    "ArtifactDirectories",
    "CaseSpec",
    "DashboardSnapshot",
    "EventRecord",
    "EventStatus",
    "EventType",
    "ExecutionContext",
    "ExecutionEvent",
    "ExecutionPlan",
    "ExecutionRequest",
    "ExecutionResult",
    "ExecutionTask",
    "FixtureSpec",
    "FunctionInvocationSpec",
    "ReportArtifact",
    "ResultSnapshot",
    "ResultStatus",
    "RetryPolicy",
]
