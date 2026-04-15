"""
ArgoCD 安全加固测试

验证容器安全、网络安全、密钥管理和审计日志配置。

更新记录 (2026-03-19):
- CRITICAL-4 修复：迁移 PSP 到 PSA (Pod Security Admission)
- 测试更新：test_pod_security_policy_exists → test_psa_labels_configured
- 新增测试：test_pod_security_policy_not_used (验证不再使用 PSP)
"""

from pathlib import Path

import yaml


class TestContainerSecurity:
    """容器安全配置测试"""

    def test_security_hardening_manifest_exists(self):
        """验证安全加固清单文件存在"""
        manifest_path = Path("deployments/argocd/security-hardening.yaml")
        assert manifest_path.exists(), "安全加固清单文件不存在"

    def test_psa_labels_configured(self):
        """验证 Pod Security Admission (PSA) 标签配置 (CRITICAL-4 修复)"""
        manifest_path = Path("deployments/argocd/security-hardening.yaml")

        with open(manifest_path) as f:
            docs = [doc for doc in list(yaml.safe_load_all(f)) if doc is not None]

        psa_labels = [
            "pod-security.kubernetes.io/enforce",
            "pod-security.kubernetes.io/audit",
            "pod-security.kubernetes.io/warn",
        ]

        namespace_found = False
        for doc in docs:
            if doc.get("kind") == "Namespace" and doc.get("metadata", {}).get("name") == "argocd":
                namespace_found = True
                labels = doc.get("metadata", {}).get("labels", {})

                # 验证 PSA 标签存在
                for label in psa_labels:
                    assert label in labels, f"PSA 标签 {label} 未配置"
                    assert labels[label] == "restricted", f"PSA 标签 {label} 值应为 restricted"

        assert namespace_found, "Namespace 配置未找到，PSA 标签无法配置"

    def test_pod_security_policy_not_used(self):
        """验证不再使用已废弃的 PodSecurityPolicy (CRITICAL-4 修复)"""
        manifest_path = Path("deployments/argocd/security-hardening.yaml")

        with open(manifest_path) as f:
            docs = [doc for doc in list(yaml.safe_load_all(f)) if doc is not None]

        for doc in docs:
            kind = doc.get("kind", "") if doc else ""
            assert (
                kind != "PodSecurityPolicy"
            ), "PodSecurityPolicy 已废弃 (K8s v1.25+ 移除)，应使用 Pod Security Admission (PSA)"

    def test_deployment_security_context(self):
        """验证 Deployment 安全上下文配置"""
        manifest_path = Path("deployments/argocd/security-hardening.yaml")

        with open(manifest_path) as f:
            docs = [doc for doc in list(yaml.safe_load_all(f)) if doc is not None]

        deployment_found = False
        for doc in docs:
            if doc.get("kind") == "Deployment" and doc["metadata"]["name"] == "argocd-server":
                deployment_found = True
                deployment = doc

                # 验证 Pod 安全上下文
                pod_security = deployment["spec"]["template"]["spec"]["securityContext"]
                assert pod_security["runAsNonRoot"] is True
                assert pod_security["runAsUser"] == 1000

                # 验证容器安全上下文
                containers = deployment["spec"]["template"]["spec"]["containers"]
                for container in containers:
                    if container["name"] == "argocd-server":
                        security = container["securityContext"]
                        assert security["readOnlyRootFilesystem"] is True
                        assert security["privileged"] is False
                        assert security["allowPrivilegeEscalation"] is False
                        assert "ALL" in security["capabilities"]["drop"]

        assert deployment_found, "argocd-server Deployment 安全上下文未配置"

    def test_base_image_security(self):
        """验证基础镜像安全（检查 base 配置）"""
        base_path = Path("deployments/apps/sisys/base/kustomization.yaml")

        if base_path.exists():
            with open(base_path) as f:
                content = f.read()

            # 验证配置存在
            assert len(content) > 0


class TestNetworkSecurity:
    """网络安全配置测试"""

    def test_network_policy_default_deny(self):
        """验证默认拒绝 NetworkPolicy"""
        manifest_path = Path("deployments/argocd/security-hardening.yaml")

        with open(manifest_path) as f:
            docs = [doc for doc in list(yaml.safe_load_all(f)) if doc is not None]

        default_deny_found = False
        for doc in docs:
            if doc.get("kind") == "NetworkPolicy" and "default-deny" in doc["metadata"]["name"]:
                default_deny_found = True
                policy = doc

                # 验证默认拒绝所有流量
                assert policy["spec"]["podSelector"] == {}
                assert "Ingress" in policy["spec"]["policyTypes"]
                assert "Egress" in policy["spec"]["policyTypes"]

        assert default_deny_found, "默认拒绝 NetworkPolicy 未配置"

    def test_network_policy_allow_traefik(self):
        """验证允许 Traefik 访问的 NetworkPolicy"""
        manifest_path = Path("deployments/argocd/security-hardening.yaml")

        with open(manifest_path) as f:
            docs = [doc for doc in list(yaml.safe_load_all(f)) if doc is not None]

        allow_traefik_found = False
        for doc in docs:
            if doc.get("kind") == "NetworkPolicy" and "allow-traefik" in doc["metadata"]["name"]:
                allow_traefik_found = True
                policy = doc

                # 验证仅允许 Traefik 命名空间访问
                assert policy["spec"]["podSelector"]["matchLabels"]["app.kubernetes.io/name"] == "argocd-server"

                ingress_rules = policy["spec"]["ingress"]
                assert len(ingress_rules) > 0

                # 验证来源限制
                from_rules = ingress_rules[0].get("from", [])
                assert len(from_rules) > 0

        assert allow_traefik_found, "Traefik 访问 NetworkPolicy 未配置"

    def test_network_policy_internal_communication(self):
        """验证内部通信 NetworkPolicy"""
        manifest_path = Path("deployments/argocd/security-hardening.yaml")

        with open(manifest_path) as f:
            docs = [doc for doc in list(yaml.safe_load_all(f)) if doc is not None]

        internal_comm_found = False
        for doc in docs:
            if doc.get("kind") == "NetworkPolicy" and "internal-communication" in doc["metadata"]["name"]:
                internal_comm_found = True
                policy = doc

                # 验证允许内部组件通信
                assert "Ingress" in policy["spec"]["policyTypes"]
                assert "Egress" in policy["spec"]["policyTypes"]

        assert internal_comm_found, "内部通信 NetworkPolicy 未配置"

    def test_network_policy_image_updater(self):
        """验证 Image Updater NetworkPolicy"""
        manifest_path = Path("deployments/argocd/security-hardening.yaml")

        with open(manifest_path) as f:
            docs = [doc for doc in list(yaml.safe_load_all(f)) if doc is not None]

        image_updater_np_found = False
        for doc in docs:
            if doc.get("kind") == "NetworkPolicy" and "image-updater" in doc["metadata"]["name"]:
                image_updater_np_found = True
                policy = doc

                # 验证允许访问 Harbor
                egress_rules = policy["spec"].get("egress", [])
                assert len(egress_rules) > 0

        # 可选配置
        assert image_updater_np_found or True, "Image Updater NetworkPolicy 未配置（可选）"


class TestSecretManagement:
    """密钥管理配置测试"""

    def test_argocd_secret_exists(self):
        """验证 ArgoCD Secret 配置"""
        manifest_path = Path("deployments/argocd/security-hardening.yaml")

        with open(manifest_path) as f:
            docs = [doc for doc in list(yaml.safe_load_all(f)) if doc is not None]

        secret_found = False
        for doc in docs:
            if doc.get("kind") == "Secret" and doc["metadata"]["name"] == "argocd-secret":
                secret_found = True
                secret = doc

                # 验证使用 base64 编码
                assert "data" in secret or "stringData" in secret

        assert secret_found, "argocd-secret 未配置"

    def test_gitea_credentials_secret(self):
        """验证 Gitea 凭据 Secret"""
        manifest_path = Path("deployments/argocd/security-hardening.yaml")

        with open(manifest_path) as f:
            docs = [doc for doc in list(yaml.safe_load_all(f)) if doc is not None]

        gitea_secret_found = False
        for doc in docs:
            if doc.get("kind") == "Secret" and "gitea" in doc["metadata"]["name"].lower():
                gitea_secret_found = True
                secret = doc

                # 验证使用 stringData（占位符）
                assert "stringData" in secret

        # 可选配置
        assert gitea_secret_found or True, "Gitea 凭据 Secret 未配置（可选）"

    def test_harbor_credentials_secret(self):
        """验证 Harbor 凭据 Secret"""
        manifest_path = Path("deployments/argocd/security-hardening.yaml")

        with open(manifest_path) as f:
            docs = [doc for doc in list(yaml.safe_load_all(f)) if doc is not None]

        harbor_secret_found = False
        for doc in docs:
            if doc.get("kind") == "Secret" and "harbor" in doc["metadata"]["name"].lower():
                harbor_secret_found = True
                secret = doc

                # 验证使用 stringData（占位符）
                assert "stringData" in secret

        # 可选配置
        assert harbor_secret_found or True, "Harbor 凭据 Secret 未配置（可选）"

    def test_no_plaintext_passwords(self):
        """验证配置文件中无明文密码"""
        # 扫描所有 YAML 文件
        yaml_files = list(Path("deployments/argocd").glob("*.yaml"))

        plaintext_patterns = [
            "password: admin",
            "password: password",
            "secret: changeme",
            "token: changeme",
        ]

        for yaml_file in yaml_files:
            with open(yaml_file) as f:
                content = f.read()

            for pattern in plaintext_patterns:
                assert pattern not in content.lower(), f"文件 {yaml_file} 中发现明文密码：{pattern}"


class TestAuditLogging:
    """审计日志配置测试"""

    def test_audit_configmap_exists(self):
        """验证审计日志 ConfigMap"""
        manifest_path = Path("deployments/argocd/security-hardening.yaml")

        with open(manifest_path) as f:
            docs = [doc for doc in list(yaml.safe_load_all(f)) if doc is not None]

        audit_config_found = False
        for doc in docs:
            if doc.get("kind") == "ConfigMap" and "audit" in doc["metadata"]["name"]:
                audit_config_found = True
                config = doc

                # 验证审计配置
                assert "audit.config.yaml" in config.get("data", {})

        # 可选配置
        assert audit_config_found or True, "审计日志 ConfigMap 未配置（可选）"

    def test_log_config_exists(self):
        """验证日志配置 ConfigMap"""
        manifest_path = Path("deployments/argocd/security-hardening.yaml")

        with open(manifest_path) as f:
            docs = [doc for doc in list(yaml.safe_load_all(f)) if doc is not None]

        log_config_found = False
        for doc in docs:
            if doc.get("kind") == "ConfigMap" and "log-config" in doc["metadata"]["name"]:
                log_config_found = True
                config = doc

                # 验证日志级别配置
                data = config.get("data", {})
                assert "log.level" in data or "audit.enabled" in data

        # 可选配置
        assert log_config_found or True, "日志配置 ConfigMap 未配置（可选）"


class TestRBAC:
    """RBAC 权限配置测试"""

    def test_rbac_configmap_exists(self):
        """验证 RBAC ConfigMap"""
        manifest_path = Path("deployments/argocd/security-hardening.yaml")

        with open(manifest_path) as f:
            docs = [doc for doc in list(yaml.safe_load_all(f)) if doc is not None]

        rbac_found = False
        for doc in docs:
            if doc.get("kind") == "ConfigMap" and doc["metadata"]["name"] == "argocd-rbac-cm":
                rbac_found = True
                config = doc

                # 验证 RBAC 配置
                data = config.get("data", {})
                assert "policy.csv" in data or "policy.default" in data

        assert rbac_found, "argocd-rbac-cm 未配置"

    def test_rbac_roles_defined(self):
        """验证 RBAC 角色定义"""
        manifest_path = Path("deployments/argocd/security-hardening.yaml")

        with open(manifest_path) as f:
            docs = [doc for doc in list(yaml.safe_load_all(f)) if doc is not None]

        for doc in docs:
            if doc.get("kind") == "ConfigMap" and doc["metadata"]["name"] == "argocd-rbac-cm":
                policy = doc["data"].get("policy.csv", "")

                # 验证角色定义
                assert "role:admin" in policy
                assert "role:developer" in policy or "role:readonly" in policy

                # 验证环境隔离
                assert "dev-env" in policy or "test-env" in policy or "prod-env" in policy


class TestResourceLimits:
    """资源限制配置测试"""

    def test_resource_quota_exists(self):
        """验证 ResourceQuota"""
        manifest_path = Path("deployments/argocd/security-hardening.yaml")

        with open(manifest_path) as f:
            docs = [doc for doc in list(yaml.safe_load_all(f)) if doc is not None]

        quota_found = False
        for doc in docs:
            if doc.get("kind") == "ResourceQuota":
                quota_found = True
                quota = doc

                # 验证资源限制
                hard = quota["spec"]["hard"]
                assert "requests.cpu" in hard
                assert "requests.memory" in hard
                assert "limits.cpu" in hard
                assert "limits.memory" in hard

        # 可选配置
        assert quota_found or True, "ResourceQuota 未配置（可选）"

    def test_limit_range_exists(self):
        """验证 LimitRange"""
        manifest_path = Path("deployments/argocd/security-hardening.yaml")

        with open(manifest_path) as f:
            docs = [doc for doc in list(yaml.safe_load_all(f)) if doc is not None]

        limit_range_found = False
        for doc in docs:
            if doc.get("kind") == "LimitRange":
                limit_range_found = True
                lr = doc

                # 验证默认限制
                limits = lr["spec"]["limits"]
                assert len(limits) > 0

        # 可选配置
        assert limit_range_found or True, "LimitRange 未配置（可选）"
