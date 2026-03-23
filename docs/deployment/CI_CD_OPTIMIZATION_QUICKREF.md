# CI/CD 优化方案 - 快速参考卡片

**版本:** 1.0.0
**日期:** 2026-03-23
**关联 Story:** 0.9 (CI/CD Pipeline 模板)

---

## 🚀 核心优化

### 三层镜像架构

```
Layer 1: PyTorch 基础镜像 (8GB)    → 本地备份，手动更新
Layer 2: 项目依赖镜像 (10GB)       → 周构建 + 依赖变更触发
Layer 3: 应用镜像 (12GB)          → 每次 CI 构建
```

**性能提升:**
- CI 时间：25-35 分钟 → **8-12 分钟** (65% 提升)
- 依赖安装：5-10 分钟 → **0 分钟** (100% 提升)
- 镜像构建：10-15 分钟 → **5-8 分钟** (50% 提升)
- 月节省成本：**~$150+**

---

## 📁 文件结构

```
project/
├── docker/
│   ├── Dockerfile.dependency        # Layer 2: 依赖镜像
│   └── Dockerfile.app               # Layer 3: 应用镜像
├── .gitea/workflows/
│   ├── ci.yaml                      # CI Pipeline (7 阶段)
│   ├── cd.yaml                      # CD Pipeline (5 阶段)
│   └── build-dependency-image.yml   # 依赖镜像构建 (周构建)
├── scripts/image/
│   ├── import-pytorch.sh            # PyTorch 镜像导入
│   └── cleanup-old-versions.sh      # 镜像清理
└── docs/deployment/
    ├── CI_CD_PIPELINE_TEMPLATE.md   # Pipeline 使用指南
    ├── LOCAL_PYTORCH_IMPORT.md      # PyTorch 镜像导入指南
    └── PREBUILT_IMAGE_MAINTENANCE.md # 预构建镜像维护指南
```

---

## 🔧 快速命令

### PyTorch 镜像导入

```bash
# 一键导入 (推荐)
./scripts/image/import-pytorch.sh

# 手动步骤
docker load -i /mnt/x/backup/images/pytorch-pytorch-2.7.1-cuda12.8-cudnn9-devel.tar
docker tag pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel harbor.sisys.local/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel
docker push harbor.sisys.local/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel
```

### 镜像清理

```bash
# 清理旧版本 (保留最近 5 个)
export HARBOR_USERNAME=admin
export HARBOR_PASSWORD=your_password
./scripts/image/cleanup-old-versions.sh
```

### GPU 验证

```bash
# 验证 GPU 支持
docker run --rm --gpus all harbor.sisys.local/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel \
  python3 -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"
```

---

## 📊 Pipeline 阶段

### CI Pipeline (7 阶段)

| 阶段 | 内容 | 时长 | GPU |
|------|------|------|-----|
| 1. 代码质量 | Ruff + MyPy | 2min | ❌ |
| 2. 单元测试 | pytest + 覆盖率 | 3min | ✅ |
| 3. 集成测试 | Docker Compose | 5min | ✅ |
| 4. 安全扫描 | Trivy + Bandit | 2min | ❌ |
| 5. 镜像构建 | Docker Build (多阶段) | 5min | ✅ |
| 6. 镜像推送 | Harbor + 漏洞扫描 | 2min | ✅ |
| 7. 自动部署 | ArgoCD + 健康检查 | 3min | ✅ |

**总计:** ~8-12 分钟

### CD Pipeline (5 阶段)

| 阶段 | 内容 | 时长 |
|------|------|------|
| 1. 部署前验证 | 镜像存在性检查 | 30s |
| 2. 部署到目标环境 | K8s update image | 2min |
| 3. 等待 Rollout | kubectl rollout status | 3min |
| 4. 健康检查 | HTTP 端点验证 | 2min |
| 5. 自动回滚 (可选) | 失败时触发 | 3min |

**总计:** ~5 分钟

---

## ⏰ 触发器配置

### 依赖镜像构建

```yaml
# .gitea/workflows/build-dependency-image.yml
on:
  schedule:
    - cron: '0 3 * * 0'        # 每周日凌晨 3 点
  push:
    paths:
      - 'pyproject.toml'
      - 'poetry.lock'
  workflow_dispatch:           # 手动触发
```

### CI Pipeline

```yaml
# .gitea/workflows/ci.yaml
on:
  push:
    branches: [main, develop, 'feature/**']
  pull_request:
    branches: [main]
```

### CD Pipeline

```yaml
# .gitea/workflows/cd.yaml
on:
  workflow_dispatch:
    inputs:
      environment:
        description: '部署环境'
        required: true
        default: 'production'
  push:
    tags:
      - 'v*.*.*'
```

---

## 🎯 关键配置

### GPU 调度

```yaml
# CI/CD Pipeline 中
jobs:
  unit-test:
    runs-on: [self-hosted, gpu]
    container:
      image: harbor.sisys.local/sisys/dependency:latest
      options: --gpus all
```

### K8s GPU 资源

```yaml
# deployments/k8s/deployment.yaml
spec:
  nodeSelector:
    nvidia.com/gpu.present: "true"
  containers:
  - name: app
    resources:
      requests:
        nvidia.com/gpu: 1
      limits:
        nvidia.com/gpu: 1
```

### 镜像版本管理

```bash
# 依赖镜像版本 (Git SHA)
harbor.sisys.local/sisys/dependency:a1b2c3d

# 应用镜像版本 (Git SHA 或 Tag)
harbor.sisys.local/sisys/app:main-abc123
harbor.sisys.local/sisys/app:v1.0.0
```

---

## 🛠️ 故障排除

### 问题 1: GPU 不可用

```bash
# 检查 NVIDIA Docker
docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu22.04 nvidia-smi

# 检查 GPU Operator
kubectl get pods -n gpu-operator
```

### 问题 2: 镜像拉取失败

```bash
# 检查 Harbor 登录
docker login harbor.sisys.local

# 检查 Secret
kubectl get secret harbor-secret -n sisys
```

### 问题 3: 构建时间过长

```bash
# 检查缓存命中
docker build --progress=plain -f docker/Dockerfile.dependency .

# 查看层缓存
docker history harbor.sisys.local/sisys/dependency:latest
```

---

## 📈 监控指标

### 每日检查

```bash
# 最新镜像版本
curl -sf -u "admin:password" \
  "https://harbor.sisys.local/api/v2.0/projects/sisys/repositories/dependency/artifacts" \
  | jq '.[0].tags[0].name'

# 镜像大小
docker images harbor.sisys.local/sisys/dependency:latest
```

### 每周检查

- [ ] 依赖镜像构建成功 (每周日 3 点)
- [ ] 镜像清理执行 (每周日 4 点)
- [ ] CI 执行时间趋势分析
- [ ] GPU 资源使用率审查

---

## 🔐 Secrets 配置

### Harbor 认证

```bash
# Docker 登录
docker login -u admin -p your_password harbor.sisys.local

# K8s Secret
kubectl create secret docker-registry harbor-secret \
  --docker-server=harbor.sisys.local \
  --docker-username=admin \
  --docker-password=your_password \
  --docker-email=admin@example.com \
  -n sisys
```

### Gitea Actions Secrets

```
# Gitea UI → 仓库 → 设置 → Actions Secrets
HARBOR_ROBOT_USERNAME=robot$sisys
HARBOR_ROBOT_PASSWORD=xxx
KUBECONFIG=base64_encoded_kubeconfig
```

---

## 📋 检查清单

### 首次部署

- [ ] PyTorch 镜像导入 (`./scripts/image/import-pytorch.sh`)
- [ ] Harbor 验证 (`docker pull harbor.sisys.local/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel`)
- [ ] GPU 测试 (`docker run --rm --gpus all ...`)
- [ ] 依赖镜像构建 (触发 `build-dependency-image.yml`)
- [ ] CI Pipeline 测试 (推送代码触发)
- [ ] CD Pipeline 测试 (手动触发部署)

### 日常运维

- [ ] CI Pipeline 执行状态检查
- [ ] GPU 资源使用情况检查
- [ ] Harbor 存储容量检查
- [ ] 镜像清理脚本执行 (每周日)

---

## 🔗 相关文档

| 文档 | 用途 |
|------|------|
| [CI_CD_PIPELINE_TEMPLATE.md](./CI_CD_PIPELINE_TEMPLATE.md) | Pipeline 完整使用指南 |
| [LOCAL_PYTORCH_IMPORT.md](./LOCAL_PYTORCH_IMPORT.md) | PyTorch 镜像导入步骤 |
| [PREBUILT_IMAGE_MAINTENANCE.md](./PREBUILT_IMAGE_MAINTENANCE.md) | 预构建镜像维护指南 |
| Story 0.9 | 故事文件 (需求来源) |

---

## 💡 最佳实践

### ✅ 推荐

- 固定依赖版本 (`torch = "2.7.1"`)
- 使用 Git SHA 版本化镜像
- 多阶段构建优化镜像大小
- 使用 `.dockerignore` 排除不必要文件
- 定期清理旧镜像 (保留 5 个版本)

### ❌ 避免

- 使用 `latest` 标签 (不可追溯)
- 依赖版本范围过宽 (`torch = "*"`)
- 复制整个项目到镜像 (`COPY . .`)
- 每个命令创建新层 (合并 `RUN` 指令)
- 忽略安全扫描结果

---

**最后更新:** 2026-03-23
**维护者:** Agimtech DevOps Team
**下次审查:** 2026-04-23
