# Harbor Robot Account 配置指南

**Story 0.6: Harbor 镜像仓库**
**版本:** 1.0
**日期:** 2026-03-14

---

## 📋 目录

1. [概述](#概述)
2. [Robot Account 与用户账号的区别](#robot-account-与用户账号的区别)
3. [创建 Robot Account](#创建-robot-account)
4. [使用 Robot Account](#使用-robot-account)
5. [Kubernetes 集成](#kubernetes-集成)
6. [安全最佳实践](#安全最佳实践)

---

## 概述

Robot Account 是 Harbor 提供的机器账户，用于自动化系统（如 CI/CD Pipeline、ArgoCD 等）访问 Harbor 镜像仓库。

### 适用场景

- ✅ CI/CD Pipeline 推送构建镜像
- ✅ ArgoCD 拉取镜像进行部署
- ✅ 备份系统拉取镜像进行备份
- ✅ 自动化测试环境拉取镜像

---

## Robot Account 与用户账号的区别

| 特性 | Robot Account | 用户账号 |
|------|--------------|---------|
| 登录 Web 界面 | ❌ 不支持 | ✅ 支持 |
| 权限范围 | 项目级精确控制 | 全局或项目级 |
| Token 过期 | 可设置永不过期 | 会话制 |
| 适用场景 | 机器对机器 | 人工操作 |
| 审计追踪 | 独立审计日志 | 用户审计日志 |

---

## 创建 Robot Account

### 方式 1: 通过 Harbor Web 界面（推荐）

1. **登录 Harbor**
   - 访问：http://harbor.harbor.svc.cluster.local
   - 用户名：`admin`
   - 密码：`Harbor@2026Secure!`

2. **创建项目（如果不存在）**
   - 点击"项目" → "新建项目"
   - 项目名称：`sisys`
   - 访问级别：私有

3. **创建 Robot Account**
   - 进入 `sisys` 项目
   - 点击"机器人账户" → "新建机器人账户"
   - 填写信息：
     - 名称：`gitea-runner-push`
     - 过期时间：永不过期
     - 权限：
       - ✅ 推送镜像
       - ✅ 拉取镜像
       - ✅ 读取制品
       - ✅ 创建标签

4. **保存 Token**
   - 创建成功后，**立即复制 Token**
   - Token 格式：`robot$gitea-runner-push:xxxxxxxxxxxxxxxxxxxx`
   - ⚠️ **Token 只显示一次，丢失需重新创建**

### 方式 2: 通过 Harbor API

```bash
#!/bin/bash

# 配置变量
# pragma: allowlist secret
HARBOR_URL="http://harbor.harbor.svc.cluster.local"
# pragma: allowlist secret
HARBOR_USER="admin"
# pragma: allowlist secret
HARBOR_PASSWORD="Harbor@2026Secure!"
PROJECT_NAME="sisys"

# 获取项目 ID
PROJECT_ID=$(curl -s -u "$HARBOR_USER:$HARBOR_PASSWORD" \
  "$HARBOR_URL/api/v2.0/projects?name=$PROJECT_NAME" | \
  jq -r '.[0].project_id')

echo "项目 ID: $PROJECT_ID"

# 创建 Robot Account
RESPONSE=$(curl -s -u "$HARBOR_USER:$HARBOR_PASSWORD" \
  -X POST "$HARBOR_URL/api/v2.0/robots" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "gitea-runner-push",
    "description": "Gitea Runner 推送镜像到 Harbor",
    "duration": -1,
    "level": "project",
    "permissions": [
      {
        "kind": "project",
        "namespace": "'$PROJECT_NAME'",
        "access": [
          {"resource": "repository", "action": "push"},
          {"resource": "repository", "action": "pull"},
          {"resource": "artifact", "action": "read"},
          {"resource": "artifact", "action": "create"},
          {"resource": "tag", "action": "create"},
          {"resource": "tag", "action": "read"}
        ]
      }
    ]
  }')

echo "创建响应:"
echo "$RESPONSE" | jq .

# 提取 Token
TOKEN=$(echo "$RESPONSE" | jq -r '.secret')
echo ""
echo "=========================================="
echo "Robot Account Token: $TOKEN"
echo "=========================================="
echo "⚠️ 请立即保存此 Token，关闭后无法再次查看！"
```

---

## 使用 Robot Account

### Docker 登录

```bash
# 使用 Robot Account 登录
docker login harbor.sisys.local -u robot$gitea-runner-push -p <YOUR_TOKEN>

# 验证登录
docker login harbor.sisys.local
# Username: robot$gitea-runner-push
# Password: <YOUR_TOKEN>
```

### 推送镜像

```bash
# 构建镜像
docker build -t harbor.sisys.local/sisys/myapp:latest .

# 推送镜像
docker push harbor.sisys.local/sisys/myapp:latest

# 推送带标签的镜像
docker tag harbor.sisys.local/sisys/myapp:latest harbor.sisys.local/sisys/myapp:v1.0.0
docker push harbor.sisys.local/sisys/myapp:v1.0.0
```

### 拉取镜像

```bash
# 拉取镜像
docker pull harbor.sisys.local/sisys/myapp:latest
```

---

## Kubernetes 集成

### 创建 Image Pull Secret

```bash
# 使用 Robot Account 创建 Kubernetes Secret
kubectl create secret docker-registry harbor-robot-secret \
  --docker-server=harbor.sisys.local \
  --docker-username=robot$gitea-runner-push \
  --docker-password=<YOUR_TOKEN> \
  --docker-email=devops@sisys.local \
  -n default
```

### 在 Deployment 中使用

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      imagePullSecrets:
      - name: harbor-robot-secret
      containers:
      - name: myapp
        image: harbor.sisys.local/sisys/myapp:latest
        ports:
        - containerPort: 8080
```

### 在 ArgoCD 中使用

```yaml
# Application 配置
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp
  namespace: argocd
spec:
  source:
    repoURL: https://gitea.sisys.local/sisys/manifests.git
    targetRevision: HEAD
    path: myapp
  destination:
    server: https://kubernetes.default.svc
    namespace: default
  imagePullSecrets:
  - harbor-robot-secret
```

---

## 安全最佳实践

### 1. Token 管理

- ✅ **立即保存**: Token 只显示一次，创建后立即保存
- ✅ **安全存储**: 使用 Kubernetes Secret 或 Vault 存储 Token
- ✅ **定期轮换**: 建议每 90 天轮换一次 Token
- ❌ **不要硬编码**: 不要在代码或配置文件中硬编码 Token

### 2. 权限最小化

- ✅ 只授予必要的权限（如只读、只推）
- ✅ 使用项目级权限，避免系统级权限
- ✅ 为不同用途创建不同的 Robot Account

### 3. 审计与监控

- ✅ 启用 Harbor 审计日志
- ✅ 定期检查 Robot Account 使用情况
- ✅ 设置异常访问告警

### 4. Token 过期策略

| 用途 | 建议过期时间 |
|------|-------------|
| CI/CD Pipeline | 永不过期（-1） |
| 临时测试 | 7-30 天 |
| 备份系统 | 365 天 |
| 外部合作 | 90 天 |

---

## 故障排查

### 问题 1: 401 Unauthorized

**症状**: `unauthorized: authentication required`

**原因**:
- Token 过期或无效
- Robot Account 被禁用
- 权限不足

**解决**:
```bash
# 验证 Token
docker login harbor.sisys.local -u robot$gitea-runner-push -p <TOKEN>

# 检查 Robot Account 状态
curl -u admin:Harbor@2026Secure! \
  http://harbor.harbor.svc.cluster.local/api/v2.0/robots
```

### 问题 2: 403 Forbidden

**症状**: `denied: requested access to the resource is denied`

**原因**:
- Robot Account 没有目标项目的权限
- 权限配置不正确

**解决**:
```bash
# 检查 Robot Account 权限
curl -u admin:Harbor@2026Secure! \
  http://harbor.harbor.svc.cluster.local/api/v2.0/robots/{robot_id} | jq .

# 重新创建具有正确权限的 Robot Account
```

### 问题 3: 证书错误

**症状**: `x509: certificate signed by unknown authority`

**原因**:
- 使用自签名证书
- Docker 未信任 Harbor 证书

**解决**:
```bash
# 开发环境：配置 Docker 信任
sudo mkdir -p /etc/docker/certs.d/harbor.sisys.local
sudo cp ca.crt /etc/docker/certs.d/harbor.sisys.local/

# 或（仅开发环境）
echo '{ "insecure-registries": ["harbor.sisys.local"] }' | \
  sudo tee /etc/docker/daemon.json
sudo systemctl restart docker
```

---

## 参考文档

- [Harbor Robot Account 官方文档](https://goharbor.io/docs/2.14.0/administration/manage-users/managing-robot-accounts/)
- [Harbor API 文档](https://goharbor.io/docs/2.14.0/swag.v2/)
- [Kubernetes Image Pull Secrets](https://kubernetes.io/docs/tasks/configure-pod-container/pull-image-private-registry/)

---

**文档维护者:** DevOps Team
**最后更新:** 2026-03-14
