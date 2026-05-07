"""Monitoring API 端点单元测试。

验证 monitoring.py API 路由正确。
Story 1.13: K8s 动态扩缩容

Reference: src/interfaces/api/monitoring.py
"""

from __future__ import annotations

from unittest import mock

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from src.application.ports.metrics_port import MetricsPort
from src.interfaces.api.monitoring import create_metrics_router


class TestMonitoringRouter:
    """验证 create_metrics_router 函数。"""

    @pytest.fixture
    def mock_metrics_port(self) -> mock.Mock:
        """创建 mock MetricsPort。"""
        port = mock.Mock(spec=MetricsPort)
        port.collect.return_value = b"# HELP test_metric Test metric\ntest_metric 1\n"
        port.collect_as_dict.return_value = {"test_metric": 1.0}
        port.get_sessions.return_value = 10
        port.get_queue_length.return_value = 5
        port.get_hit_rate.return_value = 0.95
        port.get_processing_rate.return_value = 100.0
        return port

    @pytest.fixture
    def router(self, mock_metrics_port: mock.Mock) -> APIRouter:
        """创建测试路由器。"""
        return create_metrics_router(
            metrics_port=mock_metrics_port,
            metrics_path="/metrics",
            metrics_enabled=True,
        )

    def test_router_has_get_endpoint(self, router: APIRouter) -> None:
        """验证路由器有 GET /metrics 端点。"""
        routes = {getattr(route, "path", None): route for route in router.routes}
        assert "/metrics" in routes

    def test_get_metrics_returns_prometheus_format(self, mock_metrics_port: mock.Mock) -> None:
        """验证 GET /metrics 返回 Prometheus 格式。"""
        router = create_metrics_router(
            metrics_port=mock_metrics_port,
            metrics_path="/metrics",
            metrics_enabled=True,
        )
        client = TestClient(router)
        response = client.get("/metrics")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; version=0.0.4; charset=utf-8"
        assert b"test_metric" in response.content

    def test_get_metrics_collects_from_port(self, mock_metrics_port: mock.Mock) -> None:
        """验证 GET /metrics 调用 MetricsPort.collect()。"""
        router = create_metrics_router(
            metrics_port=mock_metrics_port,
            metrics_path="/metrics",
            metrics_enabled=True,
        )
        client = TestClient(router)
        client.get("/metrics")

        mock_metrics_port.collect.assert_called_once()

    def test_custom_metrics_path(self, mock_metrics_port: mock.Mock) -> None:
        """验证自定义路径。"""
        router = create_metrics_router(
            metrics_port=mock_metrics_port,
            metrics_path="/custom/metrics",
            metrics_enabled=True,
        )
        routes = {getattr(route, "path", None): route for route in router.routes}
        assert "/custom/metrics" in routes

    def test_disabled_router_excluded_from_schema(self, mock_metrics_port: mock.Mock) -> None:
        """验证禁用的路由器不包含在 schema 中。"""
        router = create_metrics_router(
            metrics_port=mock_metrics_port,
            metrics_path="/metrics",
            metrics_enabled=False,
        )
        # Check that the route is not included in schema
        for route in router.routes:
            if hasattr(route, "include_in_schema"):
                assert route.include_in_schema is False

    def test_get_metrics_error_returns_500(self, mock_metrics_port: mock.Mock) -> None:
        """验证 collect() 抛出异常时返回 500。"""
        mock_metrics_port.collect.side_effect = Exception("Collection failed")

        router = create_metrics_router(
            metrics_port=mock_metrics_port,
            metrics_path="/metrics",
            metrics_enabled=True,
        )
        client = TestClient(router)
        response = client.get("/metrics")

        assert response.status_code == 500
        assert b"Error collecting metrics" in response.content


class TestGetMetricsRouterAlias:
    """验证 get_metrics_router 别名。"""

    def test_alias_exists(self) -> None:
        """验证 get_metrics_router 别名存在。"""
        from src.interfaces.api.monitoring import get_metrics_router

        assert get_metrics_router is not None
        assert callable(get_metrics_router)
