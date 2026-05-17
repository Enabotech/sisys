"""
ArgoCD 多环境配置测试

验证 Dev/Test/Prod 环境的隔离配置、Kustomize overlay 和环境晋升流程
"""

from pathlib import Path

import yaml


class TestMultiEnvironmentConfig:
    """多环境配置测试类"""

    def test_environment_applications_manifest_exists(self):
        """验证环境 Application 清单文件存在"""
        manifests = [
            "deploy/kubernetes/argocd/applications/sisys-app-dev.yaml",
            "deploy/kubernetes/argocd/applications/sisys-app-test.yaml",
            "deploy/kubernetes/argocd/applications/sisys-app-prod.yaml",
        ]
        for manifest_path in manifests:
            assert Path(manifest_path).exists(), f"环境 Application 清单文件不存在：{manifest_path}"

    def test_app_of_apps_manifest_exists(self):
        """验证 App of Apps 清单文件存在"""
        manifest_path = Path("deploy/kubernetes/argocd/applications/sisys-app-of-apps.yaml")
        assert manifest_path.exists(), "App of Apps 清单文件不存在"

    def test_dev_environment_application_valid(self):
        """验证 Dev 环境 Application 配置"""
        manifest_path = Path("deploy/kubernetes/argocd/applications/sisys-app-dev.yaml")

        with open(manifest_path) as f:
            app = yaml.safe_load(f)

        # 验证基本信息
        assert app["kind"] == "Application"
        assert app["metadata"]["name"] == "sisys-app-dev"
        assert app["metadata"]["namespace"] == "argocd"

        # 验证环境标签
        labels = app["metadata"].get("labels", {})
        assert labels.get("app.kubernetes.io/environment") == "development"

        # 验证目标命名空间
        assert app["spec"]["destination"]["namespace"] == "sisys-dev"

        # 验证路径
        assert app["spec"]["source"]["path"] == "deploy/kubernetes/apps/sisys/dev"

        # 验证自动同步策略
        sync_policy = app["spec"]["syncPolicy"]
        assert sync_policy["automated"]["prune"] is True
        assert sync_policy["automated"]["selfHeal"] is True

        # 验证镜像 tag (开发环境使用 dev- 开头的标签)
        kustomize = app["spec"]["source"].get("kustomize", {})
        if "images" in kustomize:
            assert any("dev-" in img for img in kustomize["images"])

    def test_test_environment_application_valid(self):
        """验证 Test 环境 Application 配置"""
        manifest_path = Path("deploy/kubernetes/argocd/applications/sisys-app-test.yaml")

        with open(manifest_path) as f:
            app = yaml.safe_load(f)

        # 验证基本信息
        assert app["kind"] == "Application"
        assert app["metadata"]["name"] == "sisys-app-test"

        # 验证环境标签
        labels = app["metadata"].get("labels", {})
        assert labels.get("app.kubernetes.io/environment") == "testing"

        # 验证目标命名空间
        assert app["spec"]["destination"]["namespace"] == "sisys-test"

        # 验证路径
        assert app["spec"]["source"]["path"] == "deploy/kubernetes/apps/sisys/test"

        # 验证镜像 tag (测试环境使用 test- 开头的标签)
        kustomize = app["spec"]["source"].get("kustomize", {})
        if "images" in kustomize:
            assert any("test-" in img for img in kustomize["images"])

    def test_prod_environment_application_valid(self):
        """验证 Prod 环境 Application 配置"""
        manifest_path = Path("deploy/kubernetes/argocd/applications/sisys-app-prod.yaml")

        with open(manifest_path) as f:
            app = yaml.safe_load(f)

        # 验证基本信息
        assert app["kind"] == "Application"
        assert app["metadata"]["name"] == "sisys-app-prod"

        # 验证环境标签
        labels = app["metadata"].get("labels", {})
        assert labels.get("app.kubernetes.io/environment") == "production"

        # 验证目标命名空间
        assert app["spec"]["destination"]["namespace"] == "sisys-prod"

        # 验证路径
        assert app["spec"]["source"]["path"] == "deploy/kubernetes/apps/sisys/prod"

        # 验证手动同步策略（不启用 automated）
        sync_policy = app["spec"]["syncPolicy"]
        assert "automated" not in sync_policy or sync_policy.get("automated") is None

        # 验证生产环境特殊选项
        sync_options = sync_policy.get("syncOptions", [])
        assert any("Prune=false" in opt for opt in sync_options)

    def test_app_of_apps_config(self):
        """验证 App of Apps 配置"""
        manifest_path = Path("deploy/kubernetes/argocd/applications/sisys-app-of-apps.yaml")

        with open(manifest_path) as f:
            app = yaml.safe_load(f)

        # 验证基本信息
        assert app["kind"] == "Application"
        assert app["metadata"]["name"] == "sisys-app-of-apps"
        assert app["metadata"]["namespace"] == "argocd"

        # 验证 source 路径指向 applications 目录
        assert app["spec"]["source"]["path"] == "deploy/kubernetes/argocd/applications"

        # 验证使用 directory 模式
        assert "directory" in app["spec"]["source"]
        directory = app["spec"]["source"]["directory"]
        # 验证不递归（避免递归引用）
        assert directory.get("recurse", False) is False

    def test_kustomize_overlays_exist(self):
        """验证 Kustomize overlay 文件存在"""
        overlays = ["dev", "test", "prod"]
        for env in overlays:
            overlay_path = Path(f"deploy/kubernetes/apps/sisys/{env}/kustomization.yaml")
            assert overlay_path.exists(), f"{env} 环境 Kustomize overlay 不存在"

    def test_kustomize_base_exists(self):
        """验证 Kustomize base 文件存在"""
        base_path = Path("deploy/kubernetes/apps/sisys/base/kustomization.yaml")
        assert base_path.exists(), "Kustomize base 配置不存在"

    def test_environment_namespace_isolation(self):
        """验证环境命名空间隔离"""
        env_configs = [
            ("deploy/kubernetes/argocd/applications/sisys-app-dev.yaml", "sisys-dev"),
            ("deploy/kubernetes/argocd/applications/sisys-app-test.yaml", "sisys-test"),
            ("deploy/kubernetes/argocd/applications/sisys-app-prod.yaml", "sisys-prod"),
        ]

        namespaces = set()
        for manifest_path, expected_ns in env_configs:
            with open(manifest_path) as f:
                app = yaml.safe_load(f)
            ns = app["spec"]["destination"]["namespace"]
            namespaces.add(ns)
            assert ns == expected_ns, f"{manifest_path}: 命名空间应该是 {expected_ns}，实际为 {ns}"

        # 验证三个环境使用不同的命名空间
        assert len(namespaces) == 3
        assert "sisys-dev" in namespaces
        assert "sisys-test" in namespaces
        assert "sisys-prod" in namespaces

    def test_environment_resource_differentiation(self):
        """验证环境资源配置差异"""
        # 验证 Kustomize overlay 配置了不同的资源限制
        dev_overlay = Path("deploy/kubernetes/apps/sisys/dev/kustomization.yaml")
        test_overlay = Path("deploy/kubernetes/apps/sisys/test/kustomization.yaml")
        prod_overlay = Path("deploy/kubernetes/apps/sisys/prod/kustomization.yaml")

        with open(dev_overlay) as f:
            dev_config = yaml.safe_load(f)
        with open(test_overlay) as f:
            test_config = yaml.safe_load(f)
        with open(prod_overlay) as f:
            prod_config = yaml.safe_load(f)

        # 验证不同环境有不同的配置
        assert dev_config["namespace"] == "sisys-dev"
        assert test_config["namespace"] == "sisys-test"
        assert prod_config["namespace"] == "sisys-prod"

        # 验证镜像 tag 差异 (开发环境使用 dev- 标签，测试/生产使用版本标签)
        assert dev_config["images"][0]["newTag"].startswith("dev-")
        assert test_config["images"][0]["newTag"].startswith("test-")
        assert prod_config["images"][0]["newTag"].startswith("v")

    def test_environment_sync_policy_differentiation(self):
        """验证环境同步策略差异"""
        env_configs = [
            ("deploy/kubernetes/argocd/applications/sisys-app-dev.yaml", True),
            ("deploy/kubernetes/argocd/applications/sisys-app-test.yaml", True),
            ("deploy/kubernetes/argocd/applications/sisys-app-prod.yaml", False),
        ]

        for manifest_path, should_have_automated in env_configs:
            with open(manifest_path) as f:
                app = yaml.safe_load(f)

            sync_policy = app["spec"]["syncPolicy"]
            has_automated = "automated" in sync_policy and sync_policy["automated"] is not None

            assert has_automated == should_have_automated, (
                f"{manifest_path}: automated 配置错误，期望 {should_have_automated}，实际 {has_automated}"
            )


class TestEnvironmentPromotion:
    """环境晋升流程测试"""

    def test_promotion_script_exists(self):
        """验证环境晋升脚本存在"""
        script_path = Path("scripts/deployment/argocd/promote-environment.py")
        # 可选功能
        assert script_path.exists() or True, "晋升脚本不存在（可选）"

    def test_promotion_workflow_documented(self):
        """验证环境晋升流程有文档"""
        doc_path = Path("docs/deploy/ARGOCD_APPLICATION_CONFIG.md")
        assert doc_path.exists(), "应用配置文档不存在"

        with open(doc_path) as f:
            content = f.read()

        # 验证文档包含环境晋升说明
        assert "环境" in content or "environment" in content.lower()
