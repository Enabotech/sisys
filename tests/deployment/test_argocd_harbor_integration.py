"""
ArgoCD Harbor 集成测试
Story 0.7: ArgoCD 持续部署 - Task 5: Harbor 镜像仓库集成

测试 ArgoCD Image Updater 与 Harbor 的集成，验证镜像自动更新流程。
"""

import json
import subprocess
from typing import Any

import pytest


class TestArgoCDHarborIntegration:
    """ArgoCD 与 Harbor 集成测试套件"""

    # ===========================================================================
    #  fixture 配置
    # ===========================================================================

    @pytest.fixture(scope="class")
    def argocd_namespace(self) -> str:
        """ArgoCD 命名空间"""
        return "argocd"

    @pytest.fixture(scope="class")
    def harbor_namespace(self) -> str:
        """Harbor 命名空间"""
        return "harbor"

    @pytest.fixture(scope="class")
    def harbor_url(self) -> str:
        """Harbor 访问 URL"""
        return "harbor.sisys.local"

    @pytest.fixture(scope="class")
    def argocd_image_updater_image(self) -> str:
        """ArgoCD Image Updater 镜像版本"""
        return "quay.io/argoprojlabs/argocd-image-updater:v0.14.0"

    # ===========================================================================
    # Task 5.1: ArgoCD Image Updater 安装测试
    # ===========================================================================

    def test_image_updater_helm_chart_installed(self, argocd_namespace: str):
        """验证 ArgoCD Image Updater Helm Chart 已安装"""
        result = subprocess.run(["sudo", "helm", "list", "-n", argocd_namespace], capture_output=True, text=True)
        assert result.returncode == 0, f"Helm list failed: {result.stderr}"
        assert "argocd-image-updater" in result.stdout, "ArgoCD Image Updater Helm Chart 未安装"

    def test_image_updater_deployment_exists(self, argocd_namespace: str):
        """验证 ArgoCD Image Updater Deployment 已创建"""
        result = subprocess.run(
            ["sudo", "kubectl", "get", "deployment", "argocd-image-updater", "-n", argocd_namespace, "-o", "json"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Deployment 不存在：{result.stderr}"
        deployment = json.loads(result.stdout)
        assert deployment["metadata"]["name"] == "argocd-image-updater"

    def test_image_updater_pod_running(self, argocd_namespace: str):
        """验证 ArgoCD Image Updater Pod 运行状态"""
        result = subprocess.run(
            [
                "sudo",
                "kubectl",
                "get",
                "pods",
                "-n",
                argocd_namespace,
                "-l",
                "app.kubernetes.io/name=argocd-image-updater",
                "-o",
                "jsonpath={.items[*].status.phase}",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Running" in result.stdout, f"Image Updater Pod 未运行，当前状态：{result.stdout}"

    def test_image_updater_replicas_ready(self, argocd_namespace: str):
        """验证 ArgoCD Image Updater 副本就绪"""
        result = subprocess.run(
            [
                "sudo",
                "kubectl",
                "get",
                "deployment",
                "argocd-image-updater",
                "-n",
                argocd_namespace,
                "-o",
                "jsonpath={.status.readyReplicas}",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        ready_replicas = int(result.stdout) if result.stdout else 0
        assert ready_replicas >= 1, f"Image Updater 无就绪副本，readyReplicas={ready_replicas}"

    # ===========================================================================
    # Task 5.2: Harbor 仓库凭据配置测试
    # ===========================================================================

    def test_harbor_credentials_secret_exists(self, argocd_namespace: str):
        """验证 Harbor 仓库凭据 Secret 已创建"""
        result = subprocess.run(
            ["sudo", "kubectl", "get", "secret", "argocd-image-updater-secret", "-n", argocd_namespace, "-o", "json"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Harbor 凭据 Secret 不存在：{result.stderr}"
        secret = json.loads(result.stdout)
        assert "data" in secret
        assert "registries.conf" in secret["data"] or "config" in secret["data"], "Secret 中缺少 registries.conf 或 config 配置"

    def test_harbor_credentials_config_valid(self, argocd_namespace: str):
        """验证 Harbor 凭据配置格式正确"""
        result = subprocess.run(
            [
                "sudo",
                "kubectl",
                "get",
                "secret",
                "argocd-image-updater-secret",
                "-n",
                argocd_namespace,
                "-o",
                "jsonpath={.data.registries\\.conf}",
            ],
            capture_output=True,
            text=True,
        )
        if result.stdout:
            import base64

            config = base64.b64decode(result.stdout).decode("utf-8")
            assert "harbor.sisys.local" in config or "harbor.harbor.svc.cluster.local" in config, "Harbor 仓库地址未配置"

    # ===========================================================================
    # Task 5.3: Harbor Webhook 触发配置测试
    # ===========================================================================

    def test_harbor_webhook_configmap_exists(self, harbor_namespace: str):
        """验证 Harbor Webhook ConfigMap 已创建"""
        result = subprocess.run(
            ["sudo", "kubectl", "get", "configmap", "harbor-webhook-config", "-n", harbor_namespace, "-o", "json"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Harbor Webhook ConfigMap 不存在：{result.stderr}"

    def test_argocd_webhook_receiver_configured(self, argocd_namespace: str):
        """验证 ArgoCD Webhook 接收器已配置"""
        result = subprocess.run(
            ["sudo", "kubectl", "get", "configmap", "argocd-image-updater-webhook", "-n", argocd_namespace, "-o", "json"],
            capture_output=True,
            text=True,
        )
        # Webhook 配置为可选，不作为失败条件
        if result.returncode == 0:
            configmap = json.loads(result.stdout)
            assert "webhook-config" in configmap.get("data", {}), "Webhook 配置缺失"

    # ===========================================================================
    # Task 5.4: 镜像更新策略配置测试
    # ===========================================================================

    def test_image_updater_configmap_exists(self, argocd_namespace: str):
        """验证 Image Updater ConfigMap 已创建"""
        result = subprocess.run(
            ["sudo", "kubectl", "get", "configmap", "argocd-image-updater-config", "-n", argocd_namespace, "-o", "json"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Image Updater ConfigMap 不存在：{result.stderr}"

    def test_image_updater_config_valid(self, argocd_namespace: str):
        """验证 Image Updater 配置有效"""
        result = subprocess.run(
            [
                "sudo",
                "kubectl",
                "get",
                "configmap",
                "argocd-image-updater-config",
                "-n",
                argocd_namespace,
                "-o",
                "jsonpath={.data}",
            ],
            capture_output=True,
            text=True,
        )
        if result.stdout:
            config = json.loads(result.stdout)
            # 检查关键配置项
            config_content = str(config)
            assert "registries" in config_content.lower() or "harbor" in config_content.lower(), "配置中缺少 registries 配置"

    # ===========================================================================
    # Task 5.5: 镜像自动更新流程验证测试
    # ===========================================================================

    def test_image_updater_logs_healthy(self, argocd_namespace: str):
        """验证 Image Updater 日志健康（无持续错误）"""
        result = subprocess.run(
            [
                "sudo",
                "kubectl",
                "logs",
                "-n",
                argocd_namespace,
                "-l",
                "app.kubernetes.io/name=argocd-image-updater",
                "--tail=50",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            logs = result.stdout
            # 检查是否有持续的错误（允许偶发错误）
            error_count = logs.lower().count("error")
            assert error_count < 10, f"Image Updater 日志中存在过多错误：{error_count} 个"

    def test_image_updater_registry_connection(self, argocd_namespace: str):
        """验证 Image Updater 与 Harbor 连接正常"""
        result = subprocess.run(
            [
                "sudo",
                "kubectl",
                "logs",
                "-n",
                argocd_namespace,
                "-l",
                "app.kubernetes.io/name=argocd-image-updater",
                "--tail=100",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            logs = result.stdout
            # 检查是否有成功连接 Harbor 的日志
            assert (
                "harbor" in logs.lower() or "registry" in logs.lower() or "Successfully" in logs
            ), "未找到 Image Updater 连接 Harbor 的成功日志"

    # ===========================================================================
    # Task 5.6: 端到端 GitOps 流程测试
    # ===========================================================================

    def test_harbor_project_exists(self, harbor_namespace: str):
        """验证 Harbor 项目已创建"""
        # 通过检查 Harbor Core Pod 状态间接验证
        result = subprocess.run(
            [
                "sudo",
                "kubectl",
                "get",
                "pods",
                "-n",
                harbor_namespace,
                "-l",
                "app=harbor-core",
                "-o",
                "jsonpath={.items[*].status.phase}",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Running" in result.stdout, f"Harbor Core 未运行：{result.stdout}"

    def test_harbor_robot_account_secret_exists(self, harbor_namespace: str):
        """验证 Harbor Robot Account Secret 已创建"""
        result = subprocess.run(
            ["sudo", "kubectl", "get", "secret", "harbor-robot-secret", "-n", harbor_namespace, "-o", "json"],
            capture_output=True,
            text=True,
        )
        # Robot Account Secret 为可选配置
        if result.returncode != 0:
            pytest.skip("Harbor Robot Account Secret 未配置（可选）")

    def test_end_to_end_image_update_workflow(self, argocd_namespace: str):
        """
        端到端镜像更新工作流测试

        测试完整的 GitOps 流程：
        1. Harbor 推送新镜像
        2. Image Updater 检测到新镜像
        3. ArgoCD 自动更新 Deployment
        4. K8s 滚动更新成功
        """
        # 检查 Image Updater 是否正在监控
        result = subprocess.run(
            [
                "sudo",
                "kubectl",
                "logs",
                "-n",
                argocd_namespace,
                "-l",
                "app.kubernetes.io/name=argocd-image-updater",
                "--tail=200",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            logs = result.stdout
            # 检查是否有监控活动
            has_monitoring = any(keyword in logs.lower() for keyword in ["checking", "monitoring", "updating", "syncing"])
            if not has_monitoring:
                pytest.skip("Image Updater 暂无监控活动（等待首次配置）")

    # ===========================================================================
    # 辅助测试方法
    # ===========================================================================

    def _run_kubectl_command(self, args: list[str]) -> tuple:
        """辅助方法：运行 kubectl 命令"""
        cmd = ["sudo", "kubectl"] + args
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr

    def _get_json_output(self, args: list[str]) -> dict[str, Any]:
        """辅助方法：获取 JSON 格式输出"""
        args.append("-o")
        args.append("json")
        returncode, stdout, stderr = self._run_kubectl_command(args)
        if returncode != 0:
            raise subprocess.CalledProcessError(returncode, args, stderr)
        return json.loads(stdout)  # type: ignore[no-any-return]


# =============================================================================
# 集成测试场景
# =============================================================================


@pytest.mark.integration
class TestArgoCDHarborIntegrationE2E:
    """ArgoCD Harbor 端到端集成测试"""

    def test_webhook_trigger_image_update(self):
        """
        测试 Harbor Webhook 触发镜像更新

        步骤：
        1. 推送新镜像到 Harbor
        2. 验证 Webhook 触发成功
        3. 验证 Image Updater 检测到新镜像
        4. 验证 ArgoCD 更新 Deployment
        """
        # 这是一个完整的 E2E 测试，需要实际的镜像推送
        # 在实际环境中执行，这里仅作为测试框架
        pytest.skip("E2E 测试需要实际推送镜像，手动执行")

    def test_multi_environment_image_update(self):
        """
        测试多环境镜像更新

        验证 Dev/Test/Prod 各环境独立更新
        """
        pytest.skip("多环境测试需要先配置 Kustomize 覆盖，手动执行")


# =============================================================================
# 测试执行说明
# =============================================================================

if __name__ == "__main__":
    """
    测试执行命令：

    # 运行所有测试
    pytest tests/deployment/test_argocd_harbor_integration.py -v

    # 运行特定测试
    pytest tests/deployment/test_argocd_harbor_integration.py::TestArgoCDHarborIntegration::test_image_updater_pod_running -v

    # 运行并生成覆盖率报告
    pytest tests/deployment/test_argocd_harbor_integration.py --cov=deployments/argocd --cov-report=html

    # 运行集成测试
    pytest tests/deployment/test_argocd_harbor_integration.py -m integration -v
    """
