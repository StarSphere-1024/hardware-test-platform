"""CLI entrypoint for dashboard rendering."""

from __future__ import annotations

from framework.dashboard import run_dashboard

from .common import normalize_cli_args


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Render the terminal dashboard")
    parser.add_argument("--workspace-root", default=".", help="workspace root for fixture lookup")
    parser.add_argument("--artifacts-root", default=".", help="root directory containing tmp/logs/reports")
    parser.add_argument("--fixture", default="", help="fixture name to display")
    parser.add_argument("--request-id", default="", help="explicit request id to display")
    parser.add_argument("--refresh", type=float, default=1.0, help="refresh interval in seconds")
    parser.add_argument("--no-monitor", action="store_true", help="disable background system monitoring")
    args = parser.parse_args(argv)
    args = normalize_cli_args(args)

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
