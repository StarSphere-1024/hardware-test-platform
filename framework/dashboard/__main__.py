"""Module entrypoint for the terminal dashboard."""

from __future__ import annotations

import argparse

from .cli_dashboard import run_dashboard


def main() -> int:
    parser = argparse.ArgumentParser(description="Terminal dashboard for hardware test execution")
    parser.add_argument("--workspace-root", default=".", help="workspace root for fixture lookup")
    parser.add_argument("--artifacts-root", default=".", help="root directory containing tmp/logs/reports")
    parser.add_argument("--fixture", default="", help="fixture name to display")
    parser.add_argument("--request-id", default="", help="explicit request id to display")
    parser.add_argument("--refresh", type=float, default=1.0, help="refresh interval in seconds")
    parser.add_argument("--no-monitor", action="store_true", help="disable background system monitoring")
    args = parser.parse_args()

    run_dashboard(
        workspace_root=args.workspace_root,
        artifacts_root=args.artifacts_root,
        fixture_name=args.fixture,
        request_id=args.request_id,
        refresh_interval=args.refresh,
        start_monitor=not args.no_monitor,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
