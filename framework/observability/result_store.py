"""Atomic storage for result snapshots."""

from __future__ import annotations

import json
from pathlib import Path

from framework.domain.results import ResultSnapshot


class ResultStore:
    def __init__(self, base_dir: str | Path = "tmp") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def snapshot_path(self, request_id: str) -> Path:
        return self.base_dir / f"{request_id}_snapshot.json"

    def write_snapshot(self, snapshot: ResultSnapshot) -> Path:
        target = self.snapshot_path(snapshot.request_id)
        temp_path = target.with_suffix(target.suffix + ".tmp")
        temp_path.write_text(
            json.dumps(snapshot.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temp_path.replace(target)
        return target

    def read_snapshot(self, request_id: str) -> ResultSnapshot | None:
        target = self.snapshot_path(request_id)
        if not target.exists():
            return None
        data = json.loads(target.read_text(encoding="utf-8"))
        return ResultSnapshot(**data)
