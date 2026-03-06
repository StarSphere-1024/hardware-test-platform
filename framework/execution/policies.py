"""Policy helpers for retry, timeout and result aggregation."""

from __future__ import annotations

from typing import Iterable

from framework.domain.results import ExecutionResult, ResultStatus


TERMINAL_FAILURE_STATUSES = {ResultStatus.FAILED.value, ResultStatus.TIMEOUT.value, ResultStatus.ABORTED.value}


def normalize_status(status: ResultStatus | str) -> str:
    return status.value if isinstance(status, ResultStatus) else str(status)


def is_success_status(status: ResultStatus | str) -> bool:
    return normalize_status(status) == ResultStatus.PASSED.value


def should_retry(status: ResultStatus | str, attempt: int, max_retries: int) -> bool:
    return normalize_status(status) in {ResultStatus.FAILED.value, ResultStatus.TIMEOUT.value} and attempt < max_retries


def aggregate_status(children: Iterable[ExecutionResult]) -> ResultStatus:
    child_statuses = [normalize_status(child.status) for child in children]
    if not child_statuses:
        return ResultStatus.SKIPPED
    if all(status == ResultStatus.PASSED.value for status in child_statuses):
        return ResultStatus.PASSED
    if any(status == ResultStatus.TIMEOUT.value for status in child_statuses):
        return ResultStatus.TIMEOUT
    if any(status == ResultStatus.ABORTED.value for status in child_statuses):
        return ResultStatus.ABORTED
    if any(status == ResultStatus.FAILED.value for status in child_statuses):
        return ResultStatus.FAILED
    if all(status == ResultStatus.SKIPPED.value for status in child_statuses):
        return ResultStatus.SKIPPED
    return ResultStatus.FAILED


def summarize_children(children: Iterable[ExecutionResult]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for child in children:
        status = normalize_status(child.status)
        summary[status] = summary.get(status, 0) + 1
    return summary
