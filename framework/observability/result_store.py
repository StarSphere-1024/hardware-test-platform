"""Atomic storage for result snapshots."""

from __future__ import annotations

import json
from pathlib import Path

from framework.domain.results import ResultSnapshot


class ResultStore:
    """Result store manager."""

    def __init__(self, base_dir: str | Path = "tmp") -> None:
        """Initialize ResultStore.

        Args:
            base_dir: Base directory.
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def snapshot_path(self, request_id: str) -> Path:
        """Get the snapshot file path.

        Args:
            request_id: Request ID.

        Returns:
            Snapshot file path.
        """
        return self.base_dir / f"{request_id}_snapshot.json"

    def write_snapshot(self, snapshot: ResultSnapshot) -> Path:
        """Write a result snapshot.

        Args:
            snapshot: Result snapshot.

        Returns:
            Target path.
        """
        target = self.snapshot_path(snapshot.request_id)
        temp_path = target.with_suffix(target.suffix + ".tmp")
        temp_path.write_text(
            json.dumps(snapshot.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temp_path.replace(target)
        return target

    def read_snapshot(self, request_id: str) -> ResultSnapshot | None:
        """Read a result snapshot.

        Args:
            request_id: Request ID.

        Returns:
            Result snapshot, or None if not found.
        """
        target = self.snapshot_path(request_id)
        if not target.exists():
            return None
        data = json.loads(target.read_text(encoding="utf-8"))
        return ResultSnapshot(**data)
