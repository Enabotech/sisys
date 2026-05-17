"""基础设施层事件指标与 OpenTelemetry 跟踪模块

提供事件处理指标收集器和 OpenTelemetry Trace 包装器实现

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from .otel_config import OtelConfig, init

logger = logging.getLogger(__name__)


# ============================================================================
# Task 5.1: EventMetrics + EventMetricsCollector
# ============================================================================


@dataclass
class EventMetrics:
    """事件处理指标数据结构

    基础计数器，不暴露 Prometheus HTTP 端点

    Attributes:
        events_processed_total: 成功处理事件总数
        events_failed_total: 失败事件总数
        events_retried_total: 重试事件总数
        events_dlq_total: 死信队列事件总数
        event_processing_duration_seconds: 处理耗时采样（有界队列，防止 OOM）
        cache_hits_total: 缓存命中总数
        cache_misses_total: 缓存未命中总数
    """

    events_processed_total: int = 0
    events_failed_total: int = 0
    events_retried_total: int = 0
    events_dlq_total: int = 0
    event_processing_duration_seconds: deque[float] = field(
        default_factory=lambda: deque(maxlen=10_000),
    )
    cache_hits_total: int = 0
    cache_misses_total: int = 0


class EventMetricsCollector:
    """指标收集器（线程安全计数器）

    Attributes:
        metrics: EventMetrics 数据实例
    """

    def __init__(self, max_processing_samples: int = 10_000):
        """初始化指标收集器

        Args:
            max_processing_samples: 处理耗时采样队列的最大长度，达到上限后自动淘汰最旧样本

        Raises:
            ValueError: max_processing_samples 不是正整数时抛出
        """
        if max_processing_samples <= 0:
            raise ValueError(f"max_processing_samples must be positive, got {max_processing_samples}")
        self.metrics = EventMetrics(
            event_processing_duration_seconds=deque(maxlen=max_processing_samples),
        )

    def record_processed(self, event_type: str, duration: float) -> None:
        """记录成功处理

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
        """记录失败

        Args:
            event_type: 事件类型
            error: 错误信息
        """
        self.metrics.events_failed_total += 1
        logger.warning("Event %s failed: %s", event_type, error)

    def record_retried(self, event_type: str) -> None:
        """记录重试

        Args:
            event_type: 事件类型
        """
        self.metrics.events_retried_total += 1
        logger.debug("Event %s retried", event_type)

    def record_dlq(self, event_type: str) -> None:
        """记录死信

        Args:
            event_type: 事件类型
        """
        self.metrics.events_dlq_total += 1
        logger.warning("Event %s sent to DLQ", event_type)

    def record_cache_hit(self, cache_type: str = "semantic") -> None:
        """记录缓存命中

        Args:
            cache_type: 缓存类型标识（如 semantic, session）
        """
        self.metrics.cache_hits_total += 1
        logger.debug("Cache hit (%s)", cache_type)

    def record_cache_miss(self, cache_type: str = "semantic") -> None:
        """记录缓存未命中

        Args:
            cache_type: 缓存类型标识（如 semantic, session）
        """
        self.metrics.cache_misses_total += 1
        logger.debug("Cache miss (%s)", cache_type)

    @property
    def hit_rate(self) -> float:
        """计算缓存命中率

        Returns:
            命中率（0.0-1.0），当总请求数为 0 时返回 0.0
        """
        total = self.metrics.cache_hits_total + self.metrics.cache_misses_total
        if total == 0:
            return 0.0
        return self.metrics.cache_hits_total / total


# ============================================================================
# Task 5.2 + Task 5.4: OpenTelemetry Trace 基础版 + OTLP 导出器配置
# ============================================================================


class OpenTelemetryTracer:
    """OpenTelemetry Trace 包装器

    默认关闭，启用后通过 OTLP 协议导出至后端（Jaeger/Tempo/collector）
    支持 gRPC/HTTP 协议选择、批量导出、采样策略和 Resource 属性

    Attributes:
        enabled: 是否启用 Trace
        _initialized: 是否已初始化
    """

    def __init__(self, config: OtelConfig | None = None):
        """初始化 Tracer

        Args:
            config: 可选的 OtelConfig 实例。如果为 None，则从环境变量读取
        """
        if config is None:
            config = OtelConfig.from_env()
        self.enabled = config.trace_enabled
        self._initialized = False
        if self.enabled:
            self._initialized = init(config)

    @contextmanager
    def create_span(
        self,
        span_name: str,
        event_id: str = "",
        event_type: str = "",
        status: str = "",
        duration: float = 0.0,
    ) -> Generator[Any | None, None, None]:
        """创建 span 并设置属性

        Args:
            span_name: span 名称
            event_id: 事件 ID
            event_type: 事件类型
            status: 处理状态
            duration: 处理耗时

        Yields:
            span 对象（如果启用）
        """
        if not self.enabled or not self._initialized:
            yield None
            return

        try:
            from opentelemetry import trace

            tracer = trace.get_tracer("sisys-event-bus")
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
            self._initialized = False
            yield None
        except Exception as e:
            logger.error("Error creating OpenTelemetry span: %s", e)
            yield None
