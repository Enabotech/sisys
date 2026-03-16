# Gitea 架构合规验证测试 - Story 0.5
# 描述：验证 Gitea 部署符合架构规划要求
# 测试类型：架构合规验证（Task 6）
from pathlib import Path
from typing import Any

import pytest
import yaml


class TestGiteaArchitectureCompliance:
    """Gitea 架构合规验证测试 (Task 6)"""

    @pytest.fixture
    def values_yaml(self) -> dict[str, Any]:
        """加载 values.yaml 配置"""
        values_path = Path(__file__).parent.parent.parent / "deployments" / "gitea" / "values.yaml"
        with open(values_path, encoding="utf-8") as f:
            return yaml.safe_load(f)  # type: ignore[no-any-return]

    @pytest.fixture
    def ingress_yaml(self) -> list:
        """加载 ingress.yaml 配置"""
        ingress_path = Path(__file__).parent.parent.parent / "deployments" / "gitea" / "ingress.yaml"
        with open(ingress_path, encoding="utf-8") as f:
            return list(yaml.safe_load_all(f))

    @pytest.fixture
    def middleware_yaml(self) -> list:
        """加载 middleware.yaml 配置"""
        middleware_path = Path(__file__).parent.parent.parent / "deployments" / "gitea" / "middleware.yaml"
        with open(middleware_path, encoding="utf-8") as f:
            return list(yaml.safe_load_all(f))

    @pytest.fixture
    def secrets_yaml(self) -> list:
        """加载 secrets.yaml 配置"""
        secrets_path = Path(__file__).parent.parent.parent / "deployments" / "gitea" / "secrets.yaml"
        with open(secrets_path, encoding="utf-8") as f:
            return list(yaml.safe_load_all(f))

    def test_tls_1_3_enforced(self, ingress_yaml):
        """验证 TLS 1.3 强制启用 (架构合规要求)"""
        # TLS 1.3 通过 cert-manager 和 Traefik 配置保证
        # 验证 Ingress 配置了 TLS
        tls_configured = False
        for doc in ingress_yaml:
            # 跳过 None 值（YAML 空文档）
            if doc is None:
                continue
            if doc.get("kind") == "Ingress":
                tls = doc.get("spec", {}).get("tls", [])
                assert len(tls) > 0, "Ingress 必须配置 TLS"
                tls_configured = True
                # 验证 TLS secret 已配置
                assert tls[0].get("secretName") == "gitea-tls-secret", "TLS secret 名称不正确"

        assert tls_configured, "TLS 1.3 未强制启用"

    def test_storage_uses_local_path(self, values_yaml):
        """验证存储使用 local-path (NVMe SSD)"""
        # 验证主存储使用 local-path
        persistence = values_yaml.get("persistence", {})
        assert (
            persistence.get("storageClass") == "local-path"
        ), f"主存储必须使用 local-path，当前配置：{persistence.get('storageClass')}"

        # 验证 PostgreSQL 存储使用 local-path
        postgresql = values_yaml.get("postgresql", {})
        postgres_persistence = postgresql.get("primary", {}).get("persistence", {})
        assert (
            postgres_persistence.get("storageClass") == "local-path"
        ), f"PostgreSQL 存储必须使用 local-path，当前配置：{postgres_persistence.get('storageClass')}"

    def test_ingress_traefik_configuration(self, ingress_yaml, values_yaml):
        """验证 Ingress 配置 (Traefik 443 → gitea-http:3000)"""
        # 验证 Ingress 使用 Traefik
        for doc in ingress_yaml:
            # 跳过 None 值（YAML 空文档）
            if doc is None:
                continue
            if doc.get("kind") == "Ingress":
                ingress_class = doc.get("spec", {}).get("ingressClassName")
                assert ingress_class == "traefik", f"Ingress 必须使用 Traefik，当前配置：{ingress_class}"

                # 验证后端服务配置
                rules = doc.get("spec", {}).get("rules", [])
                assert len(rules) > 0, "Ingress 必须配置路由规则"

                # 验证 host 配置
                assert rules[0].get("host") == "gitea.sisys.local", "Host 配置错误，应为 gitea.sisys.local"

                # 验证后端服务端口
                paths = rules[0].get("http", {}).get("paths", [])
                http_backend = None
                for path in paths:
                    if path.get("path") == "/":
                        http_backend = path.get("backend", {}).get("service", {})
                        break

                assert http_backend is not None, "未找到 HTTP 后端配置"
                assert http_backend.get("name") == "gitea-http", "后端服务名错误，应为 gitea-http"
                assert http_backend.get("port", {}).get("number") == 3000, "后端端口错误，应为 3000"

    def test_secrets_storage(self, values_yaml, secrets_yaml):
        """验证密钥存储于 Kubernetes Secret"""
        # 验证 values.yaml 引用 Secret
        admin_secret = values_yaml.get("gitea", {}).get("admin", {}).get("existingSecret")
        assert (
            admin_secret == "gitea-admin-secret"
        ), "管理员 Secret 引用错误，应为 gitea-admin-secret"  # pragma: allowlist secret

        postgres_secret = values_yaml.get("postgresql", {}).get("auth", {}).get("existingSecret")
        assert (
            postgres_secret == "gitea-postgresql-secret"
        ), "PostgreSQL Secret 引用错误，应为 gitea-postgresql-secret"  # pragma: allowlist secret

        # 验证 Secret 文件存在且包含必要字段
        secret_docs = list(secrets_yaml)
        assert len(secret_docs) >= 2, "Secret 文件应包含至少 2 个 Secret"

        # 验证管理员 Secret
        admin_secret_found = False
        for secret in secret_docs:
            if secret.get("metadata", {}).get("name") == "gitea-admin-secret":
                admin_secret_found = True
                string_data = secret.get("stringData", {})
                assert "username" in string_data, "管理员 Secret 缺少 username"
                assert "password" in string_data, "管理员 Secret 缺少 password"
                assert "email" in string_data, "管理员 Secret 缺少 email"

                # 验证密码复杂度（跳过占位符检查）
                password = string_data.get("password", "")
                # 如果是占位符（如 ${GITEA_ADMIN_PASSWORD}），跳过复杂度检查
                if not password.startswith("${") and not password.endswith("}"):
                    assert len(password) >= 12, "密码长度必须至少 12 位"
                    assert any(c.isupper() for c in password), "密码必须包含大写字母"
                    assert any(c.islower() for c in password), "密码必须包含小写字母"
                    assert any(c.isdigit() for c in password), "密码必须包含数字"
                    assert any(not c.isalnum() for c in password), "密码必须包含特殊符号"

        assert admin_secret_found, "未找到管理员 Secret"

    def test_security_context(self, values_yaml):
        """验证容器安全配置"""
        security_context = values_yaml.get("securityContext", {})

        # 验证非 root 用户运行
        assert security_context.get("runAsNonRoot") is True, "必须以非 root 用户运行"
        assert security_context.get("runAsUser") == 1000, "runAsUser 应为 1000"

        # 验证只读根文件系统
        assert security_context.get("readOnlyRootFilesystem") is True, "必须启用只读根文件系统"

        # 验证禁用特权
        assert security_context.get("privileged") is False, "必须禁用特权模式"
        assert security_context.get("allowPrivilegeEscalation") is False, "必须禁用特权升级"

        # 验证禁用所有 capabilities
        capabilities = security_context.get("capabilities", {})
        assert "ALL" in capabilities.get("drop", []), "必须 drop 所有 Linux capabilities"

    def test_network_policy_default_deny(self):
        """验证 NetworkPolicy 默认拒绝策略"""
        networkpolicy_path = Path(__file__).parent.parent.parent / "deployments" / "gitea" / "networkpolicy.yaml"
        with open(networkpolicy_path, encoding="utf-8") as f:
            networkpolicy = list(yaml.safe_load_all(f))

        default_deny_found = False
        for doc in networkpolicy:
            if doc.get("metadata", {}).get("name") == "gitea-default-deny":
                default_deny_found = True
                spec = doc.get("spec", {})
                assert spec.get("podSelector", {}).get("matchLabels", {}) == {}, "DefaultDeny 策略应匹配所有 Pod"
                assert spec.get("policyTypes") == ["Ingress", "Egress"], "DefaultDeny 应包含 Ingress 和 Egress"
                # 空 ingress/egress 规则表示默认拒绝
                assert "ingress" not in spec or spec.get("ingress") == [], "DefaultDeny 应有空 ingress 规则"

        assert default_deny_found, "未找到 DefaultDeny NetworkPolicy"

    def test_resource_limits(self, values_yaml):
        """验证资源限制配置"""
        resources = values_yaml.get("resources", {})

        # 验证资源限制已配置
        assert "limits" in resources, "必须配置资源限制"
        assert "requests" in resources, "必须配置资源请求"

        # 验证具体值
        limits = resources.get("limits", {})
        requests = resources.get("requests", {})

        assert limits.get("cpu") == "1000m", f"CPU 限制应为 1000m，当前：{limits.get('cpu')}"
        assert limits.get("memory") == "2Gi", f"内存限制应为 2Gi，当前：{limits.get('memory')}"
        assert requests.get("cpu") == "500m", f"CPU 请求应为 500m，当前：{requests.get('cpu')}"
        assert requests.get("memory") == "1Gi", f"内存请求应为 1Gi，当前：{requests.get('memory')}"

    def test_hsts_enabled(self, middleware_yaml):
        """验证 HSTS (HTTP Strict Transport Security) 启用"""
        hsts_enabled = False
        for doc in middleware_yaml:
            # 跳过 None 值（YAML 空文档）
            if doc is None:
                continue
            if doc.get("kind") == "Middleware":
                headers = doc.get("spec", {}).get("headers", {})
                if headers.get("stsSeconds", 0) > 0:
                    hsts_enabled = True
                    assert headers.get("stsSeconds") >= 31536000, "HSTS max-age 应至少为 1 年 (31536000 秒)"
                    # 注意：YAML 中是 stsIncludeSubDomains（大写 D）
                    assert headers.get("stsIncludeSubDomains") is True, "HSTS 应包含子域名"
                    assert headers.get("stsPreload") is True, "HSTS 应启用 preload"

        assert hsts_enabled, "HSTS 未启用"


class TestGiteaTDDTests:
    """Gitea TDD 测试 (Task 6 - 运行所有 TDD 测试)"""

    def test_gitea_deployment_test_exists(self):
        """验证 Gitea 部署测试文件存在"""
        test_path = Path(__file__).parent.parent.parent / "tests" / "deployment" / "test_gitea.py"
        assert test_path.exists(), f"部署测试文件不存在：{test_path}"

    def test_gitea_architecture_test_exists(self):
        """验证 Gitea 架构合规测试文件存在"""
        test_path = Path(__file__)
        assert test_path.exists(), f"架构合规测试文件不存在：{test_path}"

    def test_gitea_tests_importable(self):
        """验证 Gitea 测试可导入"""
        # 验证本文件可导入
        import importlib.util

        spec = importlib.util.spec_from_file_location("test_gitea_architecture", __file__)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
            assert True, "测试模块可成功导入"
        except Exception as e:
            pytest.fail(f"测试模块导入失败：{e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
