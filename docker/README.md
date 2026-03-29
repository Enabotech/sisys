# SISYS Docker 镜像构建指南

## 📋 镜像规格

| 组件 | 版本 | 加速源 |
|------|------|--------|
| **Ubuntu** | 22.04 LTS | 清华大学 apt 源 |
| **Python** | 3.11.15 | 源码编译 |
| **Node.js** | 20.x LTS | 清华 NodeSource 镜像 |
| **Poetry** | 2.3.2 | 清华 PyPI 源 |
| **pip** | - | 清华 PyPI 源 |

## 🚀 快速开始

### 1. 构建基础依赖镜像

```bash
# 使用 Makefile（推荐）
make docker-build-dep

# 或使用 Docker 命令
export DOCKER_BUILDKIT=1
docker build -f docker/Dockerfile.dep \
    -t ghcr.io/sisys/sisys-base:ubuntu22.04-py311.15-poetry2.3.2 \
    --progress=plain \
    .
```

### 2. 验证镜像

```bash
# 使用 Makefile
make docker-verify

# 或手动验证
docker run --rm ghcr.io/sisys/sisys-base:ubuntu22.04-py311.15-poetry2.3.2 bash -c "
    python --version &&
    node --version &&
    npm --version &&
    poetry --version
"
```

### 3. 推送到镜像仓库

```bash
# 登录镜像仓库
docker login ghcr.io

# 推送镜像
make docker-push-base
```

## 📦 Dockerfile 说明

### Dockerfile.dep - 基础依赖镜像
- **用途**: 包含 Python、Node.js、Poetry 等基础依赖
- **更新频率**: 低（依赖版本变更时）
- **构建时间**: ~10-15 分钟（首次构建）

### Dockerfile.app - 应用镜像
- **用途**: 基于基础镜像，包含应用代码和项目依赖
- **更新频率**: 中（代码提交时）
- **构建时间**: ~3-5 分钟

### Dockerfile.prod - 生产镜像
- **用途**: 多阶段构建，最小化生产镜像
- **更新频率**: 高（发布时）
- **构建时间**: ~5-8 分钟

## 🔧 常用命令

```bash
# 构建所有镜像
make docker-build-all

# 构建单个镜像
make docker-build-dep    # 基础依赖镜像
make docker-build-app    # 应用镜像
make docker-build-prod   # 生产镜像

# 验证镜像
make docker-verify

# 推送镜像
make docker-push-base    # 推送基础镜像
make docker-push-all     # 推送所有镜像

# 清理
make docker-clean-base   # 清理本地基础镜像
```

## 🎯 优化技巧

### 1. 启用 BuildKit 加速

```bash
export DOCKER_BUILDKIT=1
```

### 2. 使用构建缓存

```bash
docker build --build-arg BUILDKIT_INLINE_CACHE=1 \
    --cache-from ghcr.io/sisys/sisys-base:ubuntu22.04-py311.15-poetry2.3.2 \
    ...
```

### 3. 并行构建

```bash
# 使用多阶段构建并行化
docker buildx build --platform linux/amd64,linux/arm64 ...
```

## 📊 镜像大小优化

| 镜像 | 优化前 | 优化后 | 优化策略 |
|------|--------|--------|----------|
| 基础镜像 | ~2.5GB | ~1.8GB | 多阶段构建 + 清理缓存 |
| 应用镜像 | ~3.0GB | ~2.2GB | 层缓存 + .dockerignore |
| 生产镜像 | ~1.5GB | ~800MB | 精简依赖 + 非 root 用户 |

## 🔍 故障排查

### 问题 1: 构建速度慢

```bash
# 检查 BuildKit 是否启用
echo $DOCKER_BUILDKIT

# 使用清华源加速
# Dockerfile.dep 已配置清华源，无需额外配置
```

### 问题 2: 磁盘空间不足

```bash
# 清理 Docker 缓存
docker system prune -a

# 清理未使用的镜像
docker image prune -a
```

### 问题 3: Poetry 安装失败

```bash
# 检查网络连接
curl -I https://pypi.tuna.tsinghua.edu.cn/simple/

# 手动测试 Poetry 安装
docker run -it --rm ubuntu:22.04 bash
# 在容器内执行安装脚本
```

## 📚 相关文档

- [Docker 最佳实践](../../docs/deployment/docker-best-practices.md)
- [CI/CD 部署流程](../../docs/deployment/cicd-pipeline.md)
- [Kubernetes 部署指南](../../docs/deployment/k8s-deployment.md)

## 🆘 获取帮助

```bash
# 查看所有 Docker 相关命令
make help | grep docker
```
