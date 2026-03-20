#!/usr/bin/env python3
"""Common utilities for hardware-test-platform installer."""

from __future__ import annotations

import subprocess
import sys
import time
from typing import Callable


class Colors:
    """ANSI color codes for terminal output."""

    BLUE = "\033[94m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def log_info(message: str) -> None:
    """Print info message in blue."""
    print(f"{Colors.BLUE}[INFO]{Colors.RESET} {message}")


def log_success(message: str) -> None:
    """Print success message in green."""
    print(f"{Colors.GREEN}[SUCCESS]{Colors.RESET} {message}")


def log_error(message: str) -> None:
    """Print error message in red."""
    print(f"{Colors.RED}[ERROR]{Colors.RESET} {message}")


def log_warn(message: str) -> None:
    """Print warning message in yellow."""
    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {message}")


def log_header(message: str) -> None:
    """Print header message in bold blue."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}== {message} =={Colors.RESET}\n")


def run_command(
    command: list[str],
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    capture: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """Run a shell command with error handling.

    Args:
        command: Command and arguments as a list.
        cwd: Working directory (optional).
        env: Environment variables (optional).
        capture: If True, capture stdout/stderr.
        check: If True, raise on non-zero exit code.

    Returns:
        CompletedProcess instance.

    Raises:
        RuntimeError: If command fails and check=True.
    """
    merged_env = dict(**(env or {}), **dict(subprocess.os.environ))
    result = subprocess.run(
        command,
        cwd=cwd,
        env=merged_env,
        capture_output=capture,
        text=True,
    )
    if check and result.returncode != 0:
        error_msg = f"Command failed: {' '.join(command)}"
        if result.stderr:
            error_msg += f"\n{result.stderr}"
        raise RuntimeError(error_msg)
    return result


def retry_with_backoff(
    func: Callable[[], None],
    *,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    operation: str = "Operation",
) -> None:
    """Retry a function with exponential backoff.

    Args:
        func: Function to retry.
        max_retries: Maximum number of retry attempts.
        initial_delay: Initial delay in seconds.
        backoff_factor: Multiplier for delay after each retry.
        operation: Human-readable operation name for logging.

    Raises:
        RuntimeError: If all retries fail.
    """
    delay = initial_delay
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            func()
            return
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                log_warn(f"{operation} failed (attempt {attempt + 1}/{max_retries}): {e}")
                log_info(f"Retrying in {delay:.1f} seconds...")
                time.sleep(delay)
                delay *= backoff_factor
            else:
                log_error(f"{operation} failed after {max_retries} attempts")

    if last_error:
        raise RuntimeError(f"{operation} failed: {last_error}")


def check_command_exists(command: str) -> bool:
    """Check if a command exists in PATH."""
    import shutil

    return shutil.which(command) is not None


def get_python_version() -> str:
    """Get Python version string."""
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def check_python_version() -> bool:
    """Check if Python version is 3.8+."""
    return sys.version_info >= (3, 8)
