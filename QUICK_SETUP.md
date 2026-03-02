# sisys - 快速设置指南

> **📖 想了解项目全貌？** [阅读 README.md](README.md) 获取完整介绍

**适用于 WSL 2 (Ubuntu 22.04) 环境**

---

## 📋 本文档用途

- **目标**：5 分钟内完成开发环境设置
- **适用人群**：新加入的开发工程师
- **前置条件**：Windows 11 + WSL 2 + Ubuntu 22.04

**其他文档：**
- [README.md](README.md) - 项目综合说明
- [docker/WSL2_SETUP.md](docker/WSL2_SETUP.md) - WSL 2 详细设置指南
- [docker/WSL2_QUICK_REFERENCE.md](docker/WSL2_QUICK_REFERENCE.md) - WSL 2 快速参考卡片

---

## 🚀 快速开始（5 分钟设置）

### 前提条件检查

```bash
# 1. 检查 Python 版本（需要 3.11+）
python3 --version

# 如果版本 < 3.11，安装 Python 3.11
sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt install -y python3.11 python3.11-venv python3.11-dev
```

### 步骤 1：安装 Poetry（Python 依赖管理）

```bash
# 使用官方安装脚本
curl -sSL https://install.python-poetry.org | python3 -

# 添加 Poetry 到 PATH
export PATH="$HOME/.local/bin:$PATH"

# 验证安装（需要 Poetry 1.7+）
poetry --version
```

**要求：** Poetry 1.7+（项目 pyproject.toml 要求）

### 步骤 2：验证 Docker 服务

```bash
# 导航到 docker 目录
cd ~/sisys/docker

# 检查服务状态
docker compose ps

# 如果服务未运行，启动它们
docker compose up -d

# 再次检查状态
docker compose ps
```

**预期输出：**
```
NAME                 STATUS
sisys-postgres       Up (healthy)
sisys-redis          Up (healthy)
sisys-qdrant         Up
sisys-minio          Up (healthy)
sisys-neo4j          Up (healthy)
```

### 步骤 3：安装 Python 依赖

```bash
# 返回项目根目录
cd ~/sisys

# 使用 Poetry 安装依赖
poetry install

# 激活虚拟环境
poetry shell
```

### 步骤 4：配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件（可选 - 开发环境默认值已可用）
nano .env
```

**重要：** 开发环境使用默认值即可，生产环境请修改密码！

### 步骤 5：运行健康检查

```bash
# 运行健康检查脚本
python3 scripts/monitoring/health_check.py
```

**预期输出：**
```
============================================================
sisys - Development Environment Health Check
============================================================
🔍 Checking Docker services...
  → Using: docker compose
  ✓ PostgreSQL: sisys-postgres running on port 5432
  ✓ Redis: sisys-redis running on port 6379
  ✓ Qdrant: sisys-qdrant running on port 6333
  ✓ MinIO: sisys-minio running on port 9000
  ✓ Neo4j: sisys-neo4j running on port 7474

🔍 Checking Python environment...
  Python version...
  ✓ Python: Python 3.11.x
  Poetry installation...
  ✓ Poetry: Poetry version 1.x.x
  Virtual environment...
  ✓ Virtual environment: /home/username/sisys/.venv

🔍 Checking environment variables...
  ✓ .env file found: /home/username/sisys/.env
  ✓ DATABASE_URL: Set
  ✓ REDIS_URL: Set
  ✓ QDRANT_URL: Set
  ✓ MINIO_ENDPOINT: Set
  ✓ NEO4J_URI: Set

============================================================
Summary
============================================================
Docker Services: ✓ Passed
Python Environment: ✓ Passed
Environment Variables: ✓ Passed
============================================================
✅ All checks passed! Development environment is ready.
```

---

## 🔧 常见问题解决

### 问题 1：Python 版本不兼容

**错误信息：**
```
The currently activated Python version 3.10.12 is not supported by the project (^3.11).
```

**解决方案：**

```bash
# 方案 A: 安装 Python 3.11（推荐）
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# 方案 B: 使用 pyenv 管理多版本 Python
curl https://pyenv.run | bash
# 然后添加到 ~/.bashrc
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

# 安装并使用 Python 3.11
pyenv install 3.11.8
pyenv global 3.11.8
```

### 问题 2：Poetry 未安装

**错误信息：**
```
✗ Poetry: Not installed
```

**解决方案：**
```bash
# 安装 Poetry
curl -sSL https://install.python-poetry.org | python3 -

# 添加 PATH（如果未自动添加）
export PATH="$HOME/.local/bin:$PATH"

# 添加到 ~/.bashrc 永久生效
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### 问题 3：docker compose 命令不存在

**错误信息：**
```
[Errno 2] No such file or directory: 'docker-compose'
```

**解决方案：**
```bash
# Docker Compose v2（推荐 - 插件版本）
sudo apt install -y docker-compose-plugin

# 验证安装
docker compose version

# 注意：使用 'docker compose'（无连字符）而非 'docker-compose'
```

### 问题 4：.env 文件不存在

**错误信息：**
```
✗ .env file not found
```

**解决方案：**
```bash
# 复制环境变量模板
cp .env.example .env

# 检查文件
ls -la .env
```

### 问题 5：Docker 服务未启动

**解决方案：**
```bash
# 启动所有服务
cd docker
docker compose up -d

# 查看日志
docker compose logs -f

# 重启特定服务
docker compose restart postgres
```

---

## 📝 下一步

设置完成后，继续开发流程：

1. **Story 0.1 完成** ✅ - 开发环境已就绪
2. **Story 0.2** - CI/CD 流水线（`.github/workflows/ci.yml`）
3. **Story 0.3** - 测试框架搭建

---

## 📞 获取帮助

如果遇到问题：

1. 查看详细日志：`docker compose logs -f`
2. 运行健康检查：`python3 scripts/monitoring/health_check.py`
3. 查看文档：`docker/WSL2_SETUP.md`、`README.md`

---

## 📝 文档修订历史

| 版本 | 日期 | 修订内容 | 修订人 |
|------|------|---------|--------|
| 1.0.0 | 2026-03-02 | 初始版本（基于 Story 0.1） | 开发团队 |
| 1.1.0 | 2026-03-02 | 一致性修订：Poetry 版本要求、文档交叉引用 | AI 架构师 |

---

**最后更新：** 2026-03-02  
**文档版本：** 1.1.0  
**适用环境：** WSL 2 (Ubuntu 22.04) + Docker Compose v2 + Python 3.11+
