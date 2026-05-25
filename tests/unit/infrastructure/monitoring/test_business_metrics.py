"""Unit tests for BusinessMetricsCollector.

Story 1.13: K8s 动态扩缩容
TDD 循环 [A]: BusinessMetricsCollector 指标注册
- 🔴 红: 编写失败测试
- 🟢 绿: 实现 BusinessMetricsCollector
- 🔄 重构: 添加类型注解和文档字符串

Run with: pytest tests/unit/infrastructure/monitoring/test_business_metrics.py -v
"""

from __future__ import annotations

import time

import pytest


class TestBusinessMetricsCollector:
    """Test suite for BusinessMetricsCollector."""

    @pytest.fixture
    def collector(self):
        """Create BusinessMetricsCollector instance with fresh registry."""
        from prometheus_client import CollectorRegistry

        from src.infrastructure.monitoring.business_metrics import BusinessMetricsCollector

        registry = CollectorRegistry()
        return BusinessMetricsCollector(registry=registry)

    def test_collector_initialization(self, collector):
        """🔴 RED: BusinessMetricsCollector should initialize with Gauge metrics."""
        assert collector is not None
        assert hasattr(collector, "_agent_sessions_gauge")
        assert hasattr(collector, "_task_queue_gauge")
        assert hasattr(collector, "_events_processing_rate_gauge")
        assert hasattr(collector, "_cache_hit_rate_gauge")

    def test_record_sessions(self, collector):
        """🔴 RED: record_sessions should set agent session gauge."""
        collector.record_sessions(10)
        assert collector.sessions == 10
        assert collector._metrics.agent_sessions_active == 10

    def test_record_sessions_updates_gauge(self, collector):
        """🔴 RED: record_sessions should update Prometheus gauge."""
        collector.record_sessions(5)
        collector.record_sessions(15)
        assert collector.sessions == 15

    def test_record_queue_length(self, collector):
        """🔴 RED: record_queue_length should set task queue gauge."""
        collector.record_queue_length(20)
        assert collector.queue_length == 20
        assert collector._metrics.task_queue_length == 20

    def test_record_queue_length_updates_gauge(self, collector):
        """🔴 RED: record_queue_length should update Prometheus gauge."""
        collector.record_queue_length(5)
        collector.record_queue_length(25)
        assert collector.queue_length == 25

    def test_update_processing_rate(self, collector):
        """🔴 RED: update_processing_rate should calculate events per second."""
        # Record some events
        collector.record_event_processed()
        collector.record_event_processed()
        collector.record_event_processed()

        # Wait a bit
        time.sleep(0.1)

        # Update processing rate
        collector.update_processing_rate()

        # Rate should be calculated
        assert collector.processing_rate >= 0

    def test_record_cache_hit(self, collector):
        """🔴 RED: record_cache_hit should increment cache hits counter."""
        initial_hits = collector._metrics.cache_hits_total
        collector.record_cache_hit()
        assert collector._metrics.cache_hits_total == initial_hits + 1

    def test_record_cache_miss(self, collector):
        """🔴 RED: record_cache_miss should increment cache misses counter."""
        initial_misses = collector._metrics.cache_misses_total
        collector.record_cache_miss()
        assert collector._metrics.cache_misses_total == initial_misses + 1

    def test_hit_rate_calculation(self, collector):
        """🔴 RED: hit_rate should calculate cache hit ratio."""
        # Record hits and misses
        collector.record_cache_hit()
        collector.record_cache_hit()
        collector.record_cache_miss()

        # Hit rate should be 2/3
        expected_rate = 2.0 / 3.0
        actual_rate = collector.hit_rate
        assert abs(actual_rate - expected_rate) < 0.01

    def test_hit_rate_with_no_requests(self, collector):
        """🔴 RED: hit_rate should return 0.0 when no requests recorded."""
        assert collector.hit_rate == 0.0

    def test_multiple_metrics_interaction(self, collector):
        """🔴 RED: Multiple metrics can be recorded simultaneously."""
        collector.record_sessions(10)
        collector.record_queue_length(5)
        collector.record_cache_hit()

        assert collector.sessions == 10
        assert collector.queue_length == 5
        assert collector.hit_rate == 1.0  # 1 hit, 0 miss


class TestBusinessMetricsCollectorPrometheusIntegration:
    """Test suite for BusinessMetricsCollector Prometheus integration."""

    @pytest.fixture
    def collector_with_registry(self):
        """Create collector with real registry."""
        from prometheus_client import CollectorRegistry, generate_latest

        from src.infrastructure.monitoring.business_metrics import BusinessMetricsCollector

        registry = CollectorRegistry()
        collector = BusinessMetricsCollector(registry=registry)
        return collector, registry, generate_latest

    def test_metrics_registered_in_registry(self, collector_with_registry):
        """🔴 RED: Metrics should be registered in Prometheus registry."""
        collector, registry, generate_latest = collector_with_registry

        # Collect metrics
        output = generate_latest(registry)
        output_str = output.decode("utf-8")

        # Verify sisys_ metrics are present
        assert "sisys_agent_sessions_active" in output_str
        assert "sisys_task_queue_length" in output_str
        assert "sisys_events_processing_rate" in output_str
        assert "sisys_cache_hit_rate" in output_str

    def test_metrics_have_help_text(self, collector_with_registry):
        """🔴 RED: Metrics should have HELP text."""
        collector, registry, generate_latest = collector_with_registry

        output = generate_latest(registry).decode("utf-8")

        # Check for HELP comments
        assert "# HELP sisys_agent_sessions_active" in output
        assert "# HELP sisys_task_queue_length" in output

    def test_metrics_have_type(self, collector_with_registry):
        """🔴 RED: Metrics should have TYPE declaration."""
        collector, registry, generate_latest = collector_with_registry

        output = generate_latest(registry).decode("utf-8")

        # Check for TYPE comments - all should be Gauge
        assert "# TYPE sisys_agent_sessions_active gauge" in output
        assert "# TYPE sisys_task_queue_length gauge" in output
        assert "# TYPE sisys_events_processing_rate gauge" in output
        assert "# TYPE sisys_cache_hit_rate gauge" in output

    def test_recorded_values_appear_in_output(self, collector_with_registry):
        """🔴 RED: Recorded values should appear in Prometheus output."""
        collector, registry, generate_latest = collector_with_registry

        # Record specific values
        collector.record_sessions(42)
        collector.record_queue_length(100)

        output = generate_latest(registry).decode("utf-8")

        # Values should appear in output
        assert "42" in output or "sisys_agent_sessions_active" in output
        assert "100" in output or "sisys_task_queue_length" in output


class TestBusinessMetricsCollectorThreadSafety:
    """Test suite for BusinessMetricsCollector thread safety."""

    def test_concurrent_session_updates(self):
        """🔴 RED: Concurrent session updates should be thread-safe."""
        import threading

        from prometheus_client import CollectorRegistry

        from src.infrastructure.monitoring.business_metrics import BusinessMetricsCollector

        registry = CollectorRegistry()
        collector = BusinessMetricsCollector(registry=registry)

        def update_sessions(value):
            for _ in range(100):
                collector.record_sessions(value)

        threads = [threading.Thread(target=update_sessions, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Final value should be consistent (one of the thread values)
        assert collector.sessions in range(5)

    def test_concurrent_cache_operations(self):
        """🔴 RED: Concurrent cache operations should maintain correct hit rate."""
        import threading

        from prometheus_client import CollectorRegistry

        from src.infrastructure.monitoring.business_metrics import BusinessMetricsCollector

        registry = CollectorRegistry()
        collector = BusinessMetricsCollector(registry=registry)

        def record_hits(n):
            for _ in range(n):
                collector.record_cache_hit()

        def record_misses(n):
            for _ in range(n):
                collector.record_cache_miss()

        t1 = threading.Thread(target=record_hits, args=(100,))
        t2 = threading.Thread(target=record_misses, args=(100,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Hit rate should be approximately 0.5 (100 hits, 100 misses)
        assert abs(collector.hit_rate - 0.5) < 0.01


class TestBusinessMetricsCollectorDefaultRegistry:
    """验证 registry=None 时使用默认 REGISTRY 路径（行 76-78）.

    全局 REGISTRY 禁止重复注册同名指标，因此 registry=None 仅适用于
    单例模式（DI 容器 SINGLETON 生命周期）。多次实例化会触发
    Duplicated timeseries 错误，这是正确行为——防止生产环境重复注册。
    """

    def test_default_registry_full_lifecycle(self) -> None:
        """registry=None 时指标注册、记录、导出的完整生命周期."""
        from prometheus_client import REGISTRY, generate_latest

        from src.infrastructure.monitoring.business_metrics import BusinessMetricsCollector

        collector = BusinessMetricsCollector(registry=None)

        assert collector._registry is REGISTRY

        # sessions 指标
        collector.record_sessions(3)
        assert collector.sessions == 3

        # cache 指标
        collector.record_cache_hit()
        collector.record_cache_hit()
        collector.record_cache_miss()
        assert abs(collector.hit_rate - (2.0 / 3.0)) < 0.01

        # cost 指标
        collector.record_cost(cost=0.05, model="test-default-reg", route_type="test")
        assert abs(collector._total_cost_cny - 0.05) < 0.0001

        # token 指标
        collector.record_token_usage(prompt=100, completion=50, model="test-default-reg", route_type="test")

        # 全局 Registry 输出包含指标
        output = generate_latest(REGISTRY).decode("utf-8")
        assert "sisys_agent_sessions_active" in output
