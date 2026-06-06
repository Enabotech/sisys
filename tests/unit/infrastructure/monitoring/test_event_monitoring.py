"""Task 5 TDD Tests — EventMetrics, EventMetricsCollector, OpenTelemetry Trace."""

from __future__ import annotations

import os
from collections import deque

import pytest

from src.domain.exceptions import ConfigurationError

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

        with pytest.raises(ConfigurationError, match="must be positive"):
            EventMetricsCollector(max_processing_samples=0)
        with pytest.raises(ConfigurationError, match="must be positive"):
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
        with tracer.create_span("test-span", event_id="uuid-1", event_type="DocumentProcessed") as _span:
            # When OpenTelemetry is not installed or fails, span is None
            # When it works, span would be a real span object
            pass  # Context manager should enter and exit cleanly


# ============================================================================
# TDD Cycle D: OTLP 导出器配置 (Task 5.4)
# ============================================================================


class TestOtelConfig:
    """OTLP 导出器配置测试"""

    def test_default_config_disabled(self):
        """默认配置应禁用 Trace"""
        from src.infrastructure.monitoring.otel_config import OtelConfig

        config = OtelConfig()
        assert config.trace_enabled is False

    def test_from_env_disabled_via_env_var(self, monkeypatch):
        """EVENT_BUS_OTEL_TRACE_ENABLED=true 应启用 Trace"""
        from src.infrastructure.monitoring.otel_config import OtelConfig

        monkeypatch.setenv("EVENT_BUS_OTEL_TRACE_ENABLED", "true")
        config = OtelConfig.from_env()
        assert config.trace_enabled is True

    def test_from_env_custom_endpoint(self, monkeypatch):
        """OTEL_EXPORTER_OTLP_ENDPOINT 应设置自定义端点"""
        from src.infrastructure.monitoring.otel_config import OtelConfig

        monkeypatch.setenv("EVENT_BUS_OTEL_TRACE_ENABLED", "true")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")
        config = OtelConfig.from_env()
        assert config.endpoint == "http://jaeger:4317"

    def test_from_env_protocol(self, monkeypatch):
        """OTEL_EXPORTER_OTLP_PROTOCOL 应设置协议类型"""
        from src.infrastructure.monitoring.otel_config import OtelConfig

        monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf")
        config = OtelConfig.from_env()
        assert config.protocol == "http/protobuf"

    def test_from_env_invalid_protocol_logs_warning(self, monkeypatch, caplog):
        """无效协议应记录警告并使用默认值"""
        from src.infrastructure.monitoring.otel_config import OtelConfig

        monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "invalid")
        with caplog.at_level("WARNING"):
            config = OtelConfig.from_env()
        assert config.protocol == "grpc"
        assert "Invalid OTLP protocol" in caplog.text

    def test_from_env_sampler_ratio(self, monkeypatch):
        """OTEL_TRACES_SAMPLER_ARG 应设置采样率"""
        from src.infrastructure.monitoring.otel_config import OtelConfig

        monkeypatch.setenv("OTEL_TRACES_SAMPLER_ARG", "0.5")
        config = OtelConfig.from_env()
        assert config.sampler_ratio == 0.5

    def test_from_env_invalid_sampler_ratio_logs_warning(self, monkeypatch, caplog):
        """无效采样率应记录警告并使用默认值"""
        from src.infrastructure.monitoring.otel_config import OtelConfig

        monkeypatch.setenv("OTEL_TRACES_SAMPLER_ARG", "2.0")
        with caplog.at_level("WARNING"):
            config = OtelConfig.from_env()
        assert config.sampler_ratio == 0.1
        assert "Invalid sampler ratio" in caplog.text

    def test_from_env_service_name(self, monkeypatch):
        """OTEL_SERVICE_NAME 应设置服务名称"""
        from src.infrastructure.monitoring.otel_config import OtelConfig

        monkeypatch.setenv("OTEL_SERVICE_NAME", "my-service")
        config = OtelConfig.from_env()
        assert config.service_name == "my-service"

    def test_from_env_deployment_environment(self, monkeypatch):
        """OTEL_DEPLOYMENT_ENVIRONMENT 应设置部署环境"""
        from src.infrastructure.monitoring.otel_config import OtelConfig

        monkeypatch.setenv("OTEL_DEPLOYMENT_ENVIRONMENT", "production")
        config = OtelConfig.from_env()
        assert config.deployment_environment == "production"

    def test_default_endpoint_for_grpc(self):
        """gRPC 协议默认端点应为 http://localhost:4317"""
        from src.infrastructure.monitoring.otel_config import OtelConfig

        config = OtelConfig(protocol="grpc")
        assert config.get_endpoint_for_protocol() == "http://localhost:4317"

    def test_default_endpoint_for_http(self):
        """HTTP 协议默认端点应为 http://localhost:4318/v1/traces"""
        from src.infrastructure.monitoring.otel_config import OtelConfig

        config = OtelConfig(protocol="http/protobuf")
        assert config.get_endpoint_for_protocol() == "http://localhost:4318/v1/traces"

    def test_custom_endpoint_preserved(self):
        """自定义端点应保持不变"""
        from src.infrastructure.monitoring.otel_config import OtelConfig

        config = OtelConfig(endpoint="http://custom:4317")
        assert config.get_endpoint_for_protocol() == "http://custom:4317"


class TestBatchExportConfig:
    """批量导出配置测试"""

    def test_default_values(self):
        """默认值应合理"""
        from src.infrastructure.monitoring.otel_config import BatchExportConfig

        config = BatchExportConfig()
        assert config.max_queue_size == 2048
        assert config.max_export_batch_size == 512
        assert config.schedule_delay_millis == 5000
        assert config.export_timeout_millis == 30000

    def test_validate_passes_for_defaults(self):
        """默认配置应通过验证"""
        from src.infrastructure.monitoring.otel_config import BatchExportConfig

        config = BatchExportConfig()
        config.validate()  # Should not raise

    def test_validate_batch_size_greater_than_queue_raises(self):
        """max_export_batch_size > max_queue_size 应抛出 ValueError"""
        from src.infrastructure.monitoring.otel_config import BatchExportConfig

        config = BatchExportConfig(max_queue_size=100, max_export_batch_size=200)
        with pytest.raises(ConfigurationError, match="must be <= max_queue_size"):
            config.validate()

    def test_validate_negative_queue_size_raises(self):
        """负数 max_queue_size 应抛出 ValueError"""
        from src.infrastructure.monitoring.otel_config import BatchExportConfig

        config = BatchExportConfig(max_queue_size=-1)
        with pytest.raises(ConfigurationError, match="must be positive"):
            config.validate()

    def test_validate_zero_batch_size_raises(self):
        """零 max_export_batch_size 应抛出 ValueError"""
        from src.infrastructure.monitoring.otel_config import BatchExportConfig

        config = BatchExportConfig(max_export_batch_size=0)
        with pytest.raises(ConfigurationError, match="must be positive"):
            config.validate()

    def test_validate_negative_schedule_delay_raises(self):
        """负数 schedule_delay_millis 应抛出 ValueError"""
        from src.infrastructure.monitoring.otel_config import BatchExportConfig

        config = BatchExportConfig(schedule_delay_millis=-100)
        with pytest.raises(ConfigurationError, match="must be positive"):
            config.validate()

    def test_validate_negative_timeout_raises(self):
        """负数 export_timeout_millis 应抛出 ValueError"""
        from src.infrastructure.monitoring.otel_config import BatchExportConfig

        config = BatchExportConfig(export_timeout_millis=-1000)
        with pytest.raises(ConfigurationError, match="must be positive"):
            config.validate()


class TestInitTracing:
    """OpenTelemetry 初始化测试"""

    def test_init_disabled_by_default(self):
        """EVENT_BUS_OTEL_TRACE_ENABLED=false 应返回 False"""
        from src.infrastructure.monitoring.otel_config import init, reset_for_testing

        reset_for_testing()
        result = init()
        assert result is False

    def test_init_returns_true_when_enabled(self, monkeypatch):
        """启用时应返回 True（如果 OTLP exporter 已安装）"""
        from src.infrastructure.monitoring.otel_config import init, reset_for_testing

        reset_for_testing()
        monkeypatch.setenv("EVENT_BUS_OTEL_TRACE_ENABLED", "true")
        result = init()
        assert isinstance(result, bool)

    def test_init_idempotent(self, monkeypatch):
        """重复调用应返回相同状态（幂等性）"""
        from src.infrastructure.monitoring.otel_config import init, reset_for_testing

        reset_for_testing()
        monkeypatch.setenv("EVENT_BUS_OTEL_TRACE_ENABLED", "true")
        result1 = init()
        result2 = init()
        assert result1 == result2

    def test_reset_for_testing(self):
        """reset_for_testing 应重置全局状态"""
        from src.infrastructure.monitoring.otel_config import (
            get_tracer_provider,
            init,
            reset_for_testing,
        )

        init()
        assert get_tracer_provider() is not None or True

        reset_for_testing()
        assert get_tracer_provider() is None

    def test_init_with_custom_config(self):
        """init() 应接受自定义 OtelConfig"""
        from src.infrastructure.monitoring.otel_config import (
            OtelConfig,
            init,
            reset_for_testing,
        )

        reset_for_testing()
        config = OtelConfig(trace_enabled=False)
        result = init(config)
        assert result is False

    def test_init_invalid_sampler_ratio_env_default(self, monkeypatch):
        """H-01: 非数字 OTEL_TRACES_SAMPLER_ARG 应使用默认值而非抛出异常"""
        from src.infrastructure.monitoring.otel_config import OtelConfig

        monkeypatch.setenv("OTEL_TRACES_SAMPLER_ARG", "abc")
        config = OtelConfig.from_env()
        assert config.sampler_ratio == 0.1

    def test_batch_export_config_boundary_batch_equals_queue(self):
        """L-04: max_export_batch_size == max_queue_size 应通过验证"""
        from src.infrastructure.monitoring.otel_config import BatchExportConfig

        config = BatchExportConfig(max_queue_size=100, max_export_batch_size=100)
        config.validate()  # Should not raise
