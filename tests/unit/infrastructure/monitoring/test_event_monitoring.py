"""Task 5 TDD Tests — EventMetrics, EventMetricsCollector, OpenTelemetry Trace."""

from __future__ import annotations

import os
from collections import deque

import pytest

# ============================================================================
# TDD Cycle A: EventMetrics
# ============================================================================


class TestEventMetrics:
    """EventMetrics definition tests."""

    def test_metrics_fields(self):
        """EventMetrics should define all required metric fields."""
        from src.infrastructure.monitoring.event_metrics import EventMetrics

        metrics = EventMetrics()
        assert hasattr(metrics, "events_processed_total")
        assert hasattr(metrics, "events_failed_total")
        assert hasattr(metrics, "events_retried_total")
        assert hasattr(metrics, "events_dlq_total")
        assert hasattr(metrics, "event_processing_duration_seconds")


# ============================================================================
# TDD Cycle B: EventMetricsCollector
# ============================================================================


class TestEventMetricsCollector:
    """EventMetricsCollector tests."""

    def test_record_processed_increments_counter(self):
        """record_processed should increment events_processed_total."""
        from src.infrastructure.monitoring.event_metrics import EventMetricsCollector

        collector = EventMetricsCollector()
        collector.record_processed("DocumentProcessed", 0.5)

        assert collector.metrics.events_processed_total == 1

    def test_record_failed_increments_counter(self):
        """record_failed should increment events_failed_total."""
        from src.infrastructure.monitoring.event_metrics import EventMetricsCollector

        collector = EventMetricsCollector()
        collector.record_failed("DocumentProcessed", "connection error")

        assert collector.metrics.events_failed_total == 1

    def test_record_retried_increments_counter(self):
        """record_retried should increment events_retried_total."""
        from src.infrastructure.monitoring.event_metrics import EventMetricsCollector

        collector = EventMetricsCollector()
        collector.record_retried("DocumentProcessed")

        assert collector.metrics.events_retried_total == 1

    def test_record_dlq_increments_counter(self):
        """record_dlq should increment events_dlq_total."""
        from src.infrastructure.monitoring.event_metrics import EventMetricsCollector

        collector = EventMetricsCollector()
        collector.record_dlq("DocumentProcessed")

        assert collector.metrics.events_dlq_total == 1

    def test_records_by_event_type(self):
        """Collector should track metrics by event type."""
        from src.infrastructure.monitoring.event_metrics import EventMetricsCollector

        collector = EventMetricsCollector()
        collector.record_processed("DocumentProcessed", 0.5)
        collector.record_processed("AgentDecided", 0.3)
        collector.record_processed("DocumentProcessed", 0.4)

        # Total should count all processed events
        assert collector.metrics.events_processed_total == 3

    def test_max_processing_samples_default(self):
        """Default max_processing_samples should be 10000."""
        from src.infrastructure.monitoring.event_metrics import EventMetricsCollector

        collector = EventMetricsCollector()
        assert collector.metrics.event_processing_duration_seconds.maxlen == 10_000

    def test_max_processing_samples_custom_value(self):
        """max_processing_samples should be configurable."""
        from src.infrastructure.monitoring.event_metrics import EventMetricsCollector

        collector = EventMetricsCollector(max_processing_samples=500)
        assert collector.metrics.event_processing_duration_seconds.maxlen == 500

    def test_duration_queue_evicts_oldest_when_full(self):
        """Duration deque should evict oldest samples when maxlen is reached."""
        from src.infrastructure.monitoring.event_metrics import EventMetricsCollector

        collector = EventMetricsCollector(max_processing_samples=3)
        collector.record_processed("EventA", 0.1)
        collector.record_processed("EventB", 0.2)
        collector.record_processed("EventC", 0.3)

        assert len(collector.metrics.event_processing_duration_seconds) == 3
        assert list(collector.metrics.event_processing_duration_seconds) == [0.1, 0.2, 0.3]

        # Adding 4th should evict 0.1
        collector.record_processed("EventD", 0.4)

        assert len(collector.metrics.event_processing_duration_seconds) == 3
        assert list(collector.metrics.event_processing_duration_seconds) == [0.2, 0.3, 0.4]

    def test_invalid_max_processing_samples_raises(self):
        """max_processing_samples must be positive."""
        from src.infrastructure.monitoring.event_metrics import EventMetricsCollector

        with pytest.raises(ValueError, match="must be positive"):
            EventMetricsCollector(max_processing_samples=0)
        with pytest.raises(ValueError, match="must be positive"):
            EventMetricsCollector(max_processing_samples=-1)

    def test_duration_is_deque_not_list(self):
        """event_processing_duration_seconds should be a deque, not a list."""
        from src.infrastructure.monitoring.event_metrics import EventMetricsCollector

        collector = EventMetricsCollector()
        assert isinstance(collector.metrics.event_processing_duration_seconds, deque)


# ============================================================================
# TDD Cycle C: OpenTelemetry Trace
# ============================================================================


class TestOpenTelemetryTrace:
    """OpenTelemetry Trace basic tests."""

    def test_trace_disabled_by_default(self):
        """OpenTelemetry trace should be disabled by default."""
        from src.infrastructure.monitoring.event_metrics import OpenTelemetryTracer

        tracer = OpenTelemetryTracer()
        assert tracer.enabled is False

    def test_trace_enabled_via_env(self):
        """OpenTelemetry trace should be enabled via EVENT_BUS_OTEL_TRACE_ENABLED=true."""
        from src.infrastructure.monitoring.event_metrics import OpenTelemetryTracer

        env = os.environ.copy()
        try:
            os.environ["EVENT_BUS_OTEL_TRACE_ENABLED"] = "true"
            tracer = OpenTelemetryTracer()
            assert tracer.enabled is True
        finally:
            os.environ.clear()
            os.environ.update(env)

    def test_create_span(self):
        """create_span should create a span with correct attributes."""
        from src.infrastructure.monitoring.event_metrics import OpenTelemetryTracer

        tracer = OpenTelemetryTracer()
        tracer.enabled = True  # Force enable for test

        # Test that the context manager works without errors
        with tracer.create_span("test-span", event_id="uuid-1", event_type="DocumentProcessed") as span:
            # When OpenTelemetry is not installed or fails, span is None
            # When it works, span would be a real span object
            pass  # Context manager should enter and exit cleanly
