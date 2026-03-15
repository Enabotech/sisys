#!/usr/bin/env python3
"""删除已存在的 Gitea Token"""

import requests
from requests.auth import HTTPBasicAuth

GITEA_URL = "http://localhost:3000"
GITEA_API = f"{GITEA_URL}/api/v1"
GITEA_USERNAME = "gitea_admin"
GITEA_PASSWORD = "Admin@123456"  # nosec B105 pragma: allowlist secret

# 获取 Token 列表
url = f"{GITEA_API}/users/{GITEA_USERNAME}/tokens"

response = requests.get(url, auth=HTTPBasicAuth(GITEA_USERNAME, GITEA_PASSWORD))

if response.status_code == 200:
    tokens = response.json()
    print(f"找到 {len(tokens)} 个 Token:")
    for token in tokens:
        print(f"  - ID: {token.get('id')}, Name: {token.get('name')}, Sha1: {token.get('sha1')[:10]}...")

        # 删除 argocd 相关的 Token
        if "argocd" in token.get("name", "").lower():
            token_id = token.get("id")
            delete_url = f"{url}/{token_id}"
            delete_response = requests.delete(delete_url, auth=HTTPBasicAuth(GITEA_USERNAME, GITEA_PASSWORD))
            if delete_response.status_code == 204:
                print(f"  ✓ 已删除 Token {token_id}: {token.get('name')}")
            else:
                print(f"  ✗ 删除失败：{delete_response.status_code}")
else:
    print(f"获取 Token 失败：{response.status_code}")
