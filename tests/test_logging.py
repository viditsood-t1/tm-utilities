"""
tests/test_logging.py
----------------------
Tests for AuditLogger and get_logger.
"""

import json
import logging
import pytest

from consolidated_utility.logging import AuditLogger, get_logger


class TestAuditLogger:
    def test_info_emits_json(self, capsys):
        logger = AuditLogger("test.info", level="INFO")
        logger.info("test message")
        out = capsys.readouterr().out
        payload = json.loads(out.strip())
        assert payload["message"] == "test message"
        assert payload["level"] == "INFO"
        assert "timestamp" in payload

    def test_session_context_included(self, capsys):
        logger = AuditLogger("test.ctx", session_id="s1", user_id="u1")
        logger.info("ctx test")
        payload = json.loads(capsys.readouterr().out.strip())
        assert payload["session_id"] == "s1"
        assert payload["user_id"] == "u1"

    def test_extra_kwargs_merged(self, capsys):
        logger = AuditLogger("test.extra")
        logger.info("extra test", extra={"count": 42})
        payload = json.loads(capsys.readouterr().out.strip())
        assert payload["count"] == 42

    def test_warning_level(self, capsys):
        logger = AuditLogger("test.warn", level="WARNING")
        logger.warning("watch out")
        payload = json.loads(capsys.readouterr().out.strip())
        assert payload["level"] == "WARNING"

    def test_debug_suppressed_at_info_level(self, capsys):
        logger = AuditLogger("test.debug", level="INFO")
        logger.debug("should not appear")
        out = capsys.readouterr().out
        assert out == ""

    def test_error_level(self, capsys):
        logger = AuditLogger("test.err", level="ERROR")
        logger.error("something broke")
        payload = json.loads(capsys.readouterr().out.strip())
        assert payload["level"] == "ERROR"


class TestGetLogger:
    def test_returns_audit_logger(self):
        logger = get_logger("test.factory")
        assert isinstance(logger, AuditLogger)

    def test_custom_level(self, capsys):
        logger = get_logger("test.level", level="DEBUG")
        logger.debug("debug msg")
        out = capsys.readouterr().out
        assert "debug msg" in out
