# Harbor 镜像推送快速指南

**文档版本:** 1.0
**更新日期:** 2026-03-18
**Harbor 状态:** ✅ 已部署 (8/8 Pod Running)

---

## 📋 系统现状

| 项目 | 状态 | 说明 |
|------|------|------|
| **Harbor 版本** | v2.14.3 | ✅ 已部署 |
| **Harbor API** | ✅ 可访问 | https://<WSL2_IP>:<NODEPORT> |
| **管理员凭据** | admin/Admin@123456 | ✅ 已验证 |
| **项目 'sisys'** | ✅ 已创建 | project_id=2 |
| **Robot Account** | ❌ 未创建 | 需要创建 |
| **Docker insecure** | ❌ 未配置 | 需要配置 |
| **K3S registries** | ❌ 未配置 | 需要配置 |

---

## 🚀 快速推送方案（3 步）

### 方案 1: Docker 推送（推荐）

#### 步骤 1: 创建 Robot Account

```bash
# 登录 Harbor Web 界面
# https://<WSL2_IP>:<NODEPORT> (浏览器访问)
# 用户名：admin
# 密码：Admin@123456

# 手动创建 Robot Account:
# 1. 进入项目 → sisys → Robot Accounts
# 2. 点击"+ New Robot Account"
# 3. 填写：
#    - Name: gitea-runner-push
#    - Permissions: Push, Pull
#    - Expiration: -1 (永不过期)
# 4. 保存生成的 Token（示例：robot$gitea-runner-push:xxxxxxxx）
```

**或使用 API 自动创建:**
```bash
# 创建 Robot Account
curl -k -X POST \
  -u admin:Admin@123456 \
  "https://<WSL2_IP>:<NODEPORT>/api/v2.0/robots" \
  -H "Host: harbor.sisys.local" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "gitea-runner-push",
    "description": "Gitea Runner 推送镜像到 Harbor",
    "duration": -1,
    "level": "project",
    "permissions": [
      {
        "kind": "project",
        "namespace": "sisys",
        "access": [
          {"resource": "repository", "action": "push"},
          {"resource": "repository", "action": "pull"}
        ]
      }
    ]
  }' | jq

# 保存返回的 .secret 字段（Robot Token）
```

#### 步骤 2: 配置 Docker 信任 Harbor

```bash
# 配置 insecure-registries
sudo tee /etc/docker/daemon.json << 'EOF'
{
    "insecure-registries": [
        "harbor.sisys.local"
    ]
}
EOF

# 重启 Docker
sudo systemctl restart docker

# 验证配置
docker info | grep -A5 "Insecure Registries"
```

#### 步骤 3: 登录并推送镜像

```bash
# Docker 登录（使用 Robot Token）
docker login harbor.sisys.local \
  -u 'robot$gitea-runner-push' \
  -p 'YOUR_ROBOT_TOKEN_HERE'

# 推送镜像
docker tag nginx:alpine harbor.sisys.local/sisys/test-app:v1.0.0
docker push harbor.sisys.local/sisys/test-app:v1.0.0
```

---

### 方案 2: k3s ctr 推送（K3S 原生）

```bash
# 1. 拉取测试镜像
sudo k3s ctr images pull docker.io/library/nginx:alpine

# 2. 重新标记
sudo k3s ctr images tag docker.io/library/nginx:alpine \
  harbor.sisys.local/sisys/test-app:v1.0.0

# 3. 推送（使用 Robot Token）
sudo k3s ctr images push \
  -u 'robot$gitea-runner-push:YOUR_ROBOT_TOKEN_HERE' \
  harbor.sisys.local/sisys/test-app:v1.0.0
```

---

### 方案 3: 自动化脚本（一键配置）

```bash
# 运行自动化配置脚本
bash scripts/deployment/harbor/push-image-to-harbor.sh

# 脚本会自动完成：
# ✅ 创建 Robot Account
# ✅ 配置 Docker insecure-registries
# ✅ 配置 K3S registries.yaml
# ✅ Docker 登录 Harbor
# ✅ 推送测试镜像
# ✅ 验证 K3S 镜像拉取
```

---

## 🔧 K3S 配置（镜像拉取）

### 配置 K3S 信任 Harbor

**方式 1: 使用证书（推荐）**
```bash
# 获取 Harbor 证书
sudo kubectl get secret harbor-tls-secret -n harbor \
  -o jsonpath='{.data.tls\.crt}' | base64 -d > /tmp/harbor-ca.crt

# 复制到 K3S 信任目录
sudo mkdir -p /var/lib/rancher/k3s/agent/etc/ssl/certs
sudo cp /tmp/harbor-ca.crt /var/lib/rancher/k3s/agent/etc/ssl/certs/harbor-ca.crt

# 创建 registries.yaml
sudo tee /etc/rancher/k3s/registries.yaml << 'EOF'
mirrors:
  harbor.sisys.local:
    endpoint:
      - https://harbor.sisys.local
configs:
  harbor.sisys.local:
    tls:
      ca_file: /var/lib/rancher/k3s/agent/etc/ssl/certs/harbor-ca.crt
    auth:
      username: robot$gitea-runner-push
      password: YOUR_ROBOT_TOKEN_HERE
EOF

# 重启 K3S
sudo systemctl restart k3s
```

**方式 2: HTTP 模式（开发测试）**
```bash
sudo tee /etc/rancher/k3s/registries.yaml << 'EOF'
mirrors:
  harbor.sisys.local:
    endpoint:
      - http://<WSL2_IP>:nodeport
configs:
  harbor.sisys.local:
    tls:
      insecure_skip_verify: true
    auth:
      username: robot$gitea-runner-push
      password: YOUR_ROBOT_TOKEN_HERE
EOF

sudo systemctl restart k3s
```

---

## ✅ 验证步骤

### 1. 验证 Harbor 中的镜像

```bash
# API 查询
curl -k -u admin:Admin@123456 \
  "https://<WSL2_IP>:<NODEPORT>/api/v2.0/projects/sisys/repositories" \
  -H "Host: harbor.sisys.local" | jq '.[].name'

# 预期输出：["sisys/test-app"]
```

### 2. 验证 K3S 镜像拉取

```bash
# 使用 k3s ctr 拉取
sudo k3s ctr images pull harbor.sisys.local/sisys/test-app:v1.0.0

# 查看本地镜像
sudo k3s ctr images ls | grep test-app
```

### 3. 验证 Kubernetes Pod 部署

```bash
# 创建测试 Pod
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: test-harbor-image
  namespace: default
spec:
  containers:
  - name: test-app
    image: harbor.sisys.local/sisys/test-app:v1.0.0
    ports:
    - containerPort: 80
  imagePullSecrets:
  - name: harbor-pull-secret
EOF

# 查看 Pod 状态
kubectl get pod test-harbor-image -o wide
kubectl logs test-harbor-image

# 清理
kubectl delete pod test-harbor-image
```

---

## 🔐 Robot Account 管理

### 查看现有 Robot Account

```bash
curl -k -u admin:Admin@123456 \
  "https://<WSL2_IP>:<NODEPORT>/api/v2.0/robots" \
  -H "Host: harbor.sisys.local" | jq
```

### 删除 Robot Account

```bash
# 先获取 Robot ID
ROBOT_ID=$(curl -k -u admin:Admin@123456 \
  "https://<WSL2_IP>:<NODEPORT>/api/v2.0/robots" \
  -H "Host: harbor.sisys.local" | \
  jq -r '.[] | select(.name=="gitea-runner-push") | .id')

# 删除
curl -k -X DELETE \
  -u admin:Admin@123456 \
  "https://<WSL2_IP>:<NODEPORT>/api/v2.0/robots/${ROBOT_ID}" \
  -H "Host: harbor.sisys.local"
```

---

## 🐛 故障排除

### 问题 1: 401 Unauthorized

**原因:** 认证失败

**解决:**
```bash
# 检查 Robot Token 是否正确
docker logout harbor.sisys.local
docker login harbor.sisys.local \
  -u 'robot$gitea-runner-push' \
  -p 'YOUR_ROBOT_TOKEN_HERE'

# 验证 Token 格式：robot$NAME:TOKEN
```

### 问题 2: TLS 证书错误

**原因:** 自签名证书不受信任

**解决:**
```bash
# 方式 1: 导入证书到信任链
sudo cp /tmp/harbor-ca.crt /usr/local/share/ca-certificates/
sudo update-ca-certificates
sudo systemctl restart docker

# 方式 2: 使用 insecure-registries（开发环境）
# 参考上文配置
```

### 问题 3: K3S 无法拉取镜像

**原因:** registries.yaml 配置错误

**解决:**
```bash
# 检查配置
cat /etc/rancher/k3s/registries.yaml

# 验证格式（注意 YAML 缩进）
# 重启 K3S
sudo systemctl restart k3s

# 查看日志
sudo journalctl -u k3s -f | grep -i "harbor"
```

---

## 📊 方案对比

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| **Docker 推送** | 简单直观，调试方便 | 需要配置 insecure | 开发/测试 |
| **k3s ctr 推送** | K3S 原生，无需额外配置 | 命令较复杂 | K3S 环境 |
| **自动化脚本** | 一键配置，省时省力 | 需要审查脚本 | 批量部署 |

---

## 🎯 推荐流程

**开发环境:**
1. 运行自动化脚本配置
2. Docker 推送测试镜像
3. 验证 K3S 拉取

**生产环境:**
1. 配置 Let's Encrypt 证书
2. 创建 Robot Account
3. 配置 K3S 证书信任
4. CI/CD Pipeline 自动推送

---

## 📚 相关文档

- [Harbor 官方文档](https://goharbor.io/docs/)
- [Robot Account 配置](./HARBOR_ROBOT_ACCOUNT.md)
- [K3S 部署指南](./K3S_DEPLOYMENT_GUIDE.md)
- [认证审计报告](../../_bmad-output/implementation-artifacts/stories/0-4-0-7-authentication-audit-report.md)

---

**最后更新:** 2026-03-18
**维护者:** DevOps Team
