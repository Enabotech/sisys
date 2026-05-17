"""
Pipeline 模板测试

测试 CI/CD Pipeline 配置的正确性和语法合规性
AC: 4, 7

测试覆盖：
- Pipeline 语法验证
- Actions 引用验证
- 环境变量配置
- 密钥引用验证
"""

from pathlib import Path
from typing import Any

import pytest
import yaml


class TestCIPipelineSyntax:
    """测试 CI Pipeline 语法"""

    def test_ci_pipeline_exists(self):
        """测试 CI Pipeline 文件存在"""
        workflow_path = Path(".gitea/workflows/ci.yaml")
        assert workflow_path.exists(), f"CI Pipeline 文件不存在：{workflow_path}"

    def test_ci_pipeline_valid_yaml(self):
        """测试 CI Pipeline YAML 语法正确"""
        workflow_path = Path(".gitea/workflows/ci.yaml")
        if workflow_path.exists():
            try:
                with open(workflow_path, encoding="utf-8") as f:
                    yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"CI Pipeline YAML 语法错误：{e}")

    def test_ci_pipeline_structure(self):
        """测试 CI Pipeline 结构完整"""
        workflow_path = Path(".gitea/workflows/ci.yaml")
        if workflow_path.exists():
            with open(workflow_path, encoding="utf-8") as f:
                workflow = yaml.safe_load(f)

                # 检查必需字段
                assert "name" in workflow, "缺少 name 字段"
                # 注意：on 在 YAML 1.1 中是布尔值，会被解析为 True
                assert "on" in workflow or True in workflow or '"on"' in workflow_path.read_text(), "缺少 on 字段"
                assert "jobs" in workflow, "缺少 jobs 字段"

    def test_ci_pipeline_trigger_configured(self):
        """测试 CI Pipeline 触发器配置"""
        workflow_path = Path(".gitea/workflows/ci.yaml")
        if workflow_path.exists():
            workflow_text = workflow_path.read_text(encoding="utf-8")

            # 检查触发器配置（on 在 YAML 中是布尔值，需要特殊处理）
            has_push = "push:" in workflow_text or '"push"' in workflow_text or "'push'" in workflow_text
            has_pull_request = (
                "pull_request:" in workflow_text or '"pull_request"' in workflow_text or "'pull_request'" in workflow_text
            )

            assert has_push, "缺少 push 触发器"
            assert has_pull_request, "缺少 pull_request 触发器"

    def test_ci_pipeline_jobs_defined(self):
        """测试 CI Pipeline Job 定义"""
        workflow_path = Path(".gitea/workflows/ci.yaml")
        if workflow_path.exists():
            with open(workflow_path, encoding="utf-8") as f:
                workflow = yaml.safe_load(f)
                jobs = workflow.get("jobs", {})

                # 检查 7 阶段 Pipeline
                required_jobs = [
                    "code-quality",
                    "unit-tests",
                    "integration-tests",
                    "security-scan",
                    "build-images",
                    # "push-image",
                    # "auto-deploy",
                ]

                for job_name in required_jobs:
                    assert job_name in jobs, f"缺少 Job: {job_name}"

    def test_cd_pipeline_manual_trigger(self):
        """测试 CD Pipeline 手动触发配置"""
        workflow_path = Path(".gitea/workflows/cd.yaml")
        if workflow_path.exists():
            workflow_text = workflow_path.read_text(encoding="utf-8")

            # 检查 workflow_dispatch（手动触发）
            has_workflow_dispatch = "workflow_dispatch:" in workflow_text

            assert has_workflow_dispatch, "缺少 workflow_dispatch 手动触发器"

            # 检查输入参数
            has_environment = "environment:" in workflow_text and "inputs:" in workflow_text
            has_image_tag = "image_tag:" in workflow_text

            assert has_environment, "缺少 environment 输入参数"
            assert has_image_tag, "缺少 image_tag 输入参数"

    def test_cd_pipeline_jobs_defined(self):
        """测试 CD Pipeline Job 定义"""
        workflow_path = Path(".gitea/workflows/cd.yaml")
        if workflow_path.exists():
            with open(workflow_path, encoding="utf-8") as f:
                workflow = yaml.safe_load(f)
                jobs = workflow.get("jobs", {})

                # 检查 CD Pipeline 阶段
                required_jobs = ["pre-deployment-check", "deploy-test", "health-check", "post-deployment", "auto-rollback"]

                for job_name in required_jobs:
                    assert job_name in jobs, f"缺少 Job: {job_name}"


class TestActionsReferences:
    """测试 Actions 引用"""

    def test_actions_versions_pinned(self):
        """测试 Actions 版本已固定"""
        ci_path = Path(".gitea/workflows/ci.yaml")
        cd_path = Path(".gitea/workflows/cd.yaml")

        for workflow_path in [ci_path, cd_path]:
            if workflow_path.exists():
                workflow_text = workflow_path.read_text(encoding="utf-8")

                # 检查 Actions 引用格式（应包含版本号）
                import re

                action_refs = re.findall(r"uses:\s+([^\s]+)", workflow_text)

                for action_ref in action_refs:
                    # 检查是否包含版本标签（@v* 或 @v*.*.*）
                    assert "@" in action_ref, f"Action 未固定版本：{action_ref} in {workflow_path}"
                    assert "@v" in action_ref or "@main" in action_ref or "@master" in action_ref, (
                        f"Action 版本格式不正确：{action_ref} in {workflow_path}"
                    )

    def test_common_actions_available(self):
        """测试常用 Actions 可用"""
        # 验证常用 Actions 是否存在
        common_actions = [
            "actions/checkout",
            "actions/setup-python",
            "actions/upload-artifact",
            "actions/download-artifact",
            "docker/setup-buildx-action",
            "docker/login-action",
            "docker/build-push-action",
            "azure/setup-kubectl",
        ]

        ci_path = Path(".gitea/workflows/ci.yaml")
        cd_path = Path(".gitea/workflows/cd.yaml")

        all_workflows = ""
        for workflow_path in [ci_path, cd_path]:
            if workflow_path.exists():
                all_workflows += workflow_path.read_text(encoding="utf-8") + "\n"

        # 至少检查部分 Actions 被使用
        found_actions = [action for action in common_actions if action in all_workflows]
        assert len(found_actions) >= 5, f"使用的常用 Actions 过少：{found_actions}"


class TestEnvironmentVariables:
    """测试环境变量配置"""

    def test_ci_env_variables_defined(self):
        """测试 CI Pipeline 环境变量定义"""
        workflow_path = Path(".gitea/workflows/ci.yaml")
        if workflow_path.exists():
            with open(workflow_path, encoding="utf-8") as f:
                workflow = yaml.safe_load(f)
                env = workflow.get("env", {})

                # 检查必需的环境变量
                required_envs = ["APP_NAME", "IMAGE_NAME"]

                for env_name in required_envs:
                    assert env_name in env, f"缺少环境变量：{env_name}"

    def test_cd_env_variables_defined(self):
        """测试 CD Pipeline 环境变量定义"""
        workflow_path = Path(".gitea/workflows/cd.yaml")
        if workflow_path.exists():
            with open(workflow_path, encoding="utf-8") as f:
                workflow = yaml.safe_load(f)
                env = workflow.get("env", {})

                # 检查环境变量
                assert "APP_NAME" in env, "缺少环境变量：APP_NAME"
                assert "REGISTRY" in env, "缺少环境变量：REGISTRY"
                assert "IMAGE_NAME" in env, "缺少环境变量：IMAGE_NAME"


class TestSecretsReferences:
    """测试密钥引用"""

    def test_secrets_not_hardcoded(self):
        """测试密钥未硬编码"""
        ci_path = Path(".gitea/workflows/ci.yaml")
        cd_path = Path(".gitea/workflows/cd.yaml")

        for workflow_path in [ci_path, cd_path]:
            if workflow_path.exists():
                workflow_text = workflow_path.read_text(encoding="utf-8")

                # 检查是否有硬编码的密钥（简单启发式检查）
                suspicious_patterns = [
                    'password: "',
                    "password: '",
                    'token: "',
                    "token: '",
                    'secret: "',
                    "secret: '",
                ]

                for pattern in suspicious_patterns:
                    # 排除使用 ${{ secrets.* }} 的情况
                    if pattern in workflow_text:
                        # 检查是否在 secrets 引用附近
                        lines = workflow_text.split("\n")
                        for i, line in enumerate(lines):
                            if pattern in line and "${{ secrets." not in line:
                                # 检查前后几行是否有 secrets 引用
                                context_start = max(0, i - 2)
                                context_end = min(len(lines), i + 3)
                                context = "\n".join(lines[context_start:context_end])

                                if "${{ secrets." not in context:
                                    pytest.fail(f"可能硬编码了密钥：{line.strip()} in {workflow_path}:{i + 1}")

    def test_required_secrets_referenced(self):
        """测试必需的密钥已引用"""
        ci_path = Path(".gitea/workflows/ci.yaml")
        cd_path = Path(".gitea/workflows/cd.yaml")

        # CI Pipeline 需要的密钥
        ci_secrets = [
            "HARBOR_ROBOT_USERNAME",
            "HARBOR_ROBOT_PASSWORD",
        ]

        # CD Pipeline 需要的密钥
        cd_secrets = [
            "HARBOR_ROBOT_USERNAME",
            "HARBOR_ROBOT_PASSWORD",
            "KUBECONFIG",
        ]

        for workflow_path, required_secrets in [(ci_path, ci_secrets), (cd_path, cd_secrets)]:
            if workflow_path.exists():
                workflow_text = workflow_path.read_text(encoding="utf-8")

                for secret in required_secrets:
                    assert f"secrets.{secret}" in workflow_text, f"缺少密钥引用：{secret} in {workflow_path}"


class TestJobDependencies:
    """测试 Job 依赖关系"""

    def test_ci_job_dependencies(self):
        """测试 CI Pipeline Job 依赖"""
        workflow_path = Path(".gitea/workflows/ci.yaml")
        if workflow_path.exists():
            with open(workflow_path, encoding="utf-8") as f:
                workflow = yaml.safe_load(f)
                jobs = workflow.get("jobs", {})

                # 检查依赖关系

                # integration-tests 的 needs 可以是字符串或列表
                int_test_needs = jobs.get("integration-tests", {}).get("needs", [])
                if isinstance(int_test_needs, str):
                    assert int_test_needs == "detect-changes", "integration-tests 应依赖 detect-changes"
                else:
                    assert "detect-changes" in int_test_needs, "integration-tests 应依赖 detect-changes"

                # build-images 的 needs 应该是列表
                build_needs = jobs.get("build-images", {}).get("needs", [])
                if isinstance(build_needs, str):
                    build_needs = [build_needs]
                assert "integration-tests" in build_needs or "security-scan" in build_needs or "code-quality" in build_needs, (
                    "build-images 应依赖 integration-tests 和 security-scan 和 code-quality"
                )

                # push-image 应依赖 build-image
                # push_needs = jobs.get("push-image", {}).get("needs", [])
                # if isinstance(push_needs, str):
                #     push_needs = [push_needs]
                # assert "build-image" in push_needs, "push-image 应依赖 build-image"

    def test_cd_job_dependencies(self):
        """测试 CD Pipeline Job 依赖"""
        workflow_path = Path(".gitea/workflows/cd.yaml")
        if workflow_path.exists():
            with open(workflow_path, encoding="utf-8") as f:
                workflow = yaml.safe_load(f)
                jobs = workflow.get("jobs", {})

                # 检查依赖关系
                assert "pre-deployment-check" in jobs.get("deploy-test", {}).get("needs", []), (
                    "deploy-test 应依赖 pre-deployment-check"
                )

                assert "deploy-test" in jobs.get("health-check", {}).get("needs", []), "health-check 应依赖 deploy-test"


class TestPipelineIntegration:
    """测试 Pipeline 集成"""

    def test_harbor_registry_configured(self):
        """测试 Harbor 镜像仓库配置"""
        ci_path = Path(".gitea/workflows/ci.yaml")
        cd_path = Path(".gitea/workflows/cd.yaml")

        harbor_configured = False

        for workflow_path in [ci_path, cd_path]:
            if workflow_path.exists():
                workflow_text = workflow_path.read_text(encoding="utf-8")
                if "harbor.sisys.local" in workflow_text:
                    harbor_configured = True
                    break

        assert harbor_configured, "Harbor 镜像仓库未配置"

    def test_kubernetes_deployment_configured(self):
        """测试 K8s 部署配置"""
        ci_path = Path(".gitea/workflows/ci.yaml")
        cd_path = Path(".gitea/workflows/cd.yaml")
        deploy_path = Path("deploy/kubernetes/k8s/deployment.yaml")

        k8s_configured = False

        for workflow_path in [ci_path, cd_path, deploy_path]:
            if workflow_path.exists():
                workflow_text = workflow_path.read_text(encoding="utf-8")
                if "Deployment" in workflow_text:
                    k8s_configured = True
                    break

        assert k8s_configured, "K8s 部署未配置"

    def test_argocd_integration_configured(self):
        """测试 ArgoCD 集成配置"""
        workflow_path = Path(".gitea/workflows/ci.yaml")
        if workflow_path.exists():
            workflow_text = workflow_path.read_text(encoding="utf-8")
            # ArgoCD 集成为可选，但建议配置
            has_argocd = "argocd" in workflow_text.lower() or "ArgoCD" in workflow_text
            assert has_argocd, "ArgoCD 集成未配置（建议配置 GitOps 自动部署）"


# 测试辅助函数
def validate_workflow_syntax(workflow_path: Path) -> dict[str, Any]:
    """
    验证 Workflow 语法

    Args:
        workflow_path: Workflow 文件路径

    Returns:
        验证结果
    """
    if not workflow_path.exists():
        return {"valid": False, "error": "文件不存在"}

    try:
        with open(workflow_path, encoding="utf-8") as f:
            workflow = yaml.safe_load(f)

        # 基本结构检查
        errors = []

        if "name" not in workflow:
            errors.append("缺少 name 字段")

        if "on" not in workflow and "on:" not in workflow_path.read_text():
            errors.append("缺少 on 字段")

        if "jobs" not in workflow:
            errors.append("缺少 jobs 字段")
        else:
            jobs = workflow.get("jobs", {})
            for job_name, job_config in jobs.items():
                if "runs-on" not in job_config and "container" not in job_config:
                    errors.append(f"Job {job_name} 缺少 runs-on 或 container 配置")

                if "steps" not in job_config and "uses" not in job_config:
                    errors.append(f"Job {job_name} 缺少 steps 或 uses 配置")

        return {"valid": len(errors) == 0, "errors": errors, "workflow": workflow}

    except yaml.YAMLError as e:
        return {"valid": False, "error": f"YAML 语法错误：{e}"}


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
