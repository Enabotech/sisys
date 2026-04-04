"""
CI/CD Pipeline 测试模块

测试 Pipeline 配置的正确性和各阶段功能
"""

from pathlib import Path
from typing import Any

import pytest
import yaml


class TestCIPipeline:
    """CI Pipeline 配置测试"""

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

    def test_workflow_name(self, ci_workflow):
        """测试工作流名称"""
        assert ci_workflow["name"] == "CI Pipeline"

    def test_trigger_events(self, ci_workflow):
        """测试触发事件"""
        # 注意：on 在 YAML 1.1 中是布尔值，会被解析为 True
        on_config = ci_workflow.get("on") or ci_workflow.get(True) or {}

        # 检查 push 触发
        assert "push" in on_config
        assert "branches" in on_config["push"]
        assert "main" in on_config["push"]["branches"]

        # 检查 PR 触发
        assert "pull_request" in on_config
        assert "branches" in on_config["pull_request"]

    def test_environment_variables(self, ci_workflow):
        """测试环境变量配置"""
        env = ci_workflow["env"]

        assert "HARBOR_REGISTRY" in env
        assert env["HARBOR_REGISTRY"] == "harbor.sisys.local"

        assert "PYTHON_VERSION" in env
        assert env["PYTHON_VERSION"] == "3.11"

    def test_concurrency_control(self, ci_workflow):
        """测试并发控制"""
        assert "concurrency" in ci_workflow
        assert "group" in ci_workflow["concurrency"]
        assert ci_workflow["concurrency"]["cancel-in-progress"] is True

    def test_code_quality_job(self, ci_workflow):
        """测试代码质量检查任务"""
        jobs = ci_workflow["jobs"]
        assert "code-quality" in jobs

        code_quality = jobs["code-quality"]
        assert code_quality["name"] == "🔍 代码检查"

        # 检查步骤
        steps = [s["name"] for s in code_quality["steps"]]
        assert "代码检查 ( Ruff )" in steps
        assert "类型检查 ( MyPy )" in steps

    def test_unit_tests_job(self, ci_workflow):
        """测试单元测试任务"""
        jobs = ci_workflow["jobs"]
        assert "unit-tests" in jobs

        unit_tests = jobs["unit-tests"]
        assert unit_tests["name"] == "🧪 单元测试"

        # 检查 GPU 支持
        assert "if" in unit_tests
        assert "GPU_ENABLED" in unit_tests["if"]

    def test_integration_tests_job(self, ci_workflow):
        """测试集成测试任务"""
        jobs = ci_workflow["jobs"]
        assert "integration-tests" in jobs

        integration_tests = jobs["integration-tests"]
        assert integration_tests["name"] == "🔗 集成测试"

        # 检查服务依赖
        assert "services" in integration_tests
        services = integration_tests["services"]
        assert "postgres" in services
        assert "redis" in services

    def test_security_scan_job(self, ci_workflow):
        """测试安全扫描任务"""
        jobs = ci_workflow["jobs"]
        assert "security-scan" in jobs

        security_scan = jobs["security-scan"]
        assert security_scan["name"] == "🔒 安全扫描"

        # 检查步骤
        steps = [s["name"] for s in security_scan["steps"]]
        assert "代码安全扫描 ( Bandit )" in steps
        assert "文件系统扫描 ( Trivy )" in steps

    def test_build_image_job(self, ci_workflow):
        """测试镜像构建任务"""
        jobs = ci_workflow["jobs"]
        assert "build-image" in jobs

        build_image = jobs["build-image"]
        assert build_image["name"] == "🏗️ 构建镜像"

        # 检查 Docker Buildx
        steps = [s["name"] for s in build_image["steps"]]
        assert "设置 Buildx" in steps
        assert "构建推送镜像" in steps

    # def test_auto_deploy_job(self, ci_workflow):
    #     """测试自动部署任务"""
    #     jobs = ci_workflow["jobs"]
    #     assert "auto-deploy" in jobs

    #     auto_deploy = jobs["auto-deploy"]
    #     assert auto_deploy["name"] == "🚀 自动部署"

    #     # 检查部署条件
    #     assert "if" in auto_deploy
    #     assert "main" in auto_deploy["if"]


class TestCDPipeline:
    """CD Pipeline 配置测试"""

    @pytest.fixture
    def cd_workflow(self) -> dict[str, Any]:
        """加载 CD workflow 配置"""
        workflow_path = Path(".gitea/workflows/cd.yaml")
        if not workflow_path.exists():
            pytest.skip("CD workflow file not found")

        with open(workflow_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict)
        return data

    def test_workflow_name(self, cd_workflow):
        """测试工作流名称"""
        assert cd_workflow["name"] == "CD Pipeline"

    def test_manual_dispatch(self, cd_workflow):
        """测试手动触发配置"""
        # 注意：on 在 YAML 1.1 中是布尔值，会被解析为 True
        on_config = cd_workflow.get("on") or cd_workflow.get(True) or {}
        assert "workflow_dispatch" in on_config

        inputs = on_config["workflow_dispatch"]["inputs"]
        assert "environment" in inputs
        assert "git_sha" in inputs

    def test_deploy_test_job(self, cd_workflow):
        """测试部署到测试环境任务"""
        jobs = cd_workflow["jobs"]
        assert "deploy-test" in jobs

        deploy_test = jobs["deploy-test"]
        assert deploy_test["name"] == "🚀 部署到测试环境"

        # 检查环境配置
        assert "environment" in deploy_test
        assert deploy_test["environment"]["name"] == "test"

    def test_production_approval_job(self, cd_workflow):
        """测试生产审批任务"""
        jobs = cd_workflow["jobs"]
        assert "production-approval" in jobs

        production_approval = jobs["production-approval"]
        assert production_approval["name"] == "✅ 生产部署审批"

    def test_deploy_production_job(self, cd_workflow):
        """测试部署到生产环境任务"""
        jobs = cd_workflow["jobs"]
        assert "deploy-production" in jobs

        deploy_production = jobs["deploy-production"]
        assert deploy_production["name"] == "🚀 部署到生产环境"

        # 检查环境配置
        assert "environment" in deploy_production
        assert deploy_production["environment"]["name"] == "production"

    def test_auto_rollback_job(self, cd_workflow):
        """测试自动回滚任务"""
        jobs = cd_workflow["jobs"]
        assert "auto-rollback" in jobs

        auto_rollback = jobs["auto-rollback"]
        assert auto_rollback["name"] == "🔄 自动回滚"

        # 检查触发条件
        assert "if" in auto_rollback
        assert "failure()" in auto_rollback["if"]


class TestDependencyImageWorkflow:
    """依赖镜像构建工作流测试"""

    @pytest.fixture
    def dependency_workflow(self) -> dict[str, Any]:
        """加载依赖镜像构建 workflow 配置"""
        workflow_path = Path(".gitea/workflows/build-dependency-image.yml")
        if not workflow_path.exists():
            pytest.skip("Dependency image workflow file not found")

        with open(workflow_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict)
        return data

    def test_schedule_trigger(self, dependency_workflow):
        """测试定时触发"""
        # 注意：on 在 YAML 1.1 中是布尔值，会被解析为 True
        on_config = dependency_workflow.get("on") or dependency_workflow.get(True) or {}
        assert "schedule" in on_config

        # 检查 cron 配置 (每周日 18 点)
        cron = on_config["schedule"][0]["cron"]
        assert cron == "0 10 * * 0"  # UTC 10:00 = 北京时间 18:00

    def test_path_trigger(self, dependency_workflow):
        """测试路径触发"""
        # 注意：on 在 YAML 1.1 中是布尔值，会被解析为 True
        on_config = dependency_workflow.get("on") or dependency_workflow.get(True) or {}
        assert "push" in on_config
        assert "paths" in on_config["push"]

        paths = on_config["push"]["paths"]
        assert "pyproject.toml" in paths
        assert "poetry.lock" in paths

    def test_cleanup_strategy(self, dependency_workflow):
        """测试清理策略"""
        jobs = dependency_workflow["jobs"]
        assert "build-dependency-image" in jobs

        steps = [s["name"] for s in jobs["build-dependency-image"]["steps"]]
        assert "清理旧版本镜像 (保留最近 5 个)" in steps


class TestKubernetesDeployment:
    """Kubernetes 部署配置测试"""

    @pytest.fixture
    def deployment_config(self) -> dict[str, Any]:
        """加载 Deployment 配置"""
        deploy_path = Path("deployments/k8s/deployment.yaml")
        if not deploy_path.exists():
            pytest.skip("Deployment config file not found")

        with open(deploy_path, encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))
        data = docs[0]  # 返回测试环境配置
        assert isinstance(data, dict)
        return data

    def test_deployment_name(self, deployment_config):
        """测试部署名称"""
        assert deployment_config["metadata"]["name"] == "sisys-app"

    def test_gpu_resources(self, deployment_config):
        """测试 GPU 资源配置"""
        container = deployment_config["spec"]["template"]["spec"]["containers"][0]
        resources = container["resources"]

        # 检查 GPU 请求
        assert "requests" in resources
        assert "nvidia.com/gpu" in resources["requests"]
        assert resources["requests"]["nvidia.com/gpu"] == "1"

        # 检查 GPU 限制
        assert "limits" in resources
        assert "nvidia.com/gpu" in resources["limits"]
        assert resources["limits"]["nvidia.com/gpu"] == "1"

    def test_health_probes(self, deployment_config):
        """测试健康检查探针"""
        container = deployment_config["spec"]["template"]["spec"]["containers"][0]

        assert "livenessProbe" in container
        assert "readinessProbe" in container
        assert "startupProbe" in container

    def test_node_affinity(self, deployment_config):
        """测试节点亲和性"""
        spec = deployment_config["spec"]["template"]["spec"]

        assert "affinity" in spec
        assert "nodeAffinity" in spec["affinity"]

        # 检查 GPU 节点标签
        terms = spec["affinity"]["nodeAffinity"]["requiredDuringSchedulingIgnoredDuringExecution"]["nodeSelectorTerms"]
        gpu_label_found = False
        for term in terms:
            for expr in term["matchExpressions"]:
                if expr["key"] == "nvidia.com/gpu.present" or expr["key"] == "node-type":
                    gpu_label_found = True
                    break

        assert gpu_label_found, "GPU node affinity not configured"

    def test_tolerations(self, deployment_config):
        """测试容忍度"""
        spec = deployment_config["spec"]["template"]["spec"]

        assert "tolerations" in spec
        tolerations = spec["tolerations"]

        # 检查 GPU 容忍度
        gpu_toleration_found = False
        for tol in tolerations:
            if tol.get("key") == "nvidia.com/gpu":
                gpu_toleration_found = True
                break

        assert gpu_toleration_found, "GPU toleration not configured"


class TestDockerfiles:
    """Dockerfile 配置测试"""

    def test_dependency_dockerfile_exists(self):
        """测试依赖 Dockerfile 存在"""
        dockerfile_path = Path("docker/dockerfile.l2")
        assert dockerfile_path.exists(), "Dependency Dockerfile not found"

    def test_app_dockerfile_exists(self):
        """测试应用 Dockerfile 存在"""
        dockerfile_path = Path("docker/dockerfile.app")
        assert dockerfile_path.exists(), "App Dockerfile not found"

    def test_dependency_dockerfile_base_image(self):
        """测试依赖 Dockerfile 基础镜像"""
        dockerfile_path = Path("docker/dockerfile.l2")

        with open(dockerfile_path, encoding="utf-8") as f:
            content = f.read()

        assert "FROM" in content
        assert "dependency:l1-" in content.lower()

    def test_dependency_dockerfile_poetry(self):
        """测试依赖 Dockerfile 安装 Poetry"""
        dockerfile_path = Path("docker/dockerfile.l2")

        with open(dockerfile_path, encoding="utf-8") as f:
            content = f.read()

        assert "poetry" in content.lower()

    def test_app_dockerfile_multistage(self):
        """测试应用 Dockerfile 多阶段构建"""
        dockerfile_path = Path("docker/dockerfile.app")

        with open(dockerfile_path, encoding="utf-8") as f:
            content = f.read()

        # 检查多阶段构建
        from_count = content.count("FROM ")
        assert from_count >= 2, "App Dockerfile should use multi-stage build"


class TestDocumentation:
    """文档完整性测试"""

    def test_ci_cd_guide_exists(self):
        """测试 CI/CD 使用指南存在"""
        guide_path = Path("docs/deployment/CI_CD_PIPELINE_TEMPLATE.md")
        assert guide_path.exists(), "CI/CD guide not found"

    def test_secrets_guide_exists(self):
        """测试 Secrets 配置指南存在"""
        guide_path = Path("docs/deployment/CI_CD_SECRETS_GUIDE.md")
        assert guide_path.exists(), "Secrets guide not found"

    def test_troubleshooting_guide_exists(self):
        """测试故障排除指南存在"""
        guide_path = Path("docs/deployment/CI_CD_TROUBLESHOOTING.md")
        assert guide_path.exists(), "Troubleshooting guide not found"


class TestScripts:
    """脚本完整性测试"""

    def test_entrypoint_script_exists(self):
        """测试入口脚本存在"""
        script_path = Path("scripts/entrypoint.sh")
        assert script_path.exists(), "entrypoint.sh not found"

    def test_scripts_executable(self):
        """测试脚本可执行权限"""
        scripts = [
            Path("scripts/entrypoint.sh"),
        ]

        for script in scripts:
            if script.exists():
                assert script.stat().st_mode & 0o111, f"{script} is not executable"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
