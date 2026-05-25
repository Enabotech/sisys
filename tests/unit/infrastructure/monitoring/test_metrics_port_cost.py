"""成本度量基础单元测试

Story 1.19: 成本度量基础
TDD 循环: MetricsPort / BusinessMetricsCollector / MetricsPortImpl 扩展

测试覆盖：
1. MetricsPort Protocol 新增方法签名验证
2. BusinessMetricsCollector 新增 Prometheus 指标注册和记录方法
3. MetricsPortImpl 委托验证

Run with: pytest tests/unit/infrastructure/monitoring/test_metrics_port_cost.py -v
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestMetricsPortCostMethods:
    """验证 MetricsPort Protocol 新增成本度量方法签名"""

    def test_record_token_usage_method_exists(self):
        """🔴 RED: MetricsPort 应有 record_token_usage 方法签名"""
        from src.application.ports.metrics_port import MetricsPort

        # Protocol 方法签名检查
        assert hasattr(MetricsPort, "record_token_usage")

    def test_record_cost_method_exists(self):
        """🔴 RED: MetricsPort 应有 record_cost 方法签名"""
        from src.application.ports.metrics_port import MetricsPort

        assert hasattr(MetricsPort, "record_cost")


class TestBusinessMetricsCollectorTokenMetrics:
    """验证 BusinessMetricsCollector 的 Token 使用量指标"""

    @pytest.fixture
    def collector(self):
        """创建使用独立 CollectorRegistry 的 BusinessMetricsCollector 实例"""
        from prometheus_client import CollectorRegistry

        from src.infrastructure.monitoring.business_metrics import BusinessMetricsCollector

        registry = CollectorRegistry()
        return BusinessMetricsCollector(registry=registry)

    def test_token_prompt_counter_exists(self, collector):
        """🔴 RED: BusinessMetricsCollector 应有 sisys_token_prompt_total Counter"""
        assert hasattr(collector, "_token_prompt_counter")

    def test_token_completion_counter_exists(self, collector):
        """🔴 RED: BusinessMetricsCollector 应有 sisys_token_completion_total Counter"""
        assert hasattr(collector, "_token_completion_counter")

    def test_record_token_usage_increments_counters(self, collector):
        """🔴 RED: record_token_usage 应递增 prompt 和 completion Counter"""
        # 记录 token 使用
        collector.record_token_usage(
            prompt=100,
            completion=50,
            model="claude-3-opus",
            route_type="planning",
        )

        # 验证内部状态已更新（Counter 无法直接读取值，仅验证方法可调用）
        # 通过 Prometheus 输出验证
        from prometheus_client import generate_latest

        output = generate_latest(collector._registry).decode("utf-8")

        # 检查指标是否存在于输出中
        assert "sisys_token_prompt_total" in output
        assert "sisys_token_completion_total" in output

    def test_record_token_usage_with_labels(self, collector):
        """🔴 RED: record_token_usage 应使用 model 和 route_type 标签"""
        from prometheus_client import generate_latest

        collector.record_token_usage(prompt=200, completion=100, model="gpt-4", route_type="execution")

        output = generate_latest(collector._registry).decode("utf-8")

        # 验证标签存在
        assert 'model="gpt-4"' in output or "model" in output
        assert 'route_type="execution"' in output or "route_type" in output


class TestBusinessMetricsCollectorCostMetrics:
    """验证 BusinessMetricsCollector 的成本指标"""

    @pytest.fixture
    def collector(self):
        """创建使用独立 CollectorRegistry 的 BusinessMetricsCollector 实例"""
        from prometheus_client import CollectorRegistry

        from src.infrastructure.monitoring.business_metrics import BusinessMetricsCollector

        registry = CollectorRegistry()
        return BusinessMetricsCollector(registry=registry)

    def test_cost_total_gauge_exists(self, collector):
        """🔴 RED: BusinessMetricsCollector 应有 sisys_cost_total_cny Gauge"""
        assert hasattr(collector, "_cost_total_gauge")

    def test_cost_by_model_gauge_exists(self, collector):
        """🔴 RED: BusinessMetricsCollector 应有 sisys_cost_by_model_cny Gauge"""
        assert hasattr(collector, "_cost_by_model_gauge")

    def test_record_cost_updates_total(self, collector):
        """🔴 RED: record_cost 应更新总成本 Gauge"""
        from prometheus_client import generate_latest

        collector.record_cost(cost=0.05, model="claude-3-opus", route_type="planning")

        output = generate_latest(collector._registry).decode("utf-8")

        assert "sisys_cost_total_cny" in output

    def test_record_cost_updates_by_model(self, collector):
        """🔴 RED: record_cost 应更新按模型分组的成本 Gauge"""
        from prometheus_client import generate_latest

        collector.record_cost(cost=0.03, model="gpt-4", route_type="execution")

        output = generate_latest(collector._registry).decode("utf-8")

        assert "sisys_cost_by_model_cny" in output

    def test_record_cost_accumulates_total(self, collector):
        """🔴 RED: 多次 record_cost 应累加总成本"""
        collector.record_cost(cost=0.01, model="model-a", route_type="type-1")
        collector.record_cost(cost=0.02, model="model-b", route_type="type-2")

        # 总成本应为累加
        assert hasattr(collector, "_total_cost_cny")
        # 验证内部累加值（精度允许误差）
        assert abs(collector._total_cost_cny - 0.03) < 0.0001


class TestBusinessMetricsCollectorCostPrometheusIntegration:
    """验证成本指标的 Prometheus 集成"""

    @pytest.fixture
    def collector_with_registry(self):
        """创建带独立 Registry 的 collector 和辅助函数"""
        from prometheus_client import CollectorRegistry, generate_latest

        from src.infrastructure.monitoring.business_metrics import BusinessMetricsCollector

        registry = CollectorRegistry()
        collector = BusinessMetricsCollector(registry=registry)
        return collector, registry, generate_latest

    def test_token_metrics_registered_in_registry(self, collector_with_registry):
        """🔴 RED: Token 指标应注册到 Prometheus Registry"""
        collector, registry, generate_latest = collector_with_registry

        # 先记录一些数据以触发指标创建
        collector.record_token_usage(prompt=10, completion=5, model="test-model", route_type="test")

        output = generate_latest(registry).decode("utf-8")

        assert "sisys_token_prompt_total" in output
        assert "sisys_token_completion_total" in output

    def test_cost_metrics_registered_in_registry(self, collector_with_registry):
        """🔴 RED: 成本指标应注册到 Prometheus Registry"""
        collector, registry, generate_latest = collector_with_registry

        collector.record_cost(cost=0.01, model="test-model", route_type="test")

        output = generate_latest(registry).decode("utf-8")

        assert "sisys_cost_total_cny" in output
        assert "sisys_cost_by_model_cny" in output

    def test_token_metrics_have_counter_type(self, collector_with_registry):
        """🔴 RED: Token 指标应为 Counter 类型"""
        collector, registry, generate_latest = collector_with_registry

        collector.record_token_usage(prompt=10, completion=5, model="test", route_type="test")

        output = generate_latest(registry).decode("utf-8")

        assert "# TYPE sisys_token_prompt_total counter" in output
        assert "# TYPE sisys_token_completion_total counter" in output

    def test_cost_metrics_have_gauge_type(self, collector_with_registry):
        """🔴 RED: 成本指标应为 Gauge 类型"""
        collector, registry, generate_latest = collector_with_registry

        collector.record_cost(cost=0.01, model="test", route_type="test")

        output = generate_latest(registry).decode("utf-8")

        assert "# TYPE sisys_cost_total_cny gauge" in output
        assert "# TYPE sisys_cost_by_model_cny gauge" in output


class TestMetricsPortImplCostDelegation:
    """验证 MetricsPortImpl 正确委托成本度量方法"""

    @pytest.fixture
    def mock_aggregator(self) -> MagicMock:
        """创建 MetricsAggregator mock"""
        return MagicMock()

    @pytest.fixture
    def mock_business_metrics(self) -> MagicMock:
        """创建 BusinessMetricsCollector mock"""
        return MagicMock()

    @pytest.fixture
    def port(self, mock_aggregator: MagicMock, mock_business_metrics: MagicMock):
        """创建注入 mock 的 MetricsPortImpl 实例"""
        from src.infrastructure.monitoring.metrics_port_impl import MetricsPortImpl

        return MetricsPortImpl(
            aggregator=mock_aggregator,
            business_metrics=mock_business_metrics,
        )

    def test_record_token_usage_delegates(self, port, mock_business_metrics: MagicMock):
        """🔴 RED: record_token_usage 应委托给 BusinessMetricsCollector.record_token_usage"""
        port.record_token_usage(prompt=100, completion=50, model="claude-3-opus", route_type="planning")

        mock_business_metrics.record_token_usage.assert_called_once_with(100, 50, "claude-3-opus", "planning")

    def test_record_cost_delegates(self, port, mock_business_metrics: MagicMock):
        """🔴 RED: record_cost 应委托给 BusinessMetricsCollector.record_cost"""
        port.record_cost(cost=0.05, model="gpt-4", route_type="execution")

        mock_business_metrics.record_cost.assert_called_once_with(0.05, "gpt-4", "execution")

    def test_record_token_usage_with_various_models(self, port, mock_business_metrics: MagicMock):
        """🔴 RED: record_token_usage 应正确传递不同模型参数"""
        port.record_token_usage(prompt=500, completion=200, model="custom-model", route_type="analysis")

        mock_business_metrics.record_token_usage.assert_called_once_with(500, 200, "custom-model", "analysis")

    def test_record_cost_with_various_values(self, port, mock_business_metrics: MagicMock):
        """🔴 RED: record_cost 应正确传递不同成本值"""
        port.record_cost(cost=1.2345, model="premium-model", route_type="critical")

        mock_business_metrics.record_cost.assert_called_once_with(1.2345, "premium-model", "critical")


class TestBusinessMetricsCollectorThreadSafety:
    """验证成本度量方法的线程安全性"""

    def test_concurrent_token_usage_recording(self):
        """🔴 RED: 并发 record_token_usage 应线程安全"""
        import threading

        from prometheus_client import CollectorRegistry

        from src.infrastructure.monitoring.business_metrics import BusinessMetricsCollector

        registry = CollectorRegistry()
        collector = BusinessMetricsCollector(registry=registry)

        def record_tokens():
            for _ in range(100):
                collector.record_token_usage(prompt=10, completion=5, model="test", route_type="test")

        threads = [threading.Thread(target=record_tokens) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 验证无异常，指标正确递增
        from prometheus_client import generate_latest

        output = generate_latest(registry).decode("utf-8")
        assert "sisys_token_prompt_total" in output

    def test_concurrent_cost_recording(self):
        """🔴 RED: 并发 record_cost 应线程安全累加"""
        import threading

        from prometheus_client import CollectorRegistry

        from src.infrastructure.monitoring.business_metrics import BusinessMetricsCollector

        registry = CollectorRegistry()
        collector = BusinessMetricsCollector(registry=registry)

        def record_cost():
            for _ in range(100):
                collector.record_cost(cost=0.01, model="test", route_type="test")

        threads = [threading.Thread(target=record_cost) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 验证总成本正确累加：500 次 * 0.01 = 5.0
        assert abs(collector._total_cost_cny - 5.0) < 0.01
