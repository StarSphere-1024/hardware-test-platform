"""Execution boundary for a single function task."""

from __future__ import annotations

import inspect
import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import UTC, datetime
from queue import Queue
from typing import Any

from framework.domain.execution import ExecutionContext, ExecutionTask
from framework.domain.results import ExecutionResult, ResultStatus

from .errors import FunctionNotRegisteredError, TaskExecutionError


class FunctionExecutor:
    """Function task execution boundary."""

    def __init__(
        self, function_registry: dict[str, Callable[..., Any]] | None = None
    ) -> None:
        """Initialize FunctionExecutor.

        Args:
            function_registry: Function registry mapping names to callables.
        """
        self.function_registry = dict(function_registry or {})

    def register(self, name: str, function: Callable[..., Any]) -> None:
        """Register a function with the executor.

        Args:
            name: Function registration name.
            function: Callable object.
        """
        self.function_registry[name] = function

    def execute(
        self, task: ExecutionTask, context: ExecutionContext
    ) -> ExecutionResult:
        """Execute a function task.

        Args:
            task: Function task to execute.
            context: Execution context.

        Returns:
            Execution result.

        Raises:
            TaskExecutionError: When task type is unsupported or parameters are invalid.
            FunctionNotRegisteredError: When function is not registered.
        """
        logger = logging.getLogger("hardware_test_platform.function_executor")

        if task.task_type != "function":
            raise TaskExecutionError(
                f"unsupported task type for FunctionExecutor: {task.task_type}"
            )

        function_name = task.payload.get("function_name") or task.name
        params = task.payload.get("params", {})
        if not isinstance(params, dict):
            raise TaskExecutionError(
                f"function params must be a mapping: {function_name}"
            )

        if function_name not in self.function_registry:
            raise FunctionNotRegisteredError(
                f"function '{function_name}' is not registered"
            )

        logger.debug(
            "FunctionExecutor.execute: executing function %s with params %s",
            function_name,
            params,
        )

        started_at = datetime.now(UTC)
        started_perf = time.perf_counter()
        callable_obj = self.function_registry[function_name]

        try:
            raw_result = self._invoke(callable_obj, params, task.timeout, context)
            logger.debug(
                "FunctionExecutor.execute: function %s returned raw result",
                function_name,
            )
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
            logger.debug(
                "FunctionExecutor.execute: function %s timed out after %ss",
                function_name,
                task.timeout,
            )
            finished_at = datetime.now(UTC)
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
                details={
                    "params": dict(params),
                    "residual_risk": {
                        "kind": "timeout-background_execution_unknown",
                        "message": (
                            "timeout returned before the worker "
                            "could be confirmed stopped"
                        ),
                        "operator_action": (
                            "inspect hardware state before immediate retry "
                            "if the function has side effects"
                        ),
                    },
                },
            )
        except Exception as error:
            logger.debug(
                "FunctionExecutor.execute: function %s raised exception: %s",
                function_name,
                error,
            )
            finished_at = datetime.now(UTC)
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

        logger.debug(
            "FunctionExecutor.execute: function %s completed with status %s",
            function_name,
            status,
        )
        finished_at = datetime.now(UTC)
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
        """Invoke function in an isolated thread.

        Args:
            callable_obj: Callable object.
            params: Function parameters.
            timeout: Timeout in seconds.
            context: Execution context.

        Returns:
            Function execution result.

        Raises:
            TimeoutError: When function execution times out.
        """
        logger = logging.getLogger("hardware_test_platform.function_executor")
        invocation_params = self._build_invocation_params(callable_obj, params, context)
        logger.debug(
            "FunctionExecutor._invoke: calling function with params %s",
            invocation_params,
        )
        if timeout is None:
            return callable_obj(**invocation_params)

        result_queue: Queue[tuple[str, Any]] = Queue(maxsize=1)

        def runner() -> None:
            try:
                result_queue.put(("result", callable_obj(**invocation_params)))
            except Exception as error:
                result_queue.put(("error", error))

        worker = threading.Thread(target=runner, daemon=True)
        worker.start()
        logger.debug(
            "FunctionExecutor._invoke: started worker thread with timeout %ss", timeout
        )
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
        """Build function invocation parameters.

        Args:
            callable_obj: Callable object.
            params: Original parameter dictionary.
            context: Execution context.

        Returns:
            Complete invocation parameter dictionary.
        """
        invocation_params = dict(params)
        try:
            signature = inspect.signature(callable_obj)
        except (TypeError, ValueError):
            return invocation_params

        if (
            "execution_context" in signature.parameters
            and "execution_context" not in invocation_params
        ):
            invocation_params["execution_context"] = context
        if (
            "capability_registry" in signature.parameters
            and "capability_registry" not in invocation_params
        ):
            invocation_params["capability_registry"] = context.capability_registry
        if (
            "adapter_registry" in signature.parameters
            and "adapter_registry" not in invocation_params
        ):
            invocation_params["adapter_registry"] = context.adapter_registry
        return invocation_params

    def _normalize_result(
        self,
        raw_result: Any,
    ) -> tuple[
        ResultStatus, int | None, str | None, dict[str, Any], dict[str, float | int]
    ]:
        """Normalize function execution result.

        Args:
            raw_result: Raw execution result.

        Returns:
            Tuple containing status, code, message, details, and metrics.
        """
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
                message = (
                    "success" if status == ResultStatus.PASSED else "function failed"
                )
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
        """Apply expectation rules to execution result.

        Args:
            expect: Expectation configuration.
            status: Current execution status.
            code: Current execution code.
            message: Current message.
            details: Current details.
            metrics: Current metrics.

        Returns:
            Tuple containing updated status, code, message, and details.
        """
        logger = logging.getLogger("hardware_test_platform.function_executor")

        if not expect:
            return status, code, message, details

        rules = expect.get("rules") if isinstance(expect, dict) else None
        if not isinstance(rules, list) or not rules:
            return status, code, message, details

        logger.debug(
            "FunctionExecutor._apply_expectations: evaluating %d expect rules",
            len(rules),
        )

        pass_policy = (
            expect.get("pass_policy", "all") if isinstance(expect, dict) else "all"
        )
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
            logger.debug(
                "FunctionExecutor._apply_expectations: "
                "rule field=%s operator=%s passed=%s",
                field_path,
                operator,
                passed,
            )
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

        expectations_met = (
            any(item["passed"] for item in rule_results)
            if pass_policy == "any"
            else all(item["passed"] for item in rule_results)
        )
        if expectations_met:
            logger.debug("FunctionExecutor._apply_expectations: all expectations met")
            details_with_expect = dict(details)
            details_with_expect["expectation_results"] = rule_results
            return status, code, message, details_with_expect

        failure_messages = [
            item.get("message")
            for item in rule_results
            if not item["passed"] and item.get("message")
        ]
        details_with_expect = dict(details)
        details_with_expect["expectation_results"] = rule_results
        logger.debug(
            "FunctionExecutor._apply_expectations: expectations not met, failing"
        )
        return (
            ResultStatus.FAILED,
            code if code not in (None, 0) else -1,
            "; ".join(str(msg) for msg in failure_messages if msg)
            if failure_messages
            else "function result did not satisfy expect rules",
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
        """Resolve value at field path for expectation.

        Args:
            field_path: Field path (dot-separated for nested access).
            status: Execution status.
            code: Execution code.
            message: Execution message.
            details: Execution details.
            metrics: Execution metrics.

        Returns:
            Resolved field value.
        """
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

    def _evaluate_expectation(  # noqa: C901
        self, operator: str, actual: Any, expected: Any
    ) -> bool:
        """Evaluate expectation rule.

        Args:
            operator: Comparison operator.
            actual: Actual value.
            expected: Expected value.

        Returns:
            Whether the rule passed.

        Raises:
            TaskExecutionError: When operator is unsupported.
        """
        match operator:
            # Equality check: actual == expected
            case "eq":
                return actual == expected
            # Inequality check: actual != expected
            case "ne":
                return actual != expected
            # Greater than: actual > expected (requires both values non-None)
            case "gt":
                return (
                    actual is not None
                    and expected is not None
                    and actual > expected
                )
            # Greater than or equal: actual >= expected (requires both values non-None)
            case "gte":
                return (
                    actual is not None
                    and expected is not None
                    and actual >= expected
                )
            # Less than: actual < expected (requires both values non-None)
            case "lt":
                return (
                    actual is not None
                    and expected is not None
                    and actual < expected
                )
            # Less than or equal: actual <= expected (requires both values non-None)
            case "lte":
                return (
                    actual is not None
                    and expected is not None
                    and actual <= expected
                )
            # Containment check: expected in actual (e.g., substring, list membership)
            case "contains":
                try:
                    return expected in actual
                except TypeError:
                    return False
            # Membership check: actual in expected (e.g., value in list/range)
            case "in":
                try:
                    return actual in expected
                except TypeError:
                    return False
            # Existence check: actual is not None
            case "exists":
                return actual is not None
            # Non-empty check: actual is not None, "", [], {}, or ()
            case "non_empty":
                return actual not in (None, "", [], {}, ())
            case _:
                raise TaskExecutionError(f"unsupported expect operator: {operator}")
