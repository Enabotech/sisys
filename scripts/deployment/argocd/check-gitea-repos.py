#!/usr/bin/env python3
"""检查 Gitea 组织和仓库"""

import requests
from requests.auth import HTTPBasicAuth

GITEA_URL = "http://localhost:3000"
GITEA_API = f"{GITEA_URL}/api/v1"
GITEA_USERNAME = "gitea_admin"
GITEA_PASSWORD = "Admin@123456"  # pragma: allowlist secret

# 获取所有组织
print("获取所有组织...")
orgs_url = f"{GITEA_API}/admin/orgs"
response = requests.get(orgs_url, auth=HTTPBasicAuth(GITEA_USERNAME, GITEA_PASSWORD))
if response.status_code == 200:
    orgs = response.json()
    print(f"组织列表：{[o.get('username') for o in orgs]}")

    # 获取每个组织的仓库
    for org in orgs:
        org_name = org.get("username")
        repos_url = f"{GITEA_API}/orgs/{org_name}/repos"
        repos_response = requests.get(repos_url, auth=HTTPBasicAuth(GITEA_USERNAME, GITEA_PASSWORD))
        if repos_response.status_code == 200:
            repos = repos_response.json()
            print(f"  组织 {org_name} 的仓库：{[r.get('name') for r in repos]}")
else:
    print(f"获取组织失败：{response.status_code}")

# 获取所有用户
print("\n获取所有用户...")
users_url = f"{GITEA_API}/admin/users"
response = requests.get(users_url, auth=HTTPBasicAuth(GITEA_USERNAME, GITEA_PASSWORD))
if response.status_code == 200:
    users = response.json()
    print(f"用户列表：{[u.get('login') for u in users]}")

    # 获取每个用户的仓库
    for user in users:
        user_name = user.get("login")
        repos_url = f"{GITEA_API}/users/{user_name}/repos"
        repos_response = requests.get(repos_url, auth=HTTPBasicAuth(GITEA_USERNAME, GITEA_PASSWORD))
        if repos_response.status_code == 200:
            repos = repos_response.json()
            if repos:
                print(f"  用户 {user_name} 的仓库：{[r.get('name') for r in repos]}")
else:
    print(f"获取用户失败：{response.status_code}")
