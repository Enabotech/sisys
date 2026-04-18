#!/usr/bin/env python3
"""
ArgoCD Application 部署脚本

功能:
1. 部署 ArgoCD Application 到集群
2. 验证 Application 状态
3. 配置自动同步策略

使用方法:
    python scripts/deployment/argocd/deploy-application.py
"""

import subprocess
import sys
import time
from pathlib import Path


def run_command(cmd, check=True):
    """运行 shell 命令"""
    print(f"🔄 执行：{' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"❌ 命令失败：{result.stderr}")
        sys.exit(1)
    return result


def check_argocd_installed():
    """检查 ArgoCD 是否已安装"""
    print("📋 检查 ArgoCD 安装状态...")
    result = run_command(["kubectl", "get", "pods", "-n", "argocd", "-l", "app.kubernetes.io/name=argocd-server"], check=False)
    if result.returncode != 0:
        print("❌ ArgoCD 未安装，请先安装 ArgoCD")
        sys.exit(1)
    print("✅ ArgoCD 已安装")


def deploy_application(manifest_path):
    """部署 Application"""
    print(f"🚀 部署 Application: {manifest_path}")

    # 应用清单
    result = run_command(["kubectl", "apply", "-f", manifest_path])
    print("✅ Application 部署成功")

    # 等待 Application 创建
    time.sleep(5)

    # 检查 Application 状态
    result = run_command(["kubectl", "get", "application", "sisys-app", "-n", "argocd"], check=False)
    if result.returncode == 0:
        print(f"✅ Application 创建成功:\n{result.stdout}")
    else:
        print("⚠️ Application 可能正在创建中...")


def verify_application():
    """验证 Application 状态"""
    print("📋 验证 Application 状态...")

    # 获取 Application 详细信息
    result = run_command(["kubectl", "get", "application", "sisys-app", "-n", "argocd", "-o", "wide"], check=False)
    if result.returncode != 0:
        print("⚠️ Application 未找到")
        return False

    print(result.stdout)
    return True


def main():
    """主函数"""
    print("=" * 60)
    print("ArgoCD Application 部署脚本")
    print("=" * 60)

    # 检查 ArgoCD
    check_argocd_installed()

    # 部署 Application
    manifest_path = Path("deploy/kubernetes/argocd/applications/sisys-app.yaml")
    if not manifest_path.exists():
        print(f"❌ 清单文件不存在：{manifest_path}")
        sys.exit(1)

    deploy_application(str(manifest_path))

    # 验证部署
    if verify_application():
        print("\n✅ Application 部署完成!")
        print("\n下一步:")
        print("1. 访问 ArgoCD UI: https://argocd.sisys.local")
        print("2. 查看 Application 状态：argocd app get sisys-app -n argocd")
        print("3. 查看同步历史：argocd app history sisys-app -n argocd")
    else:
        print("\n⚠️ Application 部署可能未完成，请检查日志")
        print("查看日志：kubectl logs -n argocd -l app.kubernetes.io/name=argocd-server")


if __name__ == "__main__":
    main()
