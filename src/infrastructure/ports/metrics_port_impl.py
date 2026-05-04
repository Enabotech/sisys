"""MetricsPortImpl — MetricsPort 基础设施实现。

实现 MetricsPort 接口，依赖 prometheus_client 和基础设施层组件。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.application.ports.metrics_port import MetricsPort

if TYPE_CHECKING:
    from prometheus_client import CollectorRegistry

    from src.infrastructure.monitoring.aggregator import MetricsAggregator
    from src.infrastructure.monitoring.business_metrics import BusinessMetricsCollector


class MetricsPortImpl(MetricsPort):
    """Metrics 端口的基础设施实现。

    通过组合 MetricsAggregator 和 BusinessMetricsCollector 实现端口接口。

    Args:
        aggregator: 指标聚合器
        business_metrics: 业务指标收集器
        registry: prometheus_client CollectorRegistry
    """

    def __init__(
        self,
        aggregator: MetricsAggregator,
        business_metrics: BusinessMetricsCollector,
        registry: CollectorRegistry | None = None,
    ) -> None:
        self._aggregator = aggregator
        self._business_metrics = business_metrics
        self._registry = registry

    def collect(self) -> bytes:
        """收集所有指标。

        Returns:
            Prometheus 文本格式的指标字节串
        """
        return self._aggregator.collect()

    def collect_as_dict(self) -> dict[str, float | int]:
        """收集所有指标并返回字典格式。

        Returns:
            指标名称到指标值的字典
        """
        return self._aggregator.collect_as_dict()

    def record_sessions(self, n: int) -> None:
        """记录活跃 Agent 会话数。

        Args:
            n: 当前活跃会话数
        """
        self._business_metrics.record_sessions(n)

    def record_queue_length(self, n: int) -> None:
        """记录任务队列长度。

        Args:
            n: 任务队列长度
        """
        self._business_metrics.record_queue_length(n)

    def record_cache_hit(self) -> None:
        """记录缓存命中"""
        self._business_metrics.record_cache_hit()

    def record_cache_miss(self) -> None:
        """记录缓存未命中"""
        self._business_metrics.record_cache_miss()

    def record_event_processed(self) -> None:
        """记录一个事件已处理"""
        self._business_metrics.record_event_processed()

    def update_processing_rate(self) -> None:
        """更新事件处理速率"""
        self._business_metrics.update_processing_rate()

    def get_hit_rate(self) -> float:
        """获取当前缓存命中率。

        Returns:
            命中率（0.0-1.0）
        """
        return self._business_metrics.hit_rate

    def get_sessions(self) -> int:
        """获取当前活跃会话数"""
        return self._business_metrics.sessions

    def get_queue_length(self) -> int:
        """获取当前任务队列长度"""
        return self._business_metrics.queue_length

    def get_processing_rate(self) -> float:
        """获取当前事件处理速率"""
        return self._business_metrics.processing_rate
