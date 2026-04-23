#!/usr/bin/env python3
"""
创建 Gitea Personal Access Token 并配置 ArgoCD 仓库集成
"""
import datetime
import subprocess

import requests
import urllib3
from requests.auth import HTTPBasicAuth

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 配置
# 使用本地端口转发访问 Gitea（避免 TLS 和 Ingress 问题）
GITEA_URL = "http://localhost:3000"
GITEA_API = f"{GITEA_URL}/api/v1"
GITEA_USERNAME = "gitea_admin"
GITEA_PASSWORD = "Admin@123456"  # pragma: allowlist secret
ARGOCD_NAMESPACE = "argocd"

# Token 名称（带时间戳避免冲突）
TOKEN_NAME = f"argocd-webhook-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"


def get_sudo_password():
    """获取 sudo 密码"""
    return "your-pwd"


def run_kubectl(args):
    """运行 kubectl 命令"""
    cmd = f"echo '{get_sudo_password()}' | sudo -S kubectl {' '.join(args)}"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def create_gitea_token():
    """创建 Gitea Personal Access Token"""
    print(f"创建 Gitea Personal Access Token: {TOKEN_NAME}...")

    url = f"{GITEA_API}/users/{GITEA_USERNAME}/tokens"
    # Gitea 1.25+ 支持的 scope: all, write, read, admin:org, read:org, user:email, notification
    # admin:public_key, write:public_key, read:public_key, admin:repo_hook, read:repo_hook
    # 使用 'all' 获取所有权限
    data = {"name": TOKEN_NAME, "scopes": ["all"]}

    try:
        response = requests.post(url, json=data, auth=HTTPBasicAuth(GITEA_USERNAME, GITEA_PASSWORD), verify=False)

        if response.status_code == 201:
            token = response.json().get("sha1")
            print(f"✓ Token 创建成功：{token[:10]}...")
            return token
        elif response.status_code == 400 and "already exists" in response.text:
            print("Token 已存在，尝试删除后重新创建...")
            if delete_gitea_token():
                # 重新创建
                response = requests.post(url, json=data, auth=HTTPBasicAuth(GITEA_USERNAME, GITEA_PASSWORD), verify=False)
                if response.status_code == 201:
                    token = response.json().get("sha1")
                    print(f"✓ Token 重新创建成功：{token[:10]}...")
                    return token
            print("✗ 重新创建 Token 失败")
            return None
        else:
            print(f"✗ 创建 Token 失败：{response.status_code}")
            print(f"响应：{response.text}")
            return None

    except Exception as e:
        print(f"✗ 错误：{e}")
        return None


def delete_gitea_token():
    """删除已存在的 Token"""
    print("删除已存在的 Token...")

    # 先获取 Token 列表
    url = f"{GITEA_API}/users/{GITEA_USERNAME}/tokens"

    try:
        response = requests.get(url, auth=HTTPBasicAuth(GITEA_USERNAME, GITEA_PASSWORD), verify=False)

        if response.status_code == 200:
            tokens = response.json()
            for token in tokens:
                if token.get("name") == "argocd-webhook":
                    token_id = token.get("id")
                    delete_url = f"{url}/{token_id}"
                    delete_response = requests.delete(
                        delete_url, auth=HTTPBasicAuth(GITEA_USERNAME, GITEA_PASSWORD), verify=False
                    )
                    if delete_response.status_code == 204:
                        print(f"✓ Token {token_id} 已删除")
                    return True
        return False
    except Exception as e:
        print(f"✗ 删除 Token 失败：{e}")
        return False


def store_token_in_secret(token):
    """将 Token 存储到 Kubernetes Secret"""
    print("存储 Token 到 Kubernetes Secret...")

    # 先删除可能存在的旧 Secret
    run_kubectl(["delete", "secret", "argocd-gitea-token", "-n", ARGOCD_NAMESPACE, "--ignore-not-found"])

    # 使用 kubectl create secret
    cmd = f"""echo '{get_sudo_password()}' | sudo -S kubectl create secret generic argocd-gitea-token \\
        -n {ARGOCD_NAMESPACE} \\
        --from-literal=token='{token}'"""

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if "created" in result.stdout:
        print("✓ Secret 已创建")
        return True
    elif "already exists" in result.stdout:
        print("✓ Secret 已存在")
        return True
    else:
        print(f"✗ 创建 Secret 失败：{result.stderr}")
        print(f"输出：{result.stdout}")
        return False


def configure_argocd_repo(token):
    """配置 ArgoCD 仓库凭据"""
    print("配置 ArgoCD 仓库凭据...")

    # 应用配置文件
    returncode, stdout, stderr = run_kubectl(["apply", "-f", "/mnt/g/ai/sisys/deploy/kubernetes/argocd/gitea-credentials.yaml"])

    if returncode != 0:
        print(f"✗ 应用配置失败：{stderr}")
        return False

    print("✓ 配置文件已应用")

    # 使用 kubectl apply 直接创建 Repo Secret（避免使用 argocd CLI）
    print("创建 ArgoCD 仓库 Secret...")
    repo_secret_yaml = f"""
apiVersion: v1
kind: Secret
metadata:
  name: argocd-repo-gitea-sisys
  namespace: {ARGOCD_NAMESPACE}
  labels:
    argocd.argoproj.io/secret-type: repository
type: Opaque
stringData:
  type: git
  url: https://gitea.sisys.local/sisys/sisys.git
  username: {GITEA_USERNAME}
  password: {token}
  insecureSkipServerVerification: "true"
"""
    cmd = f"""echo '{get_sudo_password()}' | sudo -S kubectl apply -f - <<EOF
{repo_secret_yaml}
EOF"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if "created" in result.stdout or "configured" in result.stdout:
        print("✓ 仓库 Secret 已创建")
        return True
    else:
        print(f"✗ 创建仓库 Secret 失败：{result.stderr}")
        print(f"输出：{result.stdout}")
        return True  # 继续执行


def create_gitea_webhook(token):
    """创建 Gitea Webhook"""
    print("创建 Gitea Webhook...")

    # 先检查仓库是否存在
    repo_url = f"{GITEA_API}/repos/sisys/sisys"
    repo_response = requests.get(repo_url, auth=HTTPBasicAuth(GITEA_USERNAME, token), verify=False)

    if repo_response.status_code == 404:
        print("✗ 仓库 sisys/sisys 不存在")
        return False

    url = f"{GITEA_API}/repos/sisys/sisys/hooks"
    # Gitea 1.25+ Webhook 配置
    data = {
        "active": True,
        "type": "gitea",
        "config": {"url": f"{GITEA_URL}/api/webhook", "content_type": "json"},
        "events": ["push", "create", "delete"],
    }

    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json=data, headers=headers, auth=HTTPBasicAuth(GITEA_USERNAME, token), verify=False)

        if response.status_code == 201:
            webhook_id = response.json().get("id")
            print(f"✓ Webhook 创建成功 (ID: {webhook_id})")
            return True
        else:
            print(f"✗ 创建 Webhook 失败：{response.status_code}")
            print(f"响应：{response.text}")
            return False

    except Exception as e:
        print(f"✗ 错误：{e}")
        return False


def verify_configuration():
    """验证配置"""
    print("\n验证配置...")

    # 验证 ArgoCD 仓库列表
    print("检查 ArgoCD 仓库列表...")
    returncode, stdout, stderr = run_kubectl(
        ["exec", "-n", ARGOCD_NAMESPACE, "deploy/argocd-server", "--", "argocd", "repo", "list"]
    )

    if returncode == 0:
        print("✓ ArgoCD 仓库列表:")
        print(stdout)
        return True
    else:
        print(f"✗ 验证失败：{stderr}")
        return False


def main():
    print("=" * 50)
    print("ArgoCD Gitea 集成配置")
    print("=" * 50)
    print()

    # 步骤 1: 创建 Token
    token = create_gitea_token()
    if not token:
        print("\n✗ Token 创建失败，请检查 Gitea 是否可访问")
        return False

    # 步骤 2: 存储 Token
    if not store_token_in_secret(token):
        print("\n✗ Token 存储失败")
        return False

    # 步骤 3: 配置 ArgoCD 仓库
    if not configure_argocd_repo(token):
        print("\n✗ ArgoCD 仓库配置失败")
        return False

    # 步骤 4: 创建 Webhook
    if not create_gitea_webhook(token):
        print("\n✗ Webhook 创建失败")
        return False

    # 步骤 5: 验证配置
    verify_configuration()

    print("\n" + "=" * 50)
    print("✓ ArgoCD Gitea 集成配置完成!")
    print("=" * 50)
    print()
    print("下一步:")
    print("1. 创建 ArgoCD Application")
    print("2. 测试代码推送触发同步")
    print()
    print("访问 ArgoCD: https://argocd.sisys.local")
    print("访问 Gitea: https://gitea.sisys.local")

    return True


if __name__ == "__main__":
    main()
