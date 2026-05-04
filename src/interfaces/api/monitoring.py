"""Prometheus /metrics HTTP 端点 — FastAPI 路由。

Story 1.13: K8s 动态扩缩容
- 端点: GET /metrics
- 返回 Prometheus 文本格式指标
- 使用 generate_latest() 支持多进程模式

六边形架构重构：
- interfaces 层通过 MetricsPort (application/ports/) 获取指标
- 不直接导入 infrastructure 层组件
"""

from __future__ import annotations

import logging
import threading

from fastapi import APIRouter, Response
from fastapi.responses import PlainTextResponse

from src.application.ports.metrics_port import MetricsPort

logger = logging.getLogger(__name__)

router = APIRouter(tags=["monitoring"])


def create_metrics_router(
    metrics_port: MetricsPort,
    metrics_path: str = "/metrics",
    metrics_enabled: bool = True,
) -> APIRouter:
    """创建 metrics 路由。

    Args:
        metrics_port: MetricsPort 实例（应用层端口）
        metrics_path: 指标端点路径
        metrics_enabled: 是否启用端点

    Returns:
        配置好的 APIRouter
    """

    @router.get(
        metrics_path,
        response_class=PlainTextResponse,
        summary="Prometheus metrics endpoint",
        description="Returns metrics in Prometheus text format for scraping by Prometheus server.",
        include_in_schema=metrics_enabled,
    )
    async def get_metrics() -> Response:
        """获取 Prometheus 格式指标。

        Returns:
            Prometheus 文本格式指标（Content-Type: text/plain; version=0.0.4; charset=utf-8）
        """
        try:
            metrics_output = metrics_port.collect()

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


# 全局路由实例（延迟初始化，线程安全）
_metrics_router: APIRouter | None = None
_metrics_port: MetricsPort | None = None
_init_lock = threading.Lock()


def get_metrics_router(
    metrics_port: MetricsPort | None = None,
) -> APIRouter:
    """获取 metrics 路由实例（线程安全延迟初始化）。

    Args:
        metrics_port: MetricsPort 实例。如果为 None，则创建默认实现。

    Returns:
        APIRouter 实例
    """
    global _metrics_router, _metrics_port  # noqa: PLW0603

    if _metrics_router is None:
        with _init_lock:
            # 双重检查锁定 (Double-Checked Locking)
            if _metrics_router is None:
                if metrics_port is None:
                    metrics_port = _create_default_metrics_port()

                _metrics_port = metrics_port

                # 从环境变量或默认值获取配置
                from src.infrastructure.config.metrics import MetricsConfig

                metrics_config = MetricsConfig.from_env()

                _metrics_router = create_metrics_router(
                    _metrics_port,
                    metrics_path=metrics_config.path,
                    metrics_enabled=metrics_config.enabled,
                )

    return _metrics_router


def _create_default_metrics_port() -> MetricsPort:
    """创建默认 MetricsPort 实现。

    Returns:
        MetricsPort 实例
    """
    from prometheus_client import REGISTRY

    from src.infrastructure.monitoring.aggregator import MetricsAggregator
    from src.infrastructure.monitoring.business_metrics import BusinessMetricsCollector
    from src.infrastructure.monitoring.event_metrics import EventMetricsCollector
    from src.infrastructure.ports.metrics_port_impl import MetricsPortImpl

    event_metrics_collector = EventMetricsCollector()
    business_metrics_collector = BusinessMetricsCollector(registry=REGISTRY)
    aggregator = MetricsAggregator(
        event_metrics_collector=event_metrics_collector,
        business_metrics_collector=business_metrics_collector,
        registry=REGISTRY,
    )

    return MetricsPortImpl(
        aggregator=aggregator,
        business_metrics=business_metrics_collector,
        registry=REGISTRY,
    )


def reset_metrics_router() -> None:
    """重置 metrics 路由（用于测试）"""
    global _metrics_router, _metrics_port  # noqa: PLW0603
    with _init_lock:
        _metrics_router = None
        _metrics_port = None
