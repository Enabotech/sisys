"""基础设施层业务指标收集器模块

提供自定义业务指标的收集和 Prometheus 导出能力

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prometheus_client import CollectorRegistry

logger = logging.getLogger(__name__)


@dataclass
class BusinessMetrics:
    """业务指标数据结构

    Attributes:
        agent_sessions_active: 当前活跃 Agent 会话数
        task_queue_length: 任务队列长度
        events_processed_total: 事件处理总数（用于计算处理速率）
        events_processing_rate: 每秒事件处理速率
        cache_hits_total: 缓存命中总数
        cache_misses_total: 缓存未命中总数
        cache_hit_rate: 缓存命中率
    """

    agent_sessions_active: int = 0
    task_queue_length: int = 0
    events_processed_total: int = 0
    events_processing_rate: float = 0.0
    cache_hits_total: int = 0
    cache_misses_total: int = 0
    cache_hit_rate: float = 0.0
    _last_processed_count: int = field(default=0, repr=False)
    _last_sample_time: float = field(default_factory=time.time, repr=False)


class BusinessMetricsCollector:
    """业务指标收集器（线程安全）

    暴露以下 Prometheus 指标：活跃会话数、任务队列长度、事件处理速率、缓存命中率

    Attributes:
        _registry: prometheus_client CollectorRegistry 实例
        _agent_sessions_gauge: 活跃会话数 Gauge
        _task_queue_gauge: 任务队列长度 Gauge
        _events_processing_rate_gauge: 事件处理速率 Gauge
        _cache_hit_rate_gauge: 缓存命中率 Gauge
        _metrics: 业务指标数据实例
        _lock: 线程锁
    """

    def __init__(self, registry: CollectorRegistry | None = None):
        """初始化业务指标收集器

        Args:
            registry: prometheus_client CollectorRegistry 实例，None 时使用默认 Registry
        """
        from prometheus_client import Gauge

        if registry is None:
            from prometheus_client import REGISTRY

            registry = REGISTRY

        self._registry = registry

        # 初始化 Prometheus Gauge 指标
        self._agent_sessions_gauge = Gauge(
            "sisys_agent_sessions_active",
            "Current active Agent sessions",
            registry=registry,
        )
        self._task_queue_gauge = Gauge(
            "sisys_task_queue_length",
            "Task queue length",
            registry=registry,
        )
        self._events_processing_rate_gauge = Gauge(
            "sisys_events_processing_rate",
            "Event processing rate (events per second)",
            registry=registry,
        )
        self._cache_hit_rate_gauge = Gauge(
            "sisys_cache_hit_rate",
            "Cache hit rate (0.0-1.0)",
            registry=registry,
        )

        self._metrics = BusinessMetrics()
        self._lock = threading.Lock()

    def record_sessions(self, n: int) -> None:
        """记录活跃 Agent 会话数

        Args:
            n: 当前活跃会话数
        """
        with self._lock:
            self._metrics.agent_sessions_active = n
            self._agent_sessions_gauge.set(n)
        logger.debug("Recorded %d active agent sessions", n)

    def record_queue_length(self, n: int) -> None:
        """记录任务队列长度

        Args:
            n: 任务队列长度
        """
        with self._lock:
            self._metrics.task_queue_length = n
            self._task_queue_gauge.set(n)
        logger.debug("Recorded task queue length: %d", n)

    def record_event_processed(self) -> None:
        """记录一个事件已处理（内部使用，更新处理速率）"""
        with self._lock:
            self._metrics.events_processed_total += 1

    def update_processing_rate(self) -> None:
        """更新事件处理速率（每秒处理事件数）

        通过采样 events_processed_total 增量计算得出
        应定期调用（如每秒一次）
        """
        with self._lock:
            current_time = time.time()
            current_count = self._metrics.events_processed_total

            elapsed = current_time - self._metrics._last_sample_time
            if elapsed > 0:
                count_delta = current_count - self._metrics._last_processed_count
                self._metrics.events_processing_rate = count_delta / elapsed
                self._events_processing_rate_gauge.set(self._metrics.events_processing_rate)

            self._metrics._last_sample_time = current_time
            self._metrics._last_processed_count = current_count

        logger.debug("Updated event processing rate: %.2f/s", self._metrics.events_processing_rate)

    def record_cache_hit(self) -> None:
        """记录缓存命中（内部使用）"""
        with self._lock:
            self._metrics.cache_hits_total += 1
            self._update_cache_hit_rate()

    def record_cache_miss(self) -> None:
        """记录缓存未命中（内部使用）"""
        with self._lock:
            self._metrics.cache_misses_total += 1
            self._update_cache_hit_rate()

    def _update_cache_hit_rate(self) -> None:
        """更新缓存命中率"""
        total = self._metrics.cache_hits_total + self._metrics.cache_misses_total
        if total > 0:
            self._metrics.cache_hit_rate = self._metrics.cache_hits_total / total
            self._cache_hit_rate_gauge.set(self._metrics.cache_hit_rate)

    @property
    def hit_rate(self) -> float:
        """获取当前缓存命中率

        Returns:
            命中率（0.0-1.0）
        """
        return self._metrics.cache_hit_rate

    @property
    def sessions(self) -> int:
        """获取当前活跃会话数

        Returns:
            当前活跃会话数
        """
        return self._metrics.agent_sessions_active

    @property
    def queue_length(self) -> int:
        """获取当前任务队列长度

        Returns:
            当前任务队列长度
        """
        return self._metrics.task_queue_length

    @property
    def processing_rate(self) -> float:
        """获取当前事件处理速率

        Returns:
            当前事件处理速率（事件数/秒）
        """
        return self._metrics.events_processing_rate
