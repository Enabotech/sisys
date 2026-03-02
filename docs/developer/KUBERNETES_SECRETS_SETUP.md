# Kubernetes Secrets 配置指南

本指南介绍如何在 Kubernetes 集群中安全地管理 sisys 应用的敏感配置。

## 📋 目录

- [前置要求](#前置要求)
- [Secrets 类型](#secrets 类型)
- [配置方法](#配置方法)
- [最佳实践](#最佳实践)

## 🔒 前置要求

- Kubernetes 集群 1.25+
- kubectl 已配置集群访问权限
- 管理员权限创建 Secrets

## Secrets 类型

### 1. 数据库 Secrets

```bash
# PostgreSQL
kubectl create secret generic sisys-db-secrets \
  --namespace=production \
  --from-literal=POSTGRES_USER='sisys_user' \
  --from-literal=POSTGRES_PASSWORD='your-secure-password' \   # pragma: allowlist secret
  --from-literal=POSTGRES_DB='sisys'
```

### 2. 对象存储 Secrets

```bash
# MinIO
kubectl create secret generic sisys-minio-secrets \
  --namespace=production \
  --from-literal=MINIO_ROOT_USER='minio_admin' \
  --from-literal=MINIO_ROOT_PASSWORD='your-secure-minio-password'   # pragma: allowlist secret
```

### 3. 图数据库 Secrets

```bash
# Neo4j
kubectl create secret generic sisys-neo4j-secrets \
  --namespace=production \
  --from-literal=NEO4J_USER='neo4j' \
  --from-literal=NEO4J_PASSWORD='your-secure-neo4j-password'      # pragma: allowlist secret
```

### 4. 监控 Secrets

```bash
# Grafana
kubectl create secret generic sisys-grafana-secrets \
  --namespace=production \
  --from-literal=GRAFANA_ADMIN_USER='admin' \
  --from-literal=GRAFANA_ADMIN_PASSWORD='your-secure-grafana-password'  # pragma: allowlist secret
```

### 5. CI/CD Secrets

```bash
# GitHub Container Registry
kubectl create secret docker-registry ghcr-secret \
  --namespace=production \
  --docker-server=ghcr.io \
  --docker-username=your-github-username \
  --docker-password=your-github-token \
  --docker-email=your-email@example.com
```

## 配置方法

### 方法 1: kubectl 命令（推荐用于开发/测试）

```bash
# 创建完整的 Secrets
kubectl apply -f k8s/production/secrets.yaml

# 验证 Secrets
kubectl get secrets -n production
kubectl describe secret sisys-secrets -n production
```

### 方法 2: 外部 Secrets 管理（推荐用于生产）

#### HashiCorp Vault

```yaml
# external-secrets.yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: sisys-external-secrets
  namespace: production
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: ClusterSecretStore
  target:
    name: sisys-secrets
    creationPolicy: Owner
  data:
    - secretKey: POSTGRES_PASSWORD
      remoteRef:
        key: sisys/database
        property: password
    - secretKey: MINIO_ROOT_PASSWORD
      remoteRef:
        key: sisys/minio
        property: admin_password
```

#### AWS Secrets Manager

```yaml
# aws-external-secret.yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: sisys-aws-secrets
  namespace: production
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: sisys-secrets
  data:
    - secretKey: POSTGRES_PASSWORD
      remoteRef:
        key: production/sisys/database
        property: password
```

### 方法 3: Sealed Secrets（GitOps 友好）

```bash
# 安装 kubeseal
brew install kubeseal

# 创建普通 Secret
kubectl create secret generic sisys-secrets \
  --from-literal=POSTGRES_PASSWORD='secure-password' \    # pragma: allowlist secret
  --dry-run=client -o yaml > secret.yaml

# 加密为 SealedSecret
kubeseal --format=yaml < secret.yaml > sealed-secret.yaml

# 提交到 Git
git add sealed-secret.yaml
git commit -m "Add sealed secret for sisys"
```

## 最佳实践

### ✅ 推荐做法

1. **永远不要将明文 Secrets 提交到 Git**
   - 使用 Sealed Secrets 或外部 Secrets 管理
   - 将 Secrets 文件添加到 `.gitignore`

2. **定期轮换 Secrets**
   ```bash
   # 更新 Secret
   kubectl create secret generic sisys-secrets \
     --from-literal=POSTGRES_PASSWORD='new-password' \    # pragma: allowlist secret
     --dry-run=client -o yaml | \
     kubectl replace -f -

   # 重启 Pod 以使用新 Secret
   kubectl rollout restart deployment/sisys-app -n production
   ```

3. **使用 RBAC 限制访问**
   ```yaml
   # role.yaml
   apiVersion: rbac.authorization.k8s.io/v1
   kind: Role
   metadata:
     name: secrets-manager
     namespace: production
   rules:
     - apiGroups: [""]
       resources: ["secrets"]
       verbs: ["get", "list", "watch"]
   ```

4. **启用 Secrets 加密**
   ```yaml
   # Kubernetes 静态加密配置
   apiVersion: apiserver.config.k8s.io/v1
   kind: EncryptionConfiguration
   resources:
     - resources:
         - secrets
       providers:
         - aescbc:
             keys:
               - name: key1
                 secret: <base64-encoded-key>
         - identity: {}
   ```

5. **审计 Secret 访问**
   ```bash
   # 启用审计日志
   kubectl logs -n kube-system kube-apiserver | \
     grep secrets
   ```

### ❌ 避免的做法

1. **不要在 Deployment 中硬编码 Secrets**
   ```yaml
   # ❌ 错误
   env:
     - name: POSTGRES_PASSWORD
       value: "hardcoded-password"

   # ✅ 正确
   envFrom:
     - secretRef:
         name: sisys-secrets
   ```

2. **不要使用默认密码**
   ```bash
   # ❌ 避免
   POSTGRES_PASSWORD="postgres"   # pragma: allowlist secret

   # ✅ 使用强密码
   POSTGRES_PASSWORD=$(openssl rand -base64 32)
   ```

3. **不要在日志中打印 Secrets**
   ```python
   # ❌ 错误
   logger.info(f"Database password: {password}")

   # ✅ 正确
   logger.info("Database connection configured")
   ```

## 验证配置

```bash
# 检查 Secrets 是否存在
kubectl get secrets -n production

# 验证 Secret 内容（base64 解码）
kubectl get secret sisys-secrets -n production \
  -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d

# 测试 Pod 能否正确加载 Secrets
kubectl exec -it deployment/sisys-app -n production -- \
  env | grep POSTGRES
```

## 故障排查

### Secret 未挂载

```bash
# 检查 Pod 事件
kubectl describe pod <pod-name> -n production

# 检查 Secret 是否存在
kubectl get secret sisys-secrets -n production

# 验证 Secret 键名
kubectl get secret sisys-secrets -n production \
  -o jsonpath='{.data}' | jq 'keys'
```

### Pod 启动失败

```bash
# 查看 Pod 日志
kubectl logs deployment/sisys-app -n production

# 检查环境变量
kubectl exec deployment/sisys-app -n production -- env

# 验证 Secret 挂载
kubectl exec deployment/sisys-app -n production -- \
  ls -la /etc/secrets
```

## 参考文档

- [Kubernetes Secrets 官方文档](https://kubernetes.io/docs/concepts/configuration/secret/)
- [External Secrets Operator](https://external-secrets.io/)
- [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets)
- [HashiCorp Vault with Kubernetes](https://www.vaultproject.io/docs/platform/k8s)

---

**最后更新:** 2026-03-02
**版本:** 1.0.0
