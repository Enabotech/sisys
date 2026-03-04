"""
sisys - Pytest Configuration and Global Fixtures.

此文件包含所有测试共享的 Fixture 和配置。
"""

import asyncio
import uuid
from pathlib import Path
from typing import Any

import pytest
from pytest_mock import MockerFixture
from sqlalchemy.ext.asyncio import AsyncSession

# ========== 测试配置 ==========


@pytest.fixture(scope="session")
def test_config() -> dict[str, Any]:
    """
    测试配置 Fixture。

    提供所有测试共享的配置值。
    """
    return {
        "database_url": "postgresql+asyncpg://test:test@localhost:5432/test_sisys",  # pragma: allowlist secret
        "redis_url": "redis://localhost:6379/15",  # 使用 DB 15 避免冲突
        "qdrant_url": "http://localhost:6333",
        "minio_url": "http://localhost:9000",
        "neo4j_url": "bolt://localhost:7687",
        "test_db_prefix": "test_",
        "project_root": Path(__file__).parent.parent.parent,
    }


# ========== 数据库 Fixture ==========


@pytest.fixture(scope="session")
def test_engine(test_config: dict[str, Any]):
    """
    创建测试数据库引擎。

    使用 StaticPool 确保测试隔离。
    """
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import StaticPool

    engine = create_async_engine(
        test_config["database_url"],
        poolclass=StaticPool,
        echo=False,
    )
    yield engine
    asyncio.run(engine.dispose())


@pytest.fixture(scope="function")
async def db_session(test_engine):
    """
    数据库会话 Fixture - 每个测试函数独立事务。

    测试完成后自动回滚，确保测试隔离。
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    async_sessionmaker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_sessionmaker() as session:
        async with session.begin():
            yield session
        # 事务自动回滚（测试隔离）


@pytest.fixture(scope="function")
async def clean_database(db_session: AsyncSession):
    """
    清理数据库 Fixture - 每个测试前清理所有表。

    按依赖顺序删除数据，避免外键约束冲突。
    """
    from sqlalchemy import text

    # 按依赖顺序删除数据
    await db_session.execute(text("DELETE FROM event_outbox"))
    await db_session.execute(text("DELETE FROM routing_decision_log"))
    await db_session.execute(text("DELETE FROM strategic_plans"))
    await db_session.commit()
    yield db_session


# ========== 项目结构 Fixture ==========


@pytest.fixture(scope="session")
def project_root() -> Path:
    """
    返回项目根目录。

    使用 resolve() 确保路径正确解析。
    """
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def tests_root() -> Path:
    """返回测试目录根。"""
    return Path(__file__).resolve().parent


@pytest.fixture(scope="session")
def test_data_dir(tests_root: Path) -> Path:
    """返回测试数据目录。"""
    path = tests_root / "data"
    path.mkdir(parents=True, exist_ok=True)  # 创建目录（如果不存在）
    return path


# ========== Docker 服务 Fixture ==========


@pytest.fixture(scope="session")
def docker_compose_file(project_root: Path) -> Path:
    """返回 docker-compose.yml 路径。"""
    return project_root / "docker" / "docker-compose.yml"


@pytest.fixture(scope="session")
def docker_services(docker_compose_file: Path):
    """
    Fixture 用于在测试前启动 Docker 服务，测试后停止。

    Usage:
        def test_something(docker_services):
            # Docker services are running
            pass
    """
    import subprocess

    # 使用 docker compose (v2 插件版本) 而非废弃的 docker-compose
    compose_cmd = ["docker", "compose"]

    # 启动服务
    subprocess.run(
        [*compose_cmd, "up", "-d"],
        cwd=docker_compose_file.parent,
        check=True,
        capture_output=True,
    )

    yield

    # 停止服务
    subprocess.run(
        [*compose_cmd, "down"],
        cwd=docker_compose_file.parent,
        check=True,
        capture_output=True,
    )


# ========== Mock 对象工厂 ==========


@pytest.fixture
def mock_llm_router(mocker: MockerFixture):
    """
    Mock LLM 路由器。

    用于模拟 LLM 路由选择，避免真实 API 调用。
    """
    mock = mocker.AsyncMock()
    mock.route = mocker.AsyncMock(
        return_value={
            "selected_model": "ollama/qwen2.5-7b",
            "estimated_cost": 0.001,
            "estimated_latency": 500,
        }
    )
    yield mock


@pytest.fixture
def mock_repository(mocker: MockerFixture):
    """
    Mock 仓储。

    用于模拟仓储操作，避免真实数据库访问。
    """
    mock = mocker.AsyncMock()
    mock.get_by_id = mocker.AsyncMock()
    mock.find_all = mocker.AsyncMock()
    mock.add = mocker.AsyncMock()
    mock.update = mocker.AsyncMock()
    mock.delete = mocker.AsyncMock()
    yield mock


@pytest.fixture
def mock_event_bus(mocker: MockerFixture):
    """
    Mock 事件总线。

    用于模拟事件发布/订阅，避免真实 Redis 连接。
    """
    mock = mocker.AsyncMock()
    mock.publish = mocker.AsyncMock()
    mock.subscribe = mocker.AsyncMock()
    mock.unsubscribe = mocker.AsyncMock()
    yield mock


@pytest.fixture
def mock_redis(mocker: MockerFixture):
    """
    Mock Redis 客户端。

    用于模拟 Redis 操作。
    """
    mock = mocker.AsyncMock()
    mock.get = mocker.AsyncMock()
    mock.set = mocker.AsyncMock()
    mock.delete = mocker.AsyncMock()
    mock.exists = mocker.AsyncMock(return_value=True)
    yield mock


@pytest.fixture
def mock_qdrant(mocker: MockerFixture):
    """
    Mock Qdrant 客户端。

    用于模拟向量数据库操作。
    """
    mock = mocker.AsyncMock()
    mock.search = mocker.AsyncMock(return_value=[])
    mock.upsert = mocker.AsyncMock()
    mock.delete = mocker.AsyncMock()
    yield mock


@pytest.fixture
def mock_minio(mocker: MockerFixture):
    """
    Mock MinIO 客户端。

    用于模拟对象存储操作。
    """
    mock = mocker.MagicMock()
    mock.bucket_exists = mocker.MagicMock(return_value=True)
    mock.fput_object = mocker.MagicMock()
    mock.get_object = mocker.MagicMock()
    mock.remove_object = mocker.MagicMock()
    yield mock


@pytest.fixture
def mock_neo4j(mocker: MockerFixture):
    """
    Mock Neo4j 驱动。

    用于模拟图数据库操作。
    """
    mock = mocker.MagicMock()
    mock.session = mocker.MagicMock()
    yield mock


# ========== 测试数据构建器 ==========


@pytest.fixture
def uuid_generator():
    """
    可重复的 UUID 生成器。

    用于测试中生成可预测的 UUID。
    """

    class UUIDGenerator:
        def __init__(self, seed: int = 0):
            self._counter = seed

        def next(self) -> uuid.UUID:
            """生成下一个 UUID。"""
            self._counter += 1
            return uuid.UUID(int=self._counter)

    return UUIDGenerator()


@pytest.fixture
def test_data_builder():
    """
    通用测试数据构建器。

    提供链式 API 构建测试数据。
    """

    class TestDataBuilder:
        def __init__(self, base_data: dict[str, Any] | None = None):
            self._data = base_data or {}

        def with_id(self, id_value: Any) -> "TestDataBuilder":
            """设置 ID。"""
            self._data["id"] = id_value
            return self

        def with_field(self, key: str, value: Any) -> "TestDataBuilder":
            """设置任意字段。"""
            self._data[key] = value
            return self

        def build(self) -> dict[str, Any]:
            """构建最终数据。"""
            return self._data.copy()

    return TestDataBuilder


# ========== 时间工具 ==========


@pytest.fixture
def frozen_time():
    """
    冻结时间 Fixture。

    用于可重复的测试，避免时间依赖。

    Usage:
        def test_something(frozen_time):
            # Time is frozen at 2026-03-03 10:00:00
            pass
    """
    from freezegun import freeze_time

    with freeze_time("2026-03-03 10:00:00") as frozen:
        yield frozen


@pytest.fixture
def time_travel(frozen_time):
    """
    时间旅行工具。

    允许在测试中推进冻结的时间。

    Usage:
        def test_something(time_travel):
            # Move time forward by 1 hour
            time_travel.move_to("2026-03-03 11:00:00")
    """
    # frozen_time 已经是 freeze_time 上下文，直接使用
    yield frozen_time


# ========== 异步测试支持 ==========


@pytest.fixture(scope="session")
def event_loop_policy():
    """
    返回事件循环策略。

    用于 Windows 上的异步测试。
    """
    import sys

    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    else:
        return asyncio.DefaultEventLoopPolicy()


@pytest.fixture(scope="session")
def event_loop(event_loop_policy):
    """
    创建事件循环。

    用于异步测试。
    """
    asyncio.set_event_loop_policy(event_loop_policy)
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ========== 断言辅助函数 ==========


@pytest.fixture
def assert_contains():
    """
    断言列表/字典包含指定内容。

    Usage:
        def test_something(assert_contains):
            assert_contains([1, 2, 3], 2)  # Passes
            assert_contains({"a": 1}, "a")  # Passes
    """

    def _assert_contains(container, item):
        assert item in container, f"Expected {container} to contain {item}"

    return _assert_contains


@pytest.fixture
def assert_not_contains():
    """
    断言列表/字典不包含指定内容。

    Usage:
        def test_something(assert_not_contains):
            assert_not_contains([1, 2, 3], 4)  # Passes
    """

    def _assert_not_contains(container, item):
        assert item not in container, f"Expected {container} to not contain {item}"

    return _assert_not_contains


@pytest.fixture
def assert_almost_equal():
    """
    断言两个浮点数近似相等。

    Usage:
        def test_something(assert_almost_equal):
            assert_almost_equal(0.1 + 0.2, 0.3, places=7)
    """

    def _assert_almost_equal(a, b, places=7):
        assert round(a - b, places) == 0, f"Expected {a} to be almost equal to {b}"

    return _assert_almost_equal


# ========== 随机数据生成器 ==========


@pytest.fixture
def random_string():
    """
    随机字符串生成器。

    Usage:
        def test_something(random_string):
            name = random_string(length=10)
    """
    import random
    import string

    def _generate(length: int = 10, prefix: str = "") -> str:
        chars = string.ascii_lowercase + string.digits
        result = "".join(random.choice(chars) for _ in range(length))  # nosec B311
        return f"{prefix}{result}" if prefix else result

    return _generate


@pytest.fixture
def random_email(random_string):
    """
    随机邮箱生成器。

    Usage:
        def test_something(random_email):
            email = random_email()
    """

    def _generate(domain: str = "example.com") -> str:
        return f"{random_string(length=8)}@{domain}"

    return _generate


# ========== Story 验收测试 Fixture ==========


@pytest.fixture
def story_01_acceptance_criteria():
    """返回 Story 0.1 验收标准。"""
    return {
        "docker_compose": "docker-compose.yml exists and services start",
        "poetry_install": "poetry install succeeds",
        "ide_config": ".vscode/settings.json exists",
        "env_template": ".env.example exists with all required variables",
        "documentation": "README.md exists with complete sections",
    }


@pytest.fixture
def story_02_acceptance_criteria():
    """返回 Story 0.2 验收标准。"""
    return {
        "ci_pipeline": "GitHub Actions workflow exists and runs on push",
        "test_execution": "pytest runs in CI",
        "coverage_measurement": "Coverage is measured and reported",
        "quality_gates": "Code quality checks pass (linting, type checking)",
        "health_check": "Health check script validates services",
    }
