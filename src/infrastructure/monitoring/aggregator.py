"""MetricsAggregator — 指标聚合器。

Story 1.13: K8s 动态扩缩容
- 聚合职责: 统一收集 EventMetricsCollector + BusinessMetricsCollector 指标
- 方法: collect() -> bytes (Prometheus text format)
- 复用 Story 1.3 EventMetricsCollector: 通过注入获取，不修改原组件
- EventMetricsCollector 是纯内存计数器，不注册 Prometheus 指标，
  所以需要从其 metrics 属性手动获取并格式化为 Prometheus 格式
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from prometheus_client import CollectorRegistry

    from .business_metrics import BusinessMetricsCollector
    from .event_metrics import EventMetricsCollector

logger = logging.getLogger(__name__)


class MetricsAggregator:
    """指标聚合器 — 统一收集 EventMetricsCollector + BusinessMetricsCollector 指标。

    通过注入获取已存在的 EventMetricsCollector，不修改原组件。
    EventMetricsCollector 是纯内存计数器，需要手动格式化其指标值。

    Args:
        event_metrics_collector: EventMetricsCollector 实例（Story 1.3 已实现）
        business_metrics_collector: BusinessMetricsCollector 实例
        registry: prometheus_client CollectorRegistry 实例。如果为 None，则使用默认 Registry。
    """

    def __init__(
        self,
        event_metrics_collector: EventMetricsCollector,
        business_metrics_collector: BusinessMetricsCollector,
        registry: CollectorRegistry | None = None,
    ):
        if registry is None:
            from prometheus_client import REGISTRY

            registry = REGISTRY

        self._event_metrics = event_metrics_collector
        self._business_metrics = business_metrics_collector
        self._registry = registry

    def _format_event_metrics(self) -> str:
        """从 EventMetricsCollector 格式化事件指标为 Prometheus 文本格式。

        EventMetricsCollector 是纯内存计数器，不注册 Prometheus 指标，
        所以需要手动格式化其 metrics 属性中的值。

        Returns:
            Prometheus 文本格式的事件指标字符串
        """
        metrics = self._event_metrics.metrics
        lines = []

        # events_processed_total
        lines.append("# HELP events_processed_total Total events processed")
        lines.append("# TYPE events_processed_total counter")
        lines.append(f"events_processed_total {metrics.events_processed_total}")

        # events_failed_total
        lines.append("# HELP events_failed_total Total events failed")
        lines.append("# TYPE events_failed_total counter")
        lines.append(f"events_failed_total {metrics.events_failed_total}")

        # events_retried_total
        lines.append("# HELP events_retried_total Total events retried")
        lines.append("# TYPE events_retried_total counter")
        lines.append(f"events_retried_total {metrics.events_retried_total}")

        # events_dlq_total
        lines.append("# HELP events_dlq_total Total events sent to DLQ")
        lines.append("# TYPE events_dlq_total counter")
        lines.append(f"events_dlq_total {metrics.events_dlq_total}")

        # cache_hits_total
        lines.append("# HELP cache_hits_total Total cache hits")
        lines.append("# TYPE cache_hits_total counter")
        lines.append(f"cache_hits_total {metrics.cache_hits_total}")

        # cache_misses_total
        lines.append("# HELP cache_misses_total Total cache misses")
        lines.append("# TYPE cache_misses_total counter")
        lines.append(f"cache_misses_total {metrics.cache_misses_total}")

        return "\n".join(lines) + "\n"

    def collect(self) -> bytes:
        """收集所有指标。

        聚合 EventMetricsCollector 的内存指标和 BusinessMetricsCollector 的 Prometheus 指标。

        Returns:
            Prometheus 文本格式的指标字节串
        """
        # 获取 BusinessMetricsCollector 注册的 Prometheus 指标
        from prometheus_client import generate_latest

        # 生成 BusinessMetricsCollector 的 Prometheus 指标
        business_metrics_output = generate_latest(self._registry)

        # 获取 EventMetricsCollector 的格式化指标
        event_metrics_output = self._format_event_metrics()

        # 合并两个输出
        combined_output = business_metrics_output.decode("utf-8") + event_metrics_output

        logger.debug("Collected metrics: %d bytes", len(combined_output))
        return combined_output.encode("utf-8")

    def collect_as_dict(self) -> dict[str, Any]:
        """收集所有指标并返回字典格式。

        Returns:
            指标名称到指标值的字典
        """
        output = self.collect().decode("utf-8")
        result: dict[str, Any] = {}

        for line in output.split("\n"):
            if line and not line.startswith("#"):
                parts = line.split()
                if len(parts) >= 2:
                    metric_name = parts[0].split("{")[0]
                    metric_value: float | str
                    try:
                        metric_value = float(parts[-1])
                    except ValueError:
                        metric_value = parts[-1]
                    result[metric_name] = metric_value

        return result
