# Harbor Webhook 配置指南

**Story 0.6: Harbor 镜像仓库**
**版本:** 1.0
**日期:** 2026-03-14

---

## 📋 目录

1. [概述](#概述)
2. [Webhook 架构](#webhook-架构)
3. [配置 ArgoCD Image Updater](#配置-argocd-image-updater)
4. [配置 Harbor Webhook](#配置-harbor-webhook)
5. [测试 Webhook](#测试-webhook)
6. [故障排查](#故障排查)

---

## 概述

Harbor Webhook 用于在镜像事件（推送、拉取、删除）发生时自动通知外部系统，如 ArgoCD Image Updater。

### 适用场景

- ✅ 镜像推送后自动触发 ArgoCD 更新部署
- ✅ 镜像推送后触发自动化测试
- ✅ 镜像事件审计和日志记录
- ✅ 镜像推送后发送通知（Slack、邮件等）

---

## Webhook 架构

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   Gitea     │      │   Harbor    │      │   ArgoCD    │
│  代码推送    │─────▶│  镜像推送    │─────▶│  镜像更新    │
│             │      │             │      │             │
│             │      │  Webhook    │      │  Webhook    │
│             │      │  PUSH_EVENT │      │  Receiver   │
└─────────────┘      └─────────────┘      └─────────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │  其他通知目标    │
                   │  - Slack        │
                   │  - Email        │
                   │  - 自定义 API    │
                   └─────────────────┘
```

---

## 配置 ArgoCD Image Updater

### 1. 安装 ArgoCD Image Updater

```bash
# 添加 Helm 仓库
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update

# 安装 ArgoCD Image Updater
helm install argocd-image-updater argo/argocd-image-updater \
  -n argocd \
  --set argocd.server=argocd-server.argocd.svc.cluster.local \
  --set webhook.enabled=true \
  --set webhook.port=8080
```

### 2. 配置 Webhook 接收器

```yaml
# argocd-image-updater-webhook.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-image-updater-config
  namespace: argocd
data:
  # 启用 Webhook
  webhook.enabled: "true"
  webhook.port: "8080"

  # 镜像注册表配置
  registries.conf: |
    registries:
    - name: Harbor
      api_url: http://harbor.harbor.svc.cluster.local
      prefix: harbor.sisys.local
      insecure: true
```

### 3. 应用配置

```bash
kubectl apply -f argocd-image-updater-webhook.yaml
kubectl rollout restart deployment/argocd-image-updater -n argocd
```

---

## 配置 Harbor Webhook

### 方式 1: 通过 Harbor Web 界面

1. **登录 Harbor**
   - 访问：http://harbor.harbor.svc.cluster.local
   - 用户名：`admin`
   - 密码：`Harbor@2026Secure!`

2. **进入项目**
   - 点击"项目" → 选择 `sisys` 项目

3. **配置 Webhook**
   - 点击"Webhook" 标签
   - 点击"新建 Webhook"

4. **填写配置**
   ```
   名称：argocd-image-updater
   描述：Trigger ArgoCD Image Updater on image push
   请求地址：http://argocd-image-updater.argocd.svc.cluster.local:8080/api/v1/webhook
   事件类型：
     ✅ 推送事件 (PUSH_ARTIFACT)
   通知方式：HTTP
   跳过证书验证：✅ (开发环境)
   ```

5. **保存并测试**
   - 点击"保存"
   - 点击"测试"验证 Webhook 可达性

### 方式 2: 通过 Harbor API

```bash
#!/bin/bash

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

# 创建 Webhook
curl -s -u "$HARBOR_USER:$HARBOR_PASSWORD" \
  -X POST "$HARBOR_URL/api/v2.0/webhook/policies" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "argocd-image-updater",
    "description": "Trigger ArgoCD Image Updater on image push",
    "enabled": true,
    "eventTypes": ["PUSH_ARTIFACT"],
    "targets": [
      {
        "type": "http",
        "address": "http://argocd-image-updater.argocd.svc.cluster.local:8080/api/v1/webhook",
        "skip_cert_verify": true
      }
    ],
    "project_id": '$PROJECT_ID'
  }' | jq .
```

---

## 测试 Webhook

### 1. 推送测试镜像

```bash
# 登录 Harbor
docker login harbor.sisys.local -u admin -p Harbor@2026Secure!

# 构建测试镜像
docker build -t harbor.sisys.local/sisys/test-webhook:latest .

# 推送镜像
docker push harbor.sisys.local/sisys/test-webhook:latest
```

### 2. 检查 Webhook 日志

```bash
# 查看 ArgoCD Image Updater 日志
kubectl logs -n argocd -l app=argocd-image-updater --tail=50

# 查看 Harbor Webhook 日志
kubectl logs -n harbor -l app=harbor-core --tail=50 | grep webhook
```

### 3. 验证 ArgoCD 更新

```bash
# 检查 ArgoCD Application 状态
argocd app get <app-name>

# 检查 Image Updater 状态
kubectl get deployment -n argocd argocd-image-updater
```

### 4. 手动触发 Webhook 测试

```bash
# 发送测试 Webhook 请求
curl -X POST http://argocd-image-updater.argocd.svc.cluster.local:8080/api/v1/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "type": "PUSH_ARTIFACT",
    "event_data": {
      "project_id": 1,
      "project_name": "sisys",
      "repository": {
        "name": "test-app",
        "url": "harbor.sisys.local/sisys/test-app"
      },
      "resource_data": {
        "digest": "sha256:abc123456789",
        "tag": "latest"
      }
    }
  }'
```

---

## 故障排查

### 问题 1: Webhook 连接失败

**症状**: `connection refused` 或 `timeout`

**原因**:
- ArgoCD Image Updater 未运行
- 网络策略阻止连接
- 服务地址配置错误

**解决**:
```bash
# 检查 ArgoCD Image Updater 状态
kubectl get pods -n argocd -l app=argocd-image-updater

# 检查服务
kubectl get svc -n argocd argocd-image-updater

# 测试连通性
kubectl exec -n harbor harbor-core-xxx -- \
  curl -v http://argocd-image-updater.argocd.svc.cluster.local:8080/api/v1/webhook
```

### 问题 2: Webhook 触发但无响应

**症状**: Webhook 显示成功但 ArgoCD 未更新

**原因**:
- Webhook 格式不匹配
- ArgoCD Image Updater 配置错误
- 镜像标签不匹配

**解决**:
```bash
# 检查 ArgoCD Image Updater 配置
kubectl get configmap argocd-image-updater-config -n argocd -o yaml

# 查看 Webhook 接收日志
kubectl logs -n argocd -l app=argocd-image-updater | grep webhook
```

### 问题 3: 401 Unauthorized

**症状**: `unauthorized: authentication required`

**原因**:
- Webhook 需要认证但未配置
- Token 过期

**解决**:
```bash
# 在 Harbor Webhook 配置中添加认证头
# Authorization: Bearer <token>
```

---

## Webhook 事件类型

| 事件类型 | 说明 | 触发时机 |
|---------|------|---------|
| `PUSH_ARTIFACT` | 推送镜像 | 镜像推送到 Harbor |
| `PULL_ARTIFACT` | 拉取镜像 | 镜像从 Harbor 拉取 |
| `DELETE_ARTIFACT` | 删除镜像 | 镜像从 Harbor 删除 |
| `SCANNING_COMPLETED` | 扫描完成 | 漏洞扫描完成 |
| `QUOTA_EXCEED` | 配额超限 | 项目配额超限 |

---

## 参考文档

- [Harbor Webhook 官方文档](https://goharbor.io/docs/2.14.0/administration/manage-webhooks/)
- [ArgoCD Image Updater 文档](https://argocd-image-updater.readthedocs.io/)
- [Harbor API 文档](https://goharbor.io/docs/2.14.0/swag.v2/)

---

**文档维护者:** DevOps Team
**最后更新:** 2026-03-14
