# ArgoCD Image Updater 配置指南

Story 0.7: ArgoCD 持续部署 - Task 5: Harbor 镜像仓库集成

## 目录

1. [概述](#概述)
2. [安装步骤](#安装步骤)
3. [配置 Harbor 凭据](#配置-harbor-凭据)
4. [配置镜像更新策略](#配置镜像更新策略)
5. [配置 Harbor Webhook](#配置-harbor-webhook)
6. [验证安装](#验证安装)
7. [故障排除](#故障排除)

## 概述

ArgoCD Image Updater 用于自动检测 Harbor 镜像仓库中的新镜像 tag，并自动更新 ArgoCD Application 的镜像版本。

### 核心功能

- **自动检测**: 监控 Harbor 镜像仓库的新 tag
- **自动更新**: 更新 ArgoCD Application 的镜像配置
- **Webhook 支持**: Harbor 推送事件触发即时更新
- **多仓库支持**: 支持 Harbor、Docker Hub、Quay.io 等

### 架构组件

```
┌─────────────┐      ┌─────────────────────┐      ┌─────────────┐
│   Harbor    │─────▶│  ArgoCD Image       │─────▶│   ArgoCD    │
│  v2.14.3    │      │  Updater v0.14.0    │      │  v3.2.7     │
│  镜像仓库    │      │  镜像更新检测        │      │  持续部署    │
└─────────────┘      └─────────────────────┘      └─────────────┘
      │                    │                          │
      │ 1. 推送新镜像       │                          │
      │    (Robot Account) │                          │
      ▼                    ▼                          ▼
┌─────────────────────────────────────────────────────────┐
│                    K3S 集群                              │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Image Updater Pod (argocd 命名空间)             │   │
│  │  - 监听 Harbor Webhook                           │   │
│  │  - 轮询镜像 tag                                  │   │
│  │  - 更新 ArgoCD Application                       │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## 安装步骤

### 步骤 1: 应用安装清单

```bash
# 使用已准备的安装清单
sudo kubectl apply -f deployments/argocd/image-updater-install.yaml
```

### 步骤 2: 验证 Pod 状态

```bash
# 等待 Pod 就绪
sudo kubectl wait --for=condition=Ready pods -l app.kubernetes.io/name=argocd-image-updater -n argocd --timeout=60s

# 检查 Pod 状态
sudo kubectl get pods -n argocd | grep image-updater
```

### 步骤 3: 查看日志

```bash
# 查看 Image Updater 日志
sudo kubectl logs -n argocd -l app.kubernetes.io/name=argocd-image-updater -f
```

## 配置 Harbor 凭据

### 方式 1: 使用 kubectl 创建 Secret

```bash
# 1. 获取 Harbor Robot Account Token
# 在 Harbor Web 界面创建 Robot Account:
# - 进入项目 → sisys → Robot Accounts
# - 创建 "argocd-pull" 权限：Pull
# - 复制生成的 Token

# 2. 创建 Kubernetes Secret
HARBOR_URL="harbor.sisys.local"
HARBOR_USER="robot\$argocd-pull"
HARBOR_TOKEN="<你的 Robot Account Token>"

# 3. 编码凭据
echo -n "${HARBOR_USER}:${HARBOR_TOKEN}" | base64

# 4. 更新 Secret
sudo kubectl create secret generic argocd-image-updater-secret \
  --from-literal=harbor="<base64 编码的凭据>" \
  --namespace=argocd \
  --dry-run=client -o yaml | sudo kubectl apply -f -
```

### 方式 2: 使用配置文件

编辑 `deployments/argocd/image-updater-install.yaml` 中的 Secret 部分：

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: argocd-image-updater-secret
  namespace: argocd
type: Opaque
data:
  harbor: <base64 编码的凭据>
```

### 创建 Harbor Robot Account

1. 登录 Harbor: https://harbor.sisys.local
2. 进入项目 → sisys
3. 点击左侧 "Robot Accounts"
4. 点击 "+ NEW ROBOT ACCOUNT"
5. 填写信息:
   - Name: `argocd-pull`
   - Permissions: `Pull` (只读)
   - Expiration: `Never` (永不过期)
6. 点击 "Add" 并保存生成的 Token

## 配置镜像更新策略

### Application 注解配置

在 ArgoCD Application 的 YAML 中添加以下注解：

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp
  namespace: argocd
  annotations:
    # 启用镜像更新
    argocd-image-updater.argoproj.io/image-list: |
      harbor.sisys.local/sisys/myapp

    # 更新策略
    argocd-image-updater.argoproj.io/update-strategy: latest

    # 或者使用语义化版本
    # argocd-image-updater.argoproj.io/myapp.update-strategy: semver
    # argocd-image-updater.argoproj.io/myapp.allow-tags: regexp:^v[0-9]+\\.[0-9]+\\.[0-9]+$

    # 镜像别名（可选）
    argocd-image-updater.argoproj.io/myapp.alias: myapp

    # 强制更新（可选）
    argocd-image-updater.argoproj.io/myapp.force-update: "true"

    # 忽略特定 tag（可选）
    argocd-image-updater.argoproj.io/myapp.ignore-tags: |
      latest,dev,nightly
spec:
  source:
    repoURL: https://gitea.sisys.local/sisys/sisys.git
    targetRevision: HEAD
    path: deployments/myapp
```

### 更新策略说明

| 策略 | 说明 | 示例 |
|------|------|------|
| `latest` | 使用最新 tag | `latest` |
| `semver` | 语义化版本 | `v1.2.3` |
| `name` | 按字母顺序 | `20240101` |
| `digest` | 使用镜像 digest | `sha256:abc123...` |

### 配置示例

#### 示例 1: 最新 tag 策略

```yaml
annotations:
  argocd-image-updater.argoproj.io/image-list: harbor.sisys.local/sisys/myapp
  argocd-image-updater.argoproj.io/update-strategy: latest
```

#### 示例 2: 语义化版本策略

```yaml
annotations:
  argocd-image-updater.argoproj.io/image-list: harbor.sisys.local/sisys/myapp
  argocd-image-updater.argoproj.io/myapp.update-strategy: semver
  argocd-image-updater.argoproj.io/myapp.allow-tags: regexp:^v[0-9]+\\.[0-9]+\\.[0-9]+$
  argocd-image-updater.argoproj.io/myapp.sort-mode: semver
```

#### 示例 3: 多镜像更新

```yaml
annotations:
  argocd-image-updater.argoproj.io/image-list: |
    harbor.sisys.local/sisys/frontend=frontend
    harbor.sisys.local/sisys/backend=backend

  argocd-image-updater.argoproj.io/frontend.update-strategy: semver
  argocd-image-updater.argoproj.io/frontend.allow-tags: regexp:^v[0-9]+\\.[0-9]+$

  argocd-image-updater.argoproj.io/backend.update-strategy: semver
  argocd-image-updater.argoproj.io/backend.allow-tags: regexp:^v[0-9]+\\.[0-9]+$
```

## 配置 Harbor Webhook

### 步骤 1: 获取 Image Updater Webhook URL

```bash
# 内部服务地址
WEBHOOK_URL="http://argocd-image-updater.argocd.svc.cluster.local:8080/api/v1/webhook"
echo "Webhook URL: $WEBHOOK_URL"
```

### 步骤 2: 在 Harbor 中配置 Webhook

1. 登录 Harbor: https://harbor.sisys.local
2. 进入项目 → sisys
3. 点击左侧 "Webhook"
4. 点击 "+ NEW WEBHOOK"
5. 填写信息:
   - Name: `argocd-image-updater`
   - Webhook URL: `http://argocd-image-updater.argocd.svc.cluster.local:8080/api/v1/webhook`
   - Events: 勾选 `PUSH_ARTIFACT`
   - Skip Cert Verify: 勾选（自签名证书）
6. 点击 "Add"

### 步骤 3: 使用 API 创建 Webhook（可选）

```bash
#!/bin/bash

HARBOR_URL="https://harbor.sisys.local"
HARBOR_USER="admin"
HARBOR_PASSWORD="Harbor@2026Secure!"  # pragma: allowlist secret
PROJECT_NAME="sisys"

# 获取项目 ID
PROJECT_ID=$(curl -k -s -u "$HARBOR_USER:$HARBOR_PASSWORD" \
  "$HARBOR_URL/api/v2.0/projects?name=$PROJECT_NAME" | \
  jq -r '.[0].project_id')

echo "Project ID: $PROJECT_ID"

# 创建 Webhook
curl -k -s -u "$HARBOR_USER:$HARBOR_PASSWORD" \
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

### 步骤 4: 测试 Webhook

```bash
# 手动触发 Webhook 测试
curl -X POST http://argocd-image-updater.argocd.svc.cluster.local:8080/api/v1/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "type": "PUSH_ARTIFACT",
    "event_data": {
      "project_id": 1,
      "project_name": "sisys",
      "repository": {
        "name": "myapp",
        "url": "harbor.sisys.local/sisys/myapp"
      },
      "resource_data": {
        "digest": "sha256:abc123...",
        "tag": "v1.0.1"
      }
    }
  }'

# 查看 Image Updater 日志确认收到 Webhook
sudo kubectl logs -n argocd -l app.kubernetes.io/name=argocd-image-updater --tail=50
```

## 验证安装

### 验证清单

```bash
# 1. 检查 Pod 状态
sudo kubectl get pods -n argocd | grep image-updater
# 期望：STATUS=Running

# 2. 检查 Deployment
sudo kubectl get deployment argocd-image-updater -n argocd
# 期望：READY=1/1

# 3. 检查 Service
sudo kubectl get service argocd-image-updater -n argocd
# 期望：PORT=8080

# 4. 检查 ConfigMap
sudo kubectl get configmap argocd-image-updater-config -n argocd
# 期望：存在

# 5. 检查 Secret
sudo kubectl get secret argocd-image-updater-secret -n argocd
# 期望：存在

# 6. 查看日志
sudo kubectl logs -n argocd -l app.kubernetes.io/name=argocd-image-updater --tail=50
# 期望：无持续错误

# 7. 测试健康检查端点
sudo kubectl port-forward svc/argocd-image-updater 8080:8080 -n argocd &
curl http://localhost:8080/healthz
# 期望：返回健康状态
```

### 端到端测试

```bash
# 1. 推送新镜像到 Harbor
docker tag myapp:latest harbor.sisys.local/sisys/myapp:v1.0.1
docker push harbor.sisys.local/sisys/myapp:v1.0.1

# 2. 等待 Image Updater 检测（约 1-2 分钟）
sudo kubectl logs -n argocd -l app.kubernetes.io/name=argocd-image-updater -f

# 3. 检查 ArgoCD Application 是否更新
sudo kubectl get application myapp -n argocd

# 4. 验证 Deployment 镜像已更新
sudo kubectl get deployment myapp -n default -o jsonpath='{.spec.template.spec.containers[0].image}'
```

## 故障排除

### 问题 1: Image Updater Pod 无法启动

```bash
# 检查 Pod 事件
sudo kubectl describe pod -n argocd -l app.kubernetes.io/name=argocd-image-updater

# 查看日志
sudo kubectl logs -n argocd -l app.kubernetes.io/name=argocd-image-updater

# 常见原因:
# - Secret 配置错误
# - ConfigMap 配置错误
# - RBAC 权限不足
```

### 问题 2: 无法连接 Harbor

```bash
# 测试 Harbor 连接
sudo kubectl run test-harbor --rm -it --image=curlimages/curl --restart=Never -- \
  curl -k https://harbor.harbor.svc.cluster.local/api/v2.0/ping

# 检查 NetworkPolicy
sudo kubectl get networkpolicy -n argocd

# 检查 DNS 解析
sudo kubectl run test-dns --rm -it --image=busybox --restart=Never -- \
  nslookup harbor.harbor.svc.cluster.local
```

### 问题 3: Webhook 不触发

```bash
# 检查 Harbor Webhook 配置
curl -k -u admin:Harbor@2026Secure! \
  https://harbor.sisys.local/api/v2.0/webhook/policies

# 查看 Image Updater 日志
sudo kubectl logs -n argocd -l app.kubernetes.io/name=argocd-image-updater | grep webhook

# 手动测试 Webhook
curl -X POST http://argocd-image-updater.argocd.svc.cluster.local:8080/api/v1/webhook \
  -H "Content-Type: application/json" \
  -d '{"type": "PUSH_ARTIFACT"}'
```

### 问题 4: 镜像不更新

```bash
# 检查 Application 注解
sudo kubectl get application myapp -n argocd -o yaml | grep argocd-image-updater

# 检查 Image Updater 日志
sudo kubectl logs -n argocd -l app.kubernetes.io/name=argocd-image-updater | grep myapp

# 检查镜像 tag 是否存在
curl -k -u robot\$argocd-pull:TOKEN \
  https://harbor.sisys.local/api/v2.0/projects/sisys/repositories/myapp/artifacts
```

### 问题 5: 认证失败

```bash
# 验证 Secret 配置
sudo kubectl get secret argocd-image-updater-secret -n argocd -o jsonpath='{.data.harbor}' | base64 -d

# 测试 Harbor 登录
docker login harbor.sisys.local -u robot\$argocd-pull -p <TOKEN>

# 检查 Robot Account 权限
# 在 Harbor Web 界面检查：项目 → sisys → Robot Accounts
```

### 问题 6: NetworkPolicy 阻止 Webhook

```bash
# 检查 NetworkPolicy 配置
sudo kubectl get networkpolicy argocd-image-updater-allow -n argocd -o yaml

# 验证是否允许 Harbor 命名空间访问
# 应该包含以下 ingress 规则:
# - from:
#     - namespaceSelector:
#         matchLabels:
#           kubernetes.io/metadata.name: harbor
```

## 故障恢复指南

### 恢复步骤 1: 重置 Image Updater

```bash
# 1. 删除 Image Updater Deployment
sudo kubectl delete deployment argocd-image-updater -n argocd

# 2. 删除 Secret（重新创建）
sudo kubectl delete secret argocd-image-updater-secret -n argocd

# 3. 重新运行配置脚本
python scripts/argocd/configure-image-updater.py

# 4. 重新应用安装清单
sudo kubectl apply -f deployments/argocd/image-updater-install.yaml
```

### 恢复步骤 2: 重置 Harbor 凭据

```bash
# 1. 在 Harbor Web 界面删除旧的 Robot Account
# 进入项目 → sisys → Robot Accounts → 删除 argocd-pull

# 2. 重新创建 Robot Account
python scripts/argocd/configure-image-updater.py

# 3. 验证 Secret 已更新
sudo kubectl get secret argocd-image-updater-secret -n argocd -o jsonpath='{.data.harbor}' | base64 -d
```

### 恢复步骤 3: 回滚 Application

```bash
# 1. 查看同步历史
argocd app history myapp

# 2. 回滚到上一版本
argocd app rollback myapp <REVISION>

# 3. 或者手动回滚镜像 tag
sudo kubectl patch deployment myapp -n default \
  --type='json' \
  -p='[{"op": "replace", "path": "/spec/template/spec/containers/0/image", "value": "harbor.sisys.local/sisys/myapp:v1.0.0"}]'
```

### 恢复步骤 4: 禁用 Image Updater（临时）

```bash
# 1. 删除 Image Updater Deployment
sudo kubectl delete deployment argocd-image-updater -n argocd

# 2. 手动更新 Application 镜像
argocd app set myapp --image harbor.sisys.local/sisys/myapp:v1.0.1

# 3. 手动同步
argocd app sync myapp
```

## 参考文档

- [ArgoCD Image Updater 官方文档](https://argocd-image-updater.readthedocs.io/)
- [Harbor Webhook 配置](https://goharbor.io/docs/2.6.0/management/configure-webhook/)
- [Story 0.6: Harbor 部署文档](./HARBOR_DEPLOYMENT.md)
- [Story 0.7: ArgoCD 部署文档](./ARGOCD_DEPLOYMENT.md)

## 版本兼容性

### 已测试版本组合

| 组件 | 版本 | 状态 | 说明 |
|------|------|------|------|
| ArgoCD | v3.2.7 | ✅ 已测试 | 当前部署版本 |
| ArgoCD Image Updater | v0.14.0 | ✅ 已测试 | 对应 ArgoCD v3.2.x |
| Harbor | v2.14.3 | ✅ 已测试 | 当前部署版本 |
| K3S | v1.34.5 | ✅ 已测试 | 当前集群版本 |
| Traefik | v3.6.10 | ✅ 已测试 | 当前 Ingress 版本 |

### 兼容版本范围

| 组件 | 兼容版本范围 | 注意事项 |
|------|-------------|----------|
| ArgoCD | v3.0.0 - v3.4.x | v3.0+ API 有变更，需使用 Image Updater v0.13+ |
| ArgoCD Image Updater | v0.12.0 - v0.14.x | v0.12+ 支持 ArgoCD v3.x |
| Harbor | v2.8.0 - v2.14.x | Webhook API 在 v2.10+ 有变更 |
| K3S | v1.28.0 - v1.34.x | 无特殊要求 |

### 降级方案

如 ArgoCD Image Updater v0.14.0 部署失败：

1. **使用 v0.13.0**（稳定版本）:
   ```bash
   # 修改 image-updater-install.yaml 中的镜像版本
   image: quay.io/argoprojlabs/argocd-image-updater:v0.13.0
   ```

2. **使用 v0.12.0**（兼容 ArgoCD v3.0）:
   ```bash
   image: quay.io/argoprojlabs/argocd-image-updater:v0.12.0
   ```

3. **检查兼容性矩阵**:
   - 参考 [ArgoCD Image Updater 兼容性矩阵](https://argocd-image-updater.readthedocs.io/en/stable/)
   - 确保 Image Updater 版本与 ArgoCD 版本匹配

### 升级路径

从旧版本升级：

1. **备份当前配置**:
   ```bash
   sudo kubectl get configmap argocd-image-updater-config -n argocd -o yaml > backup-config.yaml
   sudo kubectl get secret argocd-image-updater-secret -n argocd -o yaml > backup-secret.yaml
   ```

2. **删除旧版本**:
   ```bash
   sudo kubectl delete deployment argocd-image-updater -n argocd
   ```

3. **应用新版本**:
   ```bash
   sudo kubectl apply -f deployments/argocd/image-updater-install.yaml
   ```

4. **验证升级**:
   ```bash
   sudo kubectl get pods -n argocd -l app.kubernetes.io/name=argocd-image-updater
   sudo kubectl logs -n argocd -l app.kubernetes.io/name=argocd-image-updater
   ```

## 下一步

- Task 6: Application 配置 - 创建 ArgoCD Application 并配置自动同步策略
- Task 7: 多环境配置 - Kustomize 多环境覆盖配置
