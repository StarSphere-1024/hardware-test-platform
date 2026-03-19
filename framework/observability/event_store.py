"""Sequential event storage using JSONL."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from framework.domain.events import EventRecord, ExecutionEvent


class EventStore:
    """Event store using JSONL format for sequential event storage.

    Supports appending and reading event records by request ID.
    """

    def __init__(self, base_dir: str | Path = "logs/events") -> None:
        """Initialize EventStore.

        Args:
            base_dir: Base directory for event log files.
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._sequence_by_request: dict[str, int] = {}

    def event_log_path(self, request_id: str) -> Path:
        """Get the event log file path for the specified request ID.

        Args:
            request_id: Unique request identifier.

        Returns:
            Path object for the event log file.
        """
        return self.base_dir / f"{request_id}.jsonl"

    def append(self, event: ExecutionEvent, *, source: str) -> EventRecord:
        """Append an execution event to storage.

        Args:
            event: Execution event object.
            source: Source identifier.

        Returns:
            Stored event record.
        """
        sequence = self._sequence_by_request.get(event.request_id, 0) + 1
        self._sequence_by_request[event.request_id] = sequence
        record = EventRecord(
            sequence=sequence,
            event=event,
            stored_at=datetime.now(UTC),
            storage_metadata={"source": source},
        )
        path = self.event_log_path(event.request_id)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        return record

    def read(self, request_id: str) -> list[EventRecord]:
        """Read all event records for the specified request.

        Args:
            request_id: Unique request identifier.

        Returns:
            List of event records, or empty list if file does not exist.
        """
        path = self.event_log_path(request_id)
        if not path.exists():
            return []
        records: list[EventRecord] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            event_payload = payload.pop("event")
            event = ExecutionEvent(**event_payload)
            records.append(EventRecord(event=event, **payload))
        self._sequence_by_request[request_id] = max(
            (record.sequence for record in records), default=0
        )
        return records
