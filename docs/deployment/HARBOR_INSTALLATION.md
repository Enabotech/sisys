# Harbor v2.14.3 部署指南

**版本：** 1.1 (已统一命名)
**日期：** 2026-03-05
**适用：** K3S 集群 (Story 0.1 完成后)

---

## 📋 概述

本指南介绍如何在 K3S 集群上部署 Harbor v2.14.3 企业级镜像仓库，为开发团队提供安全的 Docker 镜像存储和分发服务。

**技术栈:**
- Harbor v2.14.3 ✅
- Trivy (漏洞扫描)
- Notary (镜像签名)
- Longhorn (持久化存储)

**统一命名:**
- 域名：`harbor.sisys.local`
- 外部端口：80/443 (通过 Traefik)
- 内部端口：8080

---

## 🔧 前置条件

- [ ] K3S 集群已部署 (Story 0.1 ✅)
- [ ] Longhorn 存储已配置
- [ ] Helm v3 已安装
- [ ] 外部数据库 (可选，默认使用内置 PostgreSQL)

---

## 📦 步骤 1: 添加 Harbor Helm 仓库

```bash
# 添加 Harbor Helm Chart 仓库
helm repo add harbor https://helm.goharbor.io
helm repo update

# 验证仓库
helm search repo harbor
# 期望输出：harbor/harbor  2.14.3  2.14.3
```

---

## 📦 步骤 2: 创建 Harbor 配置

```bash
# 创建命名空间
kubectl create namespace harbor

# 创建 Harbor 配置文件
cat > harbor-values.yaml <<EOF
expose:
  type: ingress
  tls:
    enabled: false
  ingress:
    hosts:
      core: harbor.sisys.local
      notary: notary.sisys.local

externalURL: http://harbor.sisys.local

portal:
  replicas: 1

registry:
  replicas: 1
  storage:
    maxSpaceGB: 500

notary:
  enabled: true

database:
  type: internal
  internal:
    password: harbor
    maxIdleConns: 50
    maxOpenConns: 1000

dataWarehouse:
  enabled: true

redis:
  type: internal

trivy:
  enabled: true
  ignoreUnfixed: false
  skipUpdate: false
  offlineScan: false
  insecure: false

persistence:
  enabled: true
  resourcePolicy: "keep"
  persistentVolumeClaim:
    registry:
      storageClass: "longhorn"
      accessMode: ReadWriteOnce
      size: 200Gi
    chartmuseum:
      storageClass: "longhorn"
      accessMode: ReadWriteOnce
      size: 50Gi
    jobservice:
      jobLog:
        storageClass: "longhorn"
        accessMode: ReadWriteOnce
        size: 20Gi
    database:
      storageClass: "longhorn"
      accessMode: ReadWriteOnce
      size: 50Gi
    redis:
      storageClass: "longhorn"
      accessMode: ReadWriteOnce
      size: 20Gi
    trivy:
      storageClass: "longhorn"
      accessMode: ReadWriteOnce
      size: 50Gi

harborAdminPassword: "Harbor12345"
EOF
```

---

## 📦 步骤 3: 部署 Harbor

```bash
# 安装 Harbor
helm install harbor harbor/harbor \
  --namespace harbor \
  --create-namespace \
  --version 2.14.3 \
  -f harbor-values.yaml

# 查看部署状态
helm list -n harbor
kubectl get pods -n harbor
kubectl get svc -n harbor

# 等待 Harbor 就绪 (约 5-10 分钟)
kubectl rollout status deployment/harbor-core -n harbor
```

---

## 📦 步骤 4: 访问和验证

```bash
# 获取访问地址
kubectl get ingress -n harbor
# 输出：NAME             CLASS    HOSTS                  ADDRESS   PORTS   AGE
#       harbor-core    traefik   harbor.sisys.local     10.0.0.1   80      5m

# 配置本地 hosts
echo "10.0.0.1 harbor.sisys.local notary.sisys.local" | sudo tee -a /etc/hosts

# 浏览器访问：http://harbor.sisys.local
# 默认账号：admin / Harbor12345!
```

### 验证 Harbor 功能

```bash
# 登录 Harbor
docker login harbor.sisys.local -u admin -p Harbor12345!

# 拉取测试镜像
docker pull nginx:latest

# 打标签
docker tag nginx:latest harbor.sisys.local/library/nginx:latest

# 推送到 Harbor
docker push harbor.sisys.local/library/nginx:latest

# 验证推送成功
curl -X GET http://harbor.sisys.local/api/v2.0/projects/library/repositories/nginx/artifacts \
  -u admin:Harbor12345!
```

---

## 📦 步骤 5: 配置 Gitea Webhook 集成

### 5.1 在 Harbor 中配置 Gitea Webhook

```bash
# 登录 Harbor UI (http://harbor.sisys.local)
# 导航到：项目 → [选择项目] →  webhook
# 点击"新建 Webhook"

# Webhook 配置:
# - 名称：Gitea CI Trigger
# - Webhook URL: http://gitea.sisys.local/api/v1/repos/<owner>/<repo>/hooks
# - 触发事件：Push Event, Pull Request Event
# - 内容类型：application/json
# - 密钥：<生成一个随机密钥>
```

### 5.2 在 Gitea 中配置 Harbor 自动推送

```bash
# 登录 Gitea UI (http://gitea.sisys.local)
# 导航到：仓库 → [选择仓库] → 设置 → Webhooks
# 点击"添加 Webhook" → 选择"Harbor"

# Harbor Webhook 配置:
# - 目标 URL: http://harbor.sisys.local/service/notifications/webhook
# - 密钥：<与 Harbor 配置的密钥相同>
# - 触发事件：Push Events
```

### 5.3 创建 Harbor-Gitea 集成脚本

```bash
#!/bin/bash
# scripts/harbor-gitea-integration.sh
# Harbor 与 Gitea 自动集成脚本

set -e

HARBOR_URL="http://harbor.sisys.local"
GITEA_URL="http://gitea.sisys.local"
HARBOR_USER="admin"
HARBOR_PASSWORD="Harbor12345!"
GITEA_USER="admin"
GITEA_PASSWORD="Admin12345!"
GITEA_TOKEN="<your-gitea-token>"

# 1. 在 Harbor 创建项目
echo "Creating Harbor project..."
curl -X POST "$HARBOR_URL/api/v2.0/projects" \
  -u "$HARBOR_USER:$HARBOR_PASSWORD" \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "sisys",
    "metadata": {"public": "false"},
    "storage_limit": 10737418240
  }'

# 2. 在 Gitea 创建仓库
echo "Creating Gitea repository..."
curl -X POST "$GITEA_URL/api/v1/user/repos" \
  -H "Authorization: token $GITEA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "sisys-images",
    "private": true,
    "description": "Harbor image source repository"
  }'

# 3. 配置 Harbor Webhook 触发 Gitea Actions
echo "Configuring Harbor webhook..."
curl -X POST "$HARBOR_URL/api/v2.0/projects/sisys/webhook/policies" \
  -u "$HARBOR_USER:$HARBOR_PASSWORD" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Trigger Gitea CI",
    "enabled": true,
    "event_types": ["pushImage"],
    "notify_type": "http",
    "payload": {
      "url": "'$GITEA_URL'/api/v1/repos/admin/sisys-images/hooks",
      "skip_cert_verify": true
    }
  }'

echo "✅ Harbor-Gitea 集成完成！"
echo ""
echo "测试流程:"
echo "1. 推送镜像到 Harbor: docker push harbor.sisys.local/sisys/my-app:latest"
echo "2. Gitea 自动触发 CI: http://gitea.sisys.local/admin/sisys-images/actions"
```

### 5.4 验证集成

```bash
# 运行集成脚本
bash scripts/harbor-gitea-integration.sh

# 测试自动触发
# 1. 推送镜像到 Harbor
docker push harbor.sisys.local/sisys/test-app:latest

# 2. 检查 Gitea Actions 是否自动触发
# 访问：http://gitea.sisys.local/admin/sisys-images/actions

# 3. 查看 Harbor 日志
kubectl logs -n harbor -l app=harbor-core | grep webhook
```

---

## 📦 步骤 6: 配置 Harbor 镜像复制

```bash
# 创建镜像复制规则 (自动同步到 Gitea 触发构建)
cat > harbor-replication.yaml <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: harbor-replication
  namespace: harbor
data:
  replication-rules: |
    [
      {
        "name": "Auto-sync to Gitea",
        "src_registry": null,
        "dest_registry": {
          "url": "http://gitea.sisys.local"
        },
        "dest_namespace": "library",
        "filters": [
          {
            "type": "name",
            "value": "sisys/*"
          }
        ],
        "trigger": {
          "type": "event_based",
          "event_types": ["pushImage"]
        }
      }
    ]
EOF

kubectl apply -f harbor-replication.yaml
```

---

## 🔧 故障排查

### Harbor Pod 启动失败

```bash
# 查看 Pod 日志
kubectl logs -n harbor -l app.kubernetes.io/name=core

# 检查数据库连接
kubectl exec -it -n harbor deployment/harbor-core -- nc -zv harbor-database 5432
```

### 镜像推送失败

```bash
# 检查 Registry 状态
kubectl get pods -n harbor | grep registry
kubectl logs -n harbor -l app.kubernetes.io/name=registry

# 检查存储
kubectl get pvc -n harbor
kubectl describe pvc -n harbor
```

---

## ✅ 验收标准

- [ ] Harbor v2.14.3 部署成功
- [ ] 镜像仓库配置完成
- [ ] Trivy 漏洞扫描配置完成
- [ ] 可以通过 http://harbor.local 访问
- [ ] Docker 登录成功
- [ ] 镜像推送/拉取测试通过

---

**下一步：** `docs/deployment/ARGOCD_SETUP.md`
