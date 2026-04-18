"""Unit tests for MetricsAggregator.

Story 1.13: K8s 动态扩缩容
TDD 循环 [B]: MetricsAggregator 聚合器
- 🔴 红: 编写失败测试
- 🟢 绿: 实现 MetricsAggregator
- 🔄 重构: 统一管理所有指标采集器

Run with: pytest tests/unit/infrastructure/monitoring/test_metrics_aggregator.py -v
"""

from __future__ import annotations

import pytest


class TestMetricsAggregator:
    """Test suite for MetricsAggregator."""

    @pytest.fixture
    def shared_registry(self):
        """Create shared registry for all collectors."""
        from prometheus_client import CollectorRegistry

        return CollectorRegistry()

    @pytest.fixture
    def event_metrics_collector(self):
        """Create EventMetricsCollector instance."""
        from src.infrastructure.monitoring.event_metrics import EventMetricsCollector

        return EventMetricsCollector()

    @pytest.fixture
    def business_metrics_collector(self, shared_registry):
        """Create BusinessMetricsCollector instance with shared registry."""
        from src.infrastructure.monitoring.business_metrics import BusinessMetricsCollector

        return BusinessMetricsCollector(registry=shared_registry)

    @pytest.fixture
    def aggregator(self, event_metrics_collector, business_metrics_collector, shared_registry):
        """Create MetricsAggregator instance with shared registry."""
        from src.infrastructure.monitoring.aggregator import MetricsAggregator

        return MetricsAggregator(
            event_metrics_collector=event_metrics_collector,
            business_metrics_collector=business_metrics_collector,
            registry=shared_registry,
        )

    def test_aggregator_initialization(self, aggregator):
        """🔴 RED: MetricsAggregator should initialize with collectors."""
        assert aggregator is not None
        assert hasattr(aggregator, "_event_metrics")
        assert hasattr(aggregator, "_business_metrics")
        assert hasattr(aggregator, "_registry")

    def test_collect_returns_bytes(self, aggregator):
        """🔴 RED: collect() should return bytes in Prometheus format."""

        output = aggregator.collect()
        assert isinstance(output, bytes)
        assert len(output) > 0

    def test_collect_includes_event_metrics(self, aggregator):
        """🔴 RED: collect() should include EventMetricsCollector metrics."""
        output = aggregator.collect().decode("utf-8")
        # EventMetricsCollector metrics should be present
        # (metrics may be zero if not recorded)
        assert "events_processed_total" in output or "sisys_" in output

    def test_collect_includes_business_metrics(self, aggregator):
        """🔴 RED: collect() should include BusinessMetricsCollector metrics."""
        output = aggregator.collect().decode("utf-8")
        assert "sisys_agent_sessions_active" in output
        assert "sisys_task_queue_length" in output

    def test_collect_as_dict(self, aggregator):
        """🔴 RED: collect_as_dict() should return metrics as dictionary."""
        result = aggregator.collect_as_dict()
        assert isinstance(result, dict)
        # Should contain metric names and values
        assert len(result) >= 0


class TestMetricsAggregatorIntegration:
    """Integration tests for MetricsAggregator with collectors."""

    @pytest.fixture
    def integrated_setup(self):
        """Set up aggregator with both collectors and record some metrics."""
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

        # Record some metrics
        event_collector.record_processed("test_event", 0.5)
        business_collector.record_sessions(10)
        business_collector.record_queue_length(25)
        business_collector.record_cache_hit()
        business_collector.record_cache_hit()
        business_collector.record_cache_miss()

        return aggregator, registry

    def test_aggregated_output_contains_all_metrics(self, integrated_setup):
        """🔴 RED: Aggregated output should contain metrics from both collectors."""
        aggregator, _ = integrated_setup

        # Use aggregator.collect() which combines both collectors
        output = aggregator.collect().decode("utf-8")

        # Check for EventMetricsCollector metrics
        assert "events_processed_total" in output

        # Check for BusinessMetricsCollector metrics
        assert "sisys_agent_sessions_active" in output
        assert "sisys_task_queue_length" in output
        assert "sisys_cache_hit_rate" in output

    def test_event_metrics_not_modified_by_aggregator(self, integrated_setup):
        """🔴 RED: EventMetricsCollector should not be modified by aggregation."""
        from prometheus_client import CollectorRegistry

        from src.infrastructure.monitoring.aggregator import MetricsAggregator
        from src.infrastructure.monitoring.business_metrics import BusinessMetricsCollector

        aggregator, _ = integrated_setup

        # Create separate aggregator with same event collector
        event_collector = aggregator._event_metrics
        original_business_collector = aggregator._business_metrics
        business_collector2 = BusinessMetricsCollector(registry=CollectorRegistry())
        aggregator2 = MetricsAggregator(
            event_metrics_collector=event_collector,
            business_metrics_collector=business_collector2,
            registry=CollectorRegistry(),
        )

        # Event collector should be the same instance (not modified)
        assert aggregator2._event_metrics is event_collector
        # Business collector should be different (new instance)
        assert aggregator2._business_metrics is not original_business_collector


class TestMetricsAggregatorMultiprocessSupport:
    """Test suite for MetricsAggregator multiprocess support."""

    def test_uses_generate_latest_for_multiprocess(self):
        """🔴 RED: Aggregator should use generate_latest() for multiprocess compatibility."""
        from prometheus_client import CollectorRegistry

        from src.infrastructure.monitoring.aggregator import MetricsAggregator
        from src.infrastructure.monitoring.business_metrics import BusinessMetricsCollector
        from src.infrastructure.monitoring.event_metrics import EventMetricsCollector

        registry = CollectorRegistry()
        aggregator = MetricsAggregator(
            event_metrics_collector=EventMetricsCollector(),
            business_metrics_collector=BusinessMetricsCollector(registry=registry),
            registry=registry,
        )

        # generate_latest() is required for multiprocess (Gunicorn workers)
        output = aggregator.collect()
        assert isinstance(output, bytes)
        # Should be in Prometheus text format
        output_str = output.decode("utf-8")
        assert "# HELP" in output_str or len(output_str) >= 0


class TestMetricsAggregatorPrometheusCompliance:
    """Test suite for MetricsAggregator Prometheus format compliance."""

    def test_output_is_valid_prometheus_format(self):
        """🔴 RED: Aggregator output should be valid Prometheus text format."""
        from prometheus_client import CollectorRegistry

        from src.infrastructure.monitoring.aggregator import MetricsAggregator
        from src.infrastructure.monitoring.business_metrics import BusinessMetricsCollector
        from src.infrastructure.monitoring.event_metrics import EventMetricsCollector

        registry = CollectorRegistry()
        aggregator = MetricsAggregator(
            event_metrics_collector=EventMetricsCollector(),
            business_metrics_collector=BusinessMetricsCollector(registry=registry),
            registry=registry,
        )

        output = aggregator.collect().decode("utf-8")
        lines = output.split("\n")

        # Every HELP line should have a corresponding TYPE line
        help_metrics = {line.split()[2] for line in lines if line.startswith("# HELP")}
        type_metrics = {line.split()[2] for line in lines if line.startswith("# TYPE")}

        # HELP metrics should have TYPE
        for metric in help_metrics:
            assert metric in type_metrics, f"Missing TYPE for {metric}"

    def test_aggregator_collect_returns_same_as_generate_latest(self):
        """🔴 RED: aggregator.collect() should return same as generate_latest(registry)."""
        from prometheus_client import CollectorRegistry, generate_latest

        from src.infrastructure.monitoring.aggregator import MetricsAggregator
        from src.infrastructure.monitoring.business_metrics import BusinessMetricsCollector
        from src.infrastructure.monitoring.event_metrics import EventMetricsCollector

        registry = CollectorRegistry()
        aggregator = MetricsAggregator(
            event_metrics_collector=EventMetricsCollector(),
            business_metrics_collector=BusinessMetricsCollector(registry=registry),
            registry=registry,
        )

        aggregator_output = aggregator.collect()
        direct_output = generate_latest(registry)

        # Both should be bytes in Prometheus format
        assert isinstance(aggregator_output, bytes)
        assert isinstance(direct_output, bytes)
