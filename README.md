# sisys - Enterprise Strategic Planning System

> **🚀 新开发者？5 分钟快速开始：** [阅读 QUICK_SETUP.md](QUICK_SETUP.md)

AI-driven strategic planning and decision intelligence platform for enterprises.

---

## 📋 文档导航

| 文档 | 用途 | 目标读者 | 阅读时间 |
|------|------|---------|---------|
| [**QUICK_SETUP.md**](QUICK_SETUP.md) | 5 分钟快速设置（WSL 2） | 新开发者 | 5 分钟 |
| [**README.md**](README.md) | 项目综合说明 | 所有人员 | 15 分钟 |
| [**docker/WSL2_SETUP.md**](docker/WSL2_SETUP.md) | WSL 2 详细设置指南 | WSL 2 用户 | 10 分钟 |
| [**docker/WSL2_QUICK_REFERENCE.md**](docker/WSL2_QUICK_REFERENCE.md) | WSL 2 快速参考卡片 | WSL 2 用户 | 2 分钟 |
| [_bmad-output/planning-artifacts/architecture.md](architecture.md) | 完整架构设计文档 | 架构师/开发者 | 60 分钟 |

**快速选择：**
- 🆕 **第一次设置？** → 阅读 [QUICK_SETUP.md](QUICK_SETUP.md)
- 📖 **了解项目？** → 继续阅读本 README
- 🐧 **使用 WSL 2？** → 阅读 [docker/WSL2_SETUP.md](docker/WSL2_SETUP.md)

---

## 🚀 Quick Start

### 2026-03-02 更新：Story 0.2 CI/CD 流水线已完成！ ✅

**新功能：**
- ✅ GitHub Actions CI/CD 流水线（自动测试、构建、部署）
- ✅ Docker 多阶段构建（生产优化）
- ✅ 测试框架（单元/集成/E2E 测试）
- ✅ Pre-commit 代码质量钩子
- ✅ 覆盖率报告（Codecov 集成）

**快速开始：**
```bash
# 1. 克隆仓库
git clone <repository-url>
cd sisys

# 2. 配置环境变量
cp .env.example .env

# 3. 启动开发服务
cd docker && docker compose up -d

# 4. 安装依赖
poetry install

# 5. 运行测试
./scripts/testing/run_tests.sh --all
```

**详细文档：**
- 📖 [5 分钟快速设置](QUICK_SETUP.md)
- 🔑 [GitHub Secrets 配置](docs/developer/GITHUB_SECRETS_SETUP.md)
- 📋 [Secrets 检查清单](docs/developer/SECRETS_CHECKLIST.md)
- 🚀 [CI/CD 快速参考](docs/developer/cicd_quick_reference.md)

### Prerequisites

**Choose one of the following Docker environments:**

#### Option 1: Docker Desktop (Recommended for simplicity)

- Install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
- Enable WSL 2 backend in Docker Desktop settings
- Requirements:
  - Windows 11 with WSL 2 enabled
  - 8GB+ RAM (16GB recommended)
  - Virtualization enabled in BIOS

**Installation:**
```powershell
# Install Docker Desktop using winget (optional)
winget install Docker.DockerDesktop

# Verify installation
docker --version
docker-compose --version
```

#### Option 2: WSL 2 with Ubuntu 22.04 (Recommended for development)

- Install WSL 2 and Ubuntu 22.04 from Microsoft Store
- Install Docker Engine inside WSL 2

**Installation:**
```bash
# Update package list
sudo apt update

# Install Docker Engine
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group (avoid using sudo)
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin

# Verify installation
docker --version
docker compose version
```

**Additional Tools:**

- Python 3.11+ (will be managed by Poetry)
- Poetry 1.7+ (installed automatically)
- Git for version control
- VSCode or your preferred IDE

---

### 0. WSL 2 Setup (Option 2 only)

If using WSL 2 with Ubuntu 22.04:

**Automated Setup (Recommended):**

```powershell
# From Windows PowerShell (Administrator)
cd g:\ai\sisys\docker

# Run WSL 2 setup script
.\setup-wsl2.ps1

# After restart, open Ubuntu 22.04 and run:
bash docker/setup-wsl2-docker.sh
```

**Manual Setup:**

```powershell
# From Windows PowerShell (run once)
wsl --install -d Ubuntu-22.04
wsl --set-default Ubuntu-22.04

# From Ubuntu terminal
# Clone repository to WSL filesystem (NOT /mnt/c)
cd ~
git clone <repository-url>
cd sisys
```

**Important:** Always work within the WSL filesystem (`~/sisys`) for best performance, not in `/mnt/c/`.

**Documentation:**
- **Quick Reference:** `docker/WSL2_QUICK_REFERENCE.md`
- **Detailed Guide:** `docker/WSL2_SETUP.md`
- **Setup Scripts:** `docker/setup-wsl2.ps1` (Windows), `docker/setup-wsl2-docker.sh` (Ubuntu)

### 1. Clone Repository

```bash
git clone <repository-url>
cd sisys
```

### 2. Setup Environment Variables

```bash
# Copy environment template
cp .env.example .env

# Edit .env and set your secure passwords
# IMPORTANT: Change default passwords before deployment
```

### 3. Start Development Services

```bash
# Navigate to docker directory
cd docker

# Start all services (PostgreSQL, Redis, Qdrant, MinIO, Neo4j)
# Note: Use 'docker compose' (v2 plugin) - Docker Desktop and Docker Engine both support this
docker compose up -d

# Verify all services are running
docker compose ps

# View logs (optional)
docker compose logs -f
```

**Expected Output:**
```
NAME                 STATUS         PORTS
sisys-postgres       Up (healthy)   0.0.0.0:5432->5432/tcp
sisys-redis          Up (healthy)   0.0.0.0:6379->6379/tcp
sisys-qdrant         Up             0.0.0.0:6333->6333/tcp
sisys-minio          Up (healthy)   0.0.0.0:9000->9000/tcp, 0.0.0.0:9001->9001/tcp
sisys-neo4j          Up (healthy)   0.0.0.0:7474->7474/tcp, 0.0.0.0:7687->7687/tcp
```

**Note:** Qdrant service shows "Up" without "(healthy)" - this is normal as health check is disabled in docker-compose.yml (Alpine image missing curl/wget). Verify Qdrant via API: `curl http://localhost:6333/`

### 4. Install Python Dependencies

```bash
# Install Poetry (if not installed)
curl -sSL https://install.python-poetry.org | python3 -

# Create virtual environment and install dependencies
poetry install

# Activate virtual environment
poetry shell
```

### 5. Initialize Database

```bash
# Run database migrations
alembic upgrade head

# Verify database connection
python -c "from src.core.database import get_db; print('Database connected!')"
```

### 6. Verify Setup

```bash
# Run health check script
python scripts/monitoring/health_check.py

# Or test manually
python -c "
from src.core.config import settings
print(f'✓ PostgreSQL: {settings.DATABASE_URL}')
print(f'✓ Redis: {settings.REDIS_URL}')
print(f'✓ Qdrant: {settings.QDRANT_URL}')
print(f'✓ MinIO: {settings.MINIO_ENDPOINT}')
print(f'✓ Neo4j: {settings.NEO4J_URI}')
"
```

## 📁 Project Structure

**完整目录结构：** 详见 [architecture.md](architecture.md#13-目录结构) 第 13 章（权威来源）

**快速概览（六边形架构）：**
```
sisys/
├── src/                          # 六边形架构核心
│   ├── domain/                   # 领域层（零外部依赖 - FR-AR-01）
│   ├── application/              # 应用层（用例编排）
│   ├── infrastructure/           # 基础设施层（五层存储/消息总线）
│   └── interfaces/               # 接口层（CLI/REST API）
├── tests/                        # 测试（unit/integration/e2e）
├── scripts/                      # 脚本（database/deployment/testing/monitoring）
├── docker/                       # Docker 配置（dev/prod/test）
├── .github/workflows/            # GitHub Actions（CI/CD）
├── configs/                      # 应用配置（base/development/production/testing）
└── docs/                         # 文档（architecture/api/user_guides/developer）
```

**关键架构约束：**
- ✅ 领域层不依赖任何外部框架（FR-AR-01）
- ✅ 基础设施层实现领域层接口
- ✅ 五层存储：Redis → PostgreSQL → Qdrant → MinIO → Neo4j
- ✅ 事件驱动：RabbitMQ + Redis 双通道总线

## 🛠️ Development Tools

### Code Formatting

```bash
# Format code with Black
black src/ tests/

# Lint with Ruff
ruff check src/ tests/

# Type checking with Mypy
mypy src/
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run Story 0.1 acceptance test
python tests/e2e/test_story_01.py

# Run specific test file
pytest tests/e2e/test_story_01.py

# Run unit tests only
pytest tests/unit/

# Run integration tests only
pytest tests/integration/
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

## 🔧 Troubleshooting

### Port Already in Use

If you get "port already in use" errors:

```bash
# Find process using the port (Windows)
netstat -ano | findstr :5432

# Kill the process
taskkill /PID <PID> /F
```

### Docker Services Not Starting

```bash
# Check Docker logs
docker compose logs postgres
docker compose logs redis

# Restart services
docker compose down
docker compose up -d
```

### Poetry Installation Issues

```bash
# Clear Poetry cache
poetry cache clear pypi --all

# Reinstall dependencies
poetry install --no-cache
```

## 📝 Next Steps

After setting up the development environment:

1. **Story 0.2**: Set up CI/CD pipeline
2. **Story 0.3**: Set up test framework
3. **Epic 1**: Start building core architecture

## 📞 Support

For issues or questions, please contact the development team.

---

## 📝 Document Revision History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0.0 | 2026-02-28 | Initial release | Development Team |
| 1.1.0 | 2026-03-02 | Consistency updates: docker compose v2, Qdrant health check notes, documentation navigation | AI Architect |

---

**Status**: ✅ Development Environment Ready
**Version**: 0.1.0
**Last Updated**: 2026-03-02
