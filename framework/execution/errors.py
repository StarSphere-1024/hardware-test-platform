"""Execution-layer error types."""

from __future__ import annotations


class ExecutionError(Exception):
    """Base execution error."""


class UnsupportedExecutionModeError(ExecutionError):
    """Raised when the current scheduler cannot handle an execution mode."""


class FunctionNotRegisteredError(ExecutionError):
    """Raised when a function name cannot be resolved to an executable."""


class TaskExecutionError(ExecutionError):
    """Raised when a task payload is malformed or cannot be executed."""
