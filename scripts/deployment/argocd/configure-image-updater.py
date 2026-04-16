#!/usr/bin/env python3
"""
ArgoCD Image Updater 配置脚本
Story 0.7: ArgoCD 持续部署 - Task 5: Harbor 镜像仓库集成

功能：
1. 创建 Harbor Robot Account
2. 配置 ArgoCD Image Updater Secret
3. 配置 Harbor Webhook
4. 创建示例 Application 配置

使用方法:
    python scripts/deployment/argocd/configure-image-updater.py [选项]

选项:
    --harbor-url URL          Harbor 访问 URL (默认：https://harbor.sisys.local)
    --harbor-internal-url URL Harbor 内部服务 URL (默认：http://harbor.harbor.svc.cluster.local)
    --argocd-namespace NS     ArgoCD 命名空间 (默认：argocd)
    --harbor-namespace NS     Harbor 命名空间 (默认：harbor)
    --project-name NAME       Harbor 项目名称 (默认：sisys)
    --robot-account NAME      Robot Account 名称 (默认：argocd-pull)
    --harbor-admin-user USER  Harbor 管理员用户名 (默认：admin)
    --harbor-admin-pass PASS  Harbor 管理员密码 (默认：Harbor@2026Secure!)
    --dry-run                 只打印配置不执行
    --help                    显示帮助信息
"""

import argparse
import base64
import json
import subprocess
import sys
from pathlib import Path


class ArgoCDImageUpdaterConfigurator:
    """ArgoCD Image Updater 配置器"""

    def __init__(  # noqa: PLR0913, S107
        self,
        harbor_url: str = "https://harbor.sisys.local",
        harbor_internal_url: str = "http://harbor.harbor.svc.cluster.local",
        argocd_namespace: str = "argocd",
        harbor_namespace: str = "harbor",
        project_name: str = "sisys",
        robot_account_name: str = "argocd-pull",
        webhook_name: str = "argocd-image-updater",
        harbor_admin_user: str = "admin",
        harbor_admin_pass: str = "Harbor@2026Secure!",  # pragma: allowlist secret
        dry_run: bool = False,
    ):
        self.harbor_url = harbor_url
        self.harbor_internal_url = harbor_internal_url
        self.argocd_namespace = argocd_namespace
        self.harbor_namespace = harbor_namespace
        self.project_name = project_name
        self.robot_account_name = robot_account_name
        self.webhook_name = webhook_name
        self.harbor_admin_user = harbor_admin_user
        self.harbor_admin_pass = harbor_admin_pass
        self.dry_run = dry_run

    def run_kubectl(self, args: list, input_data: str | None = None) -> tuple:
        """运行 kubectl 命令"""
        cmd = ["sudo", "kubectl"] + args
        result = subprocess.run(cmd, capture_output=True, text=True, input=input_data)
        return result.returncode, result.stdout, result.stderr

    def run_harbor_api(self, endpoint: str, method: str = "GET", data: dict | None = None) -> dict | None:
        """运行 Harbor API 调用"""
        # 使用 curl 调用 Harbor API
        cmd = [
            "sudo",
            "curl",
            "-k",
            "-s",
            "-u",
            "admin:Harbor@2026Secure!",
            "-X",
            method,
            "-H",
            "Content-Type: application/json",
        ]

        if data:
            cmd.extend(["-d", json.dumps(data)])

        cmd.append(f"{self.harbor_internal_url}/api/v2.0{endpoint}")

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Harbor API 调用失败：{result.stderr}")

        return json.loads(result.stdout) if result.stdout else None

    def check_existing_robot_account(self) -> bool:
        """检查是否已存在 Robot Account"""
        print(f"🔍 检查是否已存在 Robot Account: {self.robot_account_name}")

        try:
            # 获取项目 ID
            projects = self.run_harbor_api(f"/projects?name={self.project_name}")
            if not projects:
                print(f"❌ 项目 {self.project_name} 不存在")
                return False

            project_id = projects[0]["project_id"]
            print(f"✓ 项目 ID: {project_id}")

            # 获取 Robot Accounts
            robots = self.run_harbor_api(f"/projects/{project_id}/robots")
            if robots:
                for robot in robots:
                    if robot["name"] == self.robot_account_name:
                        print(f"✓ Robot Account 已存在：{robot['name']}")
                        return True

            print("ℹ️  Robot Account 不存在，需要创建")
            return False

        except Exception as e:
            print(f"⚠️  检查 Robot Account 失败：{e}")
            return False

    def create_robot_account(self) -> str:
        """创建 Harbor Robot Account"""
        print(f"\n🤖 创建 Harbor Robot Account: {self.robot_account_name}")

        # 获取项目 ID
        projects = self.run_harbor_api(f"/projects?name={self.project_name}")
        if not projects:
            raise Exception(f"项目 {self.project_name} 不存在")

        project_id = projects[0]["project_id"]

        # 创建 Robot Account
        robot_data = {
            "name": self.robot_account_name,
            "description": "ArgoCD Image Updater 拉取镜像",
            "duration": -1,  # 永不过期
            "level": "project",
            "permissions": [
                {
                    "kind": "project",
                    "namespace": self.project_name,
                    "access": [{"resource": "repository", "action": "pull"}, {"resource": "artifact", "action": "read"}],
                }
            ],
        }

        result = self.run_harbor_api(f"/projects/{project_id}/robots", method="POST", data=robot_data)

        if result and "secret" in result:
            token = result["secret"]
            print("✓ Robot Account 创建成功")
            print(f"  名称：{result['name']}")
            print(f"  Token: {token[:20]}...（已隐藏完整 Token）")
            return str(token)
        else:
            raise Exception("创建 Robot Account 失败")

    def create_image_updater_secret(self, token: str):
        """创建 ArgoCD Image Updater Secret"""
        print("\n🔐 创建 Kubernetes Secret: argocd-image-updater-secret")

        # 编码凭据
        credentials = f"{self.robot_account_name}:{token}"
        encoded = base64.b64encode(credentials.encode()).decode()

        # 创建 Secret YAML
        secret_yaml = f"""
apiVersion: v1
kind: Secret
metadata:
  name: argocd-image-updater-secret
  namespace: {self.argocd_namespace}
type: Opaque
data:
  harbor: {encoded}
"""

        # 应用 Secret
        returncode, stdout, stderr = self.run_kubectl(["apply", "-f", "-"], input_data=secret_yaml)

        if returncode != 0:
            print(f"❌ Secret 创建失败：{stderr}")
            return False

        print("✓ Secret 创建成功")
        return True

    def create_webhook(self):
        """创建 Harbor Webhook"""
        print(f"\n🔔 创建 Harbor Webhook: {self.webhook_name}")

        try:
            # 获取项目 ID
            projects = self.run_harbor_api(f"/projects?name={self.project_name}")
            if not projects:
                print(f"⚠️  项目 {self.project_name} 不存在，跳过 Webhook 配置")
                return

            project_id = projects[0]["project_id"]

            # 检查是否已存在 Webhook
            webhooks = self.run_harbor_api(f"/projects/{project_id}/webhook/policies")
            for webhook in webhooks:
                if webhook["name"] == self.webhook_name:
                    print(f"✓ Webhook 已存在：{webhook['name']}")
                    return

            # 创建 Webhook
            webhook_data = {
                "name": self.webhook_name,
                "description": "Trigger ArgoCD Image Updater on image push",
                "enabled": True,
                "eventTypes": ["PUSH_ARTIFACT"],
                "targets": [
                    {
                        "type": "http",
                        "address": "http://argocd-image-updater.argocd.svc.cluster.local:8080/api/v1/webhook",
                        "skip_cert_verify": True,
                    }
                ],
                "project_id": project_id,
            }

            result = self.run_harbor_api("/webhook/policies", method="POST", data=webhook_data)

            if result:
                print("✓ Webhook 创建成功")
                print(f"  名称：{result.get('name', 'N/A')}")
                print(f"  ID: {result.get('id', 'N/A')}")
            else:
                print("⚠️  Webhook 创建可能失败")

        except Exception as e:
            print(f"⚠️  Webhook 创建失败：{e}")
            print("  可以手动在 Harbor Web 界面配置")

    def verify_installation(self):
        """验证安装"""
        print("\n✅ 验证安装")

        # 检查 Pod 状态
        returncode, stdout, stderr = self.run_kubectl(
            ["get", "pods", "-n", self.argocd_namespace, "-l", "app.kubernetes.io/name=argocd-image-updater"]
        )

        if returncode == 0 and "Running" in stdout:
            print("✓ Image Updater Pod 运行正常")
        else:
            print("⚠️  Image Updater Pod 状态异常")

        # 检查 Secret
        returncode, stdout, stderr = self.run_kubectl(
            ["get", "secret", "argocd-image-updater-secret", "-n", self.argocd_namespace]
        )

        if returncode == 0:
            print("✓ Secret 存在")
        else:
            print("⚠️  Secret 不存在")

        # 查看日志
        returncode, stdout, stderr = self.run_kubectl(
            ["logs", "-n", self.argocd_namespace, "-l", "app.kubernetes.io/name=argocd-image-updater", "--tail=10"]
        )

        if returncode == 0 and "Starting" in stdout:
            print("✓ Image Updater 启动成功")

        print("\n📋 验证完成")

    def create_example_application(self):
        """创建示例 Application 配置"""
        print("\n📝 创建示例 ArgoCD Application 配置")

        example_yaml = """
---
# 示例 Application 配置 - 展示如何配置镜像自动更新
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp-example
  namespace: argocd
  annotations:
    # 启用镜像更新
    argocd-image-updater.argoproj.io/image-list: |
      harbor.sisys.local/sisys/myapp=myapp

    # 更新策略：语义化版本
    argocd-image-updater.argoproj.io/myapp.update-strategy: semver

    # 允许的 tag 格式
    argocd-image-updater.argoproj.io/myapp.allow-tags: regexp:^v[0-9]+\\.[0-9]+\\.[0-9]+$

    # 排序方式
    argocd-image-updater.argoproj.io/myapp.sort-mode: semver

    # 忽略的 tag
    argocd-image-updater.argoproj.io/myapp.ignore-tags: |
      latest,dev,nightly

    # 强制更新
    argocd-image-updater.argoproj.io/myapp.force-update: "true"
spec:
  project: default
  source:
    repoURL: https://gitea.sisys.local/sisys/sisys.git
    targetRevision: HEAD
    path: deploy/kubernetes/myapp
  destination:
    server: https://kubernetes.default.svc
    namespace: default
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
"""

        output_path = Path("/mnt/g/ai/sisys/deploy/kubernetes/argocd/example-application.yaml")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(example_yaml)

        print(f"✓ 示例配置已保存到：{output_path}")
        print(f"  使用方法：sudo kubectl apply -f {output_path}")

    def run(self):
        """执行配置流程"""
        print("=" * 70)
        print("ArgoCD Image Updater 配置脚本")
        print("Story 0.7: ArgoCD 持续部署 - Task 5: Harbor 镜像仓库集成")
        print("=" * 70)

        try:
            # 1. 检查/创建 Robot Account
            if not self.check_existing_robot_account():
                token = self.create_robot_account()

                # 2. 创建 Secret
                self.create_image_updater_secret(token)
            else:
                print("⚠️  Robot Account 已存在，如需更新请手动删除后重新运行")

            # 3. 创建 Webhook
            self.create_webhook()

            # 4. 验证安装
            self.verify_installation()

            # 5. 创建示例配置
            self.create_example_application()

            print("\n" + "=" * 70)
            print("✅ 配置完成！")
            print("=" * 70)
            print("\n下一步:")
            print("1. 在 Harbor Web 界面验证 Robot Account: https://harbor.sisys.local")
            print("2. 创建 ArgoCD Application 并添加镜像更新注解")
            print("3. 推送新镜像测试自动更新流程")
            print("\n参考文档：docs/deployment/ARGOCD_IMAGE_UPDATER.md")

        except KeyboardInterrupt:
            print("\n\n⚠️  用户中断")
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ 配置失败：{e}")
            sys.exit(1)


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="ArgoCD Image Updater 配置脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认配置运行
  python scripts/deployment/argocd/configure-image-updater.py

  # 自定义 Harbor 管理员密码
  python scripts/deployment/argocd/configure-image-updater.py --harbor-admin-pass MySecurePass123

  # 自定义命名空间
  python scripts/deployment/argocd/configure-image-updater.py --argocd-namespace my-argocd --harbor-namespace my-harbor

  # Dry-run 模式（只打印不执行）
  python scripts/deployment/argocd/configure-image-updater.py --dry-run
        """,
    )

    parser.add_argument(
        "--harbor-url",
        default="https://harbor.sisys.local",
        help="Harbor 访问 URL (默认：https://harbor.sisys.local)",
    )
    parser.add_argument(
        "--harbor-internal-url",
        default="http://harbor.harbor.svc.cluster.local",
        help="Harbor 内部服务 URL (默认：http://harbor.harbor.svc.cluster.local)",
    )
    parser.add_argument(
        "--argocd-namespace",
        default="argocd",
        help="ArgoCD 命名空间 (默认：argocd)",
    )
    parser.add_argument(
        "--harbor-namespace",
        default="harbor",
        help="Harbor 命名空间 (默认：harbor)",
    )
    parser.add_argument(
        "--project-name",
        default="sisys",
        help="Harbor 项目名称 (默认：sisys)",
    )
    parser.add_argument(
        "--robot-account",
        default="argocd-pull",
        help="Robot Account 名称 (默认：argocd-pull)",
    )
    parser.add_argument(
        "--harbor-admin-user",
        default="admin",
        help="Harbor 管理员用户名 (默认：admin)",
    )
    parser.add_argument(
        "--harbor-admin-pass",
        default="Harbor@2026Secure!",
        help="Harbor 管理员密码 (默认：Harbor@2026Secure!)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印配置不执行",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.dry_run:
        print("=" * 70)
        print("Dry-run 模式：只打印配置，不执行实际操作")
        print("=" * 70)
        print("\n配置参数:")
        print(f"  Harbor URL: {args.harbor_url}")
        print(f"  Harbor 内部 URL: {args.harbor_internal_url}")
        print(f"  ArgoCD 命名空间：{args.argocd_namespace}")
        print(f"  Harbor 命名空间：{args.harbor_namespace}")
        print(f"  项目名称：{args.project_name}")
        print(f"  Robot Account: {args.robot_account}")
        print(f"  Harbor 管理员：{args.harbor_admin_user}")
        print("\n退出（Dry-run 模式）")
        sys.exit(0)

    configurator = ArgoCDImageUpdaterConfigurator(
        harbor_url=args.harbor_url,
        harbor_internal_url=args.harbor_internal_url,
        argocd_namespace=args.argocd_namespace,
        harbor_namespace=args.harbor_namespace,
        project_name=args.project_name,
        robot_account_name=args.robot_account,
        harbor_admin_user=args.harbor_admin_user,
        harbor_admin_pass=args.harbor_admin_pass,
    )
    configurator.run()
