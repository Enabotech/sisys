# 预构建镜像维护指南

**版本:** 1.0.0
**日期:** 2026-03-23
**关联 Story:** 0.9 (CI/CD Pipeline 模板)

---

## 📋 概述

本指南说明如何维护 SISYS 项目的三层镜像架构，确保 CI/CD Pipeline 高效运行。

### 三层镜像架构

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: 基础镜像 (PyTorch)                                 │
│  镜像：harbor.sisys.local/sisys/pytorch-base:2.7.1-cuda12.8 │
│  大小：~8GB                                                  │
│  更新：手动 (版本升级时)                                     │
│  维护：本文档第 3 章                                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: 依赖镜像 (Poetry 安装)                              │
│  镜像：harbor.sisys.local/sisys/dependency:{git-sha}        │
│  大小：~10GB (Layer 1 + 1-2GB)                               │
│  更新：每周日 3 点 + 依赖文件变更                            │
│  维护：本文档第 4 章                                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: 应用镜像 (业务代码)                                │
│  镜像：harbor.sisys.local/sisys/app:{git-sha}               │
│  大小：~12GB (Layer 2 + 2GB)                                 │
│  更新：每次代码提交                                          │
│  维护：本文档第 5 章                                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 维护目标

| 指标 | 目标值 | 测量方式 |
|------|--------|---------|
| **依赖镜像新鲜度** | < 7 天 | 最后一次构建时间 |
| **镜像构建成功率** | > 95% | CI Pipeline 统计 |
| **CI 执行时间** | < 12 分钟 | Pipeline 日志 |
| **镜像存储成本** | < 100GB | Harbor 统计 |
| **GPU 测试覆盖率** | 100% | 测试报告 |

---

## 🔧 Layer 1: 基础镜像维护

### 3.1 当前版本信息

**镜像:** `harbor.sisys.local/sisys/pytorch-base:2.7.1-cuda12.8`

**规格:**
- PyTorch: 2.7.1
- CUDA: 12.8
- cuDNN: 9
- Python: 3.11+
- 基础系统：Ubuntu 22.04

**来源:** `/mnt/x/backup/images/pytorch-pytorch-2.7.1-cuda12.8-cudnn9-devel.tar`

### 3.2 何时更新

| 场景 | 操作 | 优先级 |
|------|------|--------|
| PyTorch 大版本更新 (2.x → 3.x) | 立即更新 | 🔴 高 |
| CUDA 安全漏洞 | 立即更新 | 🔴 高 |
| PyTorch 小版本更新 (2.7 → 2.8) | 评估后更新 | 🟡 中 |
| 性能优化需求 | 按需更新 | 🟢 低 |

### 3.3 更新流程

```bash
# 1. 下载新镜像
docker pull pytorch/pytorch:3.0.0-cuda13.0-cudnn9-devel

# 2. 本地测试
docker run --rm --gpus all pytorch/pytorch:3.0.0-cuda13.0-cudnn9-devel \
  python3 -c "import torch; print(torch.__version__)"

# 3. 推送到 Harbor
docker tag pytorch/pytorch:3.0.0-cuda13.0-cudnn9-devel \
  harbor.sisys.local/sisys/pytorch-base:3.0.0-cuda13.0

docker push harbor.sisys.local/sisys/pytorch-base:3.0.0-cuda13.0

# 4. 更新文档
# 修改本文件中的版本信息

# 5. 通知团队
# 发送更新通知邮件/消息
```

### 3.4 备份策略

```bash
# 定期备份到 NAS
docker save harbor.sisys.local/sisys/pytorch-base:2.7.1-cuda12.8 \
  | gzip > /mnt/x/backup/images/pytorch-base-2.7.1-cuda12.8-$(date +%Y%m%d).tar.gz

# 验证备份
docker load -i /mnt/x/backup/images/pytorch-base-2.7.1-cuda12.8-20260323.tar.gz
```

---

## 🔧 Layer 2: 依赖镜像维护

### 4.1 自动构建触发器

**触发条件:**
1. **定时触发:** 每周日凌晨 3 点
2. **文件变更:** `pyproject.toml` 或 `poetry.lock` 变更
3. **手动触发:** 紧急修复

**配置文件:** `.gitea/workflows/build-dependency-image.yml`

### 4.2 版本管理策略

**版本命名:**
```
harbor.sisys.local/sisys/dependency:{git-sha}

示例:
- dependency:a1b2c3d  (当前)
- dependency:e4f5g6h  (历史)
```

**保留策略:**
- 保留最近 **5 个** 版本
- `latest` 标签始终指向最新版本
- 每周自动清理旧版本

### 4.3 监控指标

**每日检查:**
```bash
# 1. 检查最新镜像版本
curl -sf -u "admin:password" \
  "https://harbor.sisys.local/api/v2.0/projects/sisys/repositories/dependency/artifacts" \
  | jq '.[0].tags[0].name'

# 2. 检查镜像大小
docker images harbor.sisys.local/sisys/dependency:latest

# 3. 检查构建成功率 (过去 7 天)
# Harbor UI → 项目 → sisys → 仓库 → dependency → 标签
```

**每周检查:**
- [ ] 依赖镜像构建日志
- [ ] 镜像层大小变化
- [ ] 清理旧版本执行情况
- [ ] CI Pipeline 使用依赖镜像的成功率

### 4.4 故障处理

#### 问题 1: 构建失败

**症状:**
```
Error: poetry install failed
```

**排查步骤:**
```bash
# 1. 查看构建日志
# Gitea UI → Actions → 失败的构建 → 查看日志

# 2. 本地复现
docker build -f docker/Dockerfile.dependency .

# 3. 检查 poetry.lock
poetry check
poetry lock --no-update

# 4. 检查依赖冲突
poetry show --tree
```

**解决方案:**
```bash
# 方案 A: 清理缓存重试
poetry cache clear pypi --all
docker build --no-cache -f docker/Dockerfile.dependency .

# 方案 B: 固定依赖版本
# 编辑 pyproject.toml，固定问题依赖版本
poetry lock --no-update
git commit -m "fix: pin problematic dependency"

# 方案 C: 回退到上一版本
# 修改 CI Pipeline 使用上一版本镜像
```

#### 问题 2: 镜像过大

**症状:**
```
Warning: Image size exceeds 15GB
```

**排查步骤:**
```bash
# 1. 分析镜像层
docker history harbor.sisys.local/sisys/dependency:latest

# 2. 查找大文件
docker run --rm -it harbor.sisys.local/sisys/dependency:latest \
  bash -c "du -ah / | sort -rh | head -20"
```

**解决方案:**
```dockerfile
# Dockerfile.dependency 优化

# 1. 合并 RUN 指令
RUN apt-get update && apt-get install -y ... \
    && rm -rf /var/lib/apt/lists/*

# 2. 使用 .dockerignore
# .dockerignore
.git
*.md
tests/
docs/

# 3. 清理缓存
RUN pip cache purge && poetry cache clear pypi --all
```

---

## 🔧 Layer 3: 应用镜像维护

### 5.1 构建优化

**多阶段构建:**
```dockerfile
# docker/Dockerfile.app

# 阶段 1: 依赖层 (复用 Layer 2)
FROM harbor.sisys.local/sisys/dependency:latest AS base

# 阶段 2: 构建层
FROM base AS builder
WORKDIR /workspace
COPY src/ ./src/
RUN pip install -e .

# 阶段 3: 运行层
FROM base
WORKDIR /workspace
COPY --from=builder /workspace/src ./src
COPY --from=builder /usr/local/lib/python3.11/site-packages \
     /usr/local/lib/python3.11/site-packages

# 创建非 root 用户
RUN useradd -m -u 1000 sisys-user && chown -R sisys-user:sisys-user /workspace
USER sisys-user

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 5.2 性能监控

**CI Pipeline 中的性能指标:**
```yaml
# .gitea/workflows/ci.yaml
- name: Measure Build Time
  run: |
    echo "## 📊 镜像构建性能"
    echo ""
    echo "| 阶段 | 时长 |"
    echo "|------|------|"
    echo "| Layer 1 (Pull) | ${PULL_TIME}s |"
    echo "| Layer 2 (Cache) | ${BUILD_TIME}s |"
    echo "| Layer 3 (Build) | ${APP_BUILD_TIME}s |"
    echo "| **总计** | ${TOTAL_TIME}s |"
```

**目标指标:**
- Layer 1 拉取：< 30 秒 (本地网络)
- Layer 2 缓存命中：> 90%
- Layer 3 构建：< 5 分钟
- 总构建时间：< 12 分钟

---

## 🧹 清理策略

### 6.1 Harbor 镜像清理

**自动清理脚本:** `scripts/image/cleanup-old-versions.sh`

```bash
#!/bin/bash
set -e

# =============================================================================
# Harbor 镜像清理脚本
# =============================================================================
# 用途：清理旧版本镜像，保留最近 5 个版本
# =============================================================================

HARBOR_REGISTRY="${HARBOR_REGISTRY:-harbor.sisys.local}"
HARBOR_USERNAME="${HARBOR_USERNAME:-admin}"
HARBOR_PASSWORD="${HARBOR_PASSWORD}"
PROJECT="${PROJECT:-sisys}"
REPOSITORY="${REPOSITORY:-dependency}"
KEEP_COUNT="${KEEP_COUNT:-5}"

echo "🧹 开始清理 ${PROJECT}/${REPOSITORY}..."
echo "保留最近 ${KEEP_COUNT} 个版本"

# 获取所有版本 (按时间排序)
VERSIONS=$(curl -sf -u "${HARBOR_USERNAME}:${HARBOR_PASSWORD}" \
  "https://${HARBOR_REGISTRY}/api/v2.0/projects/${PROJECT}/repositories/${REPOSITORY}/artifacts" \
  | jq -r '.[].tags[].name' | sort -r)

# 保留最新 KEEP_COUNT 个，删除其余的
echo "${VERSIONS}" | tail -n +$((KEEP_COUNT + 1)) | while read -r VERSION; do
  if [ -n "${VERSION}" ]; then
    echo "🗑️  删除旧版本：${VERSION}"
    curl -sf -X DELETE \
      -u "${HARBOR_USERNAME}:${HARBOR_PASSWORD}" \
      "https://${HARBOR_REGISTRY}/api/v2.0/projects/${PROJECT}/repositories/${REPOSITORY}/artifacts/${VERSION}"
  fi
done

echo "✅ 清理完成"
```

**执行清理:**
```bash
# 手动执行
chmod +x scripts/image/cleanup-old-versions.sh
./scripts/image/cleanup-old-versions.sh

# 自动执行 (每周日 4 点，依赖镜像构建后 1 小时)
# .gitea/workflows/cleanup-images.yml
name: Cleanup Old Images
on:
  schedule:
    - cron: '0 4 * * 0'
  workflow_dispatch:
```

### 6.2 本地 Docker 清理

```bash
# 清理悬空镜像
docker image prune -f

# 清理所有未使用镜像
docker image prune -a -f

# 清理构建缓存
docker builder prune -f

# 查看磁盘使用
docker system df
```

---

## 📊 监控与告警

### 7.1 监控仪表板

**Grafana 仪表板配置:**

```json
{
  "dashboard": {
    "title": "SISYS 镜像监控",
    "panels": [
      {
        "title": "镜像构建成功率",
        "targets": [
          {
            "expr": "rate(ci_pipeline_success_total{job=\"build-dependency\"}[7d])"
          }
        ]
      },
      {
        "title": "镜像大小趋势",
        "targets": [
          {
            "expr": "harbor_repository_size_bytes{project=\"sisys\", repository=\"dependency\"}"
          }
        ]
      },
      {
        "title": "CI 执行时间",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(ci_pipeline_duration_seconds_bucket[7d]))"
          }
        ]
      }
    ]
  }
}
```

### 7.2 告警规则

**Prometheus 告警规则:**

```yaml
groups:
  - name: sisys-images
    rules:
      - alert: DependencyImageBuildFailure
        expr: rate(ci_pipeline_success_total{job="build-dependency"}[1h]) < 0.9
        for: 1h
        annotations:
          summary: "依赖镜像构建失败率超过 10%"

      - alert: ImageSizeExceeded
        expr: harbor_repository_size_bytes{project="sisys", repository="dependency"} > 15000000000
        for: 1h
        annotations:
          summary: "依赖镜像大小超过 15GB"

      - alert: CIExecutionTimeHigh
        expr: histogram_quantile(0.95, rate(ci_pipeline_duration_seconds_bucket[1d])) > 720
        for: 1d
        annotations:
          summary: "CI 执行时间 P95 超过 12 分钟"
```

---

## 📝 最佳实践

### 8.1 依赖管理

**✅ 推荐:**
```toml
# pyproject.toml

# 固定主要依赖版本
[tool.poetry.dependencies]
python = "3.11"
torch = "2.7.1"
fastapi = "0.110.0"

# 开发依赖使用宽松版本
[tool.poetry.group.dev.dependencies]
pytest = "^8.0"
ruff = "^0.3"
```

**❌ 避免:**
```toml
# 避免使用 * 或过宽的范围
torch = "*"  # ❌
fastapi = ">=0.100.0"  # ❌
```

### 8.2 Dockerfile 优化

**✅ 推荐:**
```dockerfile
# 多阶段构建
FROM base AS builder
RUN build commands

FROM base
COPY --from=builder /app /app

# 合并 RUN 指令
RUN apt-get update && apt-get install -y ... \
    && rm -rf /var/lib/apt/lists/*

# 使用 .dockerignore
# .dockerignore
.git
*.md
tests/
__pycache__/
```

**❌ 避免:**
```dockerfile
# 每个指令创建新层
RUN apt-get update
RUN apt-get install -y ...
RUN rm -rf /var/lib/apt/lists/*

# 复制不必要文件
COPY . .
```

### 8.3 版本控制

**Git 标签策略:**
```bash
# 依赖镜像版本
git tag dependency-20260323-a1b2c3d
git push origin dependency-20260323-a1b2c3d

# 应用镜像版本
git tag v1.0.0
git push origin v1.0.0
```

---

## 🔗 相关文档

- [本地 PyTorch 镜像导入指南](./LOCAL_PYTORCH_IMPORT.md)
- [CI/CD Pipeline 模板使用指南](./CI_CD_PIPELINE_TEMPLATE.md)
- [Harbor 镜像仓库使用指南](./HARBOR_USAGE.md)
- [Gitea Runner 配置](./GITEA_RUNNER_CONFIG.md)

---

## 📋 维护检查清单

### 每日检查
- [ ] 检查 CI Pipeline 执行状态
- [ ] 检查 GPU 资源使用情况
- [ ] 检查 Harbor 存储容量

### 每周检查
- [ ] 依赖镜像构建成功 (每周日 3 点)
- [ ] 镜像清理脚本执行 (每周日 4 点)
- [ ] 性能指标分析 (CI 执行时间趋势)
- [ ] 安全扫描结果审查

### 每月检查
- [ ] PyTorch 版本评估
- [ ] 依赖版本审查和更新
- [ ] 存储成本分析
- [ ] 备份验证

---

**最后更新:** 2026-03-23
**维护者:** Agimtech DevOps Team
**审查周期:** 每月一次
