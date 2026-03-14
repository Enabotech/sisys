# sisys 测试框架使用指南

**版本：** 1.0.0
**最后更新：** 2026-03-02
**状态：** Story 0.3 实现文档

---

## 目录

1. [快速开始](#快速开始)
2. [测试架构](#测试架构)
3. [运行测试](#运行测试)
4. [编写测试](#编写测试)
5. [测试最佳实践](#测试最佳实践)
6. [故障排查](#故障排查)

---

## 快速开始

### 安装依赖

```bash
# 安装测试依赖
poetry install --with test

# 安装 pre-commit 钩子（可选）
pre-commit install
```

### 运行测试

```bash
# 运行所有测试
./scripts/testing/run_tests.sh --all

# 运行单元测试
./scripts/testing/run_tests.sh --unit

# 运行集成测试
./scripts/testing/run_tests.sh --integration

# 运行 E2E 测试
./scripts/testing/run_tests.sh --e2e

# 生成覆盖率报告
./scripts/testing/run_coverage.sh --open
```

### 清理测试数据

```bash
# 清理所有测试数据
python scripts/testing/clean_test_data.py --all

# 仅清理数据库
python scripts/testing/clean_test_data.py --databases

# 预演（不实际删除）
python scripts/testing/clean_test_data.py --all --dry-run
```

---

## 测试架构

### 测试金字塔

sisys 采用测试金字塔架构，确保测试效率和覆盖率：

```
        /\
       /  \      E2E 测试 (10%)
      /____\     用户旅程、Story 验收标准
     /      \
    /________\   集成测试 (20%)
   /          \  仓储、消息总线、外部服务
  /____________\
 /              \  单元测试 (70%)
/________________\ 领域实体、用例、服务
```

### 目录结构

```
tests/
├── conftest.py                 # 全局 pytest 配置和 fixture
│
├── unit/                       # 单元测试
│   ├── domain/
│   │   ├── entities/           # 领域实体测试
│   │   ├── events/             # 领域事件测试
│   │   └── services/           # 领域服务测试
│   ├── application/
│   │   ├── use_cases/          # 用例测试
│   │   └── handlers/           # 处理器测试
│   └── infrastructure/
│       └── persistence/        # 存储持久化测试
│
├── integration/                # 集成测试
│   ├── conftest.py             # 集成测试 fixture
│   ├── repositories/
│   │   ├── test_postgres_repository.py
│   │   ├── test_redis_repository.py
│   │   ├── test_qdrant_repository.py
│   │   ├── test_minio_repository.py
│   │   └── test_neo4j_repository.py
│   ├── messaging/
│   │   ├── test_redis_pubsub.py
│   │   └── test_rabbitmq_events.py
│   └── external_services/
│       └── test_llm_adapter.py
│
├── e2e/                        # E2E 测试
│   ├── conftest.py             # E2E 测试 fixture
│   ├── test_story_01_dev_environment.py
│   ├── test_story_02_cicd_pipeline.py
│   └── user_journeys/
│       ├── test_document_upload_journey.py
│       └── test_rag_retrieval_journey.py
│
├── fixtures/                   # 测试固件
│   ├── sample_documents/       # 示例文档
│   └── mock_data.py            # Mock 数据
│
└── utils/                      # 测试工具
    └── assertions.py           # 自定义断言
```

---

## 运行测试

### 测试脚本选项

```bash
# 运行测试
./scripts/testing/run_tests.sh [选项]

选项:
  --unit        仅运行单元测试
  --integration 仅运行集成测试
  --e2e         仅运行 E2E 测试
  --all         运行所有测试（默认）
  --coverage    生成覆盖率报告
  --fast        仅运行快速测试（跳过慢测试）
  --watch       监视模式（文件变更时自动重跑）
```

### Pytest 直接使用

```bash
# 运行特定测试文件
poetry run pytest tests/unit/domain/test_entities.py -v

# 运行特定测试函数
poetry run pytest tests/unit/domain/test_entities.py::TestDocument::test_create_document -v

# 运行带标记的测试
poetry run pytest -m "not slow"  # 跳过慢测试
poetry run pytest -m "integration"  # 仅集成测试

# 并行测试（加速）
poetry run pytest -n auto  # 自动检测 CPU 核心数

# 失败重跑
poetry run pytest --reruns 3 --reruns-delay 1
```

### 覆盖率报告

```bash
# 生成 HTML 和 XML 报告
./scripts/testing/run_coverage.sh --open

# 设置覆盖率门槛（CI/CD）
./scripts/testing/run_coverage.sh --fail --threshold 80
```

---

## 编写测试

### 单元测试示例

```python
# tests/unit/domain/test_entities.py
import pytest
from src.domain.models.document import Document
from src.domain.exceptions import InvalidDocumentFormatError


class TestDocument:
    """测试领域实体 Document"""

    def test_create_document_with_valid_data(self):
        """Given 有效数据，When 创建文档，Then 成功返回"""
        # Arrange
        title = "测试文档"
        content = "测试内容"
        format = "txt"

        # Act
        doc = Document.create(title=title, content=content, format=format)

        # Assert
        assert doc.title == title
        assert doc.content == content
        assert doc.format == format
        assert doc.is_valid() is True

    def test_document_rejects_invalid_format(self):
        """Given 无效格式，When 创建文档，Then 抛出异常"""
        # Arrange
        title = "测试文档"
        content = "测试内容"
        invalid_format = "invalid_format"

        # Act & Assert
        with pytest.raises(InvalidDocumentFormatError):
            Document.create(title=title, content=content, format=invalid_format)

    @pytest.mark.parametrize(
        "format,expected",
        [
            ("pdf", True),
            ("txt", True),
            ("docx", True),
            ("invalid", False),
        ],
    )
    def test_document_format_validation(self, format, expected):
        """参数化测试：验证多种格式"""
        doc = Document.create(title="测试", content="内容", format=format)
        assert doc.is_valid() == expected
```

### 集成测试示例

```python
# tests/integration/repositories/test_postgres_repository.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from src.infrastructure.persistence.postgres.user_repository_impl import PostgresUserRepository
from src.domain.models.user import User


@pytest.fixture
async def test_db():
    """每个测试使用独立数据库"""
    # 创建测试数据库引擎
    engine = create_async_engine(
        "postgresql+asyncpg://test_user:test_password@localhost:5433/test_db",
        echo=True,
    )

    # 创建表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # 清理：删除所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.mark.integration
class TestPostgresUserRepository:
    """测试 PostgreSQL 仓储实现"""

    async def test_create_user_returns_success(self, test_db):
        """Given 空数据库，When 创建用户，Then 成功返回"""
        # Arrange
        async with AsyncSession(test_db) as session:
            repo = PostgresUserRepository(session)
            user = User.create(name="测试用户", email="test@example.com")

            # Act
            created_user = await repo.create(user)

            # Assert
            assert created_user.id is not None
            assert created_user.name == "测试用户"
            assert created_user.email == "test@example.com"

    async def test_find_by_id_returns_user(self, test_db, seeded_user):
        """Given 已存在用户，When 按 ID 查找，Then 返回用户"""
        # Arrange
        async with AsyncSession(test_db) as session:
            repo = PostgresUserRepository(session)

            # Act
            found_user = await repo.find_by_id(seeded_user.id)

            # Assert
            assert found_user.id == seeded_user.id
            assert found_user.name == seeded_user.name
            assert found_user.email == seeded_user.email
```

### E2E 测试示例

```python
# tests/e2e/test_story_01_dev_environment.py
import pytest
import subprocess
import requests
from pathlib import Path


@pytest.mark.e2e
class TestStory01DevEnvironment:
    """E2E 测试：Story 0.1 开发环境搭建验收"""

    def test_docker_compose_services_healthy(self, docker_compose):
        """Given Docker Compose 启动，When 检查健康状态，Then 所有服务健康"""
        # Arrange
        services = docker_compose.get_services()

        # Act & Assert
        for service in services:
            assert service.is_healthy(), f"{service.name} 未通过健康检查"

    def test_poetry_install_success(self, test_environment):
        """Given Poetry 配置，When 安装依赖，Then 成功完成"""
        # Act
        result = test_environment.run_command("poetry install")

        # Assert
        assert result.returncode == 0
        assert "Installing dependencies" in result.stdout

    def test_health_check_script(self, test_environment):
        """Given 健康检查脚本，When 执行，Then 所有检查通过"""
        # Act
        result = test_environment.run_command(
            "python scripts/monitoring/health_check.py"
        )

        # Assert
        assert result.returncode == 0
        assert "所有服务健康" in result.stdout
```

### Fixture 示例

```python
# tests/conftest.py
import pytest
from pathlib import Path


@pytest.fixture(scope="session")
def test_data_dir():
    """返回测试数据目录"""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_document_path(test_data_dir):
    """返回示例文档路径"""
    return test_data_dir / "sample_documents" / "test.pdf"


@pytest.fixture
def mock_llm_client(mocker):
    """Mock LLM 客户端"""
    mock = mocker.Mock()
    mock.generate.return_value = "Mocked response"
    return mock


@pytest.fixture
def seeded_user(test_db):
    """创建种子用户"""
    user = User.create(name="测试用户", email="test@example.com")
    # 保存到数据库
    yield user
    # 清理：删除用户
    await test_db.delete(user)
```

---

## 测试最佳实践

### 1. 测试命名规范

```python
# 好的命名：清晰描述场景和预期
def test_create_document_with_valid_data_returns_success():
    pass

def test_document_rejects_invalid_format_raises_error():
    pass

# 避免模糊命名
def test_document():  # ❌ 太模糊
    pass
```

### 2. AAA 模式（Arrange-Act-Assert）

```python
def test_example():
    # Arrange - 准备测试数据
    user = User.create(name="测试")

    # Act - 执行被测试的操作
    result = service.process(user)

    # Assert - 验证结果
    assert result.is_success() is True
```

### 3. 测试隔离

```python
# ✅ 每个测试使用独立数据库
@pytest.fixture
def test_db():
    db = create_test_database()
    yield db
    drop_test_database(db)

# ❌ 避免共享状态
@pytest.fixture(scope="session")  # 可能导致测试间相互影响
def shared_db():
    pass
```

### 4. Mock 外部服务

```python
# ✅ Mock LLM API 调用
def test_llm_integration(mock_llm_client):
    mock_llm_client.generate.return_value = "Mocked response"
    result = service.call_llm()
    assert result == "Mocked response"

# ❌ 避免真实 API 调用（慢、不稳定、花钱）
def test_llm_integration():
    result = service.call_real_llm_api()  # ❌
```

### 5. 参数化测试

```python
# ✅ 使用参数化减少重复代码
@pytest.mark.parametrize(
    "format,expected",
    [
        ("pdf", True),
        ("txt", True),
        ("docx", True),
        ("invalid", False),
    ],
)
def test_format_validation(format, expected):
    doc = Document.create(title="测试", content="内容", format=format)
    assert doc.is_valid() == expected

# ❌ 避免重复代码
def test_pdf_format():
    pass

def test_txt_format():
    pass

def test_docx_format():
    pass
```

---

## 故障排查

### 常见问题

#### 1. 集成测试失败：无法连接数据库

```bash
# 检查测试容器是否运行
docker compose -f docker/docker-compose.test.yml ps

# 启动测试容器
docker compose -f docker/docker-compose.test.yml up -d

# 查看容器日志
docker compose -f docker/docker-compose.test.yml logs postgres
```

#### 2. 覆盖率低于门槛

```bash
# 查看哪些文件覆盖率低
./scripts/testing/run_coverage.sh --open

# 在浏览器中查看 htmlcov/index.html
# 红色文件 = 覆盖率低
# 绿色文件 = 覆盖率高
```

#### 3. 测试运行缓慢

```bash
# 使用并行测试
poetry run pytest -n auto

# 跳过慢测试
poetry run pytest -m "not slow"

# 查看测试执行时间
poetry run pytest --durations=10  # 显示最慢的 10 个测试
```

#### 4. Pre-commit 钩子失败

```bash
# 查看 pre-commit 配置
cat .pre-commit-config.yaml

# 手动运行 pre-commit
pre-commit run --all-files

# 跳过 pre-commit（不推荐）
git commit --no-verify
```

---

## 参考文档

- [Pytest 官方文档](https://docs.pytest.org/)
- [Testcontainers Python](https://testcontainers-python.readthedocs.io/)
- [Coverage.py 文档](https://coverage.readthedocs.io/)
- [Pre-commit 文档](https://pre-commit.com/)
- [预提交 Hooks 规范](./pre-commit-hooks.md)

---

**修订历史：**

| 版本 | 日期 | 修订内容 | 修订人 |
|------|------|---------|--------|
| 1.0.0 | 2026-03-02 | 初始版本 | 开发团队 |
