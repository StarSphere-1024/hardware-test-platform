"""Policy helpers for retry, timeout and result aggregation."""

from __future__ import annotations

from collections.abc import Iterable

from framework.domain.results import ExecutionResult, ResultStatus

TERMINAL_FAILURE_STATUSES = {
    ResultStatus.FAILED.value,
    ResultStatus.TIMEOUT.value,
    ResultStatus.ABORTED.value,
}
NON_TERMINAL_STATUSES = {ResultStatus.RUNNING.value, ResultStatus.SKIPPED.value}


def normalize_status(status: ResultStatus | str) -> str:
    """Normalize a status value to its string representation.

    Args:
        status: Either a ResultStatus enum or string value

    Returns:
        String representation of the status
    """
    return status.value if isinstance(status, ResultStatus) else str(status)


def is_success_status(status: ResultStatus | str) -> bool:
    """Check if a status represents a successful completion.

    Args:
        status: Either a ResultStatus enum or string value

    Returns:
        True if status is PASSED, False otherwise
    """
    return normalize_status(status) == ResultStatus.PASSED.value


def should_retry(status: ResultStatus | str, attempt: int, max_retries: int) -> bool:
    """Determine if a task should be retried based on status and attempt count.

    Args:
        status: Either a ResultStatus enum or string value
        attempt: Current attempt number (0-indexed)
        max_retries: Maximum number of retries allowed

    Returns:
        True if the task should be retried, False otherwise
    """
    return (
        normalize_status(status)
        in {ResultStatus.FAILED.value, ResultStatus.TIMEOUT.value}
        and attempt < max_retries
    )


def aggregate_status(children: Iterable[ExecutionResult]) -> ResultStatus:
    """Aggregate child execution results into a single status.

    Priority order: PASSED > RUNNING > TIMEOUT > ABORTED > FAILED > SKIPPED

    Args:
        children: Iterable of child ExecutionResult objects

    Returns:
        Aggregated ResultStatus based on child statuses
    """
    child_statuses = [normalize_status(child.status) for child in children]
    if not child_statuses:
        return ResultStatus.SKIPPED
    if all(status == ResultStatus.PASSED.value for status in child_statuses):
        return ResultStatus.PASSED
    # Running is a non-terminal state; if any child is running and none have failed,
    # the aggregate should reflect that work is in progress
    if any(status == ResultStatus.RUNNING.value for status in child_statuses):
        return ResultStatus.RUNNING
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
    """Summarize status distribution of child execution results.

    Args:
        children: Iterable of child ExecutionResult objects.

    Returns:
        Status count dictionary.
    """
    summary: dict[str, int] = {}
    for child in children:
        status = normalize_status(child.status)
        summary[status] = summary.get(status, 0) + 1
    return summary
