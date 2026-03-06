"""Execution boundary for a single function task."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime, timezone
import inspect
from typing import Any, Callable

from framework.domain.execution import ExecutionContext, ExecutionTask
from framework.domain.results import ExecutionResult, ResultStatus

from .errors import FunctionNotRegisteredError, TaskExecutionError


class FunctionExecutor:
    def __init__(self, function_registry: dict[str, Callable[..., Any]] | None = None) -> None:
        self.function_registry = dict(function_registry or {})

    def register(self, name: str, function: Callable[..., Any]) -> None:
        self.function_registry[name] = function

    def execute(self, task: ExecutionTask, context: ExecutionContext) -> ExecutionResult:
        if task.task_type != "function":
            raise TaskExecutionError(f"unsupported task type for FunctionExecutor: {task.task_type}")

        function_name = task.payload.get("function_name") or task.name
        params = task.payload.get("params", {})
        if not isinstance(params, dict):
            raise TaskExecutionError(f"function params must be a mapping: {function_name}")

        if function_name not in self.function_registry:
            raise FunctionNotRegisteredError(f"function '{function_name}' is not registered")

        started_at = datetime.now(timezone.utc)
        started_perf = time.perf_counter()
        callable_obj = self.function_registry[function_name]

        try:
            raw_result = self._invoke(callable_obj, params, task.timeout, context)
            status, code, message, details, metrics = self._normalize_result(raw_result)
        except FutureTimeoutError:
            finished_at = datetime.now(timezone.utc)
            return ExecutionResult(
                task_id=task.task_id,
                task_type=task.task_type,
                name=task.name,
                status=ResultStatus.TIMEOUT,
                code=1,
                message=f"function '{function_name}' timed out after {task.timeout}s",
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=int((time.perf_counter() - started_perf) * 1000),
                details={"params": dict(params)},
            )
        except Exception as error:
            finished_at = datetime.now(timezone.utc)
            return ExecutionResult(
                task_id=task.task_id,
                task_type=task.task_type,
                name=task.name,
                status=ResultStatus.FAILED,
                code=-1,
                message=str(error),
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=int((time.perf_counter() - started_perf) * 1000),
                details={"params": dict(params)},
            )

        finished_at = datetime.now(timezone.utc)
        return ExecutionResult(
            task_id=task.task_id,
            task_type=task.task_type,
            name=task.name,
            status=status,
            code=code,
            message=message,
            details=details,
            metrics=metrics,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=int((time.perf_counter() - started_perf) * 1000),
        )

    def _invoke(
        self,
        callable_obj: Callable[..., Any],
        params: dict[str, Any],
        timeout: int | None,
        context: ExecutionContext,
    ) -> Any:
        invocation_params = self._build_invocation_params(callable_obj, params, context)
        if timeout is None:
            return callable_obj(**invocation_params)

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(callable_obj, **invocation_params)
            return future.result(timeout=timeout)

    def _build_invocation_params(
        self,
        callable_obj: Callable[..., Any],
        params: dict[str, Any],
        context: ExecutionContext,
    ) -> dict[str, Any]:
        invocation_params = dict(params)
        try:
            signature = inspect.signature(callable_obj)
        except (TypeError, ValueError):
            return invocation_params

        if "execution_context" in signature.parameters and "execution_context" not in invocation_params:
            invocation_params["execution_context"] = context
        if "capability_registry" in signature.parameters and "capability_registry" not in invocation_params:
            invocation_params["capability_registry"] = context.capability_registry
        if "adapter_registry" in signature.parameters and "adapter_registry" not in invocation_params:
            invocation_params["adapter_registry"] = context.adapter_registry
        return invocation_params

    def _normalize_result(
        self,
        raw_result: Any,
    ) -> tuple[ResultStatus, int | None, str | None, dict[str, Any], dict[str, float | int]]:
        if raw_result is None:
            return ResultStatus.PASSED, 0, "success", {}, {}

        if isinstance(raw_result, bool):
            return (
                ResultStatus.PASSED if raw_result else ResultStatus.FAILED,
                0 if raw_result else -1,
                "success" if raw_result else "function returned false",
                {},
                {},
            )

        if isinstance(raw_result, dict):
            raw_status = raw_result.get("status")
            code = raw_result.get("code")
            message = raw_result.get("message")
            details = dict(raw_result.get("details", {}))
            metrics = dict(raw_result.get("metrics", {}))

            if raw_status is not None:
                status = ResultStatus(str(raw_status))
            elif code is not None:
                status = ResultStatus.PASSED if int(code) == 0 else ResultStatus.FAILED
            else:
                status = ResultStatus.PASSED

            if message is None:
                message = "success" if status == ResultStatus.PASSED else "function failed"
            return status, code, message, details, metrics

        return ResultStatus.PASSED, 0, "success", {"result": raw_result}, {}
