"""EventMetrics + EventMetricsCollector + OpenTelemetryTracer — 基础设施层实现。

Task 5.1: EventMetrics + EventMetricsCollector 基础计数器
Task 5.2: OpenTelemetry Trace 基础版（span 创建+属性，默认关闭导出）
"""

from __future__ import annotations

import logging
import os
from collections import deque
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# Task 5.1: EventMetrics + EventMetricsCollector
# ============================================================================


@dataclass
class EventMetrics:
    """事件处理指标。

    基础计数器，不暴露 Prometheus HTTP 端点（移至 Story 1.13）。

    Attributes:
        events_processed_total: 成功处理事件总数
        events_failed_total: 失败事件总数
        events_retried_total: 重试事件总数
        events_dlq_total: 死信队列事件总数
        event_processing_duration_seconds: 处理耗时采样（有界队列，防止 OOM）
    """

    events_processed_total: int = 0
    events_failed_total: int = 0
    events_retried_total: int = 0
    events_dlq_total: int = 0
    event_processing_duration_seconds: deque[float] = field(
        default_factory=lambda: deque(maxlen=10_000),
    )


class EventMetricsCollector:
    """指标收集器 — 线程安全计数器。

    Args:
        max_processing_samples: 处理耗时采样队列的最大长度。
            达到上限后自动淘汰最旧样本（FIFO）。默认 10000。
    """

    def __init__(self, max_processing_samples: int = 10_000):
        if max_processing_samples <= 0:
            raise ValueError(f"max_processing_samples must be positive, got {max_processing_samples}")
        self.metrics = EventMetrics(
            event_processing_duration_seconds=deque(maxlen=max_processing_samples),
        )

    def record_processed(self, event_type: str, duration: float) -> None:
        """记录成功处理。

        Args:
            event_type: 事件类型
            duration: 处理耗时（秒）
        """
        self.metrics.events_processed_total += 1
        self.metrics.event_processing_duration_seconds.append(duration)
        logger.debug(
            "Event %s processed in %.3fs",
            event_type,
            duration,
        )

    def record_failed(self, event_type: str, error: str) -> None:
        """记录失败。

        Args:
            event_type: 事件类型
            error: 错误信息
        """
        self.metrics.events_failed_total += 1
        logger.warning("Event %s failed: %s", event_type, error)

    def record_retried(self, event_type: str) -> None:
        """记录重试。

        Args:
            event_type: 事件类型
        """
        self.metrics.events_retried_total += 1
        logger.debug("Event %s retried", event_type)

    def record_dlq(self, event_type: str) -> None:
        """记录死信。

        Args:
            event_type: 事件类型
        """
        self.metrics.events_dlq_total += 1
        logger.warning("Event %s sent to DLQ", event_type)


# ============================================================================
# Task 5.2: OpenTelemetry Trace 基础版
# ============================================================================


class OpenTelemetryTracer:
    """OpenTelemetry Trace 包装器。

    默认关闭（EVENT_BUS_OTEL_TRACE_ENABLED=false）。
    仅实现 span 创建+属性设置，不配置 OTLP 导出器（移至 Story 1.16）。
    """

    def __init__(self):
        self.enabled = os.getenv("EVENT_BUS_OTEL_TRACE_ENABLED", "false").lower() == "true"

    @contextmanager
    def create_span(
        self,
        span_name: str,
        event_id: str = "",
        event_type: str = "",
        status: str = "",
        duration: float = 0.0,
    ) -> Generator[Any | None, None, None]:
        """创建 span 并设置属性。

        Args:
            span_name: span 名称
            event_id: 事件 ID
            event_type: 事件类型
            status: 处理状态
            duration: 处理耗时

        Yields:
            span 对象（如果启用）
        """
        if not self.enabled:
            yield None
            return

        try:
            from opentelemetry import trace

            tracer = trace.get_tracer("event_bus")
            with tracer.start_as_current_span(span_name) as span:
                if event_id:
                    span.set_attribute("event.id", event_id)
                if event_type:
                    span.set_attribute("event.type", event_type)
                if status:
                    span.set_attribute("event.status", status)
                if duration > 0:
                    span.set_attribute("event.duration_seconds", duration)
                yield span
        except ImportError:
            logger.warning("OpenTelemetry not installed, tracing disabled")
            self.enabled = False
            yield None
        except Exception as e:
            logger.error("Error creating OpenTelemetry span: %s", e)
            yield None
