# CI/CD Secrets 配置指南

## 目录

1. [概述](#概述)
2. [现有配置评估](#现有配置评估)
3. [Gitea Secrets 配置](#gitea-secrets-配置)
4. [Kubernetes Secrets 配置](#kubernetes-secrets-配置)
5. [Harbor 配置](#harbor-配置)
6. [安全最佳实践](#安全最佳实践)

---

## 概述

本指南说明如何安全地配置 CI/CD Pipeline 所需的敏感信息。

---

## 现有配置评估

### ✅ 可用配置

| 配置项 | 值/说明 | 状态 | 用途 |
|--------|---------|------|------|
| **Gitea Admin** | `gitea_admin` / `Admin@123456` | ✅ 可用 | 管理员访问 |
| **Gitea Write Token** | `1f182aca3d38b66f7e49c034d98fb15bf02434b7` | ✅ 可用 | CI/CD 推送 (write:repository + write:user) |
| **Gitea Read Token** | `1a8e0eb9d7b712558efe03ad5fe9cda6ad980bc8` | ✅ 可用 | 只读操作 |
| **Gitea Runner Token** | `2qsfG21yaoJHUPG1E8JoikRiNJXhVrrbKKGzFMzJ` | ✅ 可用 | 组织级工作流运行器 |
| **Harbor Admin** | `admin` / `Admin@123456` | ✅ 可用 | 管理员访问 |
| **Harbor Robot (ArgoCD)** | `robot$sisys+argocd-pull` | ✅ 可用 | ArgoCD 拉取镜像 |
| **Harbor Robot Token** | `mMbDaASmDi2fE1CIIFYMyZWorAQYLQ1j` | ✅ 可用 | ArgoCD 拉取凭据 |
| **Harbor Robot (Gitea)** | `robot$sisys+gitea-runner-push` | ✅ 可用 | Gitea Runner 推送镜像 |
| **Gitea Runner Secret** | `gXuC2AcG1231JB8mfZmyCnhDKy6nKcRd` | ✅ 可用 | Gitea Runner 推送凭据 |

### 📋 需要配置

| 配置项 | 说明 | 优先级 |
|--------|------|--------|
| **KUBE_CONFIG_TEST** | 测试环境 Kubeconfig | 🔴 高 |
| **KUBE_CONFIG_PRODUCTION** | 生产环境 Kubeconfig | 🔴 高 |
| **HARBOR_USERNAME** | CI Pipeline 推送用户名 | 🟡 中 (使用 robot$sisys+gitea-runner-push) |
| **HARBOR_PASSWORD** | CI Pipeline 推送密码 | 🟡 中 (使用 gXuC2AcG1231JB8mfZmyCnhDKy6nKcRd) |

### 推荐配置映射

```yaml
# Gitea Secrets (仓库级别)
HARBOR_USERNAME: "robot$sisys+gitea-runner-push"
HARBOR_PASSWORD: "gXuC2AcG1231JB8mfZmyCnhDKy6nKcRd"
KUBE_CONFIG_TEST: "<需要配置>"
KUBE_CONFIG_PRODUCTION: "<需要配置>"

# Gitea Variables (仓库级别)
HARBOR_REGISTRY: "harbor.sisys.local"
GPU_ENABLED: "false"  # 根据实际 GPU 环境配置
```

---

## Gitea Secrets 配置

### 1. Harbor 凭据 (使用现有 Robot Account)

**步骤**:

1. 进入 Gitea 仓库
2. 点击 **设置** → **Actions** → **Secrets**
3. 添加以下 Secrets:

```yaml
# Harbor 用户名 (使用已有的 Robot Account)
Name: HARBOR_USERNAME
Value: robot$sisys+gitea-runner-push
Secret: ✅

# Harbor 密码 (使用已有的 Secret)
Name: HARBOR_PASSWORD
Value: gXuC2AcG1231JB8mfZmyCnhDKy6nKcRd
Secret: ✅
```

**验证**:

```bash
# 在 Pipeline 中测试
docker login harbor.sisys.local -u $HARBOR_USERNAME -p $HARBOR_PASSWORD
```

### 2. Kubernetes 配置 (需要配置)

**获取 Kubeconfig**:

```bash
# 导出当前 kubeconfig
cat ~/.kube/config

# Base64 编码 (用于 Gitea Secrets)
cat ~/.kube/config | base64 -w 0
```

**配置 Secrets**:

```yaml
# 测试环境
Name: KUBE_CONFIG_TEST
Value: <base64-encoded-kubeconfig>
Secret: ✅

# 生产环境
Name: KUBE_CONFIG_PRODUCTION
Value: <base64-encoded-kubeconfig>
Secret: ✅
```

**验证**:

```bash
# 解码测试
echo "<base64-string>" | base64 -d > /tmp/test-kubeconfig
KUBECONFIG=/tmp/test-kubeconfig kubectl get pods
```

### 3. 使用现有 Gitea Token

**组织级工作流 Token**:

```yaml
# 已配置的 Runner Token
Name: GITEA_RUNNER_TOKEN
Value: 2qsfG21yaoJHUPG1E8JoikRiNJXhVrrbKKGzFMzJ
Secret: ✅
```

**只读 Token (用于拉取代码)**:

```yaml
# 只读访问
Name: GITEA_READ_TOKEN
Value: 1a8e0eb9d7b712558efe03ad5fe9cda6ad980bc8
Secret: ✅
```

**写入 Token (用于推送/创建 Release)**:

```yaml
# 写入访问
Name: GITEA_WRITE_TOKEN
Value: 1f182aca3d38b66f7e49c034d98fb15bf02434b7
Secret: ✅
```

---

## Kubernetes Secrets 配置

### 1. 创建 Secrets

**测试环境**:

```bash
# 创建数据库密码
kubectl create secret generic sisys-secrets \
  --from-literal=database-url='postgresql://user:password@host:5432/db' \
  --from-literal=redis-url='redis://host:6379' \
  -n sisys-test

# 从文件创建
kubectl create secret generic sisys-secrets \
  --from-file=.env=.env.test \
  -n sisys-test
```

**生产环境**:

```bash
kubectl create secret generic sisys-secrets-prod \
  --from-literal=database-url='postgresql://user:password@host:5432/db' \
  --from-literal=redis-url='redis://host:6379' \
  -n sisys-prod
```

### 2. 创建 Harbor 镜像拉取密钥

```bash
# 创建 Docker Registry Secret
kubectl create secret docker-registry harbor-secret \
  --docker-server=harbor.sisys.local \
  --docker-username=admin \
  --docker-password=<password> \
  --docker-email=admin@sisys.local \
  -n sisys-test

kubectl create secret docker-registry harbor-secret \
  --docker-server=harbor.sisys.local \
  --docker-username=admin \
  --docker-password=<password> \
  --docker-email=admin@sisys.local \
  -n sisys-prod
```

### 3. 验证 Secrets

```bash
# 列出所有 Secrets
kubectl get secrets -n sisys-test

# 查看 Secret 详情
kubectl get secret sisys-secrets -n sisys-test -o yaml

# 解码查看
kubectl get secret sisys-secrets -n sisys-test -o jsonpath='{.data}' | jq 'with_entries(.value |= @base64d)'
```

---

## Harbor 配置

### 1. 现有 Robot Account 配置

**已配置的 Robot Account**:

| 名称 | 权限 | Token | 用途 |
|------|------|-------|------|
| `robot$sisys+argocd-pull` | Pull (只读) | `mMbDaASmDi2fE1CIIFYMyZWorAQYLQ1j` | ArgoCD 拉取镜像 |
| `robot$sisys+gitea-runner-push` | Push + Pull | `gXuC2AcG1231JB8mfZmyCnhDKy6nKcRd` | Gitea Runner 推送镜像 |

**验证命令**:

```bash
# 验证 ArgoCD Robot
docker login harbor.sisys.local -u 'robot$sisys+argocd-pull' -p 'mMbDaASmDi2fE1CIIFYMyZWorAQYLQ1j'

# 验证 Gitea Runner Robot
docker login harbor.sisys.local -u 'robot$sisys+gitea-runner-push' -p 'gXuC2AcG1231JB8mfZmyCnhDKy6nKcRd'
```

### 2. 项目配置

**步骤**:

1. 登录 Harbor UI (https://harbor.sisys.local)
2. 使用管理员账号登录：`admin` / `Admin@123456`
3. 进入项目 `sisys`
4. 点击 **机器人账户** 验证现有配置

**权限说明**:

```json
// robot$sisys+gitea-runner-push 权限
{
  "permissions": [{
    "access": [
      {"action": "create", "resource": "artifact"},
      {"action": "pull", "resource": "repository"},
      {"action": "push", "resource": "repository"},
      {"action": "read", "resource": "artifact"}
    ],
    "kind": "project",
    "namespace": "sisys"
  }]
}
```

### 3. 配置漏洞扫描

```yaml
# Harbor UI → 管理 → 配置 → 漏洞扫描
# 自动扫描：启用
# 扫描策略：每日
```

### 4. Kubernetes Secret 配置

**已存储的 Secret**:

```yaml
# ArgoCD 拉取密钥 (已存储)
apiVersion: v1
kind: Secret
metadata:
  name: harbor-secret
  namespace: sisys-test
type: kubernetes.io/dockerconfigjson
data:
  .dockerconfigjson: <base64-encoded-json>
```

**验证 Secret**:

```bash
# 查看 Secret
kubectl get secret harbor-secret -n sisys-test -o yaml

# 解码验证
kubectl get secret harbor-secret -n sisys-test -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d | jq
```

---

## 安全最佳实践

### 1. 密码管理

```bash
# ✅ 好：使用密码生成器
openssl rand -base64 32

# ✅ 好：使用 1Password/Bitwarden
# ❌ 坏：使用弱密码
password123
```

### 2. Secret 轮换

```bash
# 定期更新 Harbor 密码 (建议每 90 天)
# 1. 生成新密码
NEW_PASSWORD=$(openssl rand -base64 32)

# 2. 更新 Harbor
# Harbor UI → 用户设置 → 修改密码

# 3. 更新 Gitea Secrets
# Gitea UI → 设置 → Actions → Secrets → 编辑

# 4. 更新 Kubernetes Secrets
kubectl create secret generic sisys-secrets \
  --from-literal=database-password=$NEW_PASSWORD \
  -n sisys-test --dry-run=client -o yaml | kubectl apply -f -
```

### 3. 访问控制

```yaml
# 最小权限原则
# CI Pipeline: 只授予推送权限
# CD Pipeline: 只授予部署到测试环境权限
# 生产部署：需要手动审批
```

### 4. 审计日志

```bash
# 启用 Gitea 审计日志
# Gitea UI → 管理 → 审计日志

# 启用 Kubernetes 审计
# /etc/kubernetes/manifests/kube-apiserver.yaml
# --audit-log-path=/var/log/kubernetes/audit.log
```

### 5. 加密传输

```yaml
# 始终使用 HTTPS
HARBOR_REGISTRY: https://harbor.sisys.local

# Kubernetes 使用 TLS
kubectl create secret tls tls-secret \
  --cert=path/to/tls.crt \
  --key=path/to/tls.key \
  -n sisys-test
```

---

## 环境变量参考

### CI Pipeline 环境变量

```yaml
env:
  # 必需
  HARBOR_REGISTRY: harbor.sisys.local
  HARBOR_PROJECT: sisys
  PYTHON_VERSION: "3.11"
  
  # 可选
  GPU_ENABLED: "true"
  CUDA_VERSION: "12.8"
```

### CD Pipeline 环境变量

```yaml
env:
  # 必需
  HARBOR_REGISTRY: harbor.sisys.local
  ARGOCD_SERVER: argocd.sisys.local
  
  # 环境特定
  DEPLOY_ENV: test  # 或 production
```

---

## 故障排除

### 1. Secret 无法访问

**症状**: Pipeline 报错 `secret not found`

**解决方案**:
```bash
# 验证 Secret 存在
kubectl get secret sisys-secrets -n sisys-test

# 检查 Secret 名称是否匹配
grep -r "sisys-secrets" deployments/k8s/
```

### 2. Harbor 认证失败

**症状**: `unauthorized: authentication required`

**解决方案**:
```bash
# 验证凭据
docker login harbor.sisys.local -u $HARBOR_USERNAME -p $HARBOR_PASSWORD

# 检查机器人账户权限
# Harbor UI → 项目 → 机器人账户
```

### 3. Kubeconfig 过期

**症状**: `Unable to connect to the server: x509: certificate has expired`

**解决方案**:
```bash
# 更新 kubeconfig
kubectl config view --raw > ~/.kube/config

# 重新编码
cat ~/.kube/config | base64 -w 0

# 更新 Gitea Secret
```

---

## 检查清单

在部署前，确认以下配置已完成：

- [ ] Harbor 项目已创建
- [ ] Harbor 机器人账户已配置
- [ ] Gitea Secrets 已配置
  - [ ] HARBOR_USERNAME
  - [ ] HARBOR_PASSWORD
  - [ ] KUBE_CONFIG_TEST
  - [ ] KUBE_CONFIG_PRODUCTION
- [ ] Kubernetes Secrets 已创建
  - [ ] sisys-secrets (测试)
  - [ ] sisys-secrets-prod (生产)
  - [ ] harbor-secret (镜像拉取)
- [ ] Harbor 漏洞扫描已启用
- [ ] ArgoCD 已配置

---

## 相关文档

- [CI/CD Pipeline 模板使用指南](./CI_CD_PIPELINE_TEMPLATE.md)
- [故障排除指南](./CI_CD_TROUBLESHOOTING.md)
