# sisys - Enterprise Strategic Planning System

AI-driven strategic planning and decision intelligence platform for enterprises.

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose v2.0+
- Python 3.11+
- Poetry 1.7+

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
# Start all services (PostgreSQL, Redis, Qdrant, MinIO, Neo4j)
docker-compose up -d

# Verify all services are running
docker-compose ps
```

**Expected Output:**
```
NAME                 STATUS         PORTS
sisys-postgres       Up (healthy)   0.0.0.0:5432->5432/tcp
sisys-redis          Up (healthy)   0.0.0.0:6379->6379/tcp
sisys-qdrant         Up (healthy)   0.0.0.0:6333->6333/tcp
sisys-minio          Up (healthy)   0.0.0.0:9000->9000/tcp, 0.0.0.0:9001->9001/tcp
sisys-neo4j          Up (healthy)   0.0.0.0:7474->7474/tcp, 0.0.0.0:7687->7687/tcp
```

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
python scripts/health_check.py

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

```
sisys/
├── src/                                                   # 源代码目录
│   ├── domain/                                            # 领域层（零外部依赖）
│   │   ├── models/       # 领域实体
│   │   ├── services/     # 领域服务接口
│   │   ├── events/       # 领域事件
│   │   ├── repositories/ # 仓储接口
│   │   └── exceptions/   # 领域异常
│   ├── application/                                       # 应用层（用例编排）
│   │   ├── services/     # 应用服务
│   │   ├── use_cases/    # 用例定义
│   │   ├── commands/     # 命令定义
│   │   ├── queries/      # 查询定义
│   │   ├── handlers/     # 处理器
│   │   └── dtos/         # 数据传输对象
│   ├── infrastructure/                                    # 基础设施层
│   │   ├── workflow/              # Prefect 工作流引擎
│   │   ├── agent_orchestration/   # LangGraph Agent 编排
│   │   ├── messaging/             # 消息总线（RabbitMQ/Redis）
│   │   ├── persistence/           # 持久化实现（五层存储）
│   │   ├── external_services/     # 外部服务适配器
│   │   ├── security/              # 安全（认证/加密/审计）
│   │   └── monitoring/            # 监控（性能/CUSUM）
│   ├── interfaces/                                      # 接口层
│   │   ├── cli/          # CLI 接口（click）
│   │   ├── api/          # REST API（FastAPI）
│   │   ├── event_driven/ # 事件驱动接口
│   │   └── adapters/     # 适配器
│   └── shared/                                          # 共享组件
│       ├── containers.py # 依赖注入容器
│       ├── config.py     # 共享配置
│       └── utils.py      # 工具函数
├── tests/                                                 # 测试目录
│   ├── unit/              # 单元测试
│   ├── integration/       # 集成测试
│   ├── e2e/               # 端到端测试
│   ├── fixtures/          # 测试固件
│   └── conftest.py        # pytest 配置
├── configs/                                               # 配置文件
│   ├── development.py     # 开发环境
│   ├── production.py      # 生产环境
│   └── testing.py         # 测试环境
├── scripts/                                               # 脚本目录
│   ├── setup_environment.py
│   ├── database/
│   └── deployment/
├── docker/                                                # Docker 配置
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── docker-compose.prod.yml
├── .github/workflows/                                     # GitHub Actions
│   ├── ci.yml
│   └── cd.yml
├── requirements/                                          # 依赖管理
│   ├── requirements.txt
│   ├── dev.txt
│   └── prod.txt
├── docs/                                                  # 文档目录
│   ├── architecture/
│   ├── api/
│   └── developer/
├── pyproject.toml                                         # Python 项目配置
├── .env.example                                           # 环境变量示例
├── .pre-commit-config.yaml                                # Pre-commit 配置
└── README.md                                              # 项目说明
```

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

# Run specific test file
pytest tests/test_example.py
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
docker-compose logs postgres
docker-compose logs redis

# Restart services
docker-compose down
docker-compose up -d
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

**Status**: ✅ Development Environment Ready
**Version**: 0.1.0
**Last Updated**: 2026-02-28
