"""Execution boundary for a single function task."""

from __future__ import annotations

import inspect
import threading
import time
from datetime import datetime, timezone
from queue import Queue
from typing import Any, Callable

from concurrent.futures import TimeoutError as FutureTimeoutError

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
            status, code, message, details = self._apply_expectations(
                task.payload.get("expect"),
                status=status,
                code=code,
                message=message,
                details=details,
                metrics=metrics,
            )
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

        result_queue: Queue[tuple[str, Any]] = Queue(maxsize=1)

        def runner() -> None:
            try:
                result_queue.put(("result", callable_obj(**invocation_params)))
            except Exception as error:  # noqa: BLE001
                result_queue.put(("error", error))

        worker = threading.Thread(target=runner, daemon=True)
        worker.start()
        worker.join(timeout=timeout)

        if worker.is_alive():
            raise FutureTimeoutError()

        kind, payload = result_queue.get_nowait()
        if kind == "error":
            raise payload
        return payload

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

    def _apply_expectations(
        self,
        expect: Any,
        *,
        status: ResultStatus,
        code: int | None,
        message: str | None,
        details: dict[str, Any],
        metrics: dict[str, float | int],
    ) -> tuple[ResultStatus, int | None, str | None, dict[str, Any]]:
        if not expect:
            return status, code, message, details

        rules = expect.get("rules") if isinstance(expect, dict) else None
        if not isinstance(rules, list) or not rules:
            return status, code, message, details

        pass_policy = expect.get("pass_policy", "all") if isinstance(expect, dict) else "all"
        rule_results: list[dict[str, Any]] = []

        for rule in rules:
            if not isinstance(rule, dict):
                continue
            field_path = str(rule.get("field", "")).strip()
            operator = str(rule.get("operator", "eq")).strip()
            expected_value = rule.get("value")
            actual_value = self._resolve_expectation_field(
                field_path,
                status=status,
                code=code,
                message=message,
                details=details,
                metrics=metrics,
            )
            passed = self._evaluate_expectation(operator, actual_value, expected_value)
            rule_results.append(
                {
                    "field": field_path,
                    "operator": operator,
                    "expected": expected_value,
                    "actual": actual_value,
                    "passed": passed,
                    "message": rule.get("message"),
                }
            )

        if not rule_results:
            return status, code, message, details

        expectations_met = any(item["passed"] for item in rule_results) if pass_policy == "any" else all(
            item["passed"] for item in rule_results
        )
        if expectations_met:
            details_with_expect = dict(details)
            details_with_expect["expectation_results"] = rule_results
            return status, code, message, details_with_expect

        failure_messages = [item.get("message") for item in rule_results if not item["passed"] and item.get("message")]
        details_with_expect = dict(details)
        details_with_expect["expectation_results"] = rule_results
        return (
            ResultStatus.FAILED,
            code if code not in (None, 0) else -1,
            "; ".join(failure_messages) if failure_messages else "function result did not satisfy expect rules",
            details_with_expect,
        )

    def _resolve_expectation_field(
        self,
        field_path: str,
        *,
        status: ResultStatus,
        code: int | None,
        message: str | None,
        details: dict[str, Any],
        metrics: dict[str, float | int],
    ) -> Any:
        envelope: dict[str, Any] = {
            "status": status.value,
            "code": code,
            "message": message,
            "details": details,
            "metrics": metrics,
        }
        if not field_path:
            return None
        if "." in field_path:
            current: Any = envelope
            for part in field_path.split("."):
                if not isinstance(current, dict) or part not in current:
                    return None
                current = current[part]
            return current
        if field_path in envelope:
            return envelope[field_path]
        if field_path in details:
            return details[field_path]
        if field_path in metrics:
            return metrics[field_path]
        return None

    def _evaluate_expectation(self, operator: str, actual: Any, expected: Any) -> bool:
        if operator == "eq":
            return actual == expected
        if operator == "ne":
            return actual != expected
        if operator == "gt":
            return actual is not None and expected is not None and actual > expected
        if operator == "gte":
            return actual is not None and expected is not None and actual >= expected
        if operator == "lt":
            return actual is not None and expected is not None and actual < expected
        if operator == "lte":
            return actual is not None and expected is not None and actual <= expected
        if operator == "contains":
            try:
                return expected in actual
            except TypeError:
                return False
        if operator == "in":
            try:
                return actual in expected
            except TypeError:
                return False
        if operator == "exists":
            return actual is not None
        if operator == "non_empty":
            return actual not in (None, "", [], {}, ())
        raise TaskExecutionError(f"unsupported expect operator: {operator}")
