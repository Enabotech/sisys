# SISYS Docker 镜像 ENTRYPOINT 使用指南

## 📋 设计说明

### ENTRYPOINT 架构
```
┌─────────────────────────────────────────────────────────┐
│  entrypoint.sh (入口脚本)                                │
├─────────────────────────────────────────────────────────┤
│  1. 打印欢迎信息（版本信息）                              │
│  2. 检查 Poetry 虚拟环境                                  │
│  3. 根据参数决定行为：                                    │
│     - 有参数：执行指定命令                               │
│     - 无参数：进入交互式 bash                            │
└─────────────────────────────────────────────────────────┘
```

### 镜像信息
- **仓库**: `harbor.sisys.local/sisys/dependency`
- **Tag 格式**: `dep-v1.0.0-YYYYMMDDHHMM`
- **示例**: `harbor.sisys.local/sisys/dependency:dep-v1.0.0-202603292125`

## 🚀 使用模式

### 模式 1: 开发模式（交互式）

```bash
# 启动容器，进入交互式开发环境
docker run -it --rm \
    -v $(pwd):/app \
    harbor.sisys.local/sisys/dependency:dep-v1.0.0-202603292125

# 输出示例：
# ═══════════════════════════════════════════════════════════
#   SISYS 开发环境
# ═══════════════════════════════════════════════════════════
# ✓ Python:  Python 3.11.15
# ✓ Node.js: v20.20.0
# ✓ npm:     10.8.2
# ✓ Poetry:  Poetry (version 2.3.2)
# ═══════════════════════════════════════════════════════════
#
# 💡 常用命令:
#   poetry install          - 安装项目依赖
#   poetry shell            - 激活虚拟环境
#   poetry run python app   - 运行应用
#   poetry run pytest       - 运行测试
#   exit                    - 退出容器
```

### 模式 2: 应用模式（执行命令）

```bash
# 运行 Python 应用
docker run -it --rm \
    -v $(pwd):/app \
    harbor.sisys.local/sisys/dependency:dep-v1.0.0-202603292125 \
    poetry run python src/main.py

# 运行 Node.js 应用
docker run -it --rm \
    -v $(pwd):/app \
    harbor.sisys.local/sisys/dependency:dep-v1.0.0-202603292125 \
    node app.js

# 运行 Make 命令
docker run -it --rm \
    -v $(pwd):/app \
    harbor.sisys.local/sisys/dependency:dep-v1.0.0-202603292125 \
    make test
```

### 模式 3: CI/CD 模式（自动化）

```bash
# 运行测试
docker run --rm \
    -v $(pwd):/app \
    harbor.sisys.local/sisys/dependency:dep-v1.0.0-202603292125 \
    poetry run pytest tests/ -v

# 运行代码检查
docker run --rm \
    -v $(pwd):/app \
    harbor.sisys.local/sisys/dependency:dep-v1.0.0-202603292125 \
    make lint

# 构建文档
docker run --rm \
    -v $(pwd):/app \
    harbor.sisys.local/sisys/dependency:dep-v1.0.0-202603292125 \
    make docs
```

### 模式 4: 覆盖 ENTRYPOINT

```bash
# 完全跳过 entrypoint，直接执行命令
docker run -it --rm \
    --entrypoint /bin/bash \
    harbor.sisys.local/sisys/dependency:dep-v1.0.0-202603292125

# 使用 Python 作为入口点
docker run -it --rm \
    --entrypoint python \
    harbor.sisys.local/sisys/dependency:dep-v1.0.0-202603292125 \
    --version
```

## 📊 使用场景对比

| 场景 | 命令示例 | 说明 |
|------|---------|------|
| **本地开发** | `docker run -it -v $(pwd):/app image` | 交互式开发，代码实时挂载 |
| **运行应用** | `docker run image poetry run uvicorn src.main:app` | 启动 Web 服务 |
| **运行测试** | `docker run image poetry run pytest` | 执行测试套件 |
| **CI/CD** | `docker run --rm image make ci-full` | 完整 CI 流程 |
| **调试** | `docker run --entrypoint /bin/bash image` | 跳过 entrypoint 调试 |
| **版本检查** | `docker run image python --version` | 快速检查环境 |

## 🔧 环境变量配置

```bash
# 设置环境变量
docker run -it --rm \
    -e APP_ENV=development \
    -e APP_DEBUG=true \
    -v $(pwd):/app \
    harbor.sisys.local/sisys/dependency:dep-v1.0.0-202603292125

# 使用 .env 文件
docker run -it --rm \
    --env-file .env \
    -v $(pwd):/app \
    harbor.sisys.local/sisys/dependency:dep-v1.0.0-202603292125
```

## 💡 最佳实践

### 1. 开发环境
```yaml
# docker-compose.dev.yml
version: '3.8'
services:
  app:
    image: harbor.sisys.local/sisys/dependency:dep-v1.0.0-202603292125
    volumes:
      - .:/app
      - poetry_cache:/home/sisys/.cache/pypoetry
    environment:
      - APP_ENV=development
    stdin_open: true
    tty: true

volumes:
  poetry_cache:
```

### 2. 测试环境
```yaml
# docker-compose.test.yml
version: '3.8'
services:
  test:
    image: harbor.sisys.local/sisys/dependency:dep-v1.0.0-202603292125
    volumes:
      - .:/app
    command: poetry run pytest tests/ -v
    environment:
      - APP_ENV=test
```

### 3. 生产环境
```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  web:
    image: ghcr.io/sisys/sisys-app:prod-v1.0.0
    # 生产镜像应基于基础镜像构建，包含应用代码
    command: poetry run uvicorn src.main:app --host 0.0.0.0 --workers 4
    environment:
      - APP_ENV=production
```

## 🎯 快速参考

```bash
# 开发模式
docker run -it -v $(pwd):/app image

# 运行单次命令
docker run image poetry run pytest

# 查看帮助
docker run image --help

# 覆盖入口点
docker run --entrypoint /bin/bash image

# 设置环境变量
docker run -e KEY=value image command
```
