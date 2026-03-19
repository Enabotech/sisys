# ArgoCD Gitea 集成故障排除指南

**创建日期:** 2026-03-19  
**故事:** 0.7-argocd-continuous-deployment  
**任务:** Task 4 - Gitea 仓库集成  
**审查问题:** MEDIUM-1 修复

---

## 概述

本文档提供 ArgoCD 与 Gitea 集成的故障排除指南。

---

## 常见问题

### 问题 1: 仓库连接失败

**症状:**
```
Failed to load repository data: authentication required
```

**可能原因:**
1. Token 过期或无效
2. Token 权限不足
3. 网络连接问题

**解决方案:**

#### 步骤 1: 验证 Token

```bash
# 查看 Secret
kubectl get secret argocd-gitea-creds -n argocd -o jsonpath='{.data.password}' | base64 -d

# 测试 Token
curl -H "Authorization: token <YOUR_TOKEN>" \
  https://gitea.sisys.local/api/v1/user
```

#### 步骤 2: 重新生成 Token

```bash
# 1. 登录 Gitea: https://gitea.sisys.local
# 2. 用户设置 → Applications → Generate New Token
# 3. 权限：repository, user
# 4. 复制 Token

# 3. 更新 Secret
kubectl create secret generic argocd-gitea-creds \
  --from-literal=username=gitea_admin \
  --from-literal=password=<NEW_TOKEN> \
  --from-literal=url=https://gitea.sisys.local/sisys \
  --from-literal=insecure=true \
  -n argocd --dry-run=client -o yaml | kubectl apply -f -
```

#### 步骤 3: 验证连接

```bash
# 在 ArgoCD 中添加仓库测试
argocd repo add https://gitea.sisys.local/sisys/sisys.git \
  --username gitea_admin \
  --password <TOKEN> \
  --insecure-skip-server-verification
```

---

### 问题 2: TLS 证书验证失败

**症状:**
```
x509: certificate signed by unknown authority
```

**可能原因:**
- 使用自签名证书
- 证书过期

**解决方案:**

#### 方案 A: 配置 insecure（开发环境）

```yaml
# gitea-credentials.yaml
stringData:
  insecure: "true"
```

#### 方案 B: 导入证书到信任链（生产环境）

```bash
# 1. 获取 Gitea 证书
openssl s_client -connect gitea.sisys.local:443 -showcerts > gitea.crt

# 2. 创建 ConfigMap
kubectl create configmap gitea-tls-cert \
  --from-file=gitea.crt -n argocd

# 3. 在 ArgoCD 配置中引用
# argocd-cm ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-cm
  namespace: argocd
data:
  tls.cert.data: |
    -----BEGIN CERTIFICATE-----
    ...
    -----END CERTIFICATE-----
```

---

### 问题 3: Webhook 不触发

**症状:**
- 代码推送后 ArgoCD 不同步
- Gitea Webhook 日志显示失败

**解决方案:**

#### 步骤 1: 检查 Webhook 配置

```bash
# 查看 Webhook
curl -H "Authorization: token <TOKEN>" \
  https://gitea.sisys.local/api/v1/repos/sisys/sisys/hooks
```

#### 步骤 2: 验证 Webhook URL

```yaml
# Webhook URL 应该是
http://argocd-server.argocd.svc.cluster.local/api/webhook

# 或者通过 Ingress
https://argocd.sisys.local/api/webhook
```

#### 步骤 3: 重新创建 Webhook

```bash
# 使用脚本
bash scripts/argocd/configure-gitea-webhook.sh

# 或手动创建
# 1. Gitea 仓库 → 设置 → Webhook → 添加 Webhook
# 2. Payload URL: http://argocd-server.argocd.svc.cluster.local/api/webhook
# 3. 触发事件：Push events
```

#### 步骤 4: 测试 Webhook

```bash
# 在 Gitea Web 界面测试 Webhook
# 或手动触发
curl -X POST \
  http://argocd-server.argocd.svc.cluster.local/api/webhook \
  -H "Content-Type: application/json" \
  -d '{"ref":"refs/heads/main"}'
```

---

### 问题 4: 同步超时

**症状:**
```
Timed out waiting for the condition
```

**解决方案:**

#### 步骤 1: 增加超时时间

```yaml
# Application 配置
spec:
  syncPolicy:
    retry:
      limit: 10
      backoff:
        duration: 10s
        factor: 2
        maxDuration: 5m
```

#### 步骤 2: 检查网络延迟

```bash
# 测试从 ArgoCD 到 Gitea 的网络
kubectl exec -n argocd argocd-server-<pod> -- \
  curl -I https://gitea.sisys.local
```

#### 步骤 3: 优化 Git 操作

```bash
# 配置 Git 缓存
kubectl patch cm argocd-cm -n argocd --type merge \
  -p '{"data":{"git.submodule.enabled":"true"}}'
```

---

### 问题 5: 权限不足

**症状:**
```
permission denied
```

**解决方案:**

#### 步骤 1: 检查 Token 权限

```bash
# 查看 Token 权限
curl -H "Authorization: token <TOKEN>" \
  https://gitea.sisys.local/api/v1/user
```

#### 步骤 2: 更新 Token 权限

```bash
# 1. 登录 Gitea
# 2. 用户设置 → Applications
# 3. 编辑 Token，确保权限：
#    - repository: read/write
#    - user: read
```

#### 步骤 3: 检查 ArgoCD RBAC

```yaml
# argocd-rbac-cm
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-rbac-cm
  namespace: argocd
data:
  policy.csv: |
    p, role:admin, repositories, *, *, allow
```

---

## 诊断命令

### 检查 ArgoCD 状态

```bash
# 查看 Application 状态
argocd app get sisys-app

# 查看同步历史
argocd app history sisys-app

# 查看日志
argocd app logs sisys-app
```

### 检查 Gitea 连接

```bash
# 列出仓库
argocd repo list

# 获取仓库详情
argocd repo get https://gitea.sisys.local/sisys/sisys.git
```

### 检查 Kubernetes 资源

```bash
# 查看 Secret
kubectl get secret argocd-gitea-creds -n argocd

# 查看事件
kubectl get events -n argocd --sort-by='.lastTimestamp'

# 查看 Pod 日志
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-server
```

---

## 预防措施

### 1. Token 轮换

```bash
# 定期轮换 Token（每 90 天）
# 1. 生成新 Token
# 2. 更新 Secret
# 3. 删除旧 Token
```

### 2. 监控告警

```yaml
# Prometheus 告警规则
groups:
  - name: argocd-gitea-alerts
    rules:
      - alert: ArgoCDGiteaConnectionFailed
        expr: argocd_repo_connection_status{repo="gitea"} == 0
        for: 5m
        annotations:
          summary: "ArgoCD Gitea connection failed"
```

### 3. 备份配置

```bash
# 备份 Secret
kubectl get secret argocd-gitea-creds -n argocd -o yaml > gitea-creds-backup.yaml

# 备份 Webhook 配置
curl -H "Authorization: token <TOKEN>" \
  https://gitea.sisys.local/api/v1/repos/sisys/sisys/hooks > webhooks-backup.json
```

---

## 相关文档

- [ArgoCD Gitea 集成配置指南](./ARGOCD_GITEA_INTEGRATION.md)
- [ArgoCD Application 配置](./ARGOCD_APPLICATION_CONFIG.md)
- [ArgoCD 故障排除](./ARGOCD_TROUBLESHOOTING.md)

---

**更新记录:**
- 2026-03-19: 创建文档（MEDIUM-1 修复）
