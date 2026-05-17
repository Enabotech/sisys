"""SISYS 接口层 Prometheus 指标端点模块

提供 GET /metrics 端点，返回 Prometheus 文本格式指标，
支持多进程模式下的动态扩缩容场景

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Response
from fastapi.responses import PlainTextResponse

from src.application.ports.metrics_port import MetricsPort

logger = logging.getLogger(__name__)


def create_metrics_router(
    metrics_port: MetricsPort,
    metrics_path: str = "/metrics",
    metrics_enabled: bool = True,
) -> APIRouter:
    """创建 metrics 路由

    Args:
        metrics_port: MetricsPort 实例（应用层端口）
        metrics_path: 指标端点路径
        metrics_enabled: 是否启用端点

    Returns:
        配置好的 APIRouter
    """
    router = APIRouter(tags=["monitoring"])

    @router.get(
        metrics_path,
        response_class=PlainTextResponse,
        summary="Prometheus metrics endpoint",
        description="Returns metrics in Prometheus text format for scraping by Prometheus server.",
        include_in_schema=metrics_enabled,
    )
    async def get_metrics() -> Response:
        """获取 Prometheus 格式指标

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


# Alias for backward compatibility
get_metrics_router = create_metrics_router
