"""EventMetrics cache hit/miss extension tests."""

from __future__ import annotations

import pytest

from src.infrastructure.monitoring.event_metrics import EventMetrics, EventMetricsCollector


class TestEventMetricsExtension:
    """EventMetrics 缓存计数器测试。"""

    def test_cache_hits_total_default(self) -> None:
        """cache_hits_total 默认值为 0。"""
        metrics = EventMetrics()
        assert metrics.cache_hits_total == 0

    def test_cache_misses_total_default(self) -> None:
        """cache_misses_total 默认值为 0。"""
        metrics = EventMetrics()
        assert metrics.cache_misses_total == 0


class TestEventMetricsCollectorCache:
    """EventMetricsCollector 缓存方法测试。"""

    def test_record_cache_hit(self) -> None:
        """record_cache_hit 应增加 cache_hits_total。"""
        collector = EventMetricsCollector()
        collector.record_cache_hit()
        assert collector.metrics.cache_hits_total == 1

    def test_record_cache_miss(self) -> None:
        """record_cache_miss 应增加 cache_misses_total。"""
        collector = EventMetricsCollector()
        collector.record_cache_miss()
        assert collector.metrics.cache_misses_total == 1

    def test_multiple_hits_and_misses(self) -> None:
        """多次调用应正确累加。"""
        collector = EventMetricsCollector()
        collector.record_cache_hit()
        collector.record_cache_hit()
        collector.record_cache_miss()

        assert collector.metrics.cache_hits_total == 2
        assert collector.metrics.cache_misses_total == 1

    def test_hit_rate_zero_when_no_requests(self) -> None:
        """无请求时命中率应为 0.0。"""
        collector = EventMetricsCollector()
        assert collector.hit_rate == 0.0

    def test_hit_rate_100_percent(self) -> None:
        """全部命中时命中率应为 1.0。"""
        collector = EventMetricsCollector()
        collector.record_cache_hit()
        collector.record_cache_hit()
        assert collector.hit_rate == 1.0

    def test_hit_rate_0_percent(self) -> None:
        """全部未命中时命中率应为 0.0。"""
        collector = EventMetricsCollector()
        collector.record_cache_miss()
        collector.record_cache_miss()
        assert collector.hit_rate == 0.0

    def test_hit_rate_50_percent(self) -> None:
        """一半命中时命中率应为 0.5。"""
        collector = EventMetricsCollector()
        collector.record_cache_hit()
        collector.record_cache_miss()
        assert collector.hit_rate == pytest.approx(0.5)

    def test_hit_rate_custom_ratio(self) -> None:
        """自定义命中比例。"""
        collector = EventMetricsCollector()
        for _ in range(3):
            collector.record_cache_hit()
        for _ in range(7):
            collector.record_cache_miss()
        assert collector.hit_rate == pytest.approx(0.3)
