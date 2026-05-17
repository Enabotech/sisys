"""SISYS 基础设施层异常日志模块

提供异常结构化日志格式化和统一日志配置

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any


class ExceptionJsonFormatter(logging.Formatter):
    """异常结构化日志格式化器

    将异常信息格式化为 JSON 结构，便于日志分析和检索
    """

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录

        包含异常信息时输出结构化错误 JSON，否则输出标准日志 JSON

        Args:
            record: 标准库日志记录对象

        Returns:
            JSON 格式的日志字符串
        """
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
