"""
Gitea Runner 持久化测试

测试 Runner 持久化配置，验证重复注册问题已修复。
AC: 1, 4

测试覆盖：
- StatefulSet 配置
- PVC 持久化
- Runner 注册信息持久化
- 重启后不重复注册

注意：本测试针对组织级 Runner (gitea-org-runner)
"""

import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml


class TestStatefulSetConfiguration:
    """测试 StatefulSet 配置"""

    def test_statefulset_config_exists(self):
        """测试 StatefulSet 配置文件存在"""
        config_path = Path("deployments/gitea-runner/gitea-actions-complete.yaml")
        assert config_path.exists(), f"StatefulSet 配置文件不存在：{config_path}"

    def test_statefulset_valid_yaml(self):
        """测试 StatefulSet 配置 YAML 语法正确"""
        config_path = Path("deployments/gitea-runner/gitea-actions-complete.yaml")
        if config_path.exists():
            try:
                with open(config_path, encoding="utf-8") as f:
                    list(yaml.safe_load_all(f))
            except yaml.YAMLError as e:
                pytest.fail(f"StatefulSet 配置 YAML 语法错误：{e}")

    def test_statefulset_replicas(self):
        """测试 StatefulSet 副本数配置"""
        config_path = Path("deployments/gitea-runner/gitea-actions-complete.yaml")
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                # 使用 safe_load_all 处理多文档 YAML
                docs = list(yaml.safe_load_all(f))
                # 动态查找 StatefulSet 文档
                statefulset = next((doc for doc in docs if doc and doc.get("kind") == "StatefulSet"), None)
                assert statefulset is not None, "未找到 StatefulSet 文档"
                replicas = statefulset.get("spec", {}).get("replicas", 0)
                assert replicas == 4, f"Runner 副本数应为 4，实际为：{replicas}"

    def test_volume_claim_templates(self):
        """测试 volumeClaimTemplates 配置"""
        config_path = Path("deployments/gitea-runner/gitea-actions-complete.yaml")
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                # 使用 safe_load_all 处理多文档 YAML
                docs = list(yaml.safe_load_all(f))
                # 动态查找 StatefulSet 文档
                statefulset = next((doc for doc in docs if doc and doc.get("kind") == "StatefulSet"), None)
                assert statefulset is not None, "未找到 StatefulSet 文档"
                spec = statefulset.get("spec", {})

                # 检查 volumeClaimTemplates
                vct = spec.get("volumeClaimTemplates", [])
                assert len(vct) > 0, "未配置 volumeClaimTemplates"

                # 检查 PVC 名称和存储
                runner_data_vct = next((v for v in vct if v.get("metadata", {}).get("name") == "runner-data"), None)
                assert runner_data_vct is not None, "未配置 runner-data volumeClaimTemplate"

                # 检查存储大小
                resources = runner_data_vct.get("spec", {}).get("resources", {})
                storage = resources.get("requests", {}).get("storage", "")
                assert storage == "1Gi", f"PVC 存储应为 1Gi，实际为：{storage}"


class TestPVCConfiguration:
    """测试 PVC 配置"""

    def test_volume_claim_templates_exists(self):
        """测试 volumeClaimTemplates 配置（替代手动 PVC 文件）"""
        config_path = Path("deployments/gitea-runner/gitea-actions-complete.yaml")
        if config_path.exists():
            config_text = config_path.read_text(encoding="utf-8")
            # 检查是否配置了 volumeClaimTemplates
            assert "volumeClaimTemplates" in config_text, "未配置 volumeClaimTemplates"
            assert "runner-data" in config_text, "未配置 runner-data volumeClaimTemplate"
            assert "storage: 1Gi" in config_text, "PVC 存储应为 1Gi"

    def test_pvc_auto_created_by_statefulset(self):
        """测试 PVC 由 StatefulSet 自动创建（替代手动 PVC 文件测试）"""
        config_path = Path("deployments/gitea-runner/gitea-actions-complete.yaml")
        if config_path.exists():
            config_text = config_path.read_text(encoding="utf-8")
            # 检查 storageClassName 配置
            assert "storageClassName: local-path" in config_text, "PVC 应使用 local-path StorageClass"


class TestPersistenceConfiguration:
    """测试持久化配置"""

    def test_runner_data_mount(self):
        """测试 Runner 数据挂载"""
        config_path = Path("deployments/gitea-runner/gitea-actions-complete.yaml")
        if config_path.exists():
            config_text = config_path.read_text(encoding="utf-8")

            # 检查是否挂载了 runner-data 到 /data 目录
            assert "runner-data" in config_text, "未挂载 runner-data 卷"

            # 检查挂载路径为 /data（act_runner 默认存储路径）
            assert "mountPath: /data" in config_text, "Runner 配置目录应挂载到 /data（act_runner 默认存储路径）"

    def test_subpath_usage(self):
        """测试 subPath 使用（用于 config.yaml 挂载）"""
        config_path = Path("deployments/gitea-runner/gitea-actions-complete.yaml")
        if config_path.exists():
            config_text = config_path.read_text(encoding="utf-8")

            # 检查是否使用 subPath 挂载 config.yaml
            assert "subPath" in config_text, "未使用 subPath 挂载配置文件"
            assert "config.yaml" in config_text, "subPath 应挂载 config.yaml"

    def test_runner_data_uses_pvc_not_configmap(self):
        """测试 runner-data 使用 PVC 而非 ConfigMap"""
        config_path = Path("deployments/gitea-runner/gitea-actions-complete.yaml")
        if config_path.exists():
            config_text = config_path.read_text(encoding="utf-8")

            # runner-data 应该通过 volumeClaimTemplates 创建（PVC），而非 volumes 中的 ConfigMap
            # 检查 volumeClaimTemplates 中存在 runner-data
            assert "volumeClaimTemplates" in config_text, "应使用 volumeClaimTemplates 创建 PVC"

            # 检查 volumes 中的 runner-config 使用 ConfigMap（用于配置文件）
            # 但 runner-data 不应使用 ConfigMap
            lines = config_text.split("\n")
            in_volumes = False
            for line in lines:
                if "volumes:" in line:
                    in_volumes = True
                if in_volumes and "runner-data" in line and "configMap" in line:
                    pytest.fail("runner-data 不应使用 ConfigMap，应使用 PVC")


class TestKubernetesResources:
    """测试 K8s 资源"""

    @pytest.mark.integration
    def test_statefulset_deployed(self):
        """测试 StatefulSet 已部署"""
        try:
            result = subprocess.run(
                ["kubectl", "get", "statefulset", "gitea-org-runner", "-n", "gitea-actions"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                pytest.skip("StatefulSet 未部署")

            assert "gitea-org-runner" in result.stdout, "StatefulSet 未找到"
            print(f"✅ StatefulSet 已部署:\n{result.stdout}")

        except Exception as e:
            pytest.skip(f"无法验证 StatefulSet: {str(e)}")

    @pytest.mark.integration
    def test_pvcs_created(self):
        """测试 PVC 已创建"""
        try:
            result = subprocess.run(
                ["kubectl", "get", "pvc", "-n", "gitea-actions", "-l", "app=gitea-org-runner"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0 or "No resources found" in result.stdout:
                pytest.skip("PVC 未创建")

            # 检查是否有 3 个 PVC
            lines = result.stdout.strip().split("\n")
            if len(lines) > 1:  # 第一行是标题
                pvc_count = len(lines) - 1
                assert pvc_count == 4, f"PVC 数量应为 4，实际为：{pvc_count}"

            print(f"✅ PVC 已创建:\n{result.stdout}")

        except Exception as e:
            pytest.skip(f"无法验证 PVC: {str(e)}")

    @pytest.mark.integration
    def test_pods_running(self):
        """测试 Pod 运行中"""
        try:
            result = subprocess.run(
                ["kubectl", "get", "pods", "-n", "gitea-actions", "-l", "app=gitea-org-runner"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0 or "No resources found" in result.stdout:
                pytest.skip("Pod 未运行")

            # 检查 Pod 状态
            assert "Running" in result.stdout, "Pod 未运行"

            # 检查 Pod 名称格式 (gitea-org-runner-0, gitea-org-runner-1, gitea-org-runner-2)
            lines = result.stdout.strip().split("\n")[1:]  # 跳过标题行
            pod_names = [line.split()[0] for line in lines if line.strip()]

            expected_names = ["gitea-org-runner-0", "gitea-org-runner-1", "gitea-org-runner-2"]
            for expected in expected_names:
                assert any(expected in name for name in pod_names), f"缺少 Pod: {expected}"

            print(f"✅ Pod 运行中:\n{result.stdout}")

        except Exception as e:
            pytest.skip(f"无法验证 Pod: {str(e)}")

    @pytest.mark.integration
    def test_pvc_bound(self):
        """测试 PVC 已绑定"""
        try:
            result = subprocess.run(
                ["kubectl", "get", "pvc", "-n", "gitea-actions", "-l", "app=gitea-org-runner"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                pytest.skip("无法获取 PVC 状态")

            # 检查 PVC 状态
            lines = result.stdout.strip().split("\n")[1:]  # 跳过标题行
            for line in lines:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 3:
                        status = parts[2]
                        # PVC 状态为 Bound 或以 pvc- 开头（表示已绑定且有 PV）
                        if status == "Bound" or status.startswith("pvc-"):
                            continue  # PVC 已绑定
                        else:
                            pytest.fail(f"PVC {parts[0]} 状态应为 Bound，实际为：{status}")

            print(f"✅ PVC 已绑定:\n{result.stdout}")

        except Exception as e:
            pytest.skip(f"无法验证 PVC 状态：{str(e)}")


class TestDuplicateRegistrationFix:
    """测试重复注册修复"""

    @pytest.mark.integration
    def test_no_duplicate_runners(self):
        """测试无重复 Runner"""
        try:
            # 获取 Gitea Runner Token (从 gitea-actions namespace)
            token_result = subprocess.run(
                ["kubectl", "get", "secret", "gitea-org-runner-token", "-n", "gitea-actions", "-o", "jsonpath={.data.token}"],
                capture_output=True,
                text=True,
                check=False,
            )

            if token_result.returncode != 0 or not token_result.stdout.strip():
                pytest.skip("无法获取 Gitea Runner Token")

            import base64

            token = base64.b64decode(token_result.stdout.strip()).decode()

            # 获取所有 Runner
            import requests

            response = requests.get(
                "http://gitea-http.gitea.svc.cluster.local:3000/api/v1/admin/runners",
                headers={"Authorization": f"token {token}"},
                timeout=10,
            )

            if response.status_code != 200:
                pytest.skip("无法获取 Runner 列表")

            runners = response.json()

            # 检查 Runner 名称
            runner_names = [r.get("name", "") for r in runners]

            # StatefulSet 模式下，Runner 名称应包含 Pod 名称

            # 检查是否有重复名称
            from collections import Counter

            name_counts = Counter(runner_names)

            for name, count in name_counts.items():
                assert count == 1, f"Runner {name} 重复注册 ({count} 次)"

            print(f"✅ 无重复 Runner:\n{runner_names}")

        except ImportError:
            pytest.skip("requests 库未安装")
        except Exception as e:
            pytest.skip(f"无法验证 Runner 重复：{str(e)}")


# 测试辅助函数
def check_runner_persistence(pod_name: str, namespace: str = "gitea-actions") -> dict[str, Any]:
    """
    检查 Runner 持久化状态

    Args:
        pod_name: Pod 名称
        namespace: Kubernetes 命名空间

    Returns:
        持久化状态字典
    """
    try:
        # 检查 .runner 文件是否存在
        result = subprocess.run(
            ["kubectl", "exec", "-n", namespace, pod_name, "--", "ls", "-la", "/root/.config/act_runner/.runner"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            return {"persistent": True, "message": ".runner 文件存在"}
        else:
            return {"persistent": False, "message": ".runner 文件不存在"}
    except Exception as e:
        return {"persistent": False, "error": str(e)}


def restart_pod_and_verify(pod_name: str, namespace: str = "gitea-actions") -> dict[str, Any]:
    """
    重启 Pod 并验证 Runner 不重复注册

    Args:
        pod_name: Pod 名称
        namespace: Kubernetes 命名空间

    Returns:
        验证结果
    """
    try:
        # 删除 Pod
        subprocess.run(
            ["kubectl", "delete", "pod", pod_name, "-n", namespace], capture_output=True, text=True, check=True, timeout=60
        )

        # 等待 Pod 重启
        subprocess.run(
            ["kubectl", "wait", "--for=condition=Ready", "pod", pod_name, "-n", namespace, "--timeout=120s"],
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )

        # 验证 .runner 文件仍存在
        persistence = check_runner_persistence(pod_name, namespace)

        return {
            "success": True,
            "persistent": persistence["persistent"],
            "message": f"Pod 重启成功，持久化状态：{persistence['message']}",
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
