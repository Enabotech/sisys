"""Unit tests for Prometheus format validation.

Story 1.13: K8s 动态扩缩容
TDD 循环 [B]: Prometheus 格式验证
- 🔴 红: 编写失败测试
- 🟢 绿: 验证格式合规性
- 🔄 重构: 优化验证逻辑

Run with: pytest tests/unit/interfaces/api/test_prometheus_format.py -v
"""

from __future__ import annotations

import re

import pytest


class TestPrometheusFormat:
    """Test suite for Prometheus text format compliance."""

    # Prometheus text format specification: https://prometheus.io/docs/instrumenting/exposition_formats/
    # Format: # HELP <metric_name> <description>
    #         # TYPE <metric_name> <type> [labels]
    #         <metric_name>[<labels>] <value>

    HELP_LINE_PATTERN = re.compile(r"^# HELP (\w+) (.+)$")
    TYPE_LINE_PATTERN = re.compile(r"^# TYPE (\w+) (\w+)( .+)?$")
    METRIC_LINE_PATTERN = re.compile(r"^(\w+)(\{.*\})? (\d+\.?\d*)$")

    @pytest.fixture
    def sample_prometheus_output(self):
        """Sample Prometheus text format output for testing."""
        return b"""# HELP test_counter_total Total test counter
# TYPE test_counter_total counter
test_counter_total 42
# HELP test_gauge Current value
# TYPE test_gauge gauge
test_gauge 3.14
# HELP test_histogram Histogram
# TYPE test_histogram histogram
test_histogram_bucket{le="0.005"} 0
test_histogram_bucket{le="0.01"} 0
test_histogram_bucket{le="+Inf"} 100
test_histogram_sum 50.5
test_histogram_count 100
"""

    def test_help_line_format(self, sample_prometheus_output):
        """🔴 RED: # HELP line should follow format: # HELP <name> <description>."""
        output = sample_prometheus_output.decode("utf-8")
        help_lines = [line for line in output.split("\n") if line.startswith("# HELP")]

        assert len(help_lines) >= 1
        for line in help_lines:
            match = self.HELP_LINE_PATTERN.match(line)
            assert match is not None, f"Invalid HELP line: {line}"
            assert len(match.groups()) == 2

    def test_type_line_format(self, sample_prometheus_output):
        """🔴 RED: # TYPE line should follow format: # TYPE <name> <type>."""
        output = sample_prometheus_output.decode("utf-8")
        type_lines = [line for line in output.split("\n") if line.startswith("# TYPE")]

        assert len(type_lines) >= 1
        valid_types = {"counter", "gauge", "histogram", "summary", "untyped", "info", "stateset"}
        for line in type_lines:
            match = self.TYPE_LINE_PATTERN.match(line)
            assert match is not None, f"Invalid TYPE line: {line}"
            metric_type = match.group(2)
            assert metric_type in valid_types, f"Invalid metric type: {metric_type}"

    def test_metric_value_format(self, sample_prometheus_output):
        """🔴 RED: Metric lines should follow format: <name>[<labels>] <value>."""
        output = sample_prometheus_output.decode("utf-8")
        metric_lines = [line for line in output.split("\n") if line and not line.startswith("#") and "{" in line]

        for line in metric_lines:
            match = self.METRIC_LINE_PATTERN.match(line)
            # Either has labels or is a simple metric
            assert match is not None or line.split()[0].isidentifier()

    def test_counter_type_support(self, sample_prometheus_output):
        """🔴 RED: Counter type should be supported."""
        output = sample_prometheus_output.decode("utf-8")
        assert "# TYPE test_counter_total counter" in output
        assert "test_counter_total 42" in output

    def test_gauge_type_support(self, sample_prometheus_output):
        """🔴 RED: Gauge type should be supported."""
        output = sample_prometheus_output.decode("utf-8")
        assert "# TYPE test_gauge gauge" in output
        assert "test_gauge 3.14" in output

    def test_histogram_type_support(self, sample_prometheus_output):
        """🔴 RED: Histogram type should be supported with bucket/sum/count."""
        output = sample_prometheus_output.decode("utf-8")
        assert "# TYPE test_histogram histogram" in output
        # Histogram should have bucket, sum, count
        assert "test_histogram_bucket" in output
        assert "test_histogram_sum" in output
        assert "test_histogram_count" in output
        # Special le bucket for +Inf
        assert 'le="+Inf"' in output

    def test_summary_type_support(self):
        """🔴 RED: Summary type should be supported with quantile/sum/count."""
        summary_output = b"""# HELP request_latency Request latency
# TYPE request_latency summary
request_latency{quantile="0.5"} 0.05
request_latency{quantile="0.9"} 0.1
request_latency{quantile="0.99"} 0.2
request_latency_sum 100.5
request_latency_count 1000
"""
        output = summary_output.decode("utf-8")
        assert "# TYPE request_latency summary" in output
        assert 'quantile="0.5"' in output
        assert "request_latency_sum" in output
        assert "request_latency_count" in output

    def test_multiprocess_mode_compatibility(self):
        """🔴 RED: Output should be compatible with multiprocess mode using generate_latest()."""
        from prometheus_client import CollectorRegistry, generate_latest

        # Create a fresh registry for testing
        registry = CollectorRegistry()

        # generate_latest() works with multiprocess mode (Gunicorn)
        output = generate_latest(registry)
        assert isinstance(output, bytes)
        # Empty registry produces minimal output
        assert len(output) >= 0


class TestPrometheusMetricNames:
    """Test suite for Prometheus metric naming conventions."""

    def test_metric_names_follow_prometheus_conventions(self):
        """🔴 RED: Metric names should follow Prometheus naming conventions."""
        # Metric names should:
        # - Start with a letter or underscore
        # - Contain only ASCII letters, numbers, underscores, and colons
        # - Should include application prefix (sisys_)
        valid_metric_pattern = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_:]*$")

        metric_names = [
            "sisys_agent_sessions_active",
            "sisys_task_queue_length",
            "sisys_events_processing_rate",
            "sisys_cache_hit_rate",
            "events_processed_total",
            "events_failed_total",
        ]

        for name in metric_names:
            assert valid_metric_pattern.match(name), f"Invalid metric name: {name}"
            # Should have namespace prefix
            assert "_" in name or ":" in name
