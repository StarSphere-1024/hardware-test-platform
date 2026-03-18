#!/usr/bin/env python3
"""Package workspace sources and deploy them to a remote board for offline execution."""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

SOURCE_EXCLUDES = {
    ".git",
    ".venv",
    ".pytest_cache",
    "__pycache__",
    "wheelhouse",
    "wheels",
    "logs",
    "tmp",
    "reports",
    "remote-artifacts",
}
DEFAULT_WHEELHOUSE_CANDIDATES = ("wheelhouse", "wheels", ".offline/wheelhouse")
CORE_DEPENDENCIES = ["rich>=14.0.0,<15.0.0", "pyserial>=3.5,<4.0.0"]
OPTIONAL_DEPENDENCIES = ["psutil>=7.0.0,<8.0.0"]
OPTIONAL_BUILD_DEPENDENCIES = ["setuptools>=43", "wheel"]


def quote_args(values: list[str]) -> str:
    return " ".join(shlex.quote(value) for value in values)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Deploy hardware-test-platform sources and offline "
            "dependencies to a remote board."
        ),
    )
    parser.add_argument("host", nargs="?", default=os.getenv("REMOTE_HOST"))
    parser.add_argument("user", nargs="?", default=os.getenv("REMOTE_USER"))
    parser.add_argument("password", nargs="?", default=os.getenv("REMOTE_PASS"))
    parser.add_argument("remote_dir", nargs="?", default=os.getenv("REMOTE_DIR"))
    parser.add_argument(
        "--wheelhouse",
        default=None,
        help="local directory holding offline dependency artifacts",
    )
    parser.add_argument(
        "--download-missing",
        action="store_true",
        help="download missing runtime dependencies into the wheelhouse before deploy",
    )
    parser.add_argument(
        "--skip-psutil",
        action="store_true",
        help="skip optional psutil preparation for remote dashboard metrics",
    )
    parser.add_argument(
        "--skip-venv",
        action="store_true",
        help="reuse existing remote virtual environment",
    )
    parser.add_argument(
        "--skip-deps",
        action="store_true",
        help="reuse existing remote wheelhouse and dependency installation",
    )
    parser.add_argument(
        "--fast-reuse",
        action="store_true",
        help="shortcut for reusing remote venv and dependency layer, only sync sources",
    )
    return parser.parse_args()


def fail(message: str, code: int = 2) -> int:
    print(f"[ERROR] {message}")
    return code


def find_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_wheelhouse(repo_root: Path, explicit: str | None) -> Path:
    if explicit:
        return (
            (repo_root / explicit).resolve()
            if not Path(explicit).is_absolute()
            else Path(explicit)
        )
    for candidate in DEFAULT_WHEELHOUSE_CANDIDATES:
        path = repo_root / candidate
        if path.exists():
            return path.resolve()
    return (repo_root / DEFAULT_WHEELHOUSE_CANDIDATES[0]).resolve()


def ensure_sshpass() -> None:
    if shutil.which("sshpass") is None:
        raise RuntimeError("sshpass not found. Please install sshpass first.")


def run_command(
    command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None
) -> None:
    result = subprocess.run(command, cwd=str(cwd) if cwd else None, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(command)}")


def ensure_dependency_artifacts(
    wheelhouse: Path, *, download_missing: bool, skip_psutil: bool
) -> None:
    wheelhouse.mkdir(parents=True, exist_ok=True)
    runtime_missing = not any(wheelhouse.iterdir())
    if runtime_missing and not download_missing:
        raise RuntimeError(
            f"wheelhouse is empty: {wheelhouse}. "
            "Use --download-missing or pre-populate it first.",
        )

    if download_missing:
        run_command(
            [
                sys.executable,
                "-m",
                "pip",
                "download",
                "--dest",
                str(wheelhouse),
                *CORE_DEPENDENCIES,
            ],
        )
        if not skip_psutil:
            run_command(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "download",
                    "--dest",
                    str(wheelhouse),
                    "--no-binary",
                    "psutil",
                    *OPTIONAL_DEPENDENCIES,
                ],
            )
            run_command(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "download",
                    "--dest",
                    str(wheelhouse),
                    *OPTIONAL_BUILD_DEPENDENCIES,
                ],
            )

    artifact_names = [item.name for item in wheelhouse.iterdir() if item.is_file()]
    if not any(name.startswith("rich-") for name in artifact_names):
        raise RuntimeError(f"missing rich artifact in wheelhouse: {wheelhouse}")
    if not any(name.startswith("pyserial-") for name in artifact_names):
        raise RuntimeError(f"missing pyserial artifact in wheelhouse: {wheelhouse}")
    if not skip_psutil and not any(
        name.startswith("psutil-") for name in artifact_names
    ):
        raise RuntimeError(f"missing psutil artifact in wheelhouse: {wheelhouse}")
    if not skip_psutil and not any(
        name.startswith("setuptools-") for name in artifact_names
    ):
        raise RuntimeError(
            f"missing setuptools artifact for psutil build in wheelhouse: {wheelhouse}"
        )
    if not skip_psutil and not any(
        name.startswith("wheel-") for name in artifact_names
    ):
        raise RuntimeError(
            f"missing wheel artifact for psutil build in wheelhouse: {wheelhouse}"
        )


def should_skip(path: Path) -> bool:
    parts = set(path.parts)
    return any(name in parts for name in SOURCE_EXCLUDES)


def collect_source_entries(repo_root: Path) -> list[str]:
    entries: set[str] = set()
    for path in sorted(repo_root.rglob("*")):
        relative = path.relative_to(repo_root)
        if should_skip(relative):
            continue
        entries.add(relative.parts[0])
    return sorted(entries)


def build_source_bundle(repo_root: Path, output_path: Path) -> None:
    with tarfile.open(output_path, "w:gz") as archive:
        for path in sorted(repo_root.rglob("*")):
            if path == output_path:
                continue
            relative = path.relative_to(repo_root)
            if should_skip(relative):
                continue
            archive.add(path, arcname=str(relative), recursive=False)


def build_wheelhouse_bundle(wheelhouse: Path, output_path: Path) -> None:
    with tarfile.open(output_path, "w:gz") as archive:
        for path in sorted(wheelhouse.iterdir()):
            if path.is_file():
                archive.add(path, arcname=path.name)


def ssh_env(password: str) -> dict[str, str]:
    env = dict(os.environ)
    env["SSHPASS"] = password
    return env


def ssh_base_args(host: str, user: str) -> list[str]:
    return [
        "sshpass",
        "-e",
        "ssh",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "ConnectTimeout=5",
        f"{user}@{host}",
    ]


def scp_base_args(host: str, user: str) -> list[str]:
    return [
        "sshpass",
        "-e",
        "scp",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "ConnectTimeout=5",
    ]


def deploy_to_remote(
    *,
    host: str,
    user: str,
    password: str,
    remote_dir: str,
    source_bundle: Path,
    managed_entries: list[str],
    wheelhouse_bundle: Path | None,
    skip_venv: bool,
    skip_deps: bool,
    skip_psutil: bool,
) -> None:
    env = ssh_env(password)
    remote_venv = f"{remote_dir}/venv"
    remote_wheelhouse = f"{remote_dir}/wheelhouse"
    remote_source_bundle = f"{remote_dir}/source_bundle.tar.gz"
    remote_wheelhouse_bundle = f"{remote_dir}/wheelhouse.tar.gz"

    run_command(
        [*ssh_base_args(host, user), f"mkdir -p '{remote_dir}'"],
        env=env,
    )
    run_command(
        [
            *scp_base_args(host, user),
            str(source_bundle),
            f"{user}@{host}:{remote_source_bundle}",
        ],
        env=env,
    )

    if not skip_deps:
        if wheelhouse_bundle is None:
            raise RuntimeError(
                "wheelhouse bundle is required when dependency sync is enabled"
            )
        run_command(
            [
                *scp_base_args(host, user),
                str(wheelhouse_bundle),
                f"{user}@{host}:{remote_wheelhouse_bundle}",
            ],
            env=env,
        )

    remote_setup_lines = [
        "set -e",
        f"mkdir -p '{remote_dir}'",
        f"rm -rf '{remote_dir}/workspace'",
    ]
    for entry in managed_entries:
        remote_setup_lines.append(f"rm -rf '{remote_dir}/{entry}'")
    remote_setup_lines.append(f"tar -xzf '{remote_source_bundle}' -C '{remote_dir}'")
    if not skip_deps:
        remote_setup_lines.extend(
            [
                f"rm -rf '{remote_wheelhouse}'",
                f"mkdir -p '{remote_wheelhouse}'",
                f"tar -xzf '{remote_wheelhouse_bundle}' -C '{remote_wheelhouse}'",
            ]
        )
    if not skip_venv:
        remote_setup_lines.extend(
            [f"rm -rf '{remote_venv}'", f"python3 -m venv '{remote_venv}'"]
        )
    else:
        remote_setup_lines.extend(
            [
                f"if [ ! -x '{remote_venv}/bin/python' ]; then",
                (
                    "  echo '[ERROR] remote venv missing at {remote_venv}; "
                    "rerun without --skip-venv or --fast-reuse to create it'"
                ),
                "  exit 2",
                "fi",
            ]
        )
    if not skip_deps:
        remote_setup_lines.append(
            f"'{remote_venv}/bin/pip' install --no-index "
            f"--find-links='{remote_wheelhouse}' {quote_args(CORE_DEPENDENCIES)}"
        )
        if not skip_psutil:
            remote_setup_lines.extend(
                [
                    "if command -v gcc >/dev/null 2>&1; then",
                    (
                        f"  if ! '{remote_venv}/bin/pip' install --no-index "
                        f"--find-links='{remote_wheelhouse}' "
                        f"{quote_args(OPTIONAL_DEPENDENCIES)}; then"
                    ),
                    (
                        "    echo '[WARN] optional psutil install failed; "
                        "dashboard system metrics will be unavailable'"
                    ),
                    "  fi",
                    "else",
                    (
                        "  echo '[WARN] gcc not found on remote host, "
                        "skip optional psutil install'"
                    ),
                    "fi",
                ]
            )
    remote_setup_lines.append(
        f"rm -f '{remote_source_bundle}' '{remote_wheelhouse_bundle}'"
    )
    run_command([*ssh_base_args(host, user), "\n".join(remote_setup_lines)], env=env)


def main() -> int:
    args = parse_args()
    if not args.host:
        return fail(
            "remote host is required, pass it as an argument or set REMOTE_HOST"
        )
    if not args.user:
        return fail(
            "remote user is required, pass it as an argument or set REMOTE_USER"
        )
    if not args.password:
        return fail(
            "remote password is required, pass it as an argument or set REMOTE_PASS"
        )
    if not args.remote_dir:
        return fail("remote_dir is required, pass it as an argument or set REMOTE_DIR")
    if args.fast_reuse:
        args.skip_venv = True
        args.skip_deps = True

    repo_root = find_repo_root()
    try:
        ensure_sshpass()
        wheelhouse = resolve_wheelhouse(repo_root, args.wheelhouse)
        if not args.skip_deps:
            ensure_dependency_artifacts(
                wheelhouse,
                download_missing=args.download_missing,
                skip_psutil=args.skip_psutil,
            )

        with tempfile.TemporaryDirectory(prefix="htp-remote-") as temp_dir:
            temp_root = Path(temp_dir)
            source_bundle = temp_root / "source_bundle.tar.gz"
            wheelhouse_bundle = temp_root / "wheelhouse.tar.gz"
            managed_entries = collect_source_entries(repo_root)
            build_source_bundle(repo_root, source_bundle)
            if not args.skip_deps:
                build_wheelhouse_bundle(wheelhouse, wheelhouse_bundle)
            deploy_to_remote(
                host=args.host,
                user=args.user,
                password=args.password,
                remote_dir=args.remote_dir,
                source_bundle=source_bundle,
                managed_entries=managed_entries,
                wheelhouse_bundle=None if args.skip_deps else wheelhouse_bundle,
                skip_venv=args.skip_venv,
                skip_deps=args.skip_deps,
                skip_psutil=args.skip_psutil,
            )
        print("[INFO] Remote deployment completed")
        print(f"[INFO] Remote project root: {args.remote_dir}")
        print(f"[INFO] Remote venv: {args.remote_dir}/venv")
        return 0
    except RuntimeError as error:
        return fail(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
