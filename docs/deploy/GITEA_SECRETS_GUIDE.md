# Gitea Secrets 管理使用指南

**Story 0.5**: Gitea 代码托管
**安全验收标准**: 密钥存储于 Kubernetes Secret，无明文配置
**最后更新**: 2026-03-14

---

## 📋 目录

1. [概述](#概述)
2. [文件说明](#文件说明)
3. [开发环境快速部署](#开发环境快速部署)
4. [生产环境部署](#生产环境部署)
5. [使用外部密钥管理](#使用外部密钥管理)
6. [最佳实践](#最佳实践)
7. [故障排查](#故障排查)

---

## 概述

### 安全原则

1. **最小权限**: 仅授予必要的访问权限
2. **分离关注**: 开发/测试/生产环境使用不同的密钥
3. **自动轮换**: 定期更新密钥（建议 90 天）
4. **审计日志**: 记录所有密钥访问操作
5. **加密存储**: 生产环境使用加密的密钥管理

### 文件结构

```
deploy/kubernetes/gitea/
├── secrets.yaml              # 生产环境模板（占位符，不可直接使用）
├── secrets-example.yaml      # 开发环境示例（包含示例值）
└── ...
```

---

## 文件说明

### 1. `secrets.yaml` - 生产环境模板

**用途**: 生产环境部署模板，使用环境变量占位符

**特点**:
- ✅ 不包含实际密钥值
- ✅ 可以安全提交到 git
- ✅ 必须配合 CI/CD 或外部密钥管理使用

**占位符说明**:

| 占位符 | 用途 | 生成方式 |
|--------|------|---------|
| `${GITEA_ADMIN_PASSWORD}` | 管理员密码 | `openssl rand -base64 24` |
| `${GITEA_SECRET_KEY}` | Gitea 应用密钥 | `openssl rand -base64 32` |
| `${GITEA_INTERNAL_TOKEN}` | 内部 Token | `openssl rand -base64 32` |
| `${GITEA_JWT_SECRET}` | OAuth2 JWT 密钥 | `openssl rand -base64 32` |
| `${GITEA_DB_PASSWORD}` | 数据库密码 | `openssl rand -base64 24` |

### 2. `secrets-example.yaml` - 开发环境示例

**用途**: 开发/测试环境快速部署

**特点**:
- ⚠️ 包含示例密钥值
- ⚠️ **不可提交到 git**（已在 .gitignore 中排除）
- ⚠️ 仅用于开发环境，生产环境禁止使用

**警告**:
```yaml
# ❌ 禁止在生产环境使用
password: "Admin@123456"  # pragma: allowlist secret # 仅开发环境
```

---

## 开发环境快速部署

### 方法 1: 使用示例文件（最快）

```bash
# 1. 复制示例文件
cd deploy/kubernetes/gitea
cp secrets-example.yaml secrets-values.yaml

# 2. （可选）修改密码为自定义值
# 编辑 secrets-values.yaml

# 3. 应用配置
kubectl apply -f secrets-values.yaml -n gitea

# 4. 验证
kubectl get secrets -n gitea
```

### 方法 2: 使用命令行生成（推荐）

```bash
# 1. 生成随机密码
ADMIN_PASSWORD=$(openssl rand -base64 24)
SECRET_KEY=$(openssl rand -base64 32)
INTERNAL_TOKEN=$(openssl rand -base64 32)
JWT_SECRET=$(openssl rand -base64 32)
DB_PASSWORD=$(openssl rand -base64 24)

# 2. 创建 Secret
kubectl create secret generic gitea-admin-secret \
  --from-literal=username=gitea_admin \
  --from-literal=password="$ADMIN_PASSWORD" \
  --from-literal=email=admin@sisys.local \
  -n gitea

kubectl create secret generic gitea-app-secret \
  --from-literal=secret-key="$SECRET_KEY" \
  --from-literal=internal-token="$INTERNAL_TOKEN" \
  --from-literal=jwt-secret="$JWT_SECRET" \
  -n gitea

kubectl create secret generic gitea-postgresql-secret \
  --from-literal=username=gitea \
  --from-literal=password="$DB_PASSWORD" \
  --from-literal=admin-password="$ADMIN_PASSWORD" \
  --from-literal=postgres-password="$DB_PASSWORD" \
  -n gitea

# 3. 验证
kubectl get secrets -n gitea -o wide
```

### 方法 3: 使用 Helm values 注入

```bash
# 1. 创建 values-secrets.yaml
cat > values-secrets.yaml <<EOF
gitea:
  adminUser: gitea_admin
  adminPassword: "$(openssl rand -base64 24)"
  adminEmail: admin@sisys.local

  config:
    SECURITY:
      SECRET_KEY: "$(openssl rand -base64 32)"
      INTERNAL_TOKEN: "$(openssl rand -base64 32)"
      JWT_SECRET: "$(openssl rand -base64 32)"

postgresql:
  auth:
    password: "$(openssl rand -base64 24)"
    postgresPassword: "$(openssl rand -base64 24)"
EOF

# 2. 部署时注入
helm install gitea gitea-charts/gitea -n gitea -f values-secrets.yaml
```

---

## 生产环境部署

### 要求

- ✅ 所有密钥必须使用强随机字符串
- ✅ 密钥必须通过外部密钥管理注入
- ✅ 禁止在 git 中存储明文密钥
- ✅ 启用密钥轮换策略

### 方法 1: 使用 CI/CD 注入（推荐）

#### GitHub Actions 示例

```yaml
# .github/workflows/deploy-gitea.yml
name: Deploy Gitea

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Generate Secrets
        run: |
          echo "ADMIN_PASSWORD=$(openssl rand -base64 24)" >> $GITHUB_ENV
          echo "SECRET_KEY=$(openssl rand -base64 32)" >> $GITHUB_ENV
          echo "INTERNAL_TOKEN=$(openssl rand -base64 32)" >> $GITHUB_ENV
          echo "JWT_SECRET=$(openssl rand -base64 32)" >> $GITHUB_ENV
          echo "DB_PASSWORD=$(openssl rand -base64 24)" >> $GITHUB_ENV

      - name: Create Kubernetes Secrets
        run: |
          kubectl create secret generic gitea-admin-secret \
            --from-literal=username=gitea_admin \
            --from-literal=password="$ADMIN_PASSWORD" \
            --from-literal=email=admin@sisys.local \
            -n gitea --dry-run=client -o yaml | kubectl apply -f -

          # 应用其他 Secret...

      - name: Deploy Gitea
        run: |
          helm install gitea gitea-charts/gitea -n gitea -f values.yaml
```

#### GitLab CI 示例

```yaml
# .gitlab-ci.yml
deploy:
  stage: deploy
  script:
    - kubectl create secret generic gitea-admin-secret \
        --from-literal=username=gitea_admin \
        --from-literal=password="$CI_GITEA_ADMIN_PASSWORD" \
        --from-literal=email=admin@sisys.local \
        -n gitea --dry-run=client -o yaml | kubectl apply -f -
  variables:
    CI_GITEA_ADMIN_PASSWORD:
      value: ""  # 在 GitLab CI/CD 设置中配置
    CI_GITEA_SECRET_KEY:
      value: ""  # 在 GitLab CI/CD 设置中配置
```

### 方法 2: 使用 SealedSecrets

**安装 SealedSecrets**:

```bash
# 1. 安装 SealedSecrets Controller
helm repo add sealed-secrets https://bitnami-labs.github.io/sealed-secrets
helm install sealed-secrets sealed-secrets/sealed-secrets \
  --namespace kube-system \
  --set-string fullnameOverride=sealed-secrets-controller

# 2. 安装 kubeseal CLI
# macOS
brew install kubeseal

# Linux
wget https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.24.0/kubeseal-0.24.0-linux-amd64.tar.gz
tar -xzf kubeseal-0.24.0-linux-amd64.tar.gz
sudo install -m 755 kubeseal /usr/local/bin/kubeseal
```

**创建 SealedSecret**:

```bash
# 1. 创建普通 Secret（本地）
kubectl create secret generic gitea-admin-secret \
  --from-literal=username=gitea_admin \
  --from-literal=password="$(openssl rand -base64 24)" \
  --from-literal=email=admin@sisys.local \
  -n gitea --dry-run=client -o yaml > gitea-admin-secret.yaml

# 2. 加密为 SealedSecret
kubeseal --format yaml < gitea-admin-secret.yaml > gitea-admin-secret-sealed.yaml

# 3. 提交到 git
git add gitea-admin-secret-sealed.yaml
git commit -m "Add sealed Gitea admin secret"

# 4. 部署到集群
kubectl apply -f gitea-admin-secret-sealed.yaml -n gitea

# 5. 验证（SealedSecret Controller 会自动解密）
kubectl get secrets gitea-admin-secret -n gitea
```

### 方法 3: 使用 HashiCorp Vault

**安装 Vault**:

```bash
# 1. 部署 Vault（开发模式）
helm repo add hashicorp https://helm.releases.hashicorp.com
helm install vault hashicorp/vault --set server.dev.enabled=true -n vault

# 2. 初始化 Vault
kubectl exec -it vault-0 -n vault -- vault operator init
```

**配置 Vault Secret**:

```bash
# 1. 登录 Vault
kubectl exec -it vault-0 -n vault -- vault login

# 2. 启用 KV Secret 引擎
vault secrets enable -path=secret kv-v2

# 3. 写入 Secret
vault kv put secret/gitea/admin \
  username=gitea_admin \
  password="$(openssl rand -base64 24)" \
  email=admin@sisys.local

vault kv put secret/gitea/app \
  secret_key="$(openssl rand -base64 32)" \
  internal_token="$(openssl rand -base64 32)" \
  jwt_secret="$(openssl rand -base64 32)"

# 4. 配置 ExternalSecrets Operator 同步到 Kubernetes
```

**使用 ExternalSecrets**:

```yaml
# deploy/kubernetes/gitea/external-secret.yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: gitea-admin-secret
  namespace: gitea
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: ClusterSecretStore
  target:
    name: gitea-admin-secret
    creationPolicy: Owner
  data:
    - secretKey: username
      remoteRef:
        key: gitea/admin
        property: username
    - secretKey: password
      remoteRef:
        key: gitea/admin
        property: password
    - secretKey: email
      remoteRef:
        key: gitea/admin
        property: email
```

---

## 使用外部密钥管理

### AWS Secrets Manager

```bash
# 1. 创建 Secret
aws secretsmanager create-secret \
  --name gitea/admin \
  --secret-string '{"username":"gitea_admin","password":"'"$(openssl rand -base64 24)"'","email":"admin@sisys.local"}'

# 2. 使用 IAM Role for ServiceAccount (IRSA) 访问
# 参考：https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html
```

### Azure Key Vault

```bash
# 1. 创建 Secret
az keyvault secret set \
  --vault-name my-keyvault \
  --name gitea-admin-password \
  --value "$(openssl rand -base64 24)"

# 2. 使用 Azure AD Pod Identity 访问
```

### Google Secret Manager

```bash
# 1. 创建 Secret
echo -n "$(openssl rand -base64 24)" | \
  gcloud secrets create gitea-admin-password \
  --data-file=- \
  --project my-project
```

---

## 最佳实践

### 1. 密码复杂度要求

```yaml
# 管理员密码要求
- 最小长度：12 位
- 必须包含：大写字母 + 小写字母 + 数字 + 特殊符号
- 密码历史：不得重复最近 5 次密码
- 轮换周期：90 天

# 生成符合要求的密码
openssl rand -base64 24 | \
  base64 | \
  cut -c1-16
```

### 2. 密钥轮换

```bash
# 创建轮换脚本
cat > rotate-secrets.sh <<'EOF'
#!/bin/bash

NAMESPACE="gitea"
ROTATION_DATE=$(date +%Y-%m-%d)

echo "=== Gitea Secrets 轮换 ($ROTATION_DATE) ==="

# 生成新密码
NEW_PASSWORD=$(openssl rand -base64 24)

# 更新 Secret
kubectl create secret generic gitea-admin-secret \
  --from-literal=password="$NEW_PASSWORD" \
  -n $NAMESPACE \
  --dry-run=client -o yaml | \
  kubectl patch secret gitea-admin-secret -n $NAMESPACE --patch-file /dev/stdin

# 重启 Gitea Pod 以应用新密钥
kubectl rollout restart deployment gitea -n $NAMESPACE

echo "✓ 密钥轮换完成"
echo "⚠️  请更新密码管理工具中的记录"
EOF

chmod +x rotate-secrets.sh
```

### 3. 审计日志

```bash
# 启用 Kubernetes 审计日志
# /etc/kubernetes/audit-policy.yaml
apiVersion: audit.k8s.io/v1
kind: Policy
rules:
  - level: Metadata
    resources:
      - group: ""
        resources: ["secrets"]
    verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]

# 查看 Secret 访问日志
kubectl logs -n kube-system kube-apiserver | \
  grep "secrets" | \
  grep "gitea"
```

### 4. 访问控制

```yaml
# 配置 RBAC
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: gitea-secret-manager
  namespace: gitea
rules:
  - apiGroups: [""]
    resources: ["secrets"]
    verbs: ["get", "list", "watch", "create", "update", "patch"]
  - apiGroups: [""]
    resources: ["secrets"]
    resourceNames: ["gitea-admin-secret", "gitea-app-secret"]
    verbs: ["delete"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: gitea-secret-manager-binding
  namespace: gitea
subjects:
  - kind: ServiceAccount
    name: gitea-admin
    namespace: gitea
roleRef:
  kind: Role
  name: gitea-secret-manager
  apiGroup: rbac.authorization.k8s.io
```

---

## 故障排查

### 问题 1: Secret 创建失败

```bash
# 检查命名空间
kubectl get namespaces | grep gitea

# 检查权限
kubectl auth can-i create secrets -n gitea

# 查看详细错误
kubectl apply -f secrets.yaml -n gitea -v=10
```

### 问题 2: Gitea 无法启动

```bash
# 检查 Secret 是否存在
kubectl get secrets -n gitea | grep gitea

# 检查 Secret 内容
kubectl get secret gitea-admin-secret -n gitea -o yaml

# 检查 Gitea Pod 日志
kubectl logs -n gitea deployment/gitea | grep -i secret
kubectl logs -n gitea deployment/gitea | grep -i password
```

### 问题 3: 密码认证失败

```bash
# 重置管理员密码
kubectl exec -it -n gitea deployment/gitea -- \
  gitea admin change-password \
  --username gitea_admin \
  --password "$(openssl rand -base64 24)"

# 或手动更新 Secret
kubectl create secret generic gitea-admin-secret \
  --from-literal=password="NewSecure@Password123" \  # pragma: allowlist secret # 示例密码
  -n gitea \
  --dry-run=client -o yaml | \
  kubectl replace --force -f -
```

### 问题 4: 数据库连接失败

```bash
# 验证数据库 Secret
kubectl get secret gitea-postgresql-secret -n gitea -o jsonpath='{.data.password}' | base64 -d

# 测试数据库连接
kubectl run -it --rm postgres-client \
  --image=postgres:15 \
  --restart=Never \
  --env=PGPASSWORD="$(kubectl get secret gitea-postgresql-secret -n gitea -o jsonpath='{.data.password}' | base64 -d)" \
  -- psql -h postgresql -U gitea -c '\dt'
```

---

## 安全检查清单

部署前检查：

- [ ] 所有密钥使用强随机字符串（至少 24 位 base64）
- [ ] 开发环境和生产环境使用不同的密钥
- [ ] secrets-example.yaml 未提交到 git
- [ ] 启用了密钥轮换策略
- [ ] 配置了 RBAC 访问控制
- [ ] 启用了审计日志
- [ ] 密钥存储在外部密钥管理系统（生产环境）

部署后验证：

- [ ] `kubectl get secrets -n gitea` 显示所有 Secret
- [ ] Gitea Pod 正常启动
- [ ] 管理员可以登录
- [ ] 数据库连接正常
- [ ] 审计日志记录 Secret 访问

---

## 参考文档

- [Kubernetes Secrets 官方文档](https://kubernetes.io/docs/concepts/configuration/secret/)
- [SealedSecrets 项目](https://github.com/bitnami-labs/sealed-secrets)
- [ExternalSecrets Operator](https://external-secrets.io/)
- [HashiCorp Vault](https://www.vaultproject.io/)
- [Gitea 安全配置](https://docs.gitea.com/administration/config-cheat-sheet#security)

---

**文档维护**: Agimtech 开发团队
**最后审查**: 2026-03-14
**下次审查**: 2026-06-14（季度审查）
