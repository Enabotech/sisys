# Harbor 集成配置指南

**Story**: 0.8 - Gitea Runner Configuration
**Task**: 6 - Harbor Integration Configuration
**前置依赖**: Story 0.6 (Harbor 镜像仓库部署 ✅)

---

## 📋 概述

本指南介绍如何配置 Gitea Runner 与 Harbor 镜像仓库的集成，实现 CI/CD Pipeline 自动推送镜像并触发漏洞扫描。

### 架构图

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Gitea     │ ───► │ Gitea Runner │ ───► │   Harbor    │
│  Repository │      │  (CI/CD)     │      │  (Registry) │
└─────────────┘      └──────────────┘      └─────────────┘
                            │                     │
                            │                     ▼
                            │            ┌─────────────┐
                            │            │   Trivy     │
                            │            │  (Scanner)  │
                            │            └─────────────┘
                            ▼
                     ┌──────────────┐
                     │  ArgoCD      │
                     │  (Deploy)    │
                     └──────────────┘
```

### 认证流程

1. **Robot Account** - 为自动化系统创建的专用账号
2. **Kubernetes Secret** - 安全存储 Docker Registry 凭据
3. **imagePullSecrets** - Pod 自动使用 Secret 进行认证

---

## 🚀 快速开始

### 步骤 1: 创建 Harbor Robot Account

#### 方式 A: 通过 Harbor Web 界面（推荐）

1. 登录 Harbor Web 界面：`https://harbor.sisys.local`
2. 进入项目 → `sisys` → Robot Accounts
3. 点击 "New Robot Account"
4. 填写信息：
   - **Name**: `gitea-runner-push`
   - **Permissions**: Push, Pull
   - **Expiration**: 365 days (或 -1 永不过期)
5. 保存生成的 Token（格式：`robot$gitea-runner-push:<token>`）

#### 方式 B: 通过 Harbor API

```bash
#!/bin/bash
HARBOR_URL="https://harbor.sisys.local"
HARBOR_USER="admin"
HARBOR_PASSWORD="Harbor@2026Secure!"  # pragma: allowlist secret (example only)
PROJECT_NAME="sisys"

# 获取项目 ID
PROJECT_ID=$(curl -s -k -u "$HARBOR_USER:$HARBOR_PASSWORD" \
  "$HARBOR_URL/api/v2.0/projects?name=$PROJECT_NAME" | jq '.[0].project_id')

# 创建 Robot Account
curl -s -k -u "$HARBOR_USER:$HARBOR_PASSWORD" \
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
          {"resource": "artifact", "action": "create"}
        ]
      }
    ]
  }' | jq .
```

---

### 步骤 2: 生成 Docker Config JSON

```bash
#!/bin/bash
export HARBOR_URL="harbor.sisys.local"
export ROBOT_USER="robot\$gitea-runner-push"
export ROBOT_TOKEN="<从 Harbor 复制的 Token>"

# 生成认证字符串
export AUTH=$(echo -n "$ROBOT_USER:$ROBOT_TOKEN" | base64 -w0)

# 生成 dockerconfigjson
cat <<EOF | base64 -w0
{"auths":{"$HARBOR_URL":{"username":"$ROBOT_USER","password":"$ROBOT_TOKEN","auth":"$AUTH"}}}
EOF
```

---

### 步骤 3: 更新 Kubernetes Secret

编辑 `deployments/gitea-runner/harbor-robot-secret.yaml`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: harbor-robot-account
  namespace: gitea-actions
type: kubernetes.io/dockerconfigjson
data:
  # 替换为步骤 2 生成的 base64 编码
  .dockerconfigjson: <base64 编码的 docker config json>
```

---

### 步骤 4: 部署 Secret

```bash
# 部署 Secret
bash scripts/deployment/gitea-runner/deploy-harbor-secret.sh

# 验证部署
bash scripts/deployment/gitea-runner/validate-harbor-secret.sh
```

---

### 步骤 5: 测试 Docker Push

```bash
# 测试推送（需要真实 Token）
bash scripts/deployment/gitea-runner/test-harbor-push.sh
```

---

### 步骤 6: 验证 Trivy 扫描

```bash
# 验证 Trivy 自动扫描
bash scripts/deployment/gitea-runner/verify-trivy-scan.sh
```

---

## 📁 配置文件说明

### 文件结构

```
deployments/gitea-runner/
├── harbor-robot-secret.yaml       # Harbor Robot Account Secret
└── runner-docker-executor.yaml    # Docker Executor 配置（含 Harbor 集成）

scripts/deployment/gitea-runner/
├── deploy-harbor-secret.sh        # Secret 部署脚本
├── validate-harbor-secret.sh      # Secret 验证脚本
├── test-harbor-push.sh            # Docker Push 测试脚本
└── verify-trivy-scan.sh           # Trivy 扫描验证脚本

tests/deployment/
└── test_gitea_harbor_integration.py  # Harbor 集成测试
```

---

## 🔧 配置详解

### Docker Executor 中的 Harbor 配置

```yaml
# deployments/gitea-runner/runner-docker-executor.yaml

container:
  # Harbor 集成配置
  registry:
    harbor:
      url: https://harbor.sisys.local
      # 使用 imagePullSecrets 进行认证
      auth_secret: harbor-robot-account
      # 跳过 TLS 验证（开发环境）
      insecure: false
      # 镜像推送配置
      push:
        timeout: 5m
        retries: 3

  # 镜像拉取配置
  image_pull:
    policy: IfNotPresent
    # 使用本地 Harbor 作为镜像源
    mirrors:
      - https://harbor.sisys.local
    # 预拉取镜像列表
    prefetch:
      - harbor.sisys.local/sisys/base:latest
```

---

## 🧪 测试验证

### 测试清单

- [ ] Secret 部署成功
- [ ] Secret 类型正确（kubernetes.io/dockerconfigjson）
- [ ] dockerconfigjson 格式正确
- [ ] Harbor 注册表配置存在
- [ ] Docker 登录成功
- [ ] Docker 推送成功
- [ ] Trivy 自动扫描触发
- [ ] 扫描结果显示在 Harbor 界面

### 运行所有测试

```bash
# 单元测试（需要 pytest）
pytest tests/deployment/test_gitea_harbor_integration.py -v

# 集成测试（需要 K8s 集群和 Harbor 运行）
bash scripts/deployment/gitea-runner/deploy-harbor-secret.sh
bash scripts/deployment/gitea-runner/validate-harbor-secret.sh
bash scripts/deployment/gitea-runner/test-harbor-push.sh
bash scripts/deployment/gitea-runner/verify-trivy-scan.sh
```

---

## 🚨 故障排除

### 问题 1: 认证失败

**症状**: `unauthorized: authentication required`

**解决方案**:
1. 检查 Robot Account Token 是否正确
2. 验证 Secret 中的 dockerconfigjson 格式
3. 确认 Robot Account 有 Push/Pull 权限

```bash
# 验证 Secret
kubectl get secret harbor-robot-account -n gitea-actions -o yaml

# 解码 dockerconfigjson
kubectl get secret harbor-robot-account -n gitea-actions \
  -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d | jq .
```

---

### 问题 2: 推送失败

**症状**: `denied: requested access to the resource is denied`

**解决方案**:
1. 检查 Robot Account 的项目权限
2. 确认项目名称正确（`sisys`）
3. 验证 Harbor 项目不是私有

```bash
# 测试推送
docker push harbor.sisys.local/sisys/test:latest
```

---

### 问题 3: Trivy 扫描未触发

**症状**: 镜像推送后没有自动扫描

**解决方案**:
1. 检查 Harbor 项目扫描策略是否启用
2. 验证 Trivy 组件运行正常
3. 查看 Trivy Pod 日志

```bash
# 检查 Trivy Pod
kubectl get pods -n harbor -l app=trivy

# 查看 Trivy 日志
kubectl logs -n harbor <trivy-pod-name> | tail -100
```

---

### 问题 4: TLS 证书错误

**症状**: `x509: certificate signed by unknown authority`

**解决方案**:
1. 配置 `insecure: true`（仅开发环境）
2. 或使用有效 TLS 证书
3. 或将 Harbor CA 添加到信任列表

```yaml
# 开发环境（不推荐生产）
registry:
  harbor:
    insecure: true
```

---

## 🔒 安全最佳实践

### 1. Token 管理

- **轮换周期**: 建议每 90 天轮换一次
- **存储方式**: 仅存储在 Kubernetes Secret 中
- **权限最小化**: 仅授予必要的 Push/Pull 权限

### 2. Secret 管理

```bash
# 使用外部 Secret 管理工具（推荐）
# 例如：Sealed Secrets, External Secrets, Vault

# 查看 Secret 访问权限
kubectl auth can-i get secrets -n gitea-actions
```

### 3. 网络安全

- 使用 HTTPS 通信
- 配置 NetworkPolicy 限制访问
- 仅允许 Gitea Runner 访问 Harbor

---

## 📊 监控指标

### Prometheus Metrics

```yaml
# Harbor 推送指标
- harbor_artifact_push_total{project="sisys"}  # 推送次数
- harbor_artifact_push_duration_seconds        # 推送耗时

# Trivy 扫描指标
- trivy_scan_total{status="success"}           # 扫描次数
- trivy_scan_vulnerabilities{severity="High"}  # 漏洞数量
```

### Grafana 仪表盘

建议创建以下仪表盘：
1. **Harbor 推送监控** - 推送次数、成功率、耗时
2. **Trivy 扫描监控** - 扫描次数、漏洞趋势
3. **Gitea Pipeline 监控** - CI/CD 执行状态

---

## 📚 参考文档

- [Source: deployments/harbor/robot-account.yaml] - Story 0.6 Robot Account 配置
- [Source: deployments/gitea-runner/runner-docker-executor.yaml] - Docker Executor 配置
- [Source: https://goharbor.io/docs/2.10.0/administration/user-management/robot-accounts/] - Harbor Robot Account 官方文档
- [Source: https://goharbor.io/docs/2.10.0/administration/vulnerability-scanning/] - Harbor 漏洞扫描官方文档
- [Source: https://kubernetes.io/docs/tasks/configure-pod-container/pull-image-private-registry/] - Kubernetes Docker Registry 认证

---

## ✅ 验收标准

Task 6 完成当以下所有条件满足：

- [x] Harbor Robot Account Secret 已创建
- [x] Secret 类型为 kubernetes.io/dockerconfigjson
- [x] Secret 已部署到 gitea-actions 命名空间
- [x] Docker 登录测试通过
- [x] Docker 推送测试通过
- [x] Trivy 自动扫描验证通过
- [x] 测试文件已创建：`test_gitea_harbor_integration.py`
- [x] 部署脚本已创建：`deploy-harbor-secret.sh`
- [x] 验证脚本已创建：`validate-harbor-secret.sh`, `test-harbor-push.sh`, `verify-trivy-scan.sh`
- [x] 文档已创建：`HARBOR_INTEGRATION_CONFIG.md`

---

**最后更新**: 2026-03-22
**维护者**: Agimtech
**状态**: ✅ 完成
