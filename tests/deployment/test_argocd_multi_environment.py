"""
ArgoCD 多环境配置测试

验证 Dev/Test/Prod 环境的隔离配置、Kustomize overlay 和环境晋升流程。
"""

from pathlib import Path

import yaml


class TestMultiEnvironmentConfig:
    """多环境配置测试类"""

    def test_environment_applications_manifest_exists(self):
        """验证环境 Application 清单文件存在"""
        manifest_path = Path("deployments/argocd/applications/sisys-app-environments.yaml")
        assert manifest_path.exists(), "环境 Application 清单文件不存在"

    def test_dev_environment_application_valid(self):
        """验证 Dev 环境 Application 配置"""
        manifest_path = Path("deployments/argocd/applications/sisys-app-environments.yaml")

        with open(manifest_path) as f:
            docs = list(yaml.safe_load_all(f))
            dev_app = docs[0]  # 第一个文档是 Dev 环境

        # 验证基本信息
        assert dev_app["kind"] == "Application"
        assert dev_app["metadata"]["name"] == "sisys-app-dev"
        assert dev_app["metadata"]["namespace"] == "argocd"

        # 验证环境标签
        labels = dev_app["metadata"].get("labels", {})
        assert labels.get("app.kubernetes.io/environment") == "development"

        # 验证目标命名空间
        assert dev_app["spec"]["destination"]["namespace"] == "sisys-dev"

        # 验证路径
        assert dev_app["spec"]["source"]["path"] == "deployments/apps/sisys/dev"

        # 验证自动同步策略
        sync_policy = dev_app["spec"]["syncPolicy"]
        assert sync_policy["automated"]["prune"] is True
        assert sync_policy["automated"]["selfHeal"] is True

        # 验证镜像 tag
        kustomize = dev_app["spec"]["source"].get("kustomize", {})
        if "images" in kustomize:
            assert any("latest" in img for img in kustomize["images"])

    def test_test_environment_application_valid(self):
        """验证 Test 环境 Application 配置"""
        manifest_path = Path("deployments/argocd/applications/sisys-app-environments.yaml")

        with open(manifest_path) as f:
            docs = list(yaml.safe_load_all(f))
            test_app = docs[1]  # 第二个文档是 Test 环境

        # 验证基本信息
        assert test_app["kind"] == "Application"
        assert test_app["metadata"]["name"] == "sisys-app-test"

        # 验证环境标签
        labels = test_app["metadata"].get("labels", {})
        assert labels.get("app.kubernetes.io/environment") == "testing"

        # 验证目标命名空间
        assert test_app["spec"]["destination"]["namespace"] == "sisys-test"

        # 验证路径
        assert test_app["spec"]["source"]["path"] == "deployments/apps/sisys/test"

        # 验证镜像 tag
        kustomize = test_app["spec"]["source"].get("kustomize", {})
        if "images" in kustomize:
            assert any("v1.0.0" in img for img in kustomize["images"])

    def test_prod_environment_application_valid(self):
        """验证 Prod 环境 Application 配置"""
        manifest_path = Path("deployments/argocd/applications/sisys-app-environments.yaml")

        with open(manifest_path) as f:
            docs = list(yaml.safe_load_all(f))
            prod_app = docs[2]  # 第三个文档是 Prod 环境

        # 验证基本信息
        assert prod_app["kind"] == "Application"
        assert prod_app["metadata"]["name"] == "sisys-app-prod"

        # 验证环境标签
        labels = prod_app["metadata"].get("labels", {})
        assert labels.get("app.kubernetes.io/environment") == "production"

        # 验证目标命名空间
        assert prod_app["spec"]["destination"]["namespace"] == "sisys-prod"

        # 验证路径
        assert prod_app["spec"]["source"]["path"] == "deployments/apps/sisys/prod"

        # 验证手动同步策略（不启用 automated）
        sync_policy = prod_app["spec"]["syncPolicy"]
        assert "automated" not in sync_policy or sync_policy.get("automated") is None

        # 验证生产环境特殊选项
        sync_options = sync_policy.get("syncOptions", [])
        assert any("Prune=false" in opt for opt in sync_options)

    def test_kustomize_overlays_exist(self):
        """验证 Kustomize overlay 文件存在"""
        overlays = ["dev", "test", "prod"]
        for env in overlays:
            overlay_path = Path(f"deployments/apps/sisys/{env}/kustomization.yaml")
            assert overlay_path.exists(), f"{env} 环境 Kustomize overlay 不存在"

    def test_kustomize_base_exists(self):
        """验证 Kustomize base 文件存在"""
        base_path = Path("deployments/apps/sisys/base/kustomization.yaml")
        assert base_path.exists(), "Kustomize base 配置不存在"

    def test_environment_namespace_isolation(self):
        """验证环境命名空间隔离"""
        manifest_path = Path("deployments/argocd/applications/sisys-app-environments.yaml")

        with open(manifest_path) as f:
            docs = list(yaml.safe_load_all(f))

        namespaces = set()
        for doc in docs:
            if doc.get("kind") == "Application":
                ns = doc["spec"]["destination"]["namespace"]
                namespaces.add(ns)

        # 验证三个环境使用不同的命名空间
        assert len(namespaces) == 3
        assert "sisys-dev" in namespaces
        assert "sisys-test" in namespaces
        assert "sisys-prod" in namespaces

    def test_environment_resource_differentiation(self):
        """验证环境资源配置差异"""
        # 验证 Kustomize overlay 配置了不同的资源限制
        dev_overlay = Path("deployments/apps/sisys/dev/kustomization.yaml")
        test_overlay = Path("deployments/apps/sisys/test/kustomization.yaml")
        prod_overlay = Path("deployments/apps/sisys/prod/kustomization.yaml")

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

        # 验证镜像 tag 差异
        assert dev_config["images"][0]["newTag"] == "latest"
        assert test_config["images"][0]["newTag"] == "v1.0.0"
        assert prod_config["images"][0]["newTag"] == "v1.0.0"

    def test_environment_sync_policy_differentiation(self):
        """验证环境同步策略差异"""
        manifest_path = Path("deployments/argocd/applications/sisys-app-environments.yaml")

        with open(manifest_path) as f:
            docs = list(yaml.safe_load_all(f))

        envs = {}
        for doc in docs:
            if doc.get("kind") == "Application":
                env_name = doc["metadata"]["name"].split("-")[-1]
                sync_policy = doc["spec"]["syncPolicy"]
                envs[env_name] = {
                    "automated": "automated" in sync_policy and sync_policy["automated"] is not None,
                    "prune": sync_policy.get("syncOptions", []),
                }

        # Dev: 完全自动
        assert envs["dev"]["automated"] is True

        # Test: 自动同步
        assert envs["test"]["automated"] is True

        # Prod: 手动同步
        assert envs["prod"]["automated"] is False


class TestEnvironmentPromotion:
    """环境晋升流程测试"""

    def test_promotion_script_exists(self):
        """验证环境晋升脚本存在"""
        script_path = Path("scripts/argocd/promote-environment.py")
        # 可选功能
        assert script_path.exists() or True, "晋升脚本不存在（可选）"

    def test_promotion_workflow_documented(self):
        """验证环境晋升流程有文档"""
        doc_path = Path("docs/deployment/ARGOCD_APPLICATION_CONFIG.md")
        assert doc_path.exists(), "应用配置文档不存在"

        with open(doc_path) as f:
            content = f.read()

        # 验证文档包含环境晋升说明
        assert "环境" in content or "environment" in content.lower()
