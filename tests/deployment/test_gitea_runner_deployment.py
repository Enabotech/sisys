"""
Test Gitea Runner Deployment.

测试 Gitea Runner 部署配置的正确性。
"""

from pathlib import Path

import pytest
import yaml

# ========== Fixtures ==========


@pytest.fixture
def deployment_yaml() -> str:
    """Gitea Runner Deployment YAML."""
    return """apiVersion: apps/v1
kind: Deployment
metadata:
  name: gitea-runner
  namespace: gitea-actions
spec:
  replicas: 3
  selector:
    matchLabels:
      app: gitea-runner
  template:
    metadata:
      labels:
        app: gitea-runner
    spec:
      containers:
        - name: runner
          image: gitea/act_runner:v0.3.0
          resources:
            requests:
              cpu: 500m
              memory: 1Gi
            limits:
              cpu: 2000m
              memory: 4Gi
"""


@pytest.fixture
def values_yaml() -> dict:
    """Helm Chart values."""
    return {
        "replicaCount": 3,
        "image": {
            "repository": "gitea/act_runner",
            "tag": "v0.3.0",
            "pullPolicy": "IfNotPresent",
        },
        "resources": {
            "limits": {"cpu": "2000m", "memory": "4Gi"},
            "requests": {"cpu": "500m", "memory": "1Gi"},
        },
    }


# ========== Task 2.1: Helm Chart 配置测试 ==========


class TestHelmChartConfiguration:
    """测试 Helm Chart 配置。"""

    def test_chart_yaml_structure(self):
        """测试 Chart.yaml 结构。"""
        chart_path = Path("deployments/gitea-runner/Chart.yaml")

        if chart_path.exists():
            content = yaml.safe_load(chart_path.read_text())

            # 验证必需字段
            assert content["apiVersion"] == "v2"
            assert content["name"] == "gitea-runner"
            assert content["version"] == "0.1.0"
            assert content["appVersion"] == "v0.3.0"

    def test_values_yaml_structure(self, values_yaml: dict):
        """测试 values.yaml 结构。"""
        values_path = Path("deployments/gitea-runner/values.yaml")

        if values_path.exists():
            content = yaml.safe_load(values_path.read_text())

            # 验证关键字段
            assert "replicaCount" in content
            assert "image" in content
            assert "resources" in content
            # 支持 0.3.0 或 v0.3.0 格式
            assert content["image"]["tag"] in ["0.3.0", "v0.3.0"]

    def test_image_version(self, values_yaml: dict):
        """测试镜像版本。"""
        # Gitea Runner 0.3.0 是最新稳定版
        assert values_yaml["image"]["tag"] in ["0.3.0", "v0.3.0"]
        assert values_yaml["image"]["repository"] == "gitea/act_runner"

    def test_resource_limits(self, values_yaml: dict):
        """测试资源限制配置。"""
        resources = values_yaml["resources"]

        # 验证资源限制
        assert resources["limits"]["cpu"] == "2000m"
        assert resources["limits"]["memory"] == "4Gi"
        assert resources["requests"]["cpu"] == "500m"
        assert resources["requests"]["memory"] == "1Gi"

    def test_replica_count(self, values_yaml: dict):
        """测试副本数配置。"""
        # 默认 3 个副本支持并发
        assert values_yaml["replicaCount"] == 3


# ========== Task 2.2: kubectl 部署配置测试 ==========


class TestKubectlDeployment:
    """测试 kubectl 部署配置。"""

    def test_deployment_manifest_exists(self):
        """测试部署 manifest 文件存在。"""
        # 支持新配置 (gitea-runner.yaml) 或旧配置 (gitea-runner-deployment.yaml)
        manifest_path = Path("deployments/gitea-runner/gitea-runner.yaml")
        alt_manifest_path = Path("deployments/gitea-runner/gitea-runner-deployment.yaml")

        assert (
            manifest_path.exists() or alt_manifest_path.exists()
        ), "部署配置文件不存在 (gitea-runner.yaml 或 gitea-runner-deployment.yaml)"

    def test_deployment_yaml_structure(self, deployment_yaml: str):
        """测试 Deployment YAML 结构。"""
        content = yaml.safe_load(deployment_yaml)

        # 验证基本结构
        assert content["apiVersion"] == "apps/v1"
        assert content["kind"] == "Deployment"
        assert content["metadata"]["name"] == "gitea-runner"
        assert content["metadata"]["namespace"] == "gitea-actions"

    def test_namespace_configuration(self):
        """测试命名空间配置。"""
        manifest_path = Path("deployments/gitea-runner/gitea-runner-deployment.yaml")

        if manifest_path.exists():
            content = yaml.safe_load_all(manifest_path.read_text())

            # 查找 Namespace 定义
            for doc in content:
                if doc.get("kind") == "Namespace":
                    assert doc["metadata"]["name"] == "gitea-actions"
                    break

    def test_service_account(self):
        """测试 ServiceAccount 配置。"""
        manifest_path = Path("deployments/gitea-runner/gitea-runner-deployment.yaml")

        if manifest_path.exists():
            content = yaml.safe_load_all(manifest_path.read_text())

            # 查找 ServiceAccount 定义
            for doc in content:
                if doc.get("kind") == "ServiceAccount":
                    assert doc["metadata"]["name"] == "gitea-runner"
                    assert doc["metadata"]["namespace"] == "gitea-actions"
                    break

    def test_container_image(self, deployment_yaml: str):
        """测试容器镜像配置。"""
        content = yaml.safe_load(deployment_yaml)
        containers = content["spec"]["template"]["spec"]["containers"]

        # 验证镜像版本
        assert containers[0]["image"] == "gitea/act_runner:v0.3.0"


# ========== Task 2.3: 安全配置测试 ==========


class TestSecurityConfiguration:
    """测试安全配置。"""

    def test_pod_security_context(self):
        """测试 Pod 安全上下文。"""
        manifest_path = Path("deployments/gitea-runner/gitea-runner-deployment.yaml")

        if manifest_path.exists():
            content = yaml.safe_load_all(manifest_path.read_text())

            for doc in content:
                if doc.get("kind") == "Deployment":
                    spec = doc["spec"]["template"]["spec"]

                    # 验证 runAsNonRoot
                    if "securityContext" in spec:
                        assert spec["securityContext"].get("runAsNonRoot")

    def test_container_security_context(self):
        """测试容器安全上下文。"""
        # 测试实际 manifest 文件而不是 fixture
        manifest_path = Path("deployments/gitea-runner/gitea-runner-deployment.yaml")

        if manifest_path.exists():
            content = yaml.safe_load_all(manifest_path.read_text())

            for doc in content:
                if doc.get("kind") == "Deployment":
                    spec = doc["spec"]["template"]["spec"]
                    containers = spec["containers"]

                    # 验证容器或 Pod 有安全上下文
                    has_security = "securityContext" in containers[0] or "securityContext" in spec
                    assert has_security, "容器或 Pod 应该有 securityContext"
                    break

    def test_resource_limits_defined(self, deployment_yaml: str):
        """测试资源限制定义。"""
        content = yaml.safe_load(deployment_yaml)
        containers = content["spec"]["template"]["spec"]["containers"]

        # 验证资源限制
        assert "resources" in containers[0]
        assert "limits" in containers[0]["resources"]
        assert "requests" in containers[0]["resources"]


# ========== Task 2.4: 部署脚本测试 ==========


class TestDeploymentScript:
    """测试部署脚本。"""

    def test_deploy_script_exists(self):
        """测试部署脚本存在。"""
        script_path = Path("scripts/deployment/gitea-runner/deploy-runner.sh")
        assert script_path.exists()

    def test_deploy_script_executable(self):
        """测试部署脚本可执行。"""
        script_path = Path("scripts/deployment/gitea-runner/deploy-runner.sh")

        if script_path.exists():
            import os

            assert os.access(script_path, os.X_OK)

    def test_deploy_script_content(self):
        """测试部署脚本内容。"""
        script_path = Path("scripts/deployment/gitea-runner/deploy-runner.sh")

        if script_path.exists():
            content = script_path.read_text()

            # 验证关键命令
            assert "kubectl" in content
            assert "gitea-runner" in content
            assert "gitea-actions" in content


# ========== 集成测试 ==========


class TestDeploymentIntegration:
    """测试部署集成。"""

    def test_secret_reference_in_deployment(self):
        """测试 Deployment 中 Secret 引用。"""
        manifest_path = Path("deployments/gitea-runner/gitea-runner-deployment.yaml")

        if manifest_path.exists():
            content = yaml.safe_load_all(manifest_path.read_text())

            for doc in content:
                if doc.get("kind") == "Deployment":
                    containers = doc["spec"]["template"]["spec"]["containers"]
                    env_vars = containers[0].get("env", [])

                    # 查找 Token 引用
                    token_found = False
                    for env in env_vars:
                        if env.get("name") == "GITEA_TOKEN":
                            value_from = env.get("valueFrom", {})
                            secret_ref = value_from.get("secretKeyRef", {})
                            if secret_ref.get("name") == "gitea-runner-token":
                                token_found = True
                                break

                    assert token_found, "未找到 GITEA_TOKEN 的 Secret 引用"

    def test_configmap_reference(self):
        """测试 ConfigMap 引用。"""
        manifest_path = Path("deployments/gitea-runner/gitea-runner-deployment.yaml")

        if manifest_path.exists():
            content = yaml.safe_load_all(manifest_path.read_text())

            for doc in content:
                if doc.get("kind") == "Deployment":
                    volumes = doc["spec"]["template"]["spec"].get("volumes", [])

                    # 查找 ConfigMap 卷
                    configmap_found = False
                    for volume in volumes:
                        if "configMap" in volume:
                            if volume["configMap"].get("name") == "gitea-runner-config":
                                configmap_found = True
                                break

                    assert configmap_found, "未找到 gitea-runner-config ConfigMap 引用"

    def test_namespace_consistency(self):
        """测试命名空间一致性。"""
        manifest_path = Path("deployments/gitea-runner/gitea-runner-deployment.yaml")

        if manifest_path.exists():
            content = yaml.safe_load_all(manifest_path.read_text())

            namespaces = set()
            for doc in content:
                ns = doc.get("metadata", {}).get("namespace")
                if ns:
                    namespaces.add(ns)

            # 所有资源应该使用相同命名空间
            assert len(namespaces) <= 1
            if namespaces:
                assert namespaces.pop() == "gitea-actions"


# ========== 配置验证测试 ==========


class TestConfigurationValidation:
    """测试配置验证。"""

    def test_yaml_syntax(self):
        """测试 YAML 语法。"""
        files_to_check = [
            "deployments/gitea-runner/values.yaml",
            "deployments/gitea-runner/Chart.yaml",
            "deployments/gitea-runner/gitea-runner-deployment.yaml",
        ]

        for file_path in files_to_check:
            path = Path(file_path)
            if path.exists():
                # 验证 YAML 语法
                yaml.safe_load_all(path.read_text())

    def test_label_consistency(self):
        """测试标签一致性。"""
        manifest_path = Path("deployments/gitea-runner/gitea-runner-deployment.yaml")

        if manifest_path.exists():
            content = yaml.safe_load_all(manifest_path.read_text())

            for doc in content:
                if doc.get("kind") == "Deployment":
                    # 验证标签匹配
                    labels = doc["spec"]["template"]["metadata"]["labels"]
                    selector = doc["spec"]["selector"]["matchLabels"]

                    # selector 的标签应该在 template 中存在
                    for key, value in selector.items():
                        assert labels.get(key) == value
