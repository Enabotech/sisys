"""
GPU 任务调度测试模块

验证 GPU 资源配置和调度功能
"""

from pathlib import Path
from typing import Any

import pytest
import yaml


class TestGPUConfiguration:
    """GPU 配置测试"""

    @pytest.fixture
    def deployment_config(self) -> list[dict[str, Any]]:
        """加载 Deployment 配置"""
        deploy_path = Path("deploy/kubernetes/k8s/deployment.yaml")
        if not deploy_path.exists():
            pytest.skip("Deployment config file not found")

        with open(deploy_path, encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))
        return docs  # 返回所有文档 (测试 + 生产)

    def test_gpu_resource_requests(self, deployment_config):
        """测试 GPU 资源请求配置"""
        for doc in deployment_config:
            if doc["kind"] != "Deployment":
                continue

            containers = doc["spec"]["template"]["spec"]["containers"]
            for container in containers:
                if "resources" in container:
                    resources = container["resources"]

                    # 检查 GPU 请求
                    if "requests" in resources:
                        assert (
                            "nvidia.com/gpu" in resources["requests"]
                        ), f"GPU request not configured in {doc['metadata']['name']}"
                        assert int(resources["requests"]["nvidia.com/gpu"]) >= 1, "GPU request should be at least 1"

    def test_gpu_resource_limits(self, deployment_config):
        """测试 GPU 资源限制配置"""
        for doc in deployment_config:
            if doc["kind"] != "Deployment":
                continue

            containers = doc["spec"]["template"]["spec"]["containers"]
            for container in containers:
                if "resources" in container:
                    resources = container["resources"]

                    # 检查 GPU 限制
                    if "limits" in resources:
                        assert "nvidia.com/gpu" in resources["limits"], f"GPU limit not configured in {doc['metadata']['name']}"
                        assert int(resources["limits"]["nvidia.com/gpu"]) >= 1, "GPU limit should be at least 1"

    def test_gpu_node_affinity(self, deployment_config):
        """测试 GPU 节点亲和性配置"""
        for doc in deployment_config:
            if doc["kind"] != "Deployment":
                continue

            spec = doc["spec"]["template"]["spec"]

            if "affinity" in spec:
                affinity = spec["affinity"]

                if "nodeAffinity" in affinity:
                    node_affinity = affinity["nodeAffinity"]

                    if "requiredDuringSchedulingIgnoredDuringExecution" in node_affinity:
                        terms = node_affinity["requiredDuringSchedulingIgnoredDuringExecution"]["nodeSelectorTerms"]

                        gpu_label_found = False
                        for term in terms:
                            for expr in term["matchExpressions"]:
                                if expr["key"] in ["nvidia.com/gpu.present", "node-type"]:
                                    if "gpu" in str(expr.get("values", [])).lower():
                                        gpu_label_found = True
                                        break

                        # 如果配置了 nodeAffinity，应该有 GPU 相关标签
                        assert gpu_label_found, f"GPU node affinity not properly configured in {doc['metadata']['name']}"

    def test_gpu_tolerations(self, deployment_config):
        """测试 GPU 容忍度配置"""
        for doc in deployment_config:
            if doc["kind"] != "Deployment":
                continue

            spec = doc["spec"]["template"]["spec"]

            if "tolerations" in spec:
                tolerations = spec["tolerations"]

                gpu_toleration_found = False
                for tol in tolerations:
                    if tol.get("key") == "nvidia.com/gpu":
                        gpu_toleration_found = True
                        break

                # 如果配置了 GPU 资源，应该有对应的容忍度
                containers = spec["containers"]
                for container in containers:
                    if "resources" in container:
                        resources = container["resources"]
                        if "requests" in resources and "nvidia.com/gpu" in resources["requests"]:
                            assert gpu_toleration_found, f"GPU toleration not configured in {doc['metadata']['name']}"


class TestCIPipelineGPU:
    """CI Pipeline GPU 配置测试"""

    @pytest.fixture
    def ci_workflow(self) -> dict[str, Any]:
        """加载 CI workflow 配置"""
        workflow_path = Path(".gitea/workflows/ci.yaml")
        if not workflow_path.exists():
            pytest.skip("CI workflow file not found")

        with open(workflow_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict)
        return data

    # def test_gpu_environment_variable(self, ci_workflow):
    #     """测试 GPU 环境变量配置"""
    #     env = ci_workflow["env"]

    #     assert "GPU_ENABLED" in env, "GPU_ENABLED environment variable not configured"

    def test_unit_tests_gpu_support(self, ci_workflow):
        """测试单元测试 GPU 支持"""
        jobs = ci_workflow["jobs"]

        if "unit-tests" in jobs:
            unit_tests = jobs["unit-tests"]

            # 检查 GPU 条件
            assert "if" in unit_tests, "Unit tests should have GPU condition"
            assert "GPU_ENABLED" in unit_tests["if"], "Unit tests should check GPU_ENABLED variable"

            # 检查 GPU Runner 标签
            if "runs-on" in unit_tests:
                runs_on = unit_tests["runs-on"]
                assert "GPU_RUNNER_LABEL" in str(runs_on) or "gpu" in str(runs_on), "Unit tests should use GPU runner label"

    def test_integration_tests_gpu_support(self, ci_workflow):
        """测试集成测试 GPU 支持"""
        jobs = ci_workflow["jobs"]

        if "integration-tests" in jobs:
            integration_tests = jobs["integration-tests"]

            # 检查 GPU 条件
            assert "if" in integration_tests, "Integration tests should have GPU condition"
            assert "GPU_ENABLED" in integration_tests["if"], "Integration tests should check GPU_ENABLED variable"

    def test_gpu_commit_message_trigger(self, ci_workflow):
        """测试 GPU 提交消息触发"""
        jobs = ci_workflow["jobs"]

        # 检查是否支持 [gpu] 标记触发
        for job_name, job in jobs.items():
            if "if" in job:
                condition = job["if"]
                # 检查是否包含 GPU 标记检测
                if "gpu" in condition.lower():
                    assert (
                        "[gpu]" in condition or "gpu" in condition
                    ), f"Job {job_name} should support [gpu] commit message trigger"


# class TestDockerfileGPU:
#     """Dockerfile GPU 配置测试"""

#     def test_pytorch_base_image(self):
#         """测试 PyTorch 基础镜像配置"""
#         dockerfile_path = Path("deploy/docker/dockerfile.l2")

#         if not dockerfile_path.exists():
#             pytest.skip("Dependency Dockerfile not found")

#         with open(dockerfile_path, encoding="utf-8") as f:
#             content = f.read()

#         # 检查 CUDA 相关配置
#         assert "cuda" in content.lower() or "CUDA" in content, "Dockerfile should reference CUDA"

#     def test_gpu_verification_step(self):
#         """测试 GPU 验证步骤"""
#         dockerfile_path = Path("deploy/docker/dockerfile.l2")

#         if not dockerfile_path.exists():
#             pytest.skip("Dependency Dockerfile not found")

#         with open(dockerfile_path, encoding="utf-8") as f:
#             content = f.read()

#         # 检查 PyTorch CUDA 验证
#         assert "torch" in content.lower() or "pytorch" in content.lower(), "Dockerfile should include PyTorch for GPU support"


@pytest.mark.skip(reason="import-pytorch 方案已作废")
class TestGPUScripts:
    """GPU 相关脚本测试（已废弃）"""

    def test_import_pytorch_script_gpu_verification(self):
        """测试 PyTorch 导入脚本 GPU 验证"""
        pytest.skip("import-pytorch 方案已作废")


class TestKubernetesGPUService:
    """Kubernetes GPU Service 配置测试"""

    @pytest.fixture
    def service_config(self) -> list[dict[str, Any]]:
        """加载 Service 配置"""
        service_path = Path("deploy/kubernetes/k8s/service.yaml")
        if not service_path.exists():
            pytest.skip("Service config file not found")

        with open(service_path, encoding="utf-8") as f:
            return list(yaml.safe_load_all(f))

    def test_headless_service_for_gpu(self, service_config):
        """测试 GPU 无头服务配置"""
        for doc in service_config:
            if doc and doc.get("kind") == "Service":
                if "headless" in doc["metadata"]["name"].lower():
                    assert doc["spec"]["clusterIP"] == "None", "Headless service should have clusterIP: None"


class TestGPUHealthCheck:
    """GPU 健康检查测试"""

    @pytest.fixture
    def deployment_config(self) -> list[dict[str, Any]]:
        """加载 Deployment 配置"""
        deploy_path = Path("deploy/kubernetes/k8s/deployment.yaml")
        if not deploy_path.exists():
            pytest.skip("Deployment config file not found")

        with open(deploy_path, encoding="utf-8") as f:
            return list(yaml.safe_load_all(f))

    def test_gpu_health_probe_env(self, deployment_config):
        """测试 GPU 健康检查环境变量"""
        for doc in deployment_config:
            if doc and doc["kind"] == "Deployment":
                containers = doc["spec"]["template"]["spec"]["containers"]

                for container in containers:
                    if "env" in container:
                        env_vars = {e["name"]: e.get("value", "") for e in container["env"]}

                        # 检查 GPU 相关环境变量
                        if "GPU_ENABLED" in env_vars:
                            assert env_vars["GPU_ENABLED"] in [
                                "true",
                                "True",
                                "1",
                            ], f"GPU_ENABLED should be true in {doc['metadata']['name']}"


class TestGPUDocumentation:
    """GPU 文档测试"""

    def test_gpu_section_in_ci_cd_guide(self):
        """测试 CI/CD 指南包含 GPU 章节"""
        guide_path = Path("docs/deploy/CI_CD_PIPELINE_TEMPLATE.md")

        if not guide_path.exists():
            pytest.skip("CI/CD guide not found")

        with open(guide_path, encoding="utf-8") as f:
            content = f.read()

        # 检查 GPU 相关内容
        gpu_keywords = ["GPU", "gpu", "CUDA", "cuda", "nvidia", "NVIDIA"]
        found_keywords = [kw for kw in gpu_keywords if kw in content]

        assert len(found_keywords) >= 3, "CI/CD guide should have comprehensive GPU documentation"

    def test_gpu_scheduling_documentation(self):
        """测试 GPU 调度文档"""
        guide_path = Path("docs/deploy/CI_CD_PIPELINE_TEMPLATE.md")

        if not guide_path.exists():
            pytest.skip("CI/CD guide not found")

        with open(guide_path, encoding="utf-8") as f:
            content = f.read()

        # 检查 GPU 调度章节
        assert "GPU" in content and (
            "调度" in content or "scheduling" in content.lower()
        ), "CI/CD guide should have GPU scheduling section"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
