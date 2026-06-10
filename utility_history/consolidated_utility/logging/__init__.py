"""
consolidated_utility.logging
------------------------------
Structured, auditable logger with consistent formatting.
Every module in the package obtains its logger through get_logger() so all
output is controlled centrally.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional


class JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line for easy ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level":     record.levelname,
            "logger":    record.name,
            "message":   record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Merge any extra kwargs passed via logger.info("msg", extra={...})
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
            }:
                payload[key] = value
        return json.dumps(payload, default=str)


class AuditLogger:
    """
    Thin wrapper around stdlib logging that enforces JSON output and
    carries session/user context through every log line.

    Usage
    -----
    >>> logger = AuditLogger("history_module", session_id="abc", user_id="u1")
    >>> logger.info("Session loaded", extra={"record_count": 5})
    """

    def __init__(
        self,
        name:       str,
        level:      str            = "INFO",
        session_id: Optional[str]  = None,
        user_id:    Optional[str]  = None,
    ) -> None:
        self._base_extra: Dict[str, Any] = {}
        if session_id:
            self._base_extra["session_id"] = session_id
        if user_id:
            self._base_extra["user_id"] = user_id

        self._logger = logging.getLogger(name)
        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(JsonFormatter())
            self._logger.addHandler(handler)
        self._logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        self._logger.propagate = False

    def _merge(self, extra: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        merged = dict(self._base_extra)
        if extra:
            merged.update(extra)
        return merged

    def debug(self, msg: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self._logger.debug(msg, extra=self._merge(extra))

    def info(self, msg: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self._logger.info(msg, extra=self._merge(extra))

    def warning(self, msg: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self._logger.warning(msg, extra=self._merge(extra))

    def error(self, msg: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self._logger.error(msg, extra=self._merge(extra))

    def critical(self, msg: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self._logger.critical(msg, extra=self._merge(extra))


def get_logger(name: str, level: str = "INFO") -> AuditLogger:
    """Convenience factory for module-level loggers."""
    return AuditLogger(name, level=level)
