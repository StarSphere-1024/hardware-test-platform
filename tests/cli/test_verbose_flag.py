"""Tests for --verbose CLI flag and verbose logging support."""

from __future__ import annotations

import logging
from pathlib import Path
import tempfile


from framework.cli.common import create_base_parser
from framework.observability.logger import UnifiedLogger


class TestVerboseFlagParsing:
    """Test that --verbose flag is correctly parsed by CLI."""

    def test_verbose_flag_not_present_by_default(self) -> None:
        """Verify --verbose is False when not provided."""
        parser = create_base_parser(description="test")
        args = parser.parse_args([])
        assert args.verbose is False

    def test_verbose_short_flag(self) -> None:
        """Verify -v enables verbose mode."""
        parser = create_base_parser(description="test")
        args = parser.parse_args(["-v"])
        assert args.verbose is True

    def test_verbose_long_flag(self) -> None:
        """Verify --verbose enables verbose mode."""
        parser = create_base_parser(description="test")
        args = parser.parse_args(["--verbose"])
        assert args.verbose is True


class TestUnifiedLoggerVerbose:
    """Test UnifiedLogger respects verbose_level parameter."""

    def test_logger_default_level_is_info(self) -> None:
        """Verify default log level is INFO without verbose."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger_instance = UnifiedLogger(logs_dir=tmpdir)
            test_logger = logger_instance.get_logger("test_request")
            assert test_logger.level == logging.INFO

    def test_logger_verbose_level_1_sets_debug(self) -> None:
        """Verify verbose_level=1 sets log level to DEBUG."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # This test will fail until we implement verbose_level support
            logger_instance = UnifiedLogger(logs_dir=tmpdir, verbose_level=1)
            test_logger = logger_instance.get_logger("test_request")
            assert test_logger.level == logging.DEBUG

    def test_logger_verbose_level_0_is_info(self) -> None:
        """Verify verbose_level=0 keeps log level at INFO."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger_instance = UnifiedLogger(logs_dir=tmpdir, verbose_level=0)
            test_logger = logger_instance.get_logger("test_request")
            assert test_logger.level == logging.INFO

    def test_logger_debug_messages_visible_in_verbose_mode(
        self, tmp_path: Path
    ) -> None:
        """Verify debug messages are logged when verbose mode is enabled."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        logger_instance = UnifiedLogger(logs_dir=logs_dir, verbose_level=1)
        test_logger = logger_instance.get_logger("debug_test")

        # Debug message should be logged
        test_logger.debug("debug message for verbose mode")

        # Read the log file and verify debug message is present
        log_file = logs_dir / "debug_test.log"
        assert log_file.exists()
        log_content = log_file.read_text(encoding="utf-8")
        assert "debug message for verbose mode" in log_content

    def test_logger_debug_messages_hidden_in_non_verbose_mode(
        self, tmp_path: Path
    ) -> None:
        """Verify debug messages are NOT logged when verbose mode is disabled."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        logger_instance = UnifiedLogger(logs_dir=logs_dir, verbose_level=0)
        test_logger = logger_instance.get_logger("nodebug_test")

        # Debug message should NOT be logged
        test_logger.debug("this should not appear")
        test_logger.info("info message should appear")

        # Read the log file and verify debug message is NOT present
        log_file = logs_dir / "nodebug_test.log"
        assert log_file.exists()
        log_content = log_file.read_text(encoding="utf-8")
        assert "this should not appear" not in log_content
        assert "info message should appear" in log_content
