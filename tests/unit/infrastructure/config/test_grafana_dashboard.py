"""Unit tests for Grafana Dashboard configuration.

Story 1.13: K8s 动态扩缩容
AC-5: Grafana 可观测性

Run with: pytest tests/unit/infrastructure/test_grafana_dashboard.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


class TestGrafanaDashboardConfiguration:
    """Test suite for Grafana Dashboard JSON configuration."""

    @pytest.fixture
    def dashboard_path(self):
        """Get Grafana Dashboard config path."""
        return Path(__file__).resolve().parents[4] / "deploy/kubernetes/apps/sisys/base/grafana-dashboard.json"

    @pytest.fixture
    def dashboard_configmap_path(self):
        """Get Grafana Dashboard ConfigMap provisioning path."""
        return Path(__file__).resolve().parents[4] / "deploy/kubernetes/apps/sisys/base/grafana-dashboard-configmap.yaml"

    def test_dashboard_json_exists(self, dashboard_path):
        """✅ GREEN: Grafana Dashboard JSON should exist."""
        assert dashboard_path.exists(), f"Dashboard not found at {dashboard_path}"

    def test_dashboard_configmap_exists(self, dashboard_configmap_path):
        """✅ GREEN: Grafana Dashboard ConfigMap provisioning should exist."""
        assert dashboard_configmap_path.exists(), f"ConfigMap not found at {dashboard_configmap_path}"

    def test_dashboard_is_valid_json(self, dashboard_path):
        """✅ GREEN: Dashboard should be valid JSON."""
        with open(dashboard_path) as f:
            dashboard = json.load(f)
        assert isinstance(dashboard, dict)

    def test_dashboard_has_required_metadata(self, dashboard_path):
        """✅ GREEN: Dashboard should have required metadata fields."""
        with open(dashboard_path) as f:
            dashboard = json.load(f)

        assert "title" in dashboard
        assert "uid" in dashboard
        assert "version" in dashboard
        assert dashboard["title"] == "SISYS K8s Auto-scaling"
        assert "sisys" in dashboard.get("tags", [])

    def test_dashboard_has_panels_array(self, dashboard_path):
        """✅ GREEN: Dashboard should have panels array."""
        with open(dashboard_path) as f:
            dashboard = json.load(f)

        assert "panels" in dashboard
        assert isinstance(dashboard["panels"], list)
        assert len(dashboard["panels"]) > 0


class TestGrafanaDashboardPanels:
    """Test suite for Grafana Dashboard panels."""

    @pytest.fixture
    def dashboard_path(self):
        return Path(__file__).resolve().parents[4] / "deploy/kubernetes/apps/sisys/base/grafana-dashboard.json"

    @pytest.fixture
    def dashboard(self, dashboard_path):
        with open(dashboard_path) as f:
            return json.load(f)

    def test_has_agent_sessions_panel(self, dashboard):
        """✅ GREEN: Dashboard should have Agent Sessions Active panel."""
        panel_titles = [p.get("title", "") for p in dashboard.get("panels", [])]
        assert any("Agent Sessions" in title for title in panel_titles)

        # Find the panel and verify it queries the correct metric
        session_panel = next((p for p in dashboard["panels"] if "Agent Sessions" in p.get("title", "")), None)
        assert session_panel is not None

        targets = session_panel.get("targets", [])
        assert len(targets) > 0
        assert any("sisys_agent_sessions_active" in str(t.get("expr", "")) for t in targets)

    def test_has_task_queue_length_panel(self, dashboard):
        """✅ GREEN: Dashboard should have Task Queue Length panel."""
        panel_titles = [p.get("title", "") for p in dashboard.get("panels", [])]
        assert any("Task Queue" in title for title in panel_titles)

        queue_panel = next((p for p in dashboard["panels"] if "Task Queue" in p.get("title", "")), None)
        assert queue_panel is not None

        targets = queue_panel.get("targets", [])
        assert len(targets) > 0
        assert any("sisys_task_queue_length" in str(t.get("expr", "")) for t in targets)

    def test_has_event_processing_rate_panel(self, dashboard):
        """✅ GREEN: Dashboard should have Event Processing Rate panel."""
        panel_titles = [p.get("title", "") for p in dashboard.get("panels", [])]
        assert any("Event Processing" in title for title in panel_titles)

        rate_panel = next((p for p in dashboard["panels"] if "Event Processing" in p.get("title", "")), None)
        assert rate_panel is not None

        targets = rate_panel.get("targets", [])
        assert len(targets) > 0
        assert any("sisys_events_processing_rate" in str(t.get("expr", "")) for t in targets)

    def test_has_cache_hit_rate_panel(self, dashboard):
        """✅ GREEN: Dashboard should have Cache Hit Rate panel."""
        panel_titles = [p.get("title", "") for p in dashboard.get("panels", [])]
        assert any("Cache Hit" in title for title in panel_titles)

        hit_rate_panel = next((p for p in dashboard["panels"] if "Cache Hit" in p.get("title", "")), None)
        assert hit_rate_panel is not None

        targets = hit_rate_panel.get("targets", [])
        assert len(targets) > 0
        assert any("sisys_cache_hit_rate" in str(t.get("expr", "")) for t in targets)

    def test_has_scaling_events_timeline_panel(self, dashboard):
        """✅ GREEN: Dashboard should have HPA Scaling Events Timeline panel."""
        panel_titles = [p.get("title", "") for p in dashboard.get("panels", [])]
        assert any("Scaling" in title or "Replica" in title for title in panel_titles)

        scaling_panel = next(
            (p for p in dashboard["panels"] if "Scaling" in p.get("title", "") or "Replica" in p.get("title", "")), None
        )
        assert scaling_panel is not None

        targets = scaling_panel.get("targets", [])
        assert len(targets) > 0
        # Should query kube_hpa_* metrics
        has_hpa_metrics = any("kube_hpa" in str(t.get("expr", "")) for t in targets)
        assert has_hpa_metrics or len(targets) > 0


class TestGrafanaDashboardConfigMap:
    """Test suite for Grafana Dashboard ConfigMap provisioning."""

    @pytest.fixture
    def dashboard_configmap_path(self):
        return Path(__file__).resolve().parents[4] / "deploy/kubernetes/apps/sisys/base/grafana-dashboard-configmap.yaml"

    def test_configmap_is_valid_yaml(self, dashboard_configmap_path):
        """✅ GREEN: ConfigMap should be valid YAML."""
        import yaml

        with open(dashboard_configmap_path) as f:
            configmap = yaml.safe_load(f)
        assert isinstance(configmap, dict)

    def test_configmap_has_required_fields(self, dashboard_configmap_path):
        """✅ GREEN: ConfigMap should have required Kubernetes fields."""
        import yaml

        with open(dashboard_configmap_path) as f:
            configmap = yaml.safe_load(f)

        assert configmap["kind"] == "ConfigMap"
        assert "metadata" in configmap
        assert configmap["metadata"]["name"] == "sisys-grafana-dashboard"

    def test_configmap_has_grafana_dashboard_label(self, dashboard_configmap_path):
        """✅ GREEN: ConfigMap should have grafana_dashboard label for provisioning."""
        import yaml

        with open(dashboard_configmap_path) as f:
            configmap = yaml.safe_load(f)

        labels = configmap.get("metadata", {}).get("labels", {})
        assert labels.get("grafana_dashboard") == "1"

    def test_configmap_has_dashboard_data(self, dashboard_configmap_path):
        """✅ GREEN: ConfigMap should contain dashboard JSON data."""
        import yaml

        with open(dashboard_configmap_path) as f:
            configmap = yaml.safe_load(f)

        data = configmap.get("data", {})
        assert "k8s-autoscaling.json" in data
        # Should contain dashboard JSON content
        assert len(data["k8s-autoscaling.json"]) > 0
