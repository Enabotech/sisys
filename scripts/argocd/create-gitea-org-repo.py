#!/usr/bin/env python3
"""创建 Gitea 组织和仓库"""

import requests
from requests.auth import HTTPBasicAuth

GITEA_URL = "http://localhost:3000"
GITEA_API = f"{GITEA_URL}/api/v1"
GITEA_USERNAME = "gitea_admin"
GITEA_PASSWORD = "Admin@123456"  # nosec B105 pragma: allowlist secret

# 1. 创建 sisys 组织
print("创建 sisys 组织...")
# Gitea 1.25+ 使用 /user/orgs 创建组织（需要用户认证）
create_org_url = f"{GITEA_API}/user/orgs"
org_data = {"username": "sisys", "full_name": "SISYS Project", "description": "SISYS 项目开发组织"}

response = requests.post(create_org_url, json=org_data, auth=HTTPBasicAuth(GITEA_USERNAME, GITEA_PASSWORD))

if response.status_code == 201:
    print("✓ sisys 组织创建成功")
elif response.status_code == 409:
    print("○ sisys 组织已存在")
else:
    print(f"✗ 创建组织失败：{response.status_code}")
    # 尝试使用 /orgs 端点
    print("尝试使用 /orgs 端点...")
    create_org_url_v2 = f"{GITEA_API}/orgs"
    response = requests.post(create_org_url_v2, json=org_data, auth=HTTPBasicAuth(GITEA_USERNAME, GITEA_PASSWORD))
    if response.status_code == 201:
        print("✓ sisys 组织创建成功（使用 /orgs 端点）")
    elif response.status_code == 409:
        print("○ sisys 组织已存在")
    else:
        print(f"✗ 创建组织失败（/orgs）：{response.status_code} - {response.text}")

# 2. 创建 sisys 仓库
print("\n创建 sisys/sisys 仓库...")
create_repo_url = f"{GITEA_API}/orgs/sisys/repos"
repo_data = {
    "name": "sisys",
    "description": "SISYS 项目主仓库",
    "private": False,
    "auto_init": True,  # 自动初始化 README
    "default_branch": "main",
}

response = requests.post(create_repo_url, json=repo_data, auth=HTTPBasicAuth(GITEA_USERNAME, GITEA_PASSWORD))

if response.status_code == 201:
    print("✓ sisys/sisys 仓库创建成功")
    repo_info = response.json()
    print(f"  仓库 URL: {repo_info.get('clone_url')}")
    print(f"  默认分支：{repo_info.get('default_branch')}")
elif response.status_code == 409:
    print("○ sisys/sisys 仓库已存在")
else:
    print(f"✗ 创建仓库失败：{response.status_code} - {response.text}")

print("\n完成！")
