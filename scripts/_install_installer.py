#!/usr/bin/env python3
"""Hardware-test-platform installer - main logic."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from _install_common import (
    Colors,
    check_command_exists,
    check_python_version,
    get_python_version,
    log_error,
    log_header,
    log_info,
    log_success,
    log_warn,
    retry_with_backoff,
    run_command,
)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Install or update hardware-test-platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Fresh install to ~/hardware-test-platform
  %(prog)s --install-dir /opt/htp   # Custom install directory
  %(prog)s --update-only            # Update existing installation
  %(prog)s --force                  # Force reinstall
  %(prog)s --dry-run                # Preview changes without executing
        """,
    )
    parser.add_argument(
        "--install-dir",
        type=str,
        default=None,
        help="Installation directory (default: ~/hardware-test-platform)",
    )
    parser.add_argument(
        "--branch",
        type=str,
        default="master",
        help="Git branch to clone (default: master)",
    )
    parser.add_argument(
        "--repo-owner",
        type=str,
        default="stellar",
        help="GitHub organization/owner (default: stellar)",
    )
    parser.add_argument(
        "--repo-name",
        type=str,
        default="hardware-test-platform",
        help="Repository name (default: hardware-test-platform)",
    )
    parser.add_argument(
        "--update-only",
        action="store_true",
        help="Only update existing installation, do not clone",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reinstall (overwrite existing installation)",
    )
    parser.add_argument(
        "--no-bashrc",
        action="store_true",
        help="Do not add alias to ~/.bashrc",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview actions without executing",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    return parser.parse_args()


def get_install_dir(explicit: str | None) -> Path:
    """Resolve installation directory."""
    if explicit:
        return Path(explicit).expanduser().resolve()
    return (Path.home() / "hardware-test-platform").resolve()


def check_prerequisites() -> bool:
    """Check system prerequisites."""
    log_header("Checking prerequisites")

    all_ok = True

    # Check Python
    if not check_command_exists("python3"):
        log_error("python3 not found in PATH")
        all_ok = False
    else:
        if not check_python_version():
            log_error(f"Python 3.8+ required, found {get_python_version()}")
            all_ok = False
        else:
            log_info(f"Python {get_python_version()} found")

    # Check git
    if not check_command_exists("git"):
        log_error("git not found in PATH")
        all_ok = False
    else:
        log_info("git found")

    # Check curl
    if not check_command_exists("curl"):
        log_error("curl not found in PATH")
        all_ok = False
    else:
        log_info("curl found")

    return all_ok


def is_git_repo(path: Path) -> bool:
    """Check if path is a git repository."""
    git_dir = path / ".git"
    return git_dir.exists() and git_dir.is_dir()


def get_current_branch(repo_path: Path) -> str | None:
    """Get current git branch of a repository."""
    try:
        result = run_command(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(repo_path),
            capture=True,
            check=True,
        )
        return result.stdout.strip()
    except RuntimeError:
        return None


def needs_dependency_update(repo_path: Path) -> bool:
    """Check if dependencies need to be updated."""
    venv_python = repo_path / "venv" / "bin" / "python"
    if not venv_python.exists():
        return True

    # Check if requirements.txt has been modified since venv creation
    requirements_file = repo_path / "requirements.txt"
    if not requirements_file.exists():
        return False

    try:
        # Try importing a core dependency
        test_imports = ["rich", "serial"]
        for mod in test_imports:
            run_command(
                [str(venv_python), "-c", f"import {mod}"],
                capture=True,
                check=True,
            )
        return False
    except RuntimeError:
        return True


def clone_repo(
    repo_url: str,
    branch: str,
    target_dir: Path,
    *,
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    """Clone repository to target directory."""

    def _clone() -> None:
        run_command(
            ["git", "clone", "--branch", branch, "--depth", "1", repo_url, str(target_dir)],
            check=True,
        )

    if dry_run:
        log_info(f"[DRY-RUN] Would clone {repo_url} ({branch}) to {target_dir}")
        return

    log_info(f"Cloning {repo_url} (branch: {branch})...")
    retry_with_backoff(_clone, operation="Git clone")
    log_success(f"Repository cloned to {target_dir}")


def update_repo(
    repo_path: Path,
    branch: str,
    *,
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    """Update existing repository."""

    def _fetch() -> None:
        run_command(["git", "fetch", "origin", branch], cwd=str(repo_path), check=True)

    def _pull() -> None:
        run_command(["git", "pull", "--ff-only"], cwd=str(repo_path), check=True)

    if dry_run:
        log_info(f"[DRY-RUN] Would update repository at {repo_path}")
        return

    log_info("Updating repository...")
    retry_with_backoff(_fetch, operation="Git fetch")
    _pull()
    log_success("Repository updated")


def create_venv(
    repo_path: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    """Create virtual environment."""
    venv_path = repo_path / "venv"

    if dry_run:
        if venv_path.exists() and not force:
            log_info(f"[DRY-RUN] Would reuse existing venv at {venv_path}")
        else:
            if force and venv_path.exists():
                log_info(f"[DRY-RUN] Would remove existing venv at {venv_path}")
            log_info(f"[DRY-RUN] Would create venv at {venv_path}")
        return

    if venv_path.exists():
        if force:
            log_info(f"Removing existing venv at {venv_path}")
            shutil.rmtree(venv_path)
        else:
            log_info(f"Reusing existing venv at {venv_path}")
            return

    log_info("Creating virtual environment...")
    run_command([sys.executable, "-m", "venv", str(venv_path)], check=True)
    log_success(f"Virtual environment created at {venv_path}")


def install_dependencies(
    repo_path: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    """Install Python dependencies."""
    venv_python = repo_path / "venv" / "bin" / "python"
    requirements_file = repo_path / "requirements.txt"

    if not requirements_file.exists():
        log_warn("requirements.txt not found, skipping dependency installation")
        return

    if dry_run:
        log_info(f"[DRY-RUN] Would install dependencies from {requirements_file}")
        return

    if not needs_dependency_update(repo_path) and not force:
        log_info("Dependencies already installed and up-to-date")
        return

    log_info("Installing dependencies...")
    pip_args = [
        str(venv_python),
        "-m",
        "pip",
        "install",
        "--upgrade",
        "pip",
    ]
    run_command(pip_args, check=True)

    pip_args = [
        str(venv_python),
        "-m",
        "pip",
        "install",
        "--no-cache-dir",
        "-r",
        str(requirements_file),
    ]
    run_command(pip_args, check=True)
    log_success("Dependencies installed")


def add_bashrc_alias(
    install_dir: Path,
    *,
    no_bashrc: bool = False,
    dry_run: bool = False,
) -> None:
    """Add alias to ~/.bashrc."""
    bashrc = Path.home() / ".bashrc"
    alias_name = "htp"
    alias_cmd = f"alias {alias_name}='cd {install_dir} && source venv/bin/activate'"

    if no_bashrc:
        return

    if dry_run:
        log_info(f"[DRY-RUN] Would add to {bashrc}: {alias_cmd}")
        return

    # Check if alias already exists
    if bashrc.exists():
        content = bashrc.read_text()
        if alias_cmd in content:
            log_info(f"Alias already exists in {bashrc}")
            return

    # Add alias
    log_info(f"Adding shortcut alias to {bashrc}...")
    with open(bashrc, "a") as f:
        f.write(f"\n# hardware-test-platform alias (added by installer)\n{alias_cmd}\n")
    log_success(f"Added alias: '{alias_name}' -> cd to {install_dir}")


def print_completion_message(
    install_dir: Path,
    *,
    dry_run: bool = False,
) -> None:
    """Print installation completion message."""
    log_header("Installation Complete")

    venv_python = install_dir / "venv" / "bin" / "python"
    activate_script = install_dir / "venv" / "bin" / "activate"

    print(f"  Installation directory: {Colors.BOLD}{install_dir}{Colors.RESET}")
    print()
    print(f"  {Colors.BOLD}Quick start:{Colors.RESET}")
    print(f"    cd {install_dir}")
    print(f"    source venv/bin/activate")
    print()
    print(f"  {Colors.BOLD}Or use the alias (if added to bashrc):{Colors.RESET}")
    print(f"    htp")
    print()
    print(f"  {Colors.BOLD}Run tests:{Colors.RESET}")
    print(f"    {venv_python} -m pytest")
    print()
    print(f"  {Colors.BOLD}Update later:{Colors.RESET}")
    print(f"    curl -sSL https://raw.githubusercontent.com/stellar/hardware-test-platform/master/scripts/install.sh | bash -s -- --update-only")
    print()


def main() -> int:
    """Main entry point."""
    args = parse_args()

    if args.dry_run:
        log_warn("DRY-RUN MODE - No changes will be made")

    # Check prerequisites
    if not check_prerequisites():
        log_error("Prerequisites check failed")
        return 1

    # Resolve installation directory
    install_dir = get_install_dir(args.install_dir)

    log_header("Installation Summary")
    print(f"  Install directory: {install_dir}")
    print(f"  Repository: {args.repo_owner}/{args.repo_name}@{args.branch}")
    print(f"  Force reinstall: {args.force}")
    print(f"  Update only: {args.update_only}")
    print(f"  Dry run: {args.dry_run}")
    print()

    # Determine action
    is_installed = install_dir.exists() and is_git_repo(install_dir)

    if args.update_only and not is_installed:
        log_error("--update-only specified but no installation found at {install_dir}")
        return 1

    if is_installed and not args.force and not args.update_only:
        log_warn(f"Directory {install_dir} already exists and is a git repository")
        log_info("Use --force to overwrite or --update-only to update")
        return 1

    try:
        if is_installed and (args.force or args.update_only):
            # Update existing installation
            update_repo(
                install_dir,
                args.branch,
                dry_run=args.dry_run,
                verbose=args.verbose,
            )
        elif not is_installed:
            # Fresh installation
            repo_url = f"https://github.com/{args.repo_owner}/{args.repo_name}.git"
            clone_repo(
                repo_url,
                args.branch,
                install_dir,
                dry_run=args.dry_run,
                verbose=args.verbose,
            )

        if is_installed or not args.dry_run:
            # Create venv and install dependencies
            create_venv(
                install_dir,
                force=args.force,
                dry_run=args.dry_run,
                verbose=args.verbose,
            )
            install_dependencies(
                install_dir,
                force=args.force,
                dry_run=args.dry_run,
                verbose=args.verbose,
            )

            # Add bashrc alias
            add_bashrc_alias(
                install_dir,
                no_bashrc=args.no_bashrc,
                dry_run=args.dry_run,
            )

        if not args.dry_run:
            print_completion_message(install_dir)
        else:
            log_header("Dry-run complete")
            print("  Review the actions above. Remove --dry-run to execute.")

        return 0

    except RuntimeError as e:
        log_error(str(e))
        return 1
    except KeyboardInterrupt:
        log_warn("\nInstallation cancelled by user")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
