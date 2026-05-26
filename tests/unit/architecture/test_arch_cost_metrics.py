"""Architecture constraint tests for Cost Metrics (Story 1.19).

验证六边形架构约束：领域层零外部依赖、依赖方向正确、端口实现协议
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# ===================================================================
# 领域层零外部依赖验证
# ===================================================================


class TestCostMetricsDomainZeroDependency:
    """验证成本度量领域层仅依赖 Python 标准库和领域模块."""

    def test_cost_calculator_no_infrastructure_imports(self) -> None:
        """CostCalculator 不应导入基础设施层模块."""
        service_path = Path("src/domain/services/cost_calculator.py")
        if not service_path.exists():
            pytest.skip("CostCalculator not yet implemented")

        source = service_path.read_text()
        tree = ast.parse(source)

        forbidden_prefixes = (
            "src.infrastructure",
            "src.interfaces",
            "redis",
            "httpx",
            "aioredis",
            "neo4j",
            "qdrant",
            "minio",
            "prometheus_client",
        )

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(forbidden_prefixes), f"Forbidden import: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith(forbidden_prefixes), f"Forbidden import from: {module}"

    def test_cost_calculator_imports_domain_only(self) -> None:
        """CostCalculator 应仅导入领域层模块和标准库."""
        service_path = Path("src/domain/services/cost_calculator.py")
        if not service_path.exists():
            pytest.skip("CostCalculator not yet implemented")

        source = service_path.read_text()
        tree = ast.parse(source)

        allowed_prefixes = (
            "__future__",
            "dataclasses",
            "typing",
            "logging",
            "src.domain",
        )

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    is_allowed = any(name.startswith(p) or name == p.split(".")[-1] for p in allowed_prefixes)
                    assert is_allowed, f"Unexpected import: {name}"
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                is_allowed = any(module.startswith(p) for p in allowed_prefixes)
                assert is_allowed, f"Unexpected import from: {module}"

    def test_token_consumption_no_external_deps(self) -> None:
        """TokenConsumption 值对象不应依赖外部模块."""
        vo_path = Path("src/domain/value_objects/token_consumption.py")
        if not vo_path.exists():
            pytest.skip("TokenConsumption not yet implemented")

        source = vo_path.read_text()
        tree = ast.parse(source)

        forbidden_prefixes = (
            "src.infrastructure",
            "src.interfaces",
            "redis",
            "httpx",
            "prometheus_client",
        )

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(forbidden_prefixes), f"Forbidden import: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith(forbidden_prefixes), f"Forbidden import from: {module}"


# ===================================================================
# 依赖方向矩阵验证
# ===================================================================


class TestCostMetricsDependencyDirection:
    """验证成本度量的依赖方向符合六边形架构."""

    def test_cost_metrics_handler_imports_domain(self) -> None:
        """CostMetricsListener（application层）应导入 domain 层."""
        handler_path = Path("src/application/event_handlers/cost_metrics_handler.py")
        if not handler_path.exists():
            pytest.skip("CostMetricsListener not yet implemented")

        source = handler_path.read_text()
        assert "src.domain" in source, "CostMetricsListener should import from domain"

    def test_cost_metrics_handler_imports_application_ports(self) -> None:
        """CostMetricsListener 应导入 application 层端口."""
        handler_path = Path("src/application/event_handlers/cost_metrics_handler.py")
        if not handler_path.exists():
            pytest.skip("CostMetricsListener not yet implemented")

        source = handler_path.read_text()
        assert "src.application.ports" in source, "CostMetricsListener should import from application ports"

    def test_cost_metrics_handler_no_infrastructure_imports(self) -> None:
        """CostMetricsListener 不应直接导入基础设施层实现."""
        handler_path = Path("src/application/event_handlers/cost_metrics_handler.py")
        if not handler_path.exists():
            pytest.skip("CostMetricsListener not yet implemented")

        source = handler_path.read_text()
        forbidden = (
            "src.infrastructure.monitoring.business_metrics",
            "src.infrastructure.monitoring.static_token_estimator",
            "src.infrastructure.config.udmr",
        )
        for f in forbidden:
            assert f not in source, f"CostMetricsListener should not import {f}"

    def test_static_token_estimator_infrastructure_layer(self) -> None:
        """StaticTokenEstimator 应位于 infrastructure 层."""
        estimator_path = Path("src/infrastructure/monitoring/static_token_estimator.py")
        assert estimator_path.exists(), "StaticTokenEstimator should exist in infrastructure"

    def test_token_estimator_port_domain_layer(self) -> None:
        """TokenEstimatorPort 应位于 domain 层."""
        port_path = Path("src/domain/ports/token_estimator.py")
        assert port_path.exists(), "TokenEstimatorPort should exist in domain/ports"


# ===================================================================
# 端口实现协议验证
# ===================================================================


class TestCostMetricsPortImplementation:
    """验证端口实现满足 Protocol."""

    def test_static_token_estimator_implements_estimate(self) -> None:
        """StaticTokenEstimator 应实现 estimate() 方法."""
        from src.infrastructure.monitoring.static_token_estimator import StaticTokenEstimator

        estimator = StaticTokenEstimator()
        assert hasattr(estimator, "estimate")
        assert callable(estimator.estimate)

    def test_static_token_estimator_is_token_estimator_port(self) -> None:
        """StaticTokenEstimator 应满足 TokenEstimatorPort Protocol."""
        from src.domain.ports.token_estimator import TokenEstimatorPort
        from src.infrastructure.monitoring.static_token_estimator import StaticTokenEstimator

        estimator = StaticTokenEstimator()
        assert isinstance(estimator, TokenEstimatorPort)

    def test_inmemory_repo_implements_query_cost_summary(self) -> None:
        """InMemoryRoutingDecisionLogRepository 应实现 query_cost_summary() 方法."""
        from src.infrastructure.messaging.inmemory_routing_decision_log_repository import (
            InMemoryRoutingDecisionLogRepository,
        )

        repo = InMemoryRoutingDecisionLogRepository()
        assert hasattr(repo, "query_cost_summary")
        assert callable(repo.query_cost_summary)
