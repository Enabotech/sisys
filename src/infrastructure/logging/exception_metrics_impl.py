"""SISYS 基础设施层异常指标实现模块

提供异常监控指标的基础设施层实现，支持 Prometheus 格式导出

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock

from src.application.ports.exception_metrics_port import ExceptionMetricsPort


@dataclass
class ExceptionMetricsImpl(ExceptionMetricsPort):
    """异常指标收集器（线程安全）

    提供简单的异常计数指标，支持 Prometheus 格式导出

    Attributes:
        _counters: 异常计数字典，键为异常类型或异常类型:错误码
        _lock: 线程锁，保证并发安全
    """

    _counters: dict[str, int] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def record_exception(self, exception_type: str, code: str | None = None) -> None:
        """记录异常发生.

        Args:
            exception_type: 异常类型名称（如 "ValidationError"）
            code: 可选的错误码
        """
        key = f"{exception_type}:{code}" if code else exception_type
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + 1

    def get_counter(self, exception_type: str, code: str | None = None) -> int:
        """获取异常计数.

        Args:
            exception_type: 异常类型名称
            code: 可选的错误码

        Returns:
            异常计数
        """
        key = f"{exception_type}:{code}" if code else exception_type
        with self._lock:
            return self._counters.get(key, 0)

    def collect(self) -> bytes:
        """收集指标并返回 Prometheus 文本格式.

        Returns:
            Prometheus 文本格式的指标字节串
        """
        lines = ["# HELP sisys_exception_total Total number of exceptions by type"]
        lines.append("# TYPE sisys_exception_total counter")

        with self._lock:
            for key, count in sorted(self._counters.items()):
                exception_type, code = key.split(":", 1) if ":" in key else (key, "")
                labels = f'exception_type="{exception_type}"'
                if code:
                    labels += f', code="{code}"'
                lines.append(f"sisys_exception_total{{{labels}}} {count}")

        lines.append("")
        return "\n".join(lines).encode("utf-8")

    def collect_as_dict(self) -> dict[str, int]:
        """收集所有指标并返回字典格式.

        Returns:
            指标名称到指标值的字典
        """
        with self._lock:
            return dict(self._counters)

    def reset(self) -> None:
        """重置所有计数器（用于测试）。"""
        with self._lock:
            self._counters.clear()


# 全局单例实例
_exception_metrics: ExceptionMetricsPort | None = None
_metrics_lock: Lock = Lock()


def get_exception_metrics() -> ExceptionMetricsPort:
    """获取全局异常指标实例

    Returns:
        ExceptionMetricsPort 单例
    """
    global _exception_metrics
    with _metrics_lock:
        if _exception_metrics is None:
            _exception_metrics = ExceptionMetricsImpl()
        return _exception_metrics
