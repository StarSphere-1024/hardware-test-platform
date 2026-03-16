"""Generate minimal text and JSON reports from unified result models."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from framework.config.models import ResolvedExecutionConfig
from framework.domain.events import EventRecord
from framework.domain.results import ExecutionResult, ReportArtifact, ResultSnapshot


class ReportGenerator:
    def __init__(self, reports_dir: str | Path = "reports") -> None:
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        *,
        root_result: ExecutionResult,
        snapshot: ResultSnapshot,
        resolved_config: ResolvedExecutionConfig,
        events: list[EventRecord],
    ) -> list[ReportArtifact]:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        sku = resolved_config.board_profile.product.sku or "UNKNOWN"
        suffix = str(root_result.status)
        base_name = f"{sku}_{snapshot.request_id}_{timestamp}_{suffix}".replace("/", "_")
        text_path = self.reports_dir / f"{base_name}.report"
        json_path = self.reports_dir / f"{base_name}.report.json"

        payload = {
            "metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "event_count": len(events),
            },
            "request": resolved_config.request,
            "config_snapshot": resolved_config.to_dict(),
            "result_snapshot": snapshot.to_dict(),
            "root_result": root_result.to_dict(),
            "events": [record.to_dict() for record in events],
        }
        text_content = self._build_text_report(root_result, snapshot, events)
        text_path.write_text(text_content, encoding="utf-8")
        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

        return [
            ReportArtifact(artifact_type="text-report", uri=str(text_path), content_type="text/plain"),
            ReportArtifact(artifact_type="json-report", uri=str(json_path), content_type="application/json"),
        ]

    def _build_text_report(self, root_result: ExecutionResult, snapshot: ResultSnapshot, events: list[EventRecord]) -> str:
        lines = [
            "Hardware Test Platform Report",
            f"request_id: {snapshot.request_id}",
            f"plan_id: {snapshot.plan_id}",
            f"status: {snapshot.current_status}",
            f"event_count: {len(events)}",
            "",
            "Summary:",
        ]
        for key, value in sorted(snapshot.counters.items()):
            lines.append(f"- {key}: {value}")
        lines.extend([
            "",
            f"Root Result: {root_result.name} ({root_result.task_type}) -> {root_result.status}",
            f"Message: {root_result.message or ''}",
        ])
        residual_risks = self._collect_residual_risks(root_result)
        if residual_risks:
            lines.extend(["", "Residual Risks:"])
            for item in residual_risks:
                lines.append(f"- {item['task_name']}: {item['message']}")
        return "\n".join(lines) + "\n"

    def _collect_residual_risks(self, root_result: ExecutionResult) -> list[dict[str, str]]:
        residual_risks: list[dict[str, str]] = []

        def visit(result: ExecutionResult) -> None:
            if isinstance(result.details, dict):
                risk = result.details.get("residual_risk")
                if isinstance(risk, dict):
                    residual_risks.append(
                        {
                            "task_name": result.name,
                            "message": str(risk.get("message") or "residual risk recorded"),
                        }
                    )
            for child in result.children:
                visit(child)

        visit(root_result)
        return residual_risks
