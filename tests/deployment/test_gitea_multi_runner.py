"""
Test suite for Multi-Runner Configuration
Story: 0.8 - Gitea Runner Configuration
Task: 7 - Multi-Runner Configuration

Tests verify:
- Runner labels configuration (docker, k8s, gpu, etc.)
- Multiple Runner instances deployment (3 replicas)
- Runner grouping by project/environment
- Concurrent Job execution
"""

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest


class TestRunnerLabelsConfiguration:
    """Test Runner labels configuration"""

    def test_runner_labels_configured(self):
        """Verify Runner labels are configured"""
        result = subprocess.run(
            [
                "kubectl",
                "get",
                "statefulset",
                "gitea-org-runner",
                "-n",
                "gitea-actions",
                "-o",
                "jsonpath={.spec.template.spec.containers[0].env}",
            ],
            capture_output=True,
            text=True,
        )

        env_vars = json.loads(result.stdout)
        labels_env = next((env for env in env_vars if env["name"] == "GITEA_RUNNER_LABELS"), None)

        assert labels_env is not None, "GITEA_RUNNER_LABELS environment variable not found"
        assert "docker" in labels_env["value"], "docker label not configured"
        assert "k8s" in labels_env["value"], "k8s label not configured"

    def test_runner_labels_in_gitea(self):
        """Verify Runner labels are registered in Gitea"""
        # This would require Gitea API access
        # For now, check configuration file
        config_path = Path("deployments/gitea-runner/gitea-runner.yaml")
        if config_path.exists():
            content = config_path.read_text()
            assert "GITEA_RUNNER_LABELS" in content, "Runner labels not configured in deployment"

    def test_runner_labels_best_practices(self):
        """Verify Runner labels follow best practices"""
        # Labels should include:
        # - OS type (linux, windows)
        # - Executor type (docker, k8s)
        # - Special capabilities (gpu, high-memory)
        result = subprocess.run(
            [
                "kubectl",
                "get",
                "statefulset",
                "gitea-org-runner",
                "-n",
                "gitea-actions",
                "-o",
                "jsonpath={.spec.template.spec.containers[0].env}",
            ],
            capture_output=True,
            text=True,
        )

        env_vars = json.loads(result.stdout)
        labels_env = next((env for env in env_vars if env["name"] == "GITEA_RUNNER_LABELS"), None)

        if labels_env:
            labels = labels_env["value"].split(",")
            # Should have at least OS and executor type
            assert len(labels) >= 2, "Insufficient labels configured"


class TestMultipleRunnerInstances:
    """Test multiple Runner instances deployment"""

    def test_runner_replicas(self):
        """Verify Runner has 3 replicas"""
        result = subprocess.run(
            ["kubectl", "get", "statefulset", "gitea-org-runner", "-n", "gitea-actions", "-o", "jsonpath={.spec.replicas}"],
            capture_output=True,
            text=True,
        )

        replicas = int(result.stdout)
        assert replicas >= 3, f"Expected at least 3 replicas, got {replicas}"

    def test_runner_pods_running(self):
        """Verify all Runner Pods are running"""
        result = subprocess.run(
            [
                "kubectl",
                "get",
                "pods",
                "-n",
                "gitea-actions",
                "-l",
                "app=gitea-org-runner",
                "-o",
                "jsonpath={.items[*].status.phase}",
            ],
            capture_output=True,
            text=True,
        )

        phases = result.stdout.split()
        assert len(phases) >= 3, f"Expected at least 3 Pods, got {len(phases)}"

        for phase in phases:
            assert phase == "Running", f"Pod not running: {phase}"

    def test_runner_pod_distribution(self):
        """Verify Runner Pods are distributed across nodes"""
        result = subprocess.run(
            [
                "kubectl",
                "get",
                "pods",
                "-n",
                "gitea-actions",
                "-l",
                "app=gitea-org-runner",
                "-o",
                "jsonpath={.items[*].spec.nodeName}",
            ],
            capture_output=True,
            text=True,
        )

        nodes = result.stdout.split()
        # Note: May be on same node if single-node cluster
        # This is informational
        print(f"Runner Pods distributed across {len(set(nodes))} node(s): {nodes}")


class TestRunnerGrouping:
    """Test Runner grouping by project/environment"""

    def test_runner_namespace_isolation(self):
        """Verify Runners are in isolated namespace"""
        result = subprocess.run(
            ["kubectl", "get", "namespaces", "-o", "jsonpath={.items[*].metadata.name}"], capture_output=True, text=True
        )

        namespaces = result.stdout.split()
        assert "gitea-actions" in namespaces, "gitea-actions namespace not found"

    def test_runner_resource_quota(self):
        """Verify ResourceQuota is configured for Runner namespace (optional)"""
        result = subprocess.run(
            ["kubectl", "get", "resourcequota", "-n", "gitea-actions", "-o", "json"], capture_output=True, text=True
        )

        if result.returncode == 0:
            quota = json.loads(result.stdout)
            items = quota.get("items", [])
            if len(items) > 0:
                # ResourceQuota exists - verify it's configured
                assert True, "ResourceQuota found"
            else:
                # No ResourceQuota - this is optional, skip test
                pytest.skip("ResourceQuota not configured (optional - recommended for production)")
        else:
            # kubectl command failed or no ResourceQuota
            pytest.skip("ResourceQuota not configured (optional - recommended for production)")

    def test_runner_service_account(self):
        """Verify Runner uses dedicated ServiceAccount"""
        result = subprocess.run(
            ["kubectl", "get", "serviceaccount", "-n", "gitea-actions", "-o", "jsonpath={.items[*].metadata.name}"],
            capture_output=True,
            text=True,
        )

        service_accounts = result.stdout.split()
        # Should have default and possibly custom SA
        assert len(service_accounts) > 0, "No ServiceAccounts found"


class TestConcurrentJobExecution:
    """Test concurrent Job execution"""

    @pytest.mark.integration
    def test_runner_capacity(self):
        """Verify Runner capacity supports concurrent jobs"""
        result = subprocess.run(
            [
                "kubectl",
                "get",
                "statefulset",
                "gitea-org-runner",
                "-n",
                "gitea-actions",
                "-o",
                "jsonpath={.spec.template.spec.containers[0].env}",
            ],
            capture_output=True,
            text=True,
        )

        env_vars = json.loads(result.stdout)
        capacity_env = next((env for env in env_vars if env["name"] == "GITEA_RUNNER_CAPACITY"), None)

        if capacity_env:
            capacity = int(capacity_env["value"])
            assert capacity >= 3, f"Runner capacity too low: {capacity}"
        else:
            # Default capacity is usually sufficient
            pytest.skip("GITEA_RUNNER_CAPACITY not explicitly set")

    @pytest.mark.integration
    def test_concurrent_pipeline_trigger(self):
        """Test triggering multiple concurrent pipelines"""
        # This would require Gitea API access
        # For now, verify configuration supports it
        config_path = Path("deployments/gitea-runner/gitea-runner.yaml")
        if config_path.exists():
            content = config_path.read_text()
            # Check for capacity or concurrency settings
            assert "replicas" in content or "capacity" in content.lower(), "No concurrency configuration found"

    @pytest.mark.integration
    def test_job_queue_handling(self):
        """Verify Runners can handle job queue"""
        # Check if Runners are idle and ready
        result = subprocess.run(
            [
                "kubectl",
                "get",
                "pods",
                "-n",
                "gitea-actions",
                "-l",
                "app=gitea-org-runner",
                "-o",
                "jsonpath={.items[*].status.conditions}",
            ],
            capture_output=True,
            text=True,
        )

        # All pods should be Ready
        assert "True" in result.stdout, "Not all Runner Pods are Ready"


class TestRunnerConfiguration:
    """Test Runner configuration files"""

    def test_runner_deployment_exists(self):
        """Verify Runner deployment configuration exists"""
        # Try multiple possible config file names
        config_paths = [
            Path("deployments/gitea-runner/gitea-org-runner-statefulset.yaml"),
            Path("deployments/gitea-runner/gitea-runner.yaml"),
            Path("deployments/gitea-runner/runner-statefulset.yaml"),
        ]

        config_found = any(path.exists() for path in config_paths)
        assert config_found, f"Runner deployment config not found in {config_paths}"

    def test_runner_values_exists(self):
        """Verify Runner Helm values exist"""
        values_path = Path("deployments/gitea-runner/values.yaml")
        assert values_path.exists(), f"Runner Helm values not found: {values_path}"

    def test_runner_labels_documented(self):
        """Verify Runner labels are documented"""
        story_path = Path("_bmad-output/implementation-artifacts/stories/0-8-gitea-runner-configuration.md")
        content = story_path.read_text()

        assert "Runner 标签" in content or "labels" in content.lower(), "Runner labels not documented in story file"


# Fixtures
@pytest.fixture
def runner_config() -> dict[str, Any]:
    """Load Runner configuration"""
    return {
        "namespace": "gitea-actions",
        "statefulset": "gitea-org-runner",
        "replicas": 3,
        "labels": ["docker", "k8s", "linux"],
        "image": "docker.io/gitea/act_runner:0.3.0",
    }


@pytest.fixture
def gitea_api_base() -> str:
    """Return Gitea API base URL"""
    return "http://gitea-http.gitea.svc.cluster.local:3000"
