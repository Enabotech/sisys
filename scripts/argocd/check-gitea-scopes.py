#!/usr/bin/env python3
"""检查 Gitea API 支持的 Token scope"""
import json

import requests
from requests.auth import HTTPBasicAuth

GITEA_URL = "http://localhost:3000"
GITEA_API = f"{GITEA_URL}/api/v1"
GITEA_USERNAME = "gitea_admin"
GITEA_PASSWORD = "Admin@123456"  # nosec B105 pragma: allowlist secret

# 获取 Swagger/OpenAPI 文档查看支持的 scope
response = requests.get(f"{GITEA_URL}/api/swagger", auth=HTTPBasicAuth(GITEA_USERNAME, GITEA_PASSWORD))
print("Swagger 文档访问状态:", response.status_code)

# 尝试创建不带 scope 的 Token（使用默认权限）
print("\n尝试创建不带 scope 的 Token...")
url = f"{GITEA_API}/users/{GITEA_USERNAME}/tokens"
data = {"name": "argocd-webhook-no-scope"}

response = requests.post(url, json=data, auth=HTTPBasicAuth(GITEA_USERNAME, GITEA_PASSWORD))
print(f"状态码：{response.status_code}")
print(f"响应：{json.dumps(response.json(), indent=2, ensure_ascii=False)}")
