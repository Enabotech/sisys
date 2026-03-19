#!/usr/bin/env python3
"""验证 Gitea Webhook 配置"""

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

print(f"使用 Token: {TOKEN[:10]}...")

# 获取 Webhook 列表
url = f"{GITEA_API}/repos/sisys/sisys/hooks"
response = requests.get(url, auth=HTTPBasicAuth(GITEA_USERNAME, TOKEN), verify=False)

if response.status_code == 200:
    hooks = response.json()
    print(f"\n找到 {len(hooks)} 个 Webhook:")
    for hook in hooks:
        print(f"\n  Webhook ID: {hook.get('id')}")
        print(f"  类型：{hook.get('type')}")
        print(f"  URL: {hook.get('config', {}).get('url')}")
        print(f"  事件：{hook.get('events')}")
        print(f"  状态：{'✓ 激活' if hook.get('active') else '✗ 未激活'}")
else:
    print(f"获取 Webhook 失败：{response.status_code}")
    print(f"响应：{response.text}")
