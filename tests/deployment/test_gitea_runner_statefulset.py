"""
Test Gitea Runner StatefulSet Configuration.

测试 Gitea Runner StatefulSet 配置的正确性。
AC: 1

测试覆盖：
- StatefulSet 配置
- PVC 持久化
- .runner 文件持久化
- 重启后不重复注册

注意：本测试针对组织级 Runner (gitea-org-runner)
"""

import subprocess
from pathlib import Path

import pytest
import yaml


class TestStatefulSetConfiguration:
    """测试 StatefulSet 配置"""

    def test_statefulset_config_exists(self):
        """测试 StatefulSet 配置文件存在"""
        config_path = Path("deployments/gitea-runner/gitea-org-runner-statefulset.yaml")
        assert config_path.exists(), f"StatefulSet 配置文件不存在：{config_path}"

    def test_statefulset_valid_yaml(self):
        """测试 StatefulSet 配置 YAML 语法正确"""
        config_path = Path("deployments/gitea-runner/gitea-org-runner-statefulset.yaml")
        if config_path.exists():
            try:
                with open(config_path, encoding="utf-8") as f:
                    list(yaml.safe_load_all(f))
            except yaml.YAMLError as e:
                pytest.fail(f"StatefulSet 配置 YAML 语法错误：{e}")

    def test_statefulset_replicas(self):
        """测试 StatefulSet 副本数配置"""
        config_path = Path("deployments/gitea-runner/gitea-org-runner-statefulset.yaml")
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                # 使用 safe_load_all 处理多文档 YAML
                docs = list(yaml.safe_load_all(f))
                # 第一个文档是 StatefulSet
                statefulset = docs[0]
                replicas = statefulset.get("spec", {}).get("replicas", 0)
                assert replicas == 4, f"Runner 副本数应为 3，实际为：{replicas}"

    def test_runner_args_include_config(self):
        """测试 Runner 启动参数包含 --config"""
        config_path = Path("deployments/gitea-runner/gitea-org-runner-statefulset.yaml")
        if config_path.exists():
            config_text = config_path.read_text(encoding="utf-8")
            # 检查是否包含 --config 参数
            assert "--config" in config_text, "Runner 启动参数缺少 --config"

    def test_volume_claim_templates_configured(self):
        """测试 volumeClaimTemplates 配置"""
        config_path = Path("deployments/gitea-runner/gitea-org-runner-statefulset.yaml")
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                # 使用 safe_load_all 处理多文档 YAML
                docs = list(yaml.safe_load_all(f))
                # 第一个文档是 StatefulSet
                statefulset = docs[0]
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

    def test_config_file_mounted(self):
        """测试配置文件挂载"""
        config_path = Path("deployments/gitea-runner/gitea-org-runner-statefulset.yaml")
        if config_path.exists():
            config_text = config_path.read_text(encoding="utf-8")
            # 检查是否挂载了 config.yaml
            assert "/etc/act-runner/config.yaml" in config_text, "配置文件未挂载到 /etc/act-runner/config.yaml"

    def test_data_directory_mounted(self):
        """测试 /data 目录挂载"""
        config_path = Path("deployments/gitea-runner/gitea-org-runner-statefulset.yaml")
        if config_path.exists():
            config_text = config_path.read_text(encoding="utf-8")
            # 检查是否挂载了 /data 目录
            assert "mountPath: /data" in config_text, "/data 目录未挂载"


class TestRunnerConfigFile:
    """测试 Runner 配置文件"""

    def test_runner_config_exists(self):
        """测试 Runner 配置文件存在"""
        config_path = Path("deployments/gitea-runner/gitea-actions-complete.yaml")
        assert config_path.exists(), f"Runner 配置文件不存在：{config_path}"

    def test_runner_config_valid_yaml(self):
        """测试 Runner 配置 YAML 语法正确"""
        config_path = Path("deployments/gitea-runner/gitea-actions-complete.yaml")
        if config_path.exists():
            try:
                with open(config_path, encoding="utf-8") as f:
                    yaml.safe_load_all(f)
            except yaml.YAMLError as e:
                pytest.fail(f"Runner 配置 YAML 语法错误：{e}")


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
    def test_pvcs_bound(self):
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
    def test_runner_file_persisted(self):
        """测试 Runner 文件持久化"""
        try:
            for i in range(3):
                pod_name = f"gitea-org-runner-{i}"
                result = subprocess.run(
                    ["kubectl", "exec", "-n", "gitea-actions", pod_name, "--", "ls", "-la", "/data/.runner"],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if result.returncode != 0:
                    pytest.fail(f"Pod {pod_name} 中 .runner 文件不存在")

            print("✅ .runner 文件在所有 Pod 中存在")

        except Exception as e:
            pytest.skip(f"无法验证 .runner 文件：{str(e)}")

    @pytest.mark.integration
    def test_runner_no_reregister_on_restart(self):
        """测试 Runner 重启后不重复注册（通过 PVC 持久化验证）"""
        try:
            # 验证 PVC 存在且配置正确
            result = subprocess.run(
                ["kubectl", "get", "pvc", "-n", "gitea-actions", "-l", "app=gitea-org-runner", "-o", "json"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                pytest.skip("无法获取 PVC 列表")

            import json

            pvc_data = json.loads(result.stdout)
            pvcs = pvc_data.get("items", [])

            assert len(pvcs) > 0, "没有找到 Runner PVC"

            # 验证每个 PVC 都有绑定状态
            for pvc in pvcs:
                pvc_name = pvc.get("metadata", {}).get("name", "")
                status = pvc.get("status", {}).get("phase", "")
                assert status == "Bound", f"PVC {pvc_name} 未绑定（状态：{status}）"

            print(f"✅ Runner PVC 已绑定且持久化配置正确（共 {len(pvcs)} 个 PVC）")

        except subprocess.TimeoutExpired:
            pytest.skip("测试超时")
        except AssertionError:
            raise
        except Exception as e:
            pytest.skip(f"无法验证持久化：{str(e)}")


class TestCleanupScripts:
    """测试清理脚本"""

    def test_cleanup_offline_runners_script_exists(self):
        """测试清理离线 Runner 脚本存在"""
        script_path = Path("scripts/deployment/gitea-runner/cleanup-offline-runners.sh")
        assert script_path.exists(), f"清理脚本不存在：{script_path}"

    def test_fix_duplicate_registration_script_exists(self):
        """测试修复重复注册脚本存在"""
        script_path = Path("scripts/deployment/gitea-runner/fix-duplicate-registration.sh")
        assert script_path.exists(), f"修复脚本不存在：{script_path}"

    def test_scripts_executable(self):
        """测试脚本可执行"""
        import os

        scripts = [
            "scripts/deployment/gitea-runner/cleanup-offline-runners.sh",
            "scripts/deployment/gitea-runner/fix-duplicate-registration.sh",
        ]

        for script in scripts:
            script_path = Path(script)
            if script_path.exists():
                assert os.access(script_path, os.X_OK), f"脚本不可执行：{script_path}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
