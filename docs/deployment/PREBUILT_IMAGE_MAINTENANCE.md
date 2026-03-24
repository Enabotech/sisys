# 预构建镜像维护指南

## 目录

1. [概述](#概述)
2. [镜像架构](#镜像架构)
3. [构建流程](#构建流程)
4. [更新策略](#更新策略)
5. [版本管理](#版本管理)
6. [故障恢复](#故障恢复)
7. [监控指标](#监控指标)

---

## 概述

预构建镜像系统通过分层镜像架构加速 CI/CD Pipeline，将依赖安装时间从 5-10 分钟降至 0 分钟。

### 镜像分层

| 层级 | 镜像 | 大小 | 更新频率 | 用途 |
|------|------|------|----------|------|
| **Layer 1** | PyTorch 基础镜像 | ~8GB | 手动 (版本升级) | 提供 CUDA/cuDNN 环境 |
| **Layer 2** | 项目依赖镜像 | ~2GB | 每周 + 依赖变更 | 预装 Poetry 依赖 |
| **Layer 3** | 应用镜像 | ~2GB | 每次提交 | 业务代码 |

---

## 镜像架构

### Layer 1: PyTorch 基础镜像

**镜像信息**:
- 基础：`pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel`
- 来源：本地备份 `/mnt/x/backup/images/pytorch-...tar`
- 推送目标：`harbor.sisys.local/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel`

**导入步骤**:

```bash
# 1. 导入镜像
./scripts/image/import-pytorch.sh

# 2. 验证导入
docker images | grep pytorch

# 3. 验证 GPU
docker run --rm --gpus all \
  harbor.sisys.local/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel \
  python3 -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"
```

### Layer 2: 依赖镜像

**Dockerfile**: `docker/Dockerfile.dependency`

**构建触发**:
- 定时：每周日 18:00 (北京时间)
- 事件：`pyproject.toml` 或 `poetry.lock` 变更

**推送目标**:
- `harbor.sisys.local/sisys/dependency:${GIT_SHA}`
- `harbor.sisys.local/sisys/dependency:latest`
- `harbor.sisys.local/sisys/dependency:weekly-YYYYMMDD`

### Layer 3: 应用镜像

**Dockerfile**: `docker/Dockerfile.app`

**构建触发**: 每次代码提交

**推送目标**:
- `harbor.sisys.local/sisys/app:${GIT_SHA}`
- `harbor.sisys.local/sisys/app:latest`

---

## 构建流程

### 手动构建依赖镜像

```bash
# 1. 登录 Harbor
docker login harbor.sisys.local

# 2. 构建镜像
docker build -f docker/Dockerfile.dependency \
  --build-arg PYTORCH_IMAGE=harbor.sisys.local/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel \
  --build-arg PYTHON_VERSION=3.11 \
  --build-arg POETRY_VERSION=1.8.0 \
  -t harbor.sisys.local/sisys/dependency:test \
  .

# 3. 推送镜像
docker push harbor.sisys.local/sisys/dependency:test

# 4. 验证镜像
docker run --rm harbor.sisys.local/sisys/dependency:test poetry --version
```

### 自动化构建

```yaml
# .gitea/workflows/build-dependency-image.yml
# 已配置自动触发
# 查看构建历史：Gitea UI → Actions → Build Dependency Image
```

---

## 更新策略

### 何时更新 Layer 1

- PyTorch 版本升级
- CUDA 版本升级
- 基础镜像安全漏洞

**流程**:

```bash
# 1. 下载新基础镜像
docker pull pytorch/pytorch:2.8.0-cuda13.0-cudnn9-devel

# 2. 导入本地备份 (如果有)
docker load -i pytorch-2.8.0.tar

# 3. 推送到 Harbor
docker tag pytorch/pytorch:2.8.0-cuda13.0-cudnn9-devel \
  harbor.sisys.local/sisys/pytorch/pytorch:2.8.0-cuda13.0-cudnn9-devel
docker push harbor.sisys.local/sisys/pytorch/pytorch:2.8.0-cuda13.0-cudnn9-devel

# 4. 更新配置
# 更新 CI/CD Pipeline 中的 PYTORCH_IMAGE 变量
# 更新 Dockerfile.dependency 中的 ARG
```

### 何时更新 Layer 2

- `pyproject.toml` 依赖变更
- 每周定期更新 (安全补丁)
- 依赖镜像构建失败

**流程**:

```bash
# 1. 更新依赖
poetry add new-package
poetry update

# 2. 提交变更
git add pyproject.toml poetry.lock
git commit -m "chore: 更新依赖"
git push

# 3. 自动触发构建
# 查看构建状态：Gitea Actions
```

### 何时更新 Layer 3

- 业务代码变更
- 配置变更
- 自动触发 (CI Pipeline)

---

## 版本管理

### 标签策略

```yaml
# Git SHA 标签 (主要)
dependency:a1b2c3d
app:e5f6g7h

# 最新标签 (指向最新)
dependency:latest
app:latest

# 周标签 (仅依赖镜像)
dependency:weekly-20260323

# 版本标签 (可选)
dependency:v1.0.0
app:v1.0.0
```

### 保留策略

**规则**:
- Layer 1: 保留所有版本 (不常更新)
- Layer 2: 保留最近 5 个版本
- Layer 3: 保留最近 10 个版本 + latest

**清理脚本**:

```bash
# 清理旧版本
./scripts/image/cleanup-old-versions.sh

# 自定义保留数量
KEEP_COUNT=10 ./scripts/image/cleanup-old-versions.sh

# 清理特定仓库
./scripts/image/cleanup-old-versions.sh --repos dependency
```

### 版本追溯

```bash
# 查看镜像历史
docker history harbor.sisys.local/sisys/dependency:latest

# 查看构建信息
docker inspect harbor.sisys.local/sisys/dependency:latest | jq '.[0].Config.Labels'

# 查看 Git 提交
git log -1 --format="%H %s" a1b2c3d
```

---

## 故障恢复

### 构建失败

**症状**: `error building image`

**恢复步骤**:

```bash
# 1. 查看构建日志
# Gitea UI → Actions → Build Dependency Image → 查看日志

# 2. 本地构建测试
docker build -f docker/Dockerfile.dependency .

# 3. 检查依赖文件
poetry check
poetry lock --no-update

# 4. 清理缓存重试
docker builder prune -a
docker build --no-cache -f docker/Dockerfile.dependency .
```

### 镜像损坏

**症状**: `image pull failed: checksum mismatch`

**恢复步骤**:

```bash
# 1. 删除损坏镜像
docker rmi harbor.sisys.local/sisys/dependency:latest

# 2. 重新拉取
docker pull harbor.sisys.local/sisys/dependency:latest

# 3. 如果仍然失败，回滚到上一版本
# Harbor UI → 项目 → 仓库 → dependency → 标签
# 选择上一版本并重新推送
```

### GPU 兼容性失败

**症状**: `CUDA error: driver version is too old`

**恢复步骤**:

```bash
# 1. 检查驱动版本
nvidia-smi

# 2. 验证镜像 CUDA 版本
docker run --rm --gpus all \
  harbor.sisys.local/sisys/pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel \
  python3 -c "import torch; print(torch.version.cuda)"

# 3. 如果不匹配，更新基础镜像
# 参考 Layer 1 更新流程
```

---

## 监控指标

### 构建性能

| 指标 | 目标值 | 告警阈值 |
|------|--------|----------|
| 构建时间 (Layer 2) | < 10 分钟 | > 20 分钟 |
| 构建时间 (Layer 3) | < 8 分钟 | > 15 分钟 |
| 构建成功率 | > 95% | < 90% |
| 镜像大小 (Layer 2) | < 3GB | > 5GB |

### 使用指标

| 指标 | 目标值 | 告警阈值 |
|------|--------|----------|
| 镜像拉取时间 | < 2 分钟 | > 5 分钟 |
| 缓存命中率 | > 80% | < 60% |
| 周构建次数 | 1-2 次 | > 5 次 |

### 查看监控

```bash
# Harbor 统计
# Harbor UI → 管理 → 统计

# Prometheus 指标
# 访问 http://harbor.sisys.local/metrics
```

---

## 成本优化

### 存储成本

```bash
# 查看存储使用
du -sh /var/lib/docker

# Harbor 存储
# Harbor UI → 管理 → 存储

# 清理未使用镜像
docker image prune -a
```

### 构建成本

```yaml
# 使用缓存减少构建时间
cache-from: type=registry,ref=harbor.sisys.local/sisys/dependency:buildcache
cache-to: type=registry,ref=harbor.sisys.local/sisys/dependency:buildcache,mode=max

# 预计节省
# 原构建时间：10 分钟
# 优化后：5 分钟
# 节省：50%
```

---

## 安全检查

### 漏洞扫描

```bash
# Harbor 自动扫描
# Harbor UI → 项目 → 仓库 → 镜像 → 漏洞扫描

# 手动扫描
trivy image harbor.sisys.local/sisys/dependency:latest

# 修复漏洞
# 1. 更新基础镜像
# 2. 更新依赖
poetry update
```

### 镜像签名 (可选)

```bash
# 使用 Cosign 签名
cosign sign harbor.sisys.local/sisys/dependency:latest

# 验证签名
cosign verify harbor.sisys.local/sisys/dependency:latest
```

---

## 最佳实践

### 1. 定期更新

```bash
# 每周日检查依赖更新
poetry update

# 每月检查基础镜像更新
# PyTorch 官网查看最新版本
```

### 2. 版本锁定

```bash
# 始终使用 poetry.lock
poetry lock

# CI 中使用锁定版本
poetry install --no-interaction
```

### 3. 镜像优化

```dockerfile
# 使用 .dockerignore
# 多阶段构建
# 清理缓存
RUN apt-get clean && rm -rf /var/lib/apt/lists/*
```

### 4. 监控告警

```yaml
# 配置 Harbor 通知
# Harbor UI → 管理 → 通知 → Webhook

# 配置构建失败通知
# Gitea UI → 仓库设置 → Actions → 通知
```

---

## 相关文档

- [CI/CD Pipeline 模板使用指南](./CI_CD_PIPELINE_TEMPLATE.md)
- [本地 PyTorch 镜像导入指南](./LOCAL_PYTORCH_IMPORT.md)
