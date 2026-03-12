from __future__ import annotations

import time

from framework.execution.resource_locks import ResourceLockManager


def test_resource_lock_manager_acquires_and_releases_resources() -> None:
    state: dict[str, object] = {}
    manager = ResourceLockManager(state)

    acquired = manager.acquire(["interface:uart:/dev/ttyUSB0"], owner_task_id="task-1", owner_attempt=1, timeout_seconds=1)
    released = manager.release(
        ["interface:uart:/dev/ttyUSB0"],
        owner_task_id="task-1",
        release_reason="passed",
    )

    assert acquired["acquired"] is True
    assert released["release_reason"] == "passed"
    assert state["interface:uart:/dev/ttyUSB0"]["owner_task_id"] is None


def test_resource_lock_manager_respects_quarantine() -> None:
    state: dict[str, object] = {}
    manager = ResourceLockManager(state)

    manager.release(
        ["interface:i2c:/dev/i2c-0"],
        owner_task_id="task-timeout",
        release_reason="timeout",
        quarantine_seconds=0.02,
    )
    blocked = manager.acquire(["interface:i2c:/dev/i2c-0"], owner_task_id="task-2", owner_attempt=1, timeout_seconds=0)
    time.sleep(0.03)
    acquired = manager.acquire(["interface:i2c:/dev/i2c-0"], owner_task_id="task-2", owner_attempt=1, timeout_seconds=1)

    assert blocked["acquired"] is False
    assert blocked["reason"] == "quarantine"
    assert acquired["acquired"] is True