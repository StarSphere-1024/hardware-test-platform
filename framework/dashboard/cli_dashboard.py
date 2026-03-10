"""Terminal dashboard adapted to the current snapshot and event model."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


class _TerminalInput:
    def __init__(self) -> None:
        self.enabled = False
        self.fd: int | None = None
        self._old_attr = None

    def __enter__(self):
        try:
            import sys
            import termios
            import tty

            if not sys.stdin.isatty():
                return self

            self.fd = sys.stdin.fileno()
            self._old_attr = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
            new_attr = termios.tcgetattr(self.fd)
            new_attr[3] = new_attr[3] & ~termios.ECHO
            termios.tcsetattr(self.fd, termios.TCSANOW, new_attr)
            self.enabled = True
        except Exception:
            self.enabled = False
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            import termios

            if self.fd is not None and self._old_attr is not None:
                termios.tcsetattr(self.fd, termios.TCSADRAIN, self._old_attr)
            if self.fd is not None:
                termios.tcflush(self.fd, termios.TCIFLUSH)
        except Exception:
            pass

    def read_key(self) -> str | None:
        if not self.enabled or self.fd is None:
            return None
        try:
            import select

            ready, _, _ = select.select([self.fd], [], [], 0)
            if not ready:
                return None
            raw = os.read(self.fd, 32)
        except Exception:
            return None

        if not raw or b"\x1b" in raw:
            return None

        text = raw.decode("utf-8", errors="ignore")
        for char in text:
            if char.isprintable() and not char.isspace():
                return char.lower()
        return None


class DashboardDataSource:
    def __init__(
        self,
        *,
        workspace_root: str | Path,
        tmp_dir: str | Path,
        logs_dir: str | Path,
        reports_dir: str | Path,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.tmp_dir = Path(tmp_dir).resolve()
        self.logs_dir = Path(logs_dir).resolve()
        self.reports_dir = Path(reports_dir).resolve()

    def read_snapshot(self, request_id: str | None = None) -> dict[str, Any]:
        path = self._select_snapshot_path(request_id)
        if path is None:
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def read_events(self, request_id: str | None) -> list[dict[str, Any]]:
        if not request_id:
            return []
        path = self.logs_dir / "events" / f"{request_id}.jsonl"
        if not path.exists():
            return []
        items: list[dict[str, Any]] = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    items.append(json.loads(line))
        except (OSError, json.JSONDecodeError):
            return []
        return items

    def read_system_info(self) -> dict[str, Any]:
        path = self.tmp_dir / "system_monitor.json"
        if not path.exists():
            return {
                "platform": "linux",
                "cpu": {"usage_percent": None, "temperature": None, "frequency_mhz": None},
                "memory": {"used_mb": None, "total_mb": None, "usage_percent": None},
                "storage": {"used_gb": None, "total_gb": None, "usage_percent": None},
            }
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def load_fixture_config(self, fixture_name: str) -> dict[str, Any]:
        if not fixture_name:
            return {}
        fixtures_dir = self.workspace_root / "fixtures"
        if not fixtures_dir.exists():
            return {}
        for candidate in fixtures_dir.glob("*.json"):
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if payload.get("fixture_name") == fixture_name or candidate.stem == fixture_name:
                return payload
        return {}

    def read_log_lines(self, request_id: str | None, *, limit: int = 20) -> list[str]:
        path = self._select_log_path(request_id)
        if path is None:
            return ["No log files available"]
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError as error:
            return [f"Read log failed: {error}"]
        return [f"File: {path.name}"] + lines[-limit:]

    def has_report(self, request_id: str | None) -> bool:
        if not self.reports_dir.exists():
            return False
        if request_id:
            return any(request_id in path.name for path in self.reports_dir.iterdir())
        return any(self.reports_dir.iterdir())

    def _select_snapshot_path(self, request_id: str | None) -> Path | None:
        if request_id:
            path = self.tmp_dir / f"{request_id}_snapshot.json"
            return path if path.exists() else None
        candidates = sorted(self.tmp_dir.glob("*_snapshot.json"), key=lambda item: item.stat().st_mtime, reverse=True)
        return candidates[0] if candidates else None

    def _select_log_path(self, request_id: str | None) -> Path | None:
        if request_id:
            path = self.logs_dir / f"{request_id}.log"
            return path if path.exists() else None
        candidates = sorted(self.logs_dir.glob("*.log"), key=lambda item: item.stat().st_mtime, reverse=True)
        return candidates[0] if candidates else None


class CLIDashboard:
    def __init__(
        self,
        *,
        workspace_root: str | Path = ".",
        tmp_dir: str | Path = "tmp",
        logs_dir: str | Path = "logs",
        reports_dir: str | Path = "reports",
        refresh_interval: float = 1.0,
        fixture_name: str = "",
        request_id: str = "",
        auto_exit: bool = False,
        success_exit_linger_seconds: float | None = 3.0,
        failure_exit_linger_seconds: float | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.tmp_dir = Path(tmp_dir).resolve()
        self.logs_dir = Path(logs_dir).resolve()
        self.reports_dir = Path(reports_dir).resolve()
        self.refresh_interval = refresh_interval
        self.console = Console(record=True)
        self.data_source = DashboardDataSource(
            workspace_root=self.workspace_root,
            tmp_dir=self.tmp_dir,
            logs_dir=self.logs_dir,
            reports_dir=self.reports_dir,
        )

        self._running = False
        self._fixture_name = fixture_name
        self._request_id = request_id
        self._auto_exit = auto_exit
        self._success_exit_linger_seconds = success_exit_linger_seconds
        self._failure_exit_linger_seconds = failure_exit_linger_seconds
        self._start_time: datetime | None = None
        self._completed_at: datetime | None = None
        self._completed_status: str | None = None
        self._view_mode = "main"
        self._last_action = ""
        self._pending_snapshot = False
        self._fixture_config = self.data_source.load_fixture_config(fixture_name)

    def start(self, *, start_monitor: bool = True) -> None:
        self._running = True
        self._start_time = datetime.now()
        if start_monitor:
            self._start_monitor()
        self._run_live_display()

    def stop(self) -> None:
        self._running = False
        self._stop_monitor()

    def render_once(self) -> Layout:
        return self._generate_layout()

    def _start_monitor(self) -> None:
        try:
            from framework.monitoring import start_monitoring

            start_monitoring(output_dir=str(self.tmp_dir), refresh_interval=2.0)
        except Exception:
            pass

    def _stop_monitor(self) -> None:
        try:
            from framework.monitoring import stop_monitoring

            stop_monitoring()
        except Exception:
            pass

    def _run_live_display(self) -> None:
        try:
            with _TerminalInput() as terminal_input:
                with Live(
                    self._generate_layout(),
                    refresh_per_second=max(1, int(1 / max(0.2, self.refresh_interval))),
                    screen=True,
                    auto_refresh=False,
                    redirect_stdout=False,
                    redirect_stderr=False,
                    console=self.console,
                ) as live:
                    while self._running:
                        key = terminal_input.read_key()
                        self._handle_key(key)
                        if not self._running:
                            break
                        layout = self._generate_layout()
                        self._update_auto_exit_state()
                        live.update(layout, refresh=True)
                        if self._pending_snapshot:
                            self._save_snapshot(layout)
                            self._pending_snapshot = False
                        time.sleep(self.refresh_interval)
        finally:
            self.stop()
            self.console.show_cursor(True)
            self.console.clear()

    def _handle_key(self, key: str | None) -> None:
        if not key:
            return
        if key == "q":
            self._running = False
        elif key == "r":
            self._last_action = "manual refresh"
        elif key == "d":
            self._view_mode = "main" if self._view_mode == "debug" else "debug"
        elif key == "l":
            self._view_mode = "main" if self._view_mode == "logs" else "logs"
        elif key == "s":
            self._pending_snapshot = True

    def _update_auto_exit_state(self) -> None:
        if not self._auto_exit:
            return

        snapshot = self.data_source.read_snapshot(self._request_id or None)
        status = str(snapshot.get("current_status", "pending"))
        if status in {"passed", "failed", "timeout", "aborted", "skipped"}:
            linger_seconds = self._linger_seconds_for_status(status)
            if linger_seconds is None:
                self._completed_at = None
                self._completed_status = status
                self._last_action = f"execution completed: {status}, waiting for manual quit"
                return
            if self._completed_at is None or self._completed_status != status:
                self._completed_at = datetime.now()
                self._completed_status = status
                self._last_action = f"execution completed: {status}"
                return
            elapsed = (datetime.now() - self._completed_at).total_seconds()
            if elapsed >= linger_seconds:
                self._running = False
            return

        self._completed_at = None
        self._completed_status = None

    def _linger_seconds_for_status(self, status: str) -> float | None:
        if status in {"passed", "skipped"}:
            return self._success_exit_linger_seconds
        if status in {"failed", "timeout", "aborted"}:
            return self._failure_exit_linger_seconds
        return None

    def _generate_layout(self) -> Layout:
        if self._view_mode == "debug":
            return self._create_debug_panel()
        if self._view_mode == "logs":
            return self._create_logs_panel()

        state = self._collect_state()
        layout = Layout()
        layout.split(
            Layout(name="title", size=3),
            Layout(name="base", size=3),
            Layout(name="system", size=5),
            Layout(name="mid", ratio=1),
            Layout(name="failures", size=6),
            Layout(name="footer", size=3),
        )
        layout["title"].update(self._create_title_panel())
        layout["base"].update(self._create_base_info_panel(state))
        layout["system"].update(self._create_system_panel(state["sys_info"]))
        layout["mid"].update(self._create_module_stats_panel(state))
        layout["failures"].update(self._create_recent_failures_panel(state))
        layout["footer"].update(self._create_footer())
        return layout

    def _collect_state(self) -> dict[str, Any]:
        snapshot = self.data_source.read_snapshot(self._request_id or None)
        if snapshot.get("request_id"):
            self._request_id = str(snapshot["request_id"])
        if not self._fixture_name:
            self._fixture_name = str(snapshot.get("fixture", {}).get("name", ""))
            if self._fixture_name and not self._fixture_config:
                self._fixture_config = self.data_source.load_fixture_config(self._fixture_name)

        cases = list(snapshot.get("cases", []))
        events = self.data_source.read_events(self._request_id or None)
        sys_info = self.data_source.read_system_info()
        counts = {
            "passed": sum(1 for case in cases if case.get("status") == "passed"),
            "failed": sum(1 for case in cases if case.get("status") == "failed"),
            "timeout": sum(1 for case in cases if case.get("status") == "timeout"),
            "aborted": sum(1 for case in cases if case.get("status") == "aborted"),
            "running": sum(1 for case in cases if case.get("status") == "running"),
            "skipped": sum(1 for case in cases if case.get("status") == "skipped"),
        }
        total = len(cases)
        retry_count = sum(1 for item in events if item.get("event", {}).get("event_type") == "task_retried")
        completed_count = counts["passed"] + counts["failed"] + counts["timeout"] + counts["aborted"] + counts["skipped"]
        wait_count = max(total - completed_count - counts["running"], 0)
        pass_rate = counts["passed"] / total * 100.0 if total else 0.0
        return {
            "snapshot": snapshot,
            "cases": cases,
            "events": events,
            "sys_info": sys_info,
            "pass_count": counts["passed"],
            "fail_count": counts["failed"],
            "timeout_count": counts["timeout"],
            "aborted_count": counts["aborted"],
            "running_count": counts["running"],
            "retry_count": retry_count,
            "wait_count": wait_count,
            "completed_count": completed_count,
            "total": total,
            "pass_rate": pass_rate,
            "current_status": snapshot.get("current_status", "pending"),
            "request_id": self._request_id,
        }

    def _create_title_panel(self) -> Panel:
        title = self._fixture_name or self._request_id or "Dashboard"
        return Panel(Text(f"Hardware Test Dashboard - {title}", style="bold white"))

    def _create_base_info_panel(self, state: dict[str, Any]) -> Panel:
        info = (
            f"status: {state['current_status']}  │  "
            f"elapsed: {self._elapsed_str()}  │  "
            f"cases: {state['completed_count']}/{max(1, state['total'])}"
        )
        return Panel(info)

    def _create_system_panel(self, sys_info: dict[str, Any]) -> Panel:
        cpu = sys_info.get("cpu", {})
        memory = sys_info.get("memory", {})
        storage = sys_info.get("storage", {})
        cpu_pct = self._to_float(cpu.get("usage_percent"))
        mem_pct = self._to_float(memory.get("usage_percent"))
        storage_pct = self._to_float(storage.get("usage_percent"))
        cpu_line = (
            f"CPU: {self._bar(cpu_pct)} {self._fmt_pct(cpu_pct)}  "
            f"freq: {cpu.get('frequency_mhz', 'N/A')}MHz  temp: {cpu.get('temperature', 'N/A')}°C"
        )
        mem_line = (
            f"MEM: {self._bar(mem_pct)} {memory.get('used_mb', 'N/A')}/{memory.get('total_mb', 'N/A')}MB  "
            f"DISK: {self._bar(storage_pct)} {storage.get('used_gb', 'N/A')}/{storage.get('total_gb', 'N/A')}GB"
        )
        return Panel(f"{cpu_line}\n{mem_line}", title="System")

    def _create_module_stats_panel(self, state: dict[str, Any]) -> Layout:
        wrapper = Layout()
        wrapper.split_row(
            Layout(self._create_module_table(state["cases"]), name="module"),
            Layout(self._create_stats_panel(state), name="stats", size=34),
        )
        return wrapper

    def _create_module_table(self, cases: list[dict[str, Any]]) -> Panel:
        table = Table(show_header=True, header_style="bold")
        table.add_column("Case", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Summary", style="white")
        if not cases:
            table.add_row("-", "[grey70]pending[/grey70]", "no snapshot data")
        for case in cases:
            table.add_row(
                str(case.get("name", "unknown")),
                self._status_display(str(case.get("status", "unknown"))),
                self._compact_case(case),
            )
        return Panel(table, title="Case Status")

    def _create_stats_panel(self, state: dict[str, Any]) -> Panel:
        lines = [
            f"pass rate: [green]{state['pass_rate']:.1f}%[/green]",
            f"passed: [green]{state['pass_count']}[/green]",
            f"failed: [red]{state['fail_count']}[/red]",
            f"timeout: [yellow]{state['timeout_count']}[/yellow]",
            f"aborted: [yellow]{state['aborted_count']}[/yellow]",
            f"running: [blue]{state['running_count']}[/blue]",
            f"retries: [yellow]{state['retry_count']}[/yellow]",
            f"waiting: [grey70]{state['wait_count']}[/grey70]",
        ]
        return Panel("\n".join(lines), title="Stats")

    def _create_recent_failures_panel(self, state: dict[str, Any]) -> Panel:
        lines = self._recent_failure_lines_from_snapshot(state.get("snapshot", {}))
        if not lines:
            for case in state["cases"]:
                if case.get("status") in {"failed", "aborted", "timeout"}:
                    lines.append(f"{case.get('name')}: {case.get('message') or case.get('status')}")
        if not lines:
            for event in reversed(state["events"]):
                event_payload = event.get("event", {})
                if event_payload.get("status") == "error":
                    lines.append(f"{event_payload.get('task_name')}: {event_payload.get('message')}")
                if len(lines) >= 3:
                    break
        if not lines:
            lines = ["No recent failures"]
        return Panel("\n".join(lines[:3]), title="Recent Failures")

    def _recent_failure_lines_from_snapshot(self, snapshot: dict[str, Any]) -> list[str]:
        lines: list[str] = []
        for case_result in self._extract_case_results(snapshot):
            if case_result.get("status") not in {"failed", "aborted", "timeout"}:
                continue
            detailed_failure = self._first_failed_leaf(case_result)
            if detailed_failure is None:
                case_name = str(case_result.get("name", "unknown"))
                case_message = str(case_result.get("message") or case_result.get("status") or "failed")
                lines.append(f"{case_name}: {case_message}")
                continue

            case_name = str(case_result.get("name", "unknown"))
            failure_name = str(detailed_failure.get("name") or detailed_failure.get("task_id") or "task")
            failure_message = str(detailed_failure.get("message") or detailed_failure.get("status") or "failed")
            lines.append(f"{case_name} / {failure_name}: {failure_message}")
        return lines

    def _extract_case_results(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        results = snapshot.get("results")
        if not isinstance(results, list):
            return []

        fixture_result = next(
            (
                item
                for item in results
                if isinstance(item, dict) and item.get("task_type") == "fixture" and isinstance(item.get("children"), list)
            ),
            None,
        )
        if fixture_result is not None:
            return [
                child
                for child in fixture_result.get("children", [])
                if isinstance(child, dict) and child.get("task_type") == "case"
            ]

        seen_task_ids: set[str] = set()
        case_results: list[dict[str, Any]] = []
        for item in results:
            if not isinstance(item, dict) or item.get("task_type") != "case":
                continue
            task_id = str(item.get("task_id", ""))
            if task_id and task_id in seen_task_ids:
                continue
            if task_id:
                seen_task_ids.add(task_id)
            case_results.append(item)
        return case_results

    def _first_failed_leaf(self, result: dict[str, Any]) -> dict[str, Any] | None:
        children = result.get("children")
        if not isinstance(children, list) or not children:
            return result if result.get("status") in {"failed", "aborted", "timeout"} else None

        for child in children:
            if not isinstance(child, dict):
                continue
            failed_leaf = self._first_failed_leaf(child)
            if failed_leaf is not None:
                return failed_leaf
        return None

    def _create_footer(self) -> Panel:
        controls = "Controls: [Q] quit  [R] refresh  [D] debug  [L] logs  [S] snapshot"
        if self._last_action:
            controls += f"  │  {self._last_action}"
        return Panel(controls, style="dim")

    def _create_debug_panel(self) -> Layout:
        state = self._collect_state()
        text = Text.assemble(
            ("Debug View\n\n", "bold"),
            f"fixture={self._fixture_name}\n",
            f"request_id={self._request_id}\n",
            f"status={state['current_status']}\n",
            f"tmp_dir={self.tmp_dir}\n",
            f"logs_dir={self.logs_dir}\n",
            f"reports_dir={self.reports_dir}\n\n",
            "Press [D] to return",
        )
        return Layout(Panel(text, title="Debug"))

    def _create_logs_panel(self) -> Layout:
        return Layout(Panel("\n".join(self.data_source.read_log_lines(self._request_id or None)), title="Logs"))

    def _save_snapshot(self, layout_obj: Any) -> None:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        request_id = self._request_id or "dashboard"
        path = self.reports_dir / f"dashboard_{request_id}_{timestamp}.txt"
        try:
            temp_console = Console(width=self.console.size.width, record=True, force_terminal=False)
            temp_console.print(layout_obj)
            path.write_text(temp_console.export_text(clear=False), encoding="utf-8")
            self._last_action = f"snapshot saved: {path.name}"
        except Exception as error:
            self._last_action = f"snapshot failed: {error}"

    def _status_display(self, status: str) -> str:
        if status == "passed":
            return "[green]✓ passed[/green]"
        if status in {"failed", "timeout"}:
            return "[red]✗ failed[/red]"
        if status == "aborted":
            return "[yellow]! aborted[/yellow]"
        if status == "running":
            return "[blue]⏳ running[/blue]"
        return f"[grey70]{status or 'pending'}[/grey70]"

    def _compact_case(self, case: dict[str, Any]) -> str:
        summary = case.get("summary", {})
        if isinstance(summary, dict) and summary:
            return ", ".join(f"{key}={value}" for key, value in sorted(summary.items()))
        return str(case.get("message") or "-")

    def _elapsed_str(self) -> str:
        if self._start_time is None:
            return "00:00:00"
        total = int((datetime.now() - self._start_time).total_seconds())
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _bar(self, value: float | None, width: int = 10) -> str:
        if value is None:
            return "[░░░░░░░░░░]"
        ratio = max(0.0, min(1.0, value / 100.0))
        fill = int(ratio * width)
        return "[" + ("█" * fill) + ("░" * (width - fill)) + "]"

    def _fmt_pct(self, value: float | None) -> str:
        return "N/A" if value is None else f"{value:.0f}%"

    def _to_float(self, value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


def run_dashboard(
    *,
    workspace_root: str | Path = ".",
    artifacts_root: str | Path = ".",
    fixture_name: str = "",
    request_id: str = "",
    refresh_interval: float = 1.0,
    start_monitor: bool = True,
    auto_exit: bool = False,
    success_exit_linger_seconds: float | None = 3.0,
    failure_exit_linger_seconds: float | None = None,
) -> None:
    outputs_root = Path(artifacts_root).resolve()
    dashboard = CLIDashboard(
        workspace_root=workspace_root,
        tmp_dir=outputs_root / "tmp",
        logs_dir=outputs_root / "logs",
        reports_dir=outputs_root / "reports",
        refresh_interval=refresh_interval,
        fixture_name=fixture_name,
        request_id=request_id,
        auto_exit=auto_exit,
        success_exit_linger_seconds=success_exit_linger_seconds,
        failure_exit_linger_seconds=failure_exit_linger_seconds,
    )
    try:
        dashboard.start(start_monitor=start_monitor)
    except KeyboardInterrupt:
        dashboard.stop()
