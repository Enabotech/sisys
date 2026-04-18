"""Prometheus /metrics HTTP 端点 — FastAPI 路由。

Story 1.13: K8s 动态扩缩容
- 端点: GET /metrics
- 返回 Prometheus 文本格式指标
- 使用 generate_latest() 支持多进程模式
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Response
from fastapi.responses import PlainTextResponse

from src.infrastructure.config.metrics import MetricsConfig
from src.infrastructure.monitoring.aggregator import MetricsAggregator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["monitoring"])


def create_metrics_router(
    metrics_aggregator: MetricsAggregator,
    metrics_config: MetricsConfig | None = None,
) -> APIRouter:
    """创建 metrics 路由。

    Args:
        metrics_aggregator: MetricsAggregator 实例
        metrics_config: MetricsConfig 配置

    Returns:
        配置好的 APIRouter
    """
    if metrics_config is None:
        metrics_config = MetricsConfig.from_env()

    @router.get(
        metrics_config.path,
        response_class=PlainTextResponse,
        summary="Prometheus metrics endpoint",
        description="Returns metrics in Prometheus text format for scraping by Prometheus server.",
        include_in_schema=metrics_config.enabled,
    )
    async def get_metrics() -> Response:
        """获取 Prometheus 格式指标。

        Returns:
            Prometheus 文本格式指标（Content-Type: text/plain; version=0.0.4; charset=utf-8）
        """
        try:
            metrics_output = metrics_aggregator.collect()

            return Response(
                content=metrics_output,
                media_type="text/plain; version=0.0.4; charset=utf-8",
            )
        except Exception as e:
            logger.error("Error collecting metrics: %s", e)
            return Response(
                content=f"# Error collecting metrics: {e}\n",
                media_type="text/plain",
                status_code=500,
            )

    return router


# 全局路由实例（延迟初始化）
_metrics_router: APIRouter | None = None
_metrics_aggregator: MetricsAggregator | None = None


def get_metrics_router(
    event_metrics_collector: Any = None,
    business_metrics_collector: Any = None,
    registry: Any = None,
) -> APIRouter:
    """获取 metrics 路由实例。

    Args:
        event_metrics_collector: EventMetricsCollector 实例
        business_metrics_collector: BusinessMetricsCollector 实例
        registry: prometheus_client CollectorRegistry

    Returns:
        APIRouter 实例
    """
    global _metrics_router, _metrics_aggregator  # noqa: PLW0603

    if _metrics_router is None:
        from prometheus_client import REGISTRY

        from src.infrastructure.monitoring.business_metrics import BusinessMetricsCollector
        from src.infrastructure.monitoring.event_metrics import EventMetricsCollector

        if event_metrics_collector is None:
            event_metrics_collector = EventMetricsCollector()
        if business_metrics_collector is None:
            business_metrics_collector = BusinessMetricsCollector(registry=registry or REGISTRY)

        _metrics_aggregator = MetricsAggregator(
            event_metrics_collector=event_metrics_collector,
            business_metrics_collector=business_metrics_collector,
            registry=registry or REGISTRY,
        )

        metrics_config = MetricsConfig.from_env()
        _metrics_router = create_metrics_router(_metrics_aggregator, metrics_config)

    return _metrics_router
