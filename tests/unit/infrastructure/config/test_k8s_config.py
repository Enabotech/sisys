"""Unit tests for K8s configuration validation.

Story 1.13: K8s 动态扩缩容
TDD 循环 [A]: K8s 配置验证
- 🔴 红: 编写失败测试
- 🟢 绿: 实现配置验证逻辑
- 🔄 重构: 配置验证器优化

Run with: pytest tests/unit/infrastructure/test_k8s_config.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


class TestServiceMonitorConfig:
    """Test suite for Prometheus ServiceMonitor configuration."""

    @pytest.fixture
    def servicemonitor_path(self):
        """Get ServiceMonitor config path."""
        return Path(__file__).resolve().parents[4] / "deploy/kubernetes/apps/sisys/base/prometheus-servicemonitor.yaml"

    def test_servicemonitor_file_exists(self, servicemonitor_path):
        """🔴 RED: ServiceMonitor configuration file should exist."""
        assert servicemonitor_path.exists(), f"ServiceMonitor not found at {servicemonitor_path}"

    def test_servicemonitor_has_required_fields(self, servicemonitor_path):
        """🔴 RED: ServiceMonitor should have required fields."""
        import yaml

        with open(servicemonitor_path) as f:
            content = f.read()

        # Skip YAML document separator
        lines = [line for line in content.split("\n") if line and not line.startswith("---")]
        yaml_content = "\n".join(lines)
        config = yaml.safe_load(yaml_content)

        assert config["kind"] == "ServiceMonitor"
        assert "metadata" in config
        assert "spec" in config
        assert config["metadata"]["name"] == "sisys-app"

    def test_servicemonitor_has_prometheus_scrape_endpoint(self, servicemonitor_path):
        """🔴 RED: ServiceMonitor should specify /metrics scrape endpoint."""
        import yaml

        with open(servicemonitor_path) as f:
            content = f.read()

        lines = [line for line in content.split("\n") if line and not line.startswith("---")]
        yaml_content = "\n".join(lines)
        config = yaml.safe_load(yaml_content)

        endpoints = config["spec"].get("endpoints", [])
        assert len(endpoints) > 0
        assert endpoints[0].get("path") == "/metrics"

    def test_servicemonitor_scrape_interval_15s(self, servicemonitor_path):
        """🔴 RED: ServiceMonitor scrape interval should be ≤15 seconds for HPA requirements."""
        import yaml

        with open(servicemonitor_path) as f:
            content = f.read()

        lines = [line for line in content.split("\n") if line and not line.startswith("---")]
        yaml_content = "\n".join(lines)
        config = yaml.safe_load(yaml_content)

        scrape_interval = config["spec"].get("scrapeInterval", "30s")
        # Parse interval (e.g., "15s")
        interval_seconds = int(scrape_interval.rstrip("s"))
        assert interval_seconds <= 15, f"scrapeInterval {scrape_interval} > 15s requirement"


class TestServiceAnnotations:
    """Test suite for Prometheus annotations on Service."""

    @pytest.fixture
    def service_path(self):
        """Get Service config path."""
        return Path(__file__).resolve().parents[4] / "deploy/kubernetes/apps/sisys/base/service.yaml"

    def test_service_has_prometheus_annotations(self, service_path):
        """🔴 RED: Service should have Prometheus scrape annotations."""
        import yaml

        with open(service_path) as f:
            content = f.read()

        # Parse multi-document YAML
        docs = list(yaml.safe_load_all(content))
        service_doc = next((d for d in docs if d and d.get("kind") == "Service"), None)

        assert service_doc is not None
        annotations = service_doc.get("metadata", {}).get("annotations", {})

        assert "prometheus.io/scrape" in annotations
        assert annotations["prometheus.io/scrape"] == "true"
        assert "prometheus.io/port" in annotations
        assert "prometheus.io/path" in annotations


class TestHPAConfig:
    """Test suite for HPA configuration."""

    @pytest.fixture
    def hpa_path(self):
        """Get HPA config path."""
        return Path(__file__).resolve().parents[4] / "deploy/kubernetes/apps/sisys/base/hpa.yaml"

    def test_hpa_file_exists(self, hpa_path):
        """🔴 RED: HPA configuration file should exist."""
        assert hpa_path.exists(), f"HPA config not found at {hpa_path}"

    def test_hpa_has_resource_metrics(self, hpa_path):
        """🔴 RED: HPA should have CPU and memory resource metrics."""
        import yaml

        with open(hpa_path) as f:
            content = f.read()

        docs = list(yaml.safe_load_all(content))
        hpa_doc = next((d for d in docs if d and d.get("kind") == "HorizontalPodAutoscaler"), None)

        assert hpa_doc is not None
        metrics = hpa_doc.get("spec", {}).get("metrics", [])

        resource_metrics = [m for m in metrics if m.get("type") == "Resource"]
        assert len(resource_metrics) >= 2  # CPU and memory

        resource_names = [m.get("resource", {}).get("name") for m in resource_metrics]
        assert "cpu" in resource_names
        assert "memory" in resource_names

    def test_hpa_min_replicas_positive(self, hpa_path):
        """🔴 RED: HPA minReplicas should be positive."""
        import yaml

        with open(hpa_path) as f:
            content = f.read()

        docs = list(yaml.safe_load_all(content))
        hpa_doc = next((d for d in docs if d and d.get("kind") == "HorizontalPodAutoscaler"), None)

        min_replicas = hpa_doc.get("spec", {}).get("minReplicas", 1)
        assert min_replicas >= 1

    def test_hpa_max_replicas_greater_than_min(self, hpa_path):
        """🔴 RED: HPA maxReplicas should be greater than minReplicas."""
        import yaml

        with open(hpa_path) as f:
            content = f.read()

        docs = list(yaml.safe_load_all(content))
        hpa_doc = next((d for d in docs if d and d.get("kind") == "HorizontalPodAutoscaler"), None)

        min_replicas = hpa_doc.get("spec", {}).get("minReplicas", 1)
        max_replicas = hpa_doc.get("spec", {}).get("maxReplicas", 10)
        assert max_replicas > min_replicas


class TestGrafanaDashboard:
    """Test suite for Grafana Dashboard configuration."""

    @pytest.fixture
    def dashboard_path(self):
        """Get Grafana Dashboard config path."""
        return Path(__file__).resolve().parents[4] / "deploy/kubernetes/apps/sisys/base/grafana-dashboard.json"

    def test_dashboard_file_exists(self, dashboard_path):
        """🔴 RED: Grafana Dashboard JSON should exist."""
        assert dashboard_path.exists(), f"Dashboard not found at {dashboard_path}"

    def test_dashboard_is_valid_json(self, dashboard_path):
        """🔴 RED: Dashboard should be valid JSON."""
        with open(dashboard_path) as f:
            dashboard = json.load(f)
        assert dashboard is not None

    def test_dashboard_has_required_fields(self, dashboard_path):
        """🔴 RED: Dashboard should have required fields."""
        with open(dashboard_path) as f:
            dashboard = json.load(f)

        assert "title" in dashboard
        assert "panels" in dashboard
        assert "uid" in dashboard

    def test_dashboard_has_sisys_panels(self, dashboard_path):
        """🔴 RED: Dashboard should have SISYS-specific panels."""
        with open(dashboard_path) as f:
            dashboard = json.load(f)

        panel_titles = [p.get("title", "") for p in dashboard.get("panels", [])]

        expected_panels = ["Agent Sessions Active", "Task Queue Length", "Event Processing Rate", "Cache Hit Rate"]
        for expected in expected_panels:
            assert any(expected in title for title in panel_titles), f"Missing panel: {expected}"

    def test_dashboard_has_scaling_events_panel(self, dashboard_path):
        """🔴 RED: Dashboard should have HPA scaling events timeline panel."""
        with open(dashboard_path) as f:
            dashboard = json.load(f)

        panel_titles = [p.get("title", "") for p in dashboard.get("panels", [])]
        assert any("Scaling" in title or "Replica" in title for title in panel_titles)

    def test_dashboard_refresh_interval(self, dashboard_path):
        """🔴 RED: Dashboard refresh interval should be ≤30s for real-time monitoring."""
        with open(dashboard_path) as f:
            dashboard = json.load(f)

        refresh = dashboard.get("refresh", "5s")
        if isinstance(refresh, str):
            interval = int(refresh.rstrip("s"))
            assert interval <= 30
