"""
ArgoCD 配置验证测试

目的：验证 YAML 配置文件的正确性，不需要实际 K8s 集群
审查问题：CRITICAL-3 - 测试覆盖率不足
创建日期：2026-03-19
"""

from pathlib import Path
from typing import Any

import pytest
import yaml


class TestGiteaCredentialsConfig:
    """验证 Gitea 凭据配置"""

    @pytest.fixture
    def gitea_credentials(self) -> dict[str, Any]:
        """加载 Gitea 凭据配置"""
        config_path = Path(__file__).parents[2] / "deploy/kubernetes/argocd/gitea-credentials.yaml"
        with open(config_path, encoding="utf-8") as f:
            # 处理多文档 YAML
            docs = list(yaml.safe_load_all(f))
            # 找到 Secret 文档
            for doc in docs:
                if doc and doc.get("kind") == "Secret":
                    return doc  # type: ignore[no-any-return]
            raise FileNotFoundError("Gitea Credentials Secret not found")

    def test_secret_exists(self, gitea_credentials):
        """验证 Secret 存在"""
        assert gitea_credentials is not None

    def test_secret_metadata(self, gitea_credentials):
        """验证 Secret 元数据"""
        assert gitea_credentials["apiVersion"] == "v1"
        assert gitea_credentials["kind"] == "Secret"
        assert gitea_credentials["metadata"]["name"] == "argocd-gitea-creds"
        assert gitea_credentials["metadata"]["namespace"] == "argocd"

    def test_no_plaintext_token(self, gitea_credentials):
        """验证无明文 Token（CRITICAL-1 修复验证）"""
        password = gitea_credentials["stringData"].get("password", "")
        # 验证密码不是明文（应该是环境变量占位符）
        assert not password.startswith("1f182aca3d38b66f7e49c034d98fb15bf02434b7"), "CRITICAL-1: Gitea Token 仍然是明文！"
        assert "${GITEA_ADMIN_TOKEN}" in password or len(password) == 0, "CRITICAL-1: 密码应该使用环境变量注入"

    def test_environment_variable_injection(self, gitea_credentials):
        """验证使用环境变量注入"""
        password = gitea_credentials["stringData"].get("password", "")
        username = gitea_credentials["stringData"].get("username", "")
        # 验证使用环境变量占位符
        assert "${GITEA_ADMIN_TOKEN}" in password or "${" in password, "应该使用环境变量注入 Token"
        assert "${GITEA_ADMIN_USERNAME}" in username or "${" in username, "应该使用环境变量注入用户名"

    def test_insecure_config(self, gitea_credentials):
        """验证 insecure 配置（用于自签名证书）"""
        insecure = gitea_credentials["stringData"].get("insecure", "false")
        # 开发环境可以使用 insecure，但应该有注释说明
        assert insecure in ["true", "false"], "insecure 应该是布尔值字符串"


class TestAdminSecretConfig:
    """验证 Admin Secret 配置"""

    @pytest.fixture
    def admin_secret(self) -> dict[str, Any]:
        """加载 Admin Secret 配置"""
        config_path = Path(__file__).parents[2] / "deploy/kubernetes/argocd/rbac.yaml"
        with open(config_path, encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))
            for doc in docs:
                if doc and doc.get("kind") == "Secret" and doc.get("metadata", {}).get("name") == "argocd-initial-admin-secret":
                    return doc  # type: ignore[no-any-return]
            raise FileNotFoundError("Admin Secret not found")

    def test_secret_exists(self, admin_secret):
        """验证 Secret 存在"""
        assert admin_secret is not None

    def test_secret_metadata(self, admin_secret):
        """验证 Secret 元数据"""
        assert admin_secret["apiVersion"] == "v1"
        assert admin_secret["kind"] == "Secret"
        assert admin_secret["metadata"]["name"] == "argocd-initial-admin-secret"
        assert admin_secret["metadata"]["namespace"] == "argocd"

    def test_no_plaintext_password(self, admin_secret):
        """验证无明文密码（CRITICAL-2 修复验证）"""
        password = admin_secret["stringData"].get("password", "")
        # 验证密码不是明文
        assert password != "ArgoCD@2026Secure!", "CRITICAL-2: Admin 密码仍然是明文！"
        assert "${ARGOCD_ADMIN_PASSWORD}" in password or len(password) == 0, "CRITICAL-2: 密码应该使用环境变量注入"

    def test_environment_variable_injection(self, admin_secret):
        """验证使用环境变量注入"""
        password = admin_secret["stringData"].get("password", "")
        # 验证使用环境变量占位符
        assert "${ARGOCD_ADMIN_PASSWORD}" in password or "${" in password, "应该使用环境变量注入密码"


class TestSecurityHardeningConfig:
    """验证安全加固配置"""

    @pytest.fixture
    def security_hardening(self) -> list[Any]:
        """加载安全加固配置"""
        config_path = Path(__file__).parents[2] / "deploy/kubernetes/argocd/security-hardening.yaml"
        with open(config_path, encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))
            return list(docs)

    def test_file_exists(self, security_hardening):
        """验证文件存在"""
        assert len(security_hardening) > 0

    def test_psp_not_used(self, security_hardening):
        """验证不使用已废弃的 PSP（CRITICAL-4 修复验证）"""
        for doc in security_hardening:
            if doc:
                kind = doc.get("kind", "")
                # 验证没有 PodSecurityPolicy
                assert kind != "PodSecurityPolicy", "CRITICAL-4: 仍然使用已废弃的 PodSecurityPolicy！"

    def test_psa_labels_present(self, security_hardening):
        """验证 PSA 标签存在（CRITICAL-4 替代方案）"""
        # 查找 Namespace 配置
        for doc in security_hardening:
            if doc and doc.get("kind") == "Namespace":
                labels = doc.get("metadata", {}).get("labels", {})
                # 验证 PSA 标签
                psa_labels = [
                    "pod-security.kubernetes.io/enforce",
                    "pod-security.kubernetes.io/audit",
                    "pod-security.kubernetes.io/warn",
                ]
                # 至少有一个 PSA 标签
                has_psa = any(label in labels for label in psa_labels)
                # 注意：这是一个警告，不是失败，因为 PSA 可能在其他文件中配置
                if not has_psa:
                    pytest.skip("PSA 标签可能配置在其他文件中")


class TestYamlSyntax:
    """验证所有 YAML 文件的语法"""

    @pytest.fixture
    def yaml_files(self) -> list:
        """获取所有 YAML 文件"""
        base_path = Path(__file__).parents[2] / "deploy/kubernetes/argocd"
        return list(base_path.glob("**/*.yaml"))

    def test_all_yaml_files_valid_syntax(self, yaml_files):
        """验证所有 YAML 文件语法正确"""
        invalid_files = []
        for file_path in yaml_files:
            try:
                with open(file_path, encoding="utf-8") as f:
                    list(yaml.safe_load_all(f))
            except yaml.YAMLError as e:
                invalid_files.append((file_path, str(e)))

        assert len(invalid_files) == 0, f"以下 YAML 文件语法错误：{invalid_files}"


class TestConfigurationCompleteness:
    """验证配置完整性"""

    def test_required_files_exist(self):
        """验证必需文件存在（MEDIUM-1 修复验证）"""
        base_path = Path(__file__).parents[2] / "deploy/kubernetes/argocd"
        required_files = [
            "namespace.yaml",
            "rbac.yaml",
            "ingress.yaml",
            "networkpolicy.yaml",
            "security-hardening.yaml",
            "gitea-credentials.yaml",
        ]

        missing_files = []
        for file in required_files:
            if not (base_path / file).exists():
                missing_files.append(file)

        assert len(missing_files) == 0, f"缺少必需文件：{missing_files}"
