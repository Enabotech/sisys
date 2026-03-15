#!/usr/bin/env python3
"""更新 Gitea Webhook URL 为 ArgoCD 地址"""

import subprocess

import requests
from requests.auth import HTTPBasicAuth

GITEA_URL = "http://localhost:3000"
GITEA_API = f"{GITEA_URL}/api/v1"
GITEA_USERNAME = "gitea_admin"

# 获取最新的 Token
result = subprocess.run(
    [
        "bash",
        "-c",
        "echo 'H9yglwH7sdyj' | sudo -S kubectl get secret argocd-gitea-token -n argocd -o jsonpath='{.data.token}' | base64 -d",
    ],
    capture_output=True,
    text=True,
)
TOKEN = result.stdout.strip()

# ArgoCD Webhook URL（通过内部服务访问）
ARGOCD_WEBHOOK_URL = "http://argocd-server.argocd.svc.cluster.local/api/webhook"

# 获取 Webhook 列表
url = f"{GITEA_API}/repos/sisys/sisys/hooks"
response = requests.get(url, auth=HTTPBasicAuth(GITEA_USERNAME, TOKEN), verify=False)

if response.status_code == 200:
    hooks = response.json()
    for hook in hooks:
        hook_id = hook.get("id")
        current_url = hook.get("config", {}).get("url")
        print(f"当前 Webhook {hook_id} URL: {current_url}")

        # 更新 Webhook URL
        update_url = f"{url}/{hook_id}"
        update_data = {"config": {"url": ARGOCD_WEBHOOK_URL, "content_type": "json"}}

        response = requests.patch(update_url, json=update_data, auth=HTTPBasicAuth(GITEA_USERNAME, TOKEN), verify=False)

        if response.status_code == 200:
            print(f"✓ Webhook {hook_id} URL 已更新为：{ARGOCD_WEBHOOK_URL}")
        else:
            print(f"✗ 更新失败：{response.status_code}")
            print(f"响应：{response.text}")
else:
    print(f"获取 Webhook 失败：{response.status_code}")
