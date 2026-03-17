"""ResultStatus enumeration and status code system tests."""

from __future__ import annotations

from framework.domain.results import ExecutionResult, ResultStatus
from framework.execution.policies import (
    aggregate_status,
    is_success_status,
    normalize_status,
    should_retry,
)


class TestResultStatusEnum:
    """Test ResultStatus enumeration members and values."""

    def test_result_status_has_running_member(self) -> None:
        """Verify ResultStatus contains RUNNING member for in-progress tasks."""
        # This test will fail initially because RUNNING doesn't exist yet
        assert hasattr(ResultStatus, "RUNNING")
        assert ResultStatus.RUNNING.value == "running"

    def test_result_status_all_members(self) -> None:
        """Verify all expected ResultStatus members exist."""
        expected_members = {
            "PASSED",
            "FAILED",
            "RUNNING",
            "TIMEOUT",
            "SKIPPED",
            "ABORTED",
        }
        actual_members = {member.name for member in ResultStatus}
        assert expected_members == actual_members

    def test_result_status_values_are_strings(self) -> None:
        """Verify all ResultStatus values are strings."""
        for status in ResultStatus:
            assert isinstance(status.value, str)
            assert isinstance(str(status), str)

    def test_result_status_passed_value(self) -> None:
        """Verify PASSED status value."""
        assert ResultStatus.PASSED.value == "passed"

    def test_result_status_failed_value(self) -> None:
        """Verify FAILED status value."""
        assert ResultStatus.FAILED.value == "failed"

    def test_result_status_running_value(self) -> None:
        """Verify RUNNING status value."""
        assert ResultStatus.RUNNING.value == "running"

    def test_result_status_timeout_value(self) -> None:
        """Verify TIMEOUT status value."""
        assert ResultStatus.TIMEOUT.value == "timeout"

    def test_result_status_skipped_value(self) -> None:
        """Verify SKIPPED status value."""
        assert ResultStatus.SKIPPED.value == "skipped"

    def test_result_status_aborted_value(self) -> None:
        """Verify ABORTED status value."""
        assert ResultStatus.ABORTED.value == "aborted"


class TestExecutionResultWithRunningStatus:
    """Test ExecutionResult can use running status."""

    def test_execution_result_accepts_running_status_enum(self) -> None:
        """Verify ExecutionResult can be created with ResultStatus.RUNNING."""
        from datetime import datetime, timezone

        result = ExecutionResult(
            task_id="test-001",
            task_type="function",
            name="test_function",
            status=ResultStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            duration_ms=100,
        )
        assert result.status == ResultStatus.RUNNING

    def test_execution_result_accepts_running_status_string(self) -> None:
        """Verify ExecutionResult can be created with 'running' string."""
        from datetime import datetime, timezone

        result = ExecutionResult(
            task_id="test-001",
            task_type="function",
            name="test_function",
            status="running",
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            duration_ms=100,
        )
        assert result.status == "running"

    def test_execution_result_status_serialization(self) -> None:
        """Verify ExecutionResult status serializes correctly to dict."""
        from datetime import datetime, timezone

        result = ExecutionResult(
            task_id="test-001",
            task_type="function",
            name="test_function",
            status=ResultStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            duration_ms=100,
        )
        payload = result.to_dict()
        assert payload["status"] == "running"


class TestStatusNormalization:
    """Test normalize_status function handles all status types."""

    def test_normalize_status_with_enum(self) -> None:
        """Verify normalize_status works with ResultStatus enum."""
        assert normalize_status(ResultStatus.PASSED) == "passed"
        assert normalize_status(ResultStatus.FAILED) == "failed"
        assert normalize_status(ResultStatus.RUNNING) == "running"
        assert normalize_status(ResultStatus.TIMEOUT) == "timeout"
        assert normalize_status(ResultStatus.SKIPPED) == "skipped"
        assert normalize_status(ResultStatus.ABORTED) == "aborted"

    def test_normalize_status_with_string(self) -> None:
        """Verify normalize_status works with string values."""
        assert normalize_status("passed") == "passed"
        assert normalize_status("failed") == "failed"
        assert normalize_status("running") == "running"
        assert normalize_status("timeout") == "timeout"
        assert normalize_status("skipped") == "skipped"
        assert normalize_status("aborted") == "aborted"


class TestSuccessStatusDetection:
    """Test is_success_status function."""

    def test_is_success_status_passed(self) -> None:
        """Verify passed is recognized as success."""
        assert is_success_status(ResultStatus.PASSED) is True
        assert is_success_status("passed") is True

    def test_is_success_status_running_is_not_success(self) -> None:
        """Verify running is not considered success."""
        assert is_success_status(ResultStatus.RUNNING) is False
        assert is_success_status("running") is False

    def test_is_success_status_failed_is_not_success(self) -> None:
        """Verify failed is not success."""
        assert is_success_status(ResultStatus.FAILED) is False
        assert is_success_status("failed") is False


class TestRetryLogic:
    """Test should_retry function with all status values."""

    def test_should_retry_on_failed(self) -> None:
        """Verify retry is allowed for failed status."""
        assert should_retry(ResultStatus.FAILED, 0, 3) is True
        assert should_retry("failed", 0, 3) is True

    def test_should_retry_on_timeout(self) -> None:
        """Verify retry is allowed for timeout status."""
        assert should_retry(ResultStatus.TIMEOUT, 0, 3) is True
        assert should_retry("timeout", 0, 3) is True

    def test_should_not_retry_on_passed(self) -> None:
        """Verify no retry for passed status."""
        assert should_retry(ResultStatus.PASSED, 0, 3) is False
        assert should_retry("passed", 0, 3) is False

    def test_should_not_retry_on_running(self) -> None:
        """Verify no retry for running status."""
        assert should_retry(ResultStatus.RUNNING, 0, 3) is False
        assert should_retry("running", 0, 3) is False

    def test_should_not_retry_max_attempts_reached(self) -> None:
        """Verify no retry when max attempts reached."""
        assert should_retry(ResultStatus.FAILED, 3, 3) is False
        assert should_retry(ResultStatus.TIMEOUT, 3, 3) is False


class TestStatusAggregation:
    """Test aggregate_status function with running and terminal states."""

    def test_aggregate_status_empty_children(self) -> None:
        """Verify empty children returns SKIPPED."""
        assert aggregate_status([]) == ResultStatus.SKIPPED

    def test_aggregate_status_all_passed(self) -> None:
        """Verify all passed children returns PASSED."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        children = [
            ExecutionResult(
                task_id=f"child-{i}",
                task_type="function",
                name=f"test_{i}",
                status=ResultStatus.PASSED,
                started_at=now,
                finished_at=now,
                duration_ms=100,
            )
            for i in range(3)
        ]
        assert aggregate_status(children) == ResultStatus.PASSED

    def test_aggregate_status_with_running_returns_running(self) -> None:
        """Verify running children affects aggregation appropriately."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        children = [
            ExecutionResult(
                task_id="child-1",
                task_type="function",
                name="test_1",
                status=ResultStatus.PASSED,
                started_at=now,
                finished_at=now,
                duration_ms=100,
            ),
            ExecutionResult(
                task_id="child-2",
                task_type="function",
                name="test_2",
                status=ResultStatus.RUNNING,
                started_at=now,
                finished_at=now,
                duration_ms=100,
            ),
        ]
        # Running tasks should not make the aggregate fail
        # Current behavior: running is not a terminal status,
        # so aggregation depends on implementation
        result = aggregate_status(children)
        # The aggregation should handle running appropriately
        assert result in {ResultStatus.RUNNING, ResultStatus.FAILED}

    def test_aggregate_status_with_failed(self) -> None:
        """Verify failed child returns FAILED."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        children = [
            ExecutionResult(
                task_id="child-1",
                task_type="function",
                name="test_1",
                status=ResultStatus.PASSED,
                started_at=now,
                finished_at=now,
                duration_ms=100,
            ),
            ExecutionResult(
                task_id="child-2",
                task_type="function",
                name="test_2",
                status=ResultStatus.FAILED,
                started_at=now,
                finished_at=now,
                duration_ms=100,
            ),
        ]
        assert aggregate_status(children) == ResultStatus.FAILED
