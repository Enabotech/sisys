"""MetricsPortImpl 委托模式单元测试

验证 MetricsPortImpl 正确地将所有调用委托给底层组件：
- MetricsAggregator: collect(), collect_as_dict()
- BusinessMetricsCollector: record_*, update_*, 属性访问

使用构造器注入 mock 对象，验证每次调用都命中正确的底层方法

Run with: pytest tests/unit/infrastructure/monitoring/test_metrics_port_impl.py -v
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.infrastructure.monitoring.metrics_port_impl import MetricsPortImpl


class TestMetricsPortImplAggregatorDelegation:
    """验证 MetricsPortImpl 将聚合器相关方法正确委托给 MetricsAggregator"""

    @pytest.fixture
    def mock_aggregator(self) -> MagicMock:
        """创建 MetricsAggregator mock"""
        agg = MagicMock()
        agg.collect.return_value = b"# test metrics output"
        agg.collect_as_dict.return_value = {"test_metric": 1.0}
        return agg

    @pytest.fixture
    def mock_business_metrics(self) -> MagicMock:
        """创建 BusinessMetricsCollector mock"""
        bm = MagicMock()
        bm.hit_rate = 0.75
        bm.sessions = 5
        bm.queue_length = 10
        bm.processing_rate = 3.14
        return bm

    @pytest.fixture
    def port(self, mock_aggregator: MagicMock, mock_business_metrics: MagicMock) -> MetricsPortImpl:
        """创建注入 mock 的 MetricsPortImpl 实例"""
        return MetricsPortImpl(
            aggregator=mock_aggregator,
            business_metrics=mock_business_metrics,
        )

    def test_collect_should_delegate_to_aggregator(self, port: MetricsPortImpl, mock_aggregator: MagicMock):
        """collect() 应委托给 MetricsAggregator.collect() 并返回其结果"""
        result = port.collect()

        mock_aggregator.collect.assert_called_once_with()
        assert result == b"# test metrics output"

    def test_collect_as_dict_should_delegate_to_aggregator(self, port: MetricsPortImpl, mock_aggregator: MagicMock):
        """collect_as_dict() 应委托给 MetricsAggregator.collect_as_dict() 并返回其结果"""
        result = port.collect_as_dict()

        mock_aggregator.collect_as_dict.assert_called_once_with()
        assert result == {"test_metric": 1.0}

    def test_collect_returns_exact_aggregator_output(self, port: MetricsPortImpl, mock_aggregator: MagicMock):
        """collect() 应原样返回聚合器的输出，不做任何转换"""
        expected = b"prometheus text format bytes 123"
        mock_aggregator.collect.return_value = expected

        assert port.collect() is expected


class TestMetricsPortImplBusinessMetricsDelegation:
    """验证 MetricsPortImpl 将业务指标记录方法正确委托给 BusinessMetricsCollector"""

    @pytest.fixture
    def mock_aggregator(self) -> MagicMock:
        """创建 MetricsAggregator mock"""
        return MagicMock()

    @pytest.fixture
    def mock_business_metrics(self) -> MagicMock:
        """创建 BusinessMetricsCollector mock"""
        return MagicMock()

    @pytest.fixture
    def port(self, mock_aggregator: MagicMock, mock_business_metrics: MagicMock) -> MetricsPortImpl:
        """创建注入 mock 的 MetricsPortImpl 实例"""
        return MetricsPortImpl(
            aggregator=mock_aggregator,
            business_metrics=mock_business_metrics,
        )

    def test_record_sessions_delegates(self, port: MetricsPortImpl, mock_business_metrics: MagicMock):
        """record_sessions(n) 应委托给 BusinessMetricsCollector.record_sessions(n)"""
        port.record_sessions(42)

        mock_business_metrics.record_sessions.assert_called_once_with(42)

    def test_record_sessions_with_zero(self, port: MetricsPortImpl, mock_business_metrics: MagicMock):
        """record_sessions(0) 应传递零值"""
        port.record_sessions(0)

        mock_business_metrics.record_sessions.assert_called_once_with(0)

    def test_record_queue_length_delegates(self, port: MetricsPortImpl, mock_business_metrics: MagicMock):
        """record_queue_length(n) 应委托给 BusinessMetricsCollector.record_queue_length(n)"""
        port.record_queue_length(100)

        mock_business_metrics.record_queue_length.assert_called_once_with(100)

    def test_record_queue_length_with_zero(self, port: MetricsPortImpl, mock_business_metrics: MagicMock):
        """record_queue_length(0) 应传递零值"""
        port.record_queue_length(0)

        mock_business_metrics.record_queue_length.assert_called_once_with(0)

    def test_record_cache_hit_delegates(self, port: MetricsPortImpl, mock_business_metrics: MagicMock):
        """record_cache_hit() 应委托给 BusinessMetricsCollector.record_cache_hit()"""
        port.record_cache_hit()

        mock_business_metrics.record_cache_hit.assert_called_once_with()

    def test_record_cache_miss_delegates(self, port: MetricsPortImpl, mock_business_metrics: MagicMock):
        """record_cache_miss() 应委托给 BusinessMetricsCollector.record_cache_miss()"""
        port.record_cache_miss()

        mock_business_metrics.record_cache_miss.assert_called_once_with()

    def test_record_event_processed_delegates(self, port: MetricsPortImpl, mock_business_metrics: MagicMock):
        """record_event_processed() 应委托给 BusinessMetricsCollector.record_event_processed()"""
        port.record_event_processed()

        mock_business_metrics.record_event_processed.assert_called_once_with()

    def test_update_processing_rate_delegates(self, port: MetricsPortImpl, mock_business_metrics: MagicMock):
        """update_processing_rate() 应委托给 BusinessMetricsCollector.update_processing_rate()"""
        port.update_processing_rate()

        mock_business_metrics.update_processing_rate.assert_called_once_with()


class TestMetricsPortImplPropertyGetters:
    """验证 MetricsPortImpl 的属性访问方法正确读取 BusinessMetricsCollector 的属性"""

    @pytest.fixture
    def mock_aggregator(self) -> MagicMock:
        """创建 MetricsAggregator mock"""
        return MagicMock()

    @pytest.fixture
    def mock_business_metrics(self) -> MagicMock:
        """创建 BusinessMetricsCollector mock，设置预设属性值"""
        bm = MagicMock()
        bm.hit_rate = 0.85
        bm.sessions = 12
        bm.queue_length = 37
        bm.processing_rate = 2.718
        return bm

    @pytest.fixture
    def port(self, mock_aggregator: MagicMock, mock_business_metrics: MagicMock) -> MetricsPortImpl:
        """创建注入 mock 的 MetricsPortImpl 实例"""
        return MetricsPortImpl(
            aggregator=mock_aggregator,
            business_metrics=mock_business_metrics,
        )

    def test_get_hit_rate_returns_business_metrics_hit_rate(self, port: MetricsPortImpl, mock_business_metrics: MagicMock):
        """get_hit_rate() 应返回 BusinessMetricsCollector.hit_rate 的值"""
        assert port.get_hit_rate() == 0.85

    def test_get_sessions_returns_business_metrics_sessions(self, port: MetricsPortImpl, mock_business_metrics: MagicMock):
        """get_sessions() 应返回 BusinessMetricsCollector.sessions 的值"""
        assert port.get_sessions() == 12

    def test_get_queue_length_returns_business_metrics_queue_length(
        self, port: MetricsPortImpl, mock_business_metrics: MagicMock
    ):
        """get_queue_length() 应返回 BusinessMetricsCollector.queue_length 的值"""
        assert port.get_queue_length() == 37

    def test_get_processing_rate_returns_business_metrics_processing_rate(
        self, port: MetricsPortImpl, mock_business_metrics: MagicMock
    ):
        """get_processing_rate() 应返回 BusinessMetricsCollector.processing_rate 的值"""
        assert port.get_processing_rate() == 2.718

    def test_property_getters_reflect_updated_values(self, port: MetricsPortImpl, mock_business_metrics: MagicMock):
        """属性访问器应反映底层 mock 更新后的值（非缓存）"""
        mock_business_metrics.hit_rate = 0.5
        mock_business_metrics.sessions = 99
        mock_business_metrics.queue_length = 0
        mock_business_metrics.processing_rate = 0.0

        assert port.get_hit_rate() == 0.5
        assert port.get_sessions() == 99
        assert port.get_queue_length() == 0
        assert port.get_processing_rate() == 0.0


class TestMetricsPortImplIsolation:
    """验证 MetricsPortImpl 各方法之间的隔离性——调用一个方法不影响其他组件"""

    @pytest.fixture
    def mock_aggregator(self) -> MagicMock:
        """创建 MetricsAggregator mock"""
        return MagicMock()

    @pytest.fixture
    def mock_business_metrics(self) -> MagicMock:
        """创建 BusinessMetricsCollector mock"""
        return MagicMock()

    @pytest.fixture
    def port(self, mock_aggregator: MagicMock, mock_business_metrics: MagicMock) -> MetricsPortImpl:
        """创建注入 mock 的 MetricsPortImpl 实例"""
        return MetricsPortImpl(
            aggregator=mock_aggregator,
            business_metrics=mock_business_metrics,
        )

    def test_business_metrics_call_does_not_touch_aggregator(self, port: MetricsPortImpl, mock_aggregator: MagicMock):
        """调用业务指标方法不应触发聚合器的任何方法"""
        port.record_sessions(5)
        port.record_cache_hit()

        mock_aggregator.collect.assert_not_called()
        mock_aggregator.collect_as_dict.assert_not_called()

    def test_aggregator_call_does_not_touch_business_metrics(self, port: MetricsPortImpl, mock_business_metrics: MagicMock):
        """调用聚合器方法不应触发业务指标收集器的任何方法"""
        port.collect()

        mock_business_metrics.record_sessions.assert_not_called()
        mock_business_metrics.record_queue_length.assert_not_called()
        mock_business_metrics.record_cache_hit.assert_not_called()
        mock_business_metrics.record_cache_miss.assert_not_called()
        mock_business_metrics.record_event_processed.assert_not_called()
        mock_business_metrics.update_processing_rate.assert_not_called()


class TestMetricsPortImplWithRealRegistry:
    """使用真实 CollectorRegistry 验证 MetricsPortImpl 端到端委托行为"""

    @pytest.fixture
    def port_with_real_deps(self):
        """创建使用真实依赖的 MetricsPortImpl 实例"""
        from prometheus_client import CollectorRegistry

        from src.infrastructure.monitoring.aggregator import MetricsAggregator
        from src.infrastructure.monitoring.business_metrics import BusinessMetricsCollector
        from src.infrastructure.monitoring.event_metrics import EventMetricsCollector

        registry = CollectorRegistry()
        event_collector = EventMetricsCollector()
        business_collector = BusinessMetricsCollector(registry=registry)
        aggregator = MetricsAggregator(
            event_metrics_collector=event_collector,
            business_metrics_collector=business_collector,
            registry=registry,
        )

        port = MetricsPortImpl(
            aggregator=aggregator,
            business_metrics=business_collector,
            registry=registry,
        )
        return port, business_collector

    def test_collect_returns_bytes(self, port_with_real_deps):
        """collect() 通过完整委托链应返回有效的 Prometheus 文本格式"""
        port, _ = port_with_real_deps

        output = port.collect()
        assert isinstance(output, bytes)
        assert len(output) > 0

    def test_record_sessions_updates_get_sessions(self, port_with_real_deps):
        """record_sessions → get_sessions 端到端验证"""
        port, _ = port_with_real_deps

        port.record_sessions(7)
        assert port.get_sessions() == 7

    def test_record_queue_length_updates_get_queue_length(self, port_with_real_deps):
        """record_queue_length → get_queue_length 端到端验证"""
        port, _ = port_with_real_deps

        port.record_queue_length(15)
        assert port.get_queue_length() == 15

    def test_cache_hit_miss_updates_hit_rate(self, port_with_real_deps):
        """record_cache_hit/miss → get_hit_rate 端到端验证"""
        port, _ = port_with_real_deps

        port.record_cache_hit()
        port.record_cache_hit()
        port.record_cache_miss()

        hit_rate = port.get_hit_rate()
        assert abs(hit_rate - (2.0 / 3.0)) < 0.01
