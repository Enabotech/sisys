"""异常结构化日志处理器.

提供统一的异常日志格式化，便于日志分析。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any


class ExceptionJsonFormatter(logging.Formatter):
    """异常结构化日志格式化器."""

    def format(self, record: logging.LogRecord) -> str:
        if record.exc_info and record.exc_info[0]:
            exc = record.exc_info[1]
            if exc is not None:
                return self._format_exception(record, exc)
        return self._format_standard(record)

    def _format_exception(self, record: logging.LogRecord, exc: Any) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "error": {
                "code": getattr(exc, "code", None) or "EXCEPTION_000",
                "message": getattr(exc, "message", None) or str(exc),
                "context": getattr(exc, "context", None) or {},
            },
        }
        cause = getattr(exc, "cause", None)
        if cause:
            log_entry["error"]["cause"] = {
                "type": type(cause).__name__,
                "message": str(cause),
            }
        return json.dumps(log_entry)

    def _format_standard(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(log_entry)


def configure_exception_logging() -> None:
    """配置异常日志处理器."""
    handler = logging.StreamHandler()
    handler.setFormatter(ExceptionJsonFormatter())

    logger = logging.getLogger("exception")
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)
