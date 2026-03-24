# CI/CD Secrets 配置指南

## 目录

1. [概述](#概述)
2. [Gitea Secrets 配置](#gitea-secrets-配置)
3. [Kubernetes Secrets 配置](#kubernetes-secrets-配置)
4. [Harbor 配置](#harbor-配置)
5. [安全最佳实践](#安全最佳实践)

---

## 概述

本指南说明如何安全地配置 CI/CD Pipeline 所需的敏感信息。

### Secrets 分类

| 类别 | 示例 | 存储位置 |
|------|------|----------|
| **认证凭据** | Harbor 密码、API Key | Gitea Secrets |
| **Kubeconfig** | Kubernetes 配置 | Gitea Secrets (Base64) |
| **数据库连接** | 数据库 URL | Kubernetes Secrets |
| **通知配置** | Webhook URL | Gitea Secrets |

---

## Gitea Secrets 配置

### 1. Harbor 凭据

**步骤**:

1. 进入 Gitea 仓库
2. 点击 **设置** → **Actions** → **Secrets**
3. 添加以下 Secrets:

```yaml
# Harbor 用户名
Name: HARBOR_USERNAME
Value: admin
Secret: ✅

# Harbor 密码
Name: HARBOR_PASSWORD
Value: <your-secure-password>
Secret: ✅
```

**验证**:

```bash
# 在 Pipeline 中测试
docker login harbor.sisys.local -u $HARBOR_USERNAME -p $HARBOR_PASSWORD
```

### 2. Kubernetes 配置

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

### 3. 通知配置 (可选)

```yaml
# 通用通知 Webhook
Name: NOTIFICATION_WEBHOOK
Value: https://hooks.slack.com/services/xxx
Secret: ✅

# 生产环境通知
Name: PRODUCTION_NOTIFICATION_WEBHOOK
Value: https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
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

### 1. 创建项目

```bash
# 通过 Harbor UI 创建项目
# 项目名称：sisys
# 访问级别：私有
# 内容信任：启用
# 漏洞扫描：自动
```

### 2. 配置机器人账户

**步骤**:

1. 登录 Harbor UI
2. 进入项目 `sisys`
3. 点击 **机器人账户** → **+ 机器人账户**
4. 配置:
   - 名称：`ci-pipeline`
   - 权限：推送、拉取、删除
   - 有效期：永久

**使用机器人账户**:

```yaml
# Gitea Secrets
HARBOR_USERNAME: robot$ci-pipeline
HARBOR_PASSWORD: <robot-token>
```

### 3. 配置漏洞扫描

```yaml
# Harbor UI → 管理 → 配置 → 漏洞扫描
# 自动扫描：启用
# 扫描策略：每日
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
