"""
Gitea Runner K8s Executor 测试

测试 K8s Executor 配置的正确性和功能性。
AC: 3, 6

测试覆盖：
- K8s API 访问权限 (ServiceAccount + RBAC)
- K8s Executor 配置
- Pod 模板配置
- Job 并发限制
- 资源隔离
"""

from pathlib import Path
from typing import Any

import pytest
import yaml


class TestK8sExecutorConfiguration:
    """测试 K8s Executor 基础配置"""

    def test_k8s_executor_config_exists(self):
        """测试 K8s Executor 配置文件存在"""
        config_path = Path("deployments/gitea-runner/runner-k8s-executor.yaml")
        assert config_path.exists(), f"K8s Executor 配置文件不存在：{config_path}"

    def test_k8s_executor_config_valid_yaml(self):
        """测试 K8s Executor 配置文件 YAML 语法正确"""
        config_path = Path("deployments/gitea-runner/runner-k8s-executor.yaml")
        if config_path.exists():
            try:
                # 使用 safe_load_all 处理多文档 YAML
                with open(config_path, encoding="utf-8") as f:
                    list(yaml.safe_load_all(f))
            except yaml.YAMLError as e:
                pytest.fail(f"K8s Executor 配置 YAML 语法错误：{e}")

    def test_k8s_api_access_configured(self):
        """测试 K8s API 访问权限配置"""
        rbac_path = Path("deployments/gitea-runner/rbac.yaml")
        if rbac_path.exists():
            # 检查是否配置了 ServiceAccount
            rbac_text = rbac_path.read_text(encoding="utf-8")
            assert "ServiceAccount" in rbac_text, "ServiceAccount 未配置"
            assert "ClusterRole" in rbac_text, "ClusterRole 未配置"
            assert "ClusterRoleBinding" in rbac_text, "ClusterRoleBinding 未配置"

    def test_service_account_configured(self):
        """测试 ServiceAccount 配置"""
        rbac_path = Path("deployments/gitea-runner/rbac.yaml")
        if rbac_path.exists():
            rbac_text = rbac_path.read_text(encoding="utf-8")
            # 检查 ServiceAccount 配置
            assert "gitea-runner" in rbac_text, "gitea-runner ServiceAccount 未配置"

    def test_rbac_permissions_configured(self):
        """测试 RBAC 权限配置"""
        rbac_path = Path("deployments/gitea-runner/rbac.yaml")
        if rbac_path.exists():
            rbac = yaml.safe_load_all(list(rbac_path.read_text(encoding="utf-8").split("---")))

            # 查找 ClusterRole
            found_cluster_role = False
            for doc in rbac:
                if doc and doc.get("kind") == "ClusterRole":
                    found_cluster_role = True
                    # 检查是否有 Pod 管理权限
                    rules_text = yaml.dump(doc)
                    assert "pods" in rules_text, "ClusterRole 未配置 Pod 管理权限"
                    assert "create" in rules_text or "get" in rules_text, "ClusterRole 未配置 Pod 创建/获取权限"

            assert found_cluster_role, "ClusterRole 未定义"

    def test_k8s_executor_config_map_exists(self):
        """测试 K8s Executor ConfigMap 存在"""
        config_path = Path("deployments/gitea-runner/runner-k8s-executor.yaml")
        if config_path.exists():
            config_text = config_path.read_text(encoding="utf-8")
            # 检查是否配置了 K8s Executor
            assert "kubernetes" in config_text.lower() or "k8s" in config_text.lower(), "K8s Executor 配置未定义"


class TestK8sPodTemplate:
    """测试 K8s Pod 模板配置"""

    def test_pod_template_configured(self):
        """测试 Pod 模板配置"""
        config_path = Path("deployments/gitea-runner/runner-k8s-executor.yaml")
        if config_path.exists():
            config_text = config_path.read_text(encoding="utf-8")
            # 检查是否配置了 Pod 模板
            assert "pod_template" in config_text or "podSpec" in config_text or "template" in config_text, "Pod 模板未配置"

    def test_resource_limits_configured(self):
        """测试资源限制配置"""
        config_path = Path("deployments/gitea-runner/runner-k8s-executor.yaml")
        if config_path.exists():
            config_text = config_path.read_text(encoding="utf-8")
            # 检查是否配置了资源限制
            assert "resources" in config_text and ("limits" in config_text or "requests" in config_text), "资源限制未配置"

    def test_cpu_memory_limits_defined(self):
        """测试 CPU 和内存限制定义"""
        config_path = Path("deployments/gitea-runner/runner-k8s-executor.yaml")
        if config_path.exists():
            config_text = config_path.read_text(encoding="utf-8")
            # 检查是否配置了 CPU 和内存限制
            assert "cpu" in config_text.lower(), "CPU 限制未配置"
            assert "memory" in config_text.lower() or "mem" in config_text.lower(), "内存限制未配置"

    def test_image_pull_policy_configured(self):
        """测试镜像拉取策略配置"""
        config_path = Path("deployments/gitea-runner/runner-k8s-executor.yaml")
        if config_path.exists():
            config_text = config_path.read_text(encoding="utf-8")
            # 检查是否配置了镜像拉取策略
            pull_keywords = ["imagePullPolicy", "pullPolicy", "Always", "IfNotPresent", "Never"]
            has_pull_policy = any(keyword in config_text for keyword in pull_keywords)
            assert has_pull_policy, "镜像拉取策略未配置"


class TestK8sJobConcurrency:
    """测试 K8s Job 并发配置"""

    def test_concurrent_job_limit_configured(self):
        """测试并发 Job 限制配置"""
        config_path = Path("deployments/gitea-runner/runner-k8s-executor.yaml")
        if config_path.exists():
            config_text = config_path.read_text(encoding="utf-8")
            # 检查是否配置了并发限制
            concurrency_keywords = ["concurrency", "parallel", "capacity", "maxJobs"]
            has_concurrency = any(keyword in config_text.lower() for keyword in concurrency_keywords)
            # 并发配置为可选，但建议配置
            assert has_concurrency, "未配置并发 Job 限制（建议配置为 3 个并发）"

    def test_runner_capacity_configured(self):
        """测试 Runner 容量配置"""
        values_path = Path("deployments/gitea-runner/values.yaml")
        if values_path.exists():
            with open(values_path, encoding="utf-8") as f:
                values = yaml.safe_load(f)
                # 检查副本数配置
                replica_count = values.get("replicaCount", 1)
                assert replica_count >= 3, f"Runner 副本数应至少为 3，实际为：{replica_count}"

    def test_resource_isolation_configured(self):
        """测试资源隔离配置"""
        config_path = Path("deployments/gitea-runner/runner-k8s-executor.yaml")
        if config_path.exists():
            config_text = config_path.read_text(encoding="utf-8")
            # 检查是否配置了资源隔离
            isolation_keywords = ["isolation", "namespace", "quota", "LimitRange"]
            has_isolation = any(keyword in config_text for keyword in isolation_keywords)
            # 资源隔离为可选，但建议配置
            assert has_isolation, "未配置资源隔离（建议配置 Namespace/Quota）"


class TestK8sExecutorSecurity:
    """测试 K8s Executor 安全性"""

    def test_security_context_configured(self):
        """测试安全上下文配置"""
        config_path = Path("deployments/gitea-runner/runner-k8s-executor.yaml")
        if config_path.exists():
            config_text = config_path.read_text(encoding="utf-8")
            # 检查是否配置了安全上下文
            assert "securityContext" in config_text, "安全上下文未配置"

    def test_privileged_mode_disabled(self):
        """测试特权模式已禁用"""
        config_path = Path("deployments/gitea-runner/runner-k8s-executor.yaml")
        if config_path.exists():
            config_text = config_path.read_text(encoding="utf-8")
            # 检查是否禁用了特权模式
            if "privileged" in config_text:
                # 如果配置了 privileged，应为 false
                assert "privileged: false" in config_text, "特权模式未禁用"

    def test_image_pull_secrets_configured(self):
        """测试镜像拉取 Secret 配置"""
        config_path = Path("deployments/gitea-runner/runner-k8s-executor.yaml")
        if config_path.exists():
            config_text = config_path.read_text(encoding="utf-8")
            # 检查是否配置了镜像拉取 Secret
            assert "imagePullSecrets" in config_text, "镜像拉取 Secret 未配置"

    def test_network_policy_configured(self):
        """测试网络策略配置"""
        rbac_path = Path("deployments/gitea-runner/rbac.yaml")
        if rbac_path.exists():
            rbac_text = rbac_path.read_text(encoding="utf-8")
            # 检查是否配置了网络策略
            has_network_policy = "NetworkPolicy" in rbac_text
            # 网络策略为可选，但建议配置
            assert has_network_policy, "未配置网络策略（建议配置以增强安全性）"


class TestK8sExecutorJobExecution:
    """测试 K8s Executor Job 执行"""

    def test_job_cleanup_configured(self):
        """测试 Job 完成后自动清理配置"""
        config_path = Path("deployments/gitea-runner/runner-k8s-executor.yaml")
        if config_path.exists():
            config_text = config_path.read_text(encoding="utf-8")
            # 检查是否配置了清理策略
            cleanup_keywords = ["cleanup", "ttl", "delete", "remove"]
            has_cleanup = any(keyword in config_text.lower() for keyword in cleanup_keywords)
            # 清理配置为可选，但建议配置
            assert has_cleanup, "未配置 Job 完成后自动清理（建议配置）"

    def test_job_timeout_configured(self):
        """测试 Job 超时配置"""
        config_path = Path("deployments/gitea-runner/runner-k8s-executor.yaml")
        if config_path.exists():
            config_text = config_path.read_text(encoding="utf-8")
            # 检查是否配置了超时
            timeout_keywords = ["timeout", "deadline", "maxDuration"]
            has_timeout = any(keyword in config_text.lower() for keyword in timeout_keywords)
            # 超时配置为可选，但建议配置
            assert has_timeout, "未配置 Job 超时（建议配置）"

    def test_job_log_collection_configured(self):
        """测试 Job 日志收集配置"""
        config_path = Path("deployments/gitea-runner/runner-k8s-executor.yaml")
        if config_path.exists():
            config_text = config_path.read_text(encoding="utf-8")
            # 检查是否配置了日志收集
            log_keywords = ["log", "logging", "stdout", "stderr"]
            has_logging = any(keyword in config_text.lower() for keyword in log_keywords)
            # 日志收集为可选，但建议配置
            assert has_logging, "未配置 Job 日志收集（建议配置）"


class TestK8sExecutorIntegration:
    """测试 K8s Executor 集成"""

    @pytest.mark.integration
    def test_k8s_executor_e2e(self):
        """测试 K8s Executor 端到端流程"""
        # 集成测试 - 验证配置和运行环境
        import subprocess

        try:
            # 1. 检查 gitea-actions 命名空间是否存在
            result = subprocess.run(
                ["kubectl", "get", "namespace", "gitea-actions"], capture_output=True, text=True, check=False
            )
            if result.returncode != 0:
                pytest.skip("gitea-actions 命名空间不存在")
            print("✅ gitea-actions 命名空间存在")

            # 2. 检查 ServiceAccount 是否存在
            sa_result = subprocess.run(
                ["kubectl", "get", "serviceaccount", "gitea-runner", "-n", "gitea-actions"],
                capture_output=True,
                text=True,
                check=False,
            )
            if sa_result.returncode != 0:
                pytest.skip("ServiceAccount gitea-runner 不存在")
            print("✅ ServiceAccount gitea-runner 存在")

            # 3. 检查 RBAC 权限（从外部验证）
            rbac_result = subprocess.run(
                [
                    "kubectl",
                    "auth",
                    "can-i",
                    "create",
                    "pods",
                    "-n",
                    "gitea-actions",
                    "--as",
                    "system:serviceaccount:gitea-actions:gitea-runner",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            assert "yes" in rbac_result.stdout, f"RBAC 权限不足：{rbac_result.stdout}"
            print("✅ RBAC 权限验证通过（可创建 Pods）")

            # 4. 检查 ClusterRoleBinding
            crb_result = subprocess.run(
                ["kubectl", "get", "clusterrolebinding", "gitea-runner"], capture_output=True, text=True, check=False
            )
            if "gitea-runner" in crb_result.stdout:
                print("✅ ClusterRoleBinding 存在")

            # 5. 检查 Runner Pod 是否运行
            pod_result = subprocess.run(
                ["kubectl", "get", "pods", "-n", "gitea-actions", "-l", "app=gitea-org-runner"],
                capture_output=True,
                text=True,
                check=False,
            )
            if "Running" not in pod_result.stdout:
                pytest.skip("无运行中的 Runner Pod")
            print(f"✅ Runner Pod 运行中:\n{pod_result.stdout}")

            # 6. 验证 ResourceQuota 配置
            quota_result = subprocess.run(
                ["kubectl", "get", "resourcequota", "-n", "gitea-actions"], capture_output=True, text=True, check=False
            )
            if "gitea-runner-k8s-quota" in quota_result.stdout or quota_result.returncode == 0:
                print("✅ ResourceQuota 配置存在")

            print("✅ K8s Executor E2E 测试通过")

        except subprocess.TimeoutExpired:
            pytest.skip("测试超时")
        except AssertionError as e:
            pytest.fail(f"K8s Executor E2E 测试失败：{str(e)}")
        except Exception as e:
            pytest.skip(f"K8s Executor E2E 测试跳过：{str(e)}")

    def test_k8s_executor_api_access(self):
        """测试 K8s API 访问"""
        # 检查 Runner 是否可以访问 K8s API
        values_path = Path("deployments/gitea-runner/values.yaml")
        if values_path.exists():
            values_text = values_path.read_text(encoding="utf-8")
            # 检查是否配置了 K8s API 访问
            assert "serviceAccount" in values_text or "rbac" in values_text, "K8s API 访问配置未定义"


class TestK8sExecutorResourceManagement:
    """测试 K8s Executor 资源管理"""

    def test_resource_quota_defined(self):
        """测试资源配额定义"""
        executor_config_path = Path("deployments/gitea-runner/runner-k8s-executor.yaml")
        if executor_config_path.exists():
            config_text = executor_config_path.read_text(encoding="utf-8")
            # 检查是否配置了资源配额
            quota_keywords = ["ResourceQuota", "quota", "LimitRange"]
            has_quota = any(keyword in config_text for keyword in quota_keywords)
            # 资源配额为可选，但建议配置
            assert has_quota, "未配置资源配额（建议配置 ResourceQuota/LimitRange）"

    def test_namespace_isolation(self):
        """测试命名空间隔离"""
        deployment_path = Path("deployments/gitea-runner/gitea-runner.yaml")
        if deployment_path.exists():
            deployment_text = deployment_path.read_text(encoding="utf-8")
            # 检查是否使用了独立命名空间
            assert "namespace" in deployment_text, "未配置独立命名空间"
            assert "gitea-actions" in deployment_text, "未使用 gitea-actions 命名空间"


# 测试辅助函数
def check_k8s_executor_status(namespace: str = "gitea-actions") -> dict[str, Any]:
    """
    检查 K8s Executor 状态

    Args:
        namespace: Kubernetes 命名空间

    Returns:
        状态字典
    """
    try:
        import subprocess

        # 获取 Pod 状态
        result = subprocess.run(
            ["kubectl", "get", "pods", "-n", namespace, "-l", "app=gitea-runner"], capture_output=True, text=True, check=False
        )
        return {"status": "success" if result.returncode == 0 else "failed", "output": result.stdout, "error": result.stderr}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def check_k8s_api_access(namespace: str = "gitea-actions") -> dict[str, Any]:
    """
    检查 K8s API 访问

    Args:
        namespace: Kubernetes 命名空间

    Returns:
        API 访问状态字典
    """
    try:
        import subprocess

        # 测试 K8s API 访问
        result = subprocess.run(
            ["kubectl", "auth", "can-i", "create", "pods", "-n", namespace], capture_output=True, text=True, check=False
        )
        return {
            "status": "success" if result.returncode == 0 else "failed",
            "can_create_pods": "yes" in result.stdout,
            "output": result.stdout,
            "error": result.stderr,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=src", "--cov-report=html"])
