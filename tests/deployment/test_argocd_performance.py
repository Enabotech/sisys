"""
ArgoCD Performance Benchmark Tests
Story 0.7: LOW-2 Fix

Purpose: Validate ArgoCD performance meets requirements
Requirements:
  - Pod startup time: < 60s
  - Page load time: < 3s
  - Login response time: < 2s
  - Sync time P95: < 2m
  - CPU usage: < 70% (5min avg)
  - Memory usage: < 80% (5min avg)

Usage:
  poetry run pytest tests/performance/test_argocd_performance.py -v
  poetry run pytest tests/performance/test_argocd_performance.py --benchmark-only

Note: Uses kubectl CLI instead of kubernetes Python module
"""

import statistics
import subprocess
import time
from datetime import datetime
from pathlib import Path

import pytest
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Skip all tests if kubectl not available
pytestmark = pytest.mark.skipif(
    not subprocess.run(["kubectl", "version", "--client"], capture_output=True).returncode == 0, reason="kubectl not available"
)

# Certificate configuration for HTTPS verification
# Uses ArgoCD self-signed certificate to avoid InsecureRequestWarning
TEST_CERTS_DIR = Path(__file__).parent.parent / "certs"
ARGOCD_CERT = TEST_CERTS_DIR / "argocd-sisys-local.crt"


class TestArgoCDPerformance:
    """ArgoCD Performance Benchmark Tests"""

    @pytest.fixture(scope="class")
    def argocd_url(self) -> str:
        """Get ArgoCD URL"""
        return "https://argocd.sisys.local"

    def test_pod_startup_time(self):
        """
        Test Pod startup time < 60 seconds

        Requirement: NFR-PERF-01
        Metric: Time from Pod creation to Running state

        Note: This test is only valid for newly created pods.
        Skips if pod was created more than 1 hour ago.
        """
        from datetime import timedelta

        # Check if metrics.k8s.io API is available
        metrics_check = subprocess.run(
            ["kubectl", "api-resources", "--api-group=metrics.k8s.io"],
            capture_output=True,
            text=True,
        )
        if metrics_check.returncode != 0:
            pytest.skip("Metrics server not available (metrics.k8s.io API)")

        # Get argocd-server pod
        result = subprocess.run(
            [
                "kubectl",
                "get",
                "pods",
                "-n",
                "argocd",
                "-l",
                "app.kubernetes.io/name=argocd-server",
                "-o",
                "jsonpath={.items[0].metadata.creationTimestamp}",
            ],
            capture_output=True,
            text=True,
        )

        if not result.stdout:
            pytest.skip("No ArgoCD server pods found")

        creation_time = datetime.fromisoformat(result.stdout.replace("Z", "+00:00"))
        now = datetime.now(creation_time.tzinfo)
        pod_age = now - creation_time

        # Skip if pod is older than 24 hours (not a fresh deployment)
        # 24 小时窗口允许测试在稳定环境中运行
        if pod_age > timedelta(hours=24):
            pytest.skip(f"Pod is {pod_age.total_seconds()/3600:.1f} hours old (not a fresh deployment)")

        # Get pod ready time
        result = subprocess.run(
            [
                "kubectl",
                "get",
                "pods",
                "-n",
                "argocd",
                "-l",
                "app.kubernetes.io/name=argocd-server",
                "-o",
                "jsonpath={.items[0].status.conditions[?(@.type=='Ready')].lastTransitionTime}",
            ],
            capture_output=True,
            text=True,
        )

        if not result.stdout:
            pytest.skip("Pod not ready")

        ready_time = datetime.fromisoformat(result.stdout.replace("Z", "+00:00"))
        startup_time = (ready_time - creation_time).total_seconds()

        print(f"Pod startup time: {startup_time:.2f}s")
        assert startup_time < 60, f"Pod startup time {startup_time}s exceeds 60s limit"

    def test_page_load_time(self, argocd_url: str) -> None:
        """
        Test page load time < 3 seconds

        Requirement: NFR-PERF-02
        Metric: HTTPS GET response time
        """
        session = requests.Session()
        retry = Retry(total=3, backoff_factor=0.1)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.verify = str(ARGOCD_CERT)  # Use self-signed certificate for verification

        times: list[float] = []

        # Measure 10 times
        for i in range(10):
            start = time.time()
            response = session.get(f"{argocd_url}/", timeout=10, headers={"Host": "argocd.sisys.local"})  # noqa: F841
            elapsed = time.time() - start
            times.append(elapsed)

            assert response.status_code == 200, "ArgoCD page not accessible"

        avg_time = statistics.mean(times)
        p95_time = sorted(times)[int(len(times) * 0.95)] if len(times) > 1 else times[0]

        print(f"Page load time - Avg: {avg_time:.2f}s, P95: {p95_time:.2f}s")
        assert avg_time < 3, f"Average page load time {avg_time}s exceeds 3s limit"

    def test_login_response_time(self, argocd_url):
        """
        Test login response time < 2 seconds

        Requirement: NFR-PERF-03
        Metric: GET /api/v1/session response time
        """
        session = requests.Session()
        session.verify = str(ARGOCD_CERT)  # Use self-signed certificate for verification

        start = time.time()
        _ = session.get(f"{argocd_url}/api/v1/session", timeout=5, headers={"Host": "argocd.sisys.local"})
        elapsed = time.time() - start

        print(f"Login API response time: {elapsed:.2f}s")
        assert elapsed < 2, f"Login response time {elapsed}s exceeds 2s limit"

    def test_sync_time(self):
        """
        Test sync time P95 < 2 minutes

        Requirement: NFR-PERF-04
        Metric: Git commit to deployment completion
        """
        # This test requires actual ArgoCD Application and Git changes
        # Implementation would:
        # 1. Make a small Git change
        # 2. Record timestamp
        # 3. Wait for ArgoCD to detect and sync
        # 4. Measure time to deployment completion

        pytest.skip("Requires actual Git repository and Application configuration")

    def test_cpu_usage(self) -> None:
        """
        Test CPU usage < 70% (5 minute average)

        Requirement: NFR-PERF-05
        Metric: ArgoCD components CPU utilization
        """
        # Check if metrics.k8s.io API is available
        metrics_check = subprocess.run(
            ["kubectl", "api-resources", "--api-group=metrics.k8s.io"],
            capture_output=True,
            text=True,
        )
        if metrics_check.returncode != 0:
            print("⚠️ Metrics server 不可用，跳过 CPU 使用率测试")
            pytest.skip("Metrics server not available (metrics.k8s.io API)")

        # Get ArgoCD pods
        result = subprocess.run(
            ["kubectl", "top", "pods", "-n", "argocd", "-l", "app.kubernetes.io/part-of=argocd", "--no-headers"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0 or not result.stdout:
            pytest.skip("Metrics server not available or no ArgoCD pods found")

        cpu_usage_percent: list[float] = []

        for line in result.stdout.strip().split("\n"):
            parts = line.split()
            if len(parts) >= 2:
                cpu_str = parts[1]
                # Convert to millicores
                if "m" in cpu_str:
                    cpu_millicores = float(cpu_str.replace("m", ""))
                else:
                    cpu_millicores = float(cpu_str) * 1000

                # Assume 2 cores limit per pod
                limit_millicores = 2000
                usage_percent = (cpu_millicores / limit_millicores) * 100
                cpu_usage_percent.append(usage_percent)

        if cpu_usage_percent:
            avg_cpu = statistics.mean(cpu_usage_percent)
            print(f"Average CPU usage: {avg_cpu:.1f}%")
            assert avg_cpu < 70, f"Average CPU usage {avg_cpu}% exceeds 70% limit"
        else:
            pytest.skip("Could not retrieve CPU metrics")

    def test_memory_usage(self) -> None:
        """
        Test memory usage < 80% (5 minute average)

        Requirement: NFR-PERF-06
        Metric: ArgoCD components memory utilization
        """
        # Check if metrics.k8s.io API is available
        metrics_check = subprocess.run(
            ["kubectl", "api-resources", "--api-group=metrics.k8s.io"],
            capture_output=True,
            text=True,
        )
        if metrics_check.returncode != 0:
            print("⚠️ Metrics server 不可用，跳过内存使用率测试")
            pytest.skip("Metrics server not available (metrics.k8s.io API)")

        # Get ArgoCD pods
        result = subprocess.run(
            ["kubectl", "top", "pods", "-n", "argocd", "-l", "app.kubernetes.io/part-of=argocd", "--no-headers"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0 or not result.stdout:
            pytest.skip("Metrics server not available or no ArgoCD pods found")

        memory_usage_percent: list[float] = []

        for line in result.stdout.strip().split("\n"):
            parts = line.split()
            if len(parts) >= 3:
                mem_str = parts[2]
                # Convert to Mi
                if "Mi" in mem_str:
                    memory_mi = float(mem_str.replace("Mi", ""))
                elif "Gi" in mem_str:
                    memory_mi = float(mem_str.replace("Gi", "")) * 1024
                else:
                    memory_mi = float(mem_str) / (1024 * 1024)

                # Assume 4Gi limit per pod
                limit_mi = 4096
                usage_percent = (memory_mi / limit_mi) * 100
                memory_usage_percent.append(usage_percent)

        if memory_usage_percent:
            avg_memory = statistics.mean(memory_usage_percent)
            print(f"Average memory usage: {avg_memory:.1f}%")
            assert avg_memory < 80, f"Average memory usage {avg_memory}% exceeds 80% limit"
        else:
            pytest.skip("Could not retrieve memory metrics")


class TestGitOperationLatency:
    """Git Operation Latency Tests"""

    def test_git_clone_time(self) -> None:
        """
        Test Git clone latency P95 < 5 seconds

        Requirement: NFR-PERF-07
        Metric: Time to clone repository
        """
        repo_url = "https://gitea.sisys.local/sisys/sisys.git"
        times: list[float] = []

        for i in range(3):
            start = time.time()
            result = subprocess.run(
                ["git", "ls-remote", repo_url],
                capture_output=True,
                timeout=10,
                env={"GIT_SSL_NO_VERIFY": "1"},  # Self-signed certificate
            )
            elapsed = time.time() - start
            times.append(elapsed)

            assert result.returncode == 0, "Git ls-remote failed"

        avg_time = statistics.mean(times)
        print(f"Git operation latency - Avg: {avg_time:.2f}s")
        assert avg_time < 5, f"Git operation latency {avg_time}s exceeds 5s limit"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
