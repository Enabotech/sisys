"""EventMetrics 缓存扩展测试。"""

from __future__ import annotations

import pytest

from src.infrastructure.monitoring.event_metrics import EventMetricsCollector


class TestEventMetricsCacheExtension:
    """EventMetricsCollector 缓存扩展测试。"""

    def test_record_cache_hit(self) -> None:
        """record_cache_hit 应增加计数器。"""
        metrics = EventMetricsCollector()
        metrics.record_cache_hit()
        assert metrics.metrics.cache_hits_total == 1
        assert metrics.metrics.cache_misses_total == 0

    def test_record_cache_miss(self) -> None:
        """record_cache_miss 应增加计数器。"""
        metrics = EventMetricsCollector()
        metrics.record_cache_miss()
        assert metrics.metrics.cache_misses_total == 1
        assert metrics.metrics.cache_hits_total == 0

    def test_hit_rate_with_hits_and_misses(self) -> None:
        """命中率 = hits / (hits + misses)。"""
        metrics = EventMetricsCollector()
        metrics.record_cache_hit()
        metrics.record_cache_hit()
        metrics.record_cache_miss()
        metrics.record_cache_miss()
        metrics.record_cache_miss()
        assert metrics.hit_rate == pytest.approx(0.4)

    def test_hit_rate_zero_when_no_requests(self) -> None:
        """无请求时命中率应为 0.0。"""
        metrics = EventMetricsCollector()
        assert metrics.hit_rate == 0.0

    def test_hit_rate_100_percent(self) -> None:
        """全命中时命中率应为 1.0。"""
        metrics = EventMetricsCollector()
        metrics.record_cache_hit()
        metrics.record_cache_hit()
        assert metrics.hit_rate == 1.0

    def test_hit_rate_0_percent(self) -> None:
        """全未命中时命中率应为 0.0。"""
        metrics = EventMetricsCollector()
        metrics.record_cache_miss()
        metrics.record_cache_miss()
        assert metrics.hit_rate == 0.0

    def test_record_cache_hit_with_type(self) -> None:
        """record_cache_hit 支持 cache_type 参数。"""
        metrics = EventMetricsCollector()
        metrics.record_cache_hit(cache_type="session")
        assert metrics.metrics.cache_hits_total == 1

    def test_record_cache_miss_with_type(self) -> None:
        """record_cache_miss 支持 cache_type 参数。"""
        metrics = EventMetricsCollector()
        metrics.record_cache_miss(cache_type="session")
        assert metrics.metrics.cache_misses_total == 1

    def test_multiple_hit_miss_cycles(self) -> None:
        """多次循环后计数器应准确。"""
        metrics = EventMetricsCollector()
        for _ in range(10):
            metrics.record_cache_hit()
        for _ in range(5):
            metrics.record_cache_miss()
        assert metrics.metrics.cache_hits_total == 10
        assert metrics.metrics.cache_misses_total == 5
        assert metrics.hit_rate == pytest.approx(10 / 15)
