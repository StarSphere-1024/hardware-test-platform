"""In-memory resource lock manager for execution tasks."""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime, timedelta
from typing import Any


class ResourceLockManager:
    def __init__(self, state: dict[str, Any] | None = None) -> None:
        self._state = state if state is not None else {}
        self._mutex = threading.Lock()

    def acquire(
        self,
        resources: list[str],
        *,
        owner_task_id: str,
        owner_attempt: int,
        timeout_seconds: int | None,
    ) -> dict[str, Any]:
        normalized_resources = self._normalize_resources(resources)
        started_perf = time.perf_counter()
        deadline = (
            None if timeout_seconds is None else started_perf + max(timeout_seconds, 0)
        )

        while True:
            blocked_resource: str | None = None
            blocked_reason: str | None = None
            sleep_seconds = 0.01
            now_perf = time.perf_counter()
            now_utc = datetime.now(UTC)

            with self._mutex:
                for resource in normalized_resources:
                    entry = self._entry(resource)
                    quarantine_until_perf = entry.get("quarantine_until_perf")
                    owner = entry.get("owner_task_id")
                    if (
                        quarantine_until_perf is not None
                        and quarantine_until_perf > now_perf
                    ):
                        blocked_resource = resource
                        blocked_reason = "quarantine"
                        sleep_seconds = max(quarantine_until_perf - now_perf, 0.01)
                        break
                    if owner is not None and owner != owner_task_id:
                        blocked_resource = resource
                        blocked_reason = "locked"
                        sleep_seconds = 0.01
                        break

                if blocked_resource is None:
                    acquired_at = now_utc.isoformat()
                    for resource in normalized_resources:
                        entry = self._entry(resource)
                        entry["owner_task_id"] = owner_task_id
                        entry["owner_attempt"] = owner_attempt
                        entry["acquired_at"] = acquired_at
                        entry["last_wait_ms"] = int(
                            (time.perf_counter() - started_perf) * 1000
                        )
                    return {
                        "acquired": True,
                        "resources": normalized_resources,
                        "wait_ms": int((time.perf_counter() - started_perf) * 1000),
                    }

            if deadline is not None and now_perf >= deadline:
                return {
                    "acquired": False,
                    "resources": normalized_resources,
                    "wait_ms": int((time.perf_counter() - started_perf) * 1000),
                    "blocked_resource": blocked_resource,
                    "reason": blocked_reason or "timeout",
                }

            if deadline is not None:
                remaining = deadline - now_perf
                if remaining <= 0:
                    return {
                        "acquired": False,
                        "resources": normalized_resources,
                        "wait_ms": int((time.perf_counter() - started_perf) * 1000),
                        "blocked_resource": blocked_resource,
                        "reason": blocked_reason or "timeout",
                    }
                sleep_seconds = min(sleep_seconds, remaining)

            time.sleep(sleep_seconds)

    def release(
        self,
        resources: list[str],
        *,
        owner_task_id: str,
        release_reason: str,
        quarantine_seconds: float = 0,
    ) -> dict[str, Any]:
        normalized_resources = self._normalize_resources(resources)
        released_at = datetime.now(UTC)
        quarantine_until = None
        quarantine_until_perf = None
        if quarantine_seconds > 0:
            quarantine_until = (
                released_at + timedelta(seconds=quarantine_seconds)
            ).isoformat()
            quarantine_until_perf = time.perf_counter() + quarantine_seconds

        with self._mutex:
            for resource in normalized_resources:
                entry = self._entry(resource)
                if entry.get("owner_task_id") not in (None, owner_task_id):
                    continue
                entry["owner_task_id"] = None
                entry["owner_attempt"] = None
                entry["released_at"] = released_at.isoformat()
                entry["last_release_reason"] = release_reason
                entry["quarantine_until"] = quarantine_until
                entry["quarantine_until_perf"] = quarantine_until_perf

        return {
            "resources": normalized_resources,
            "released_at": released_at.isoformat(),
            "release_reason": release_reason,
            "quarantine_until": quarantine_until,
        }

    def _entry(self, resource: str) -> dict[str, Any]:
        entry = self._state.get(resource)
        if isinstance(entry, dict):
            return entry
        entry = {}
        self._state[resource] = entry
        return entry

    def _normalize_resources(self, resources: list[str]) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []
        for resource in resources:
            if not isinstance(resource, str):
                continue
            value = resource.strip()
            if not value or value in seen:
                continue
            seen.add(value)
            normalized.append(value)
        normalized.sort()
        return normalized
