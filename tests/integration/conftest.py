"""Shared pytest fixtures for integration tests.

Provides both Mock services (fakeredis/AsyncMock) for unit-level integration tests
AND real service fixtures for end-to-end integration tests with actual deployments.

Mock fixtures use fakeredis and unittest.mock for isolated testing.
Real service fixtures connect to actual Redis/PostgreSQL/Qdrant/MinIO/Neo4j instances.

Use pytest markers to select which fixtures to use:
- @pytest.mark.asyncio + mock fixtures: standard integration tests
- real service fixtures: require actual services running (skip if unavailable)
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import fakeredis.aioredis
import pytest
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

# Ensure all domain events are imported so DomainEvent._registry is populated.
# This MUST happen before any test that uses EventOutboxAdapter.
from src.domain.events import (  # noqa: F401, E402
    AgentDecided,
    CheckpointReached,
    CheckpointRecovered,
    CorrectionApproved,
    DocumentProcessed,
    HeartbeatTriggered,
    IsolationLevelSwitched,
    RoutingDecided,
    StrategicDeviationWarning,
    ToolExecuted,
)
from src.domain.events.base import DomainEvent
from src.infrastructure.messaging.inmemory_event_store import InMemoryEventStore
from src.infrastructure.messaging.retry.checker import IdempotencyChecker
from src.infrastructure.messaging.retry.retry_policy import RetryPolicy

# Use tests/environments.py for standardized test environment configuration
from tests.environments import get_test_env  # noqa: E402

# Import reset_test_environment from tests.fixtures for test isolation
# Note: reset_test_environment in tests/fixtures.py is already autouse=True
from tests.fixtures import reset_test_environment  # noqa: F401


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """自动为 integration 目录下的测试添加 marker

    1. 所有 integration 测试添加 @pytest.mark.integration
    2. 根据文件名中的服务关键词添加服务依赖 marker
    """
    service_markers: dict[str, str] = {
        "redis": "redis",
        "qdrant": "qdrant",
        "postgres": "database",
        "minio": "minio",
        "neo4j": "neo4j",
        "rabbitmq": "database",
        "docker": "docker",
    }

    for item in items:
        if "tests/integration" not in str(item.fspath):
            continue

        item.add_marker("integration")

        # 按文件名检测服务依赖并自动标记
        filename = str(item.fspath).lower()
        for keyword, marker in service_markers.items():
            if keyword in filename:
                item.add_marker(marker)


# ===================================================================
# Mock Fixtures (for isolated unit-level integration tests)
# ===================================================================


@pytest.fixture
def mock_redis() -> fakeredis.aioredis.FakeRedis:
    """Provide a fakeredis instance mimicking real Redis behavior."""
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture
def mock_postgresql_repo() -> AsyncMock:
    """Mock PostgreSQL repository interface."""
    return AsyncMock()


@pytest.fixture
def mock_rabbitmq_publisher() -> AsyncMock:
    """Mock RabbitMQ async publisher."""
    mock = AsyncMock()
    mock.async_publish.return_value = None
    return mock


# ===================================================================
# Test Data Factory
# ===================================================================


@pytest.fixture
def event_id() -> UUID:
    """Provide a unique event ID for tests."""
    return uuid4()


@pytest.fixture
def sample_event(event_id: UUID) -> DomainEvent:
    """Provide a sample DomainEvent for testing."""
    return DomainEvent(
        event_id=event_id,
        event_type="DocumentProcessed",
        source="test",
        aggregate_id=uuid4(),
        aggregate_type="Document",
        version=1,
        payload={"document_id": "test-doc-1"},
    )


@pytest.fixture
def event_list(event_id: UUID) -> list[DomainEvent]:
    """Provide a list of sample events for testing."""
    return [
        DomainEvent(
            event_id=uuid4(),
            event_type=f"EventType{i}",
            source="test",
            aggregate_id=uuid4(),
            aggregate_type="TestAggregate",
            version=i,
            payload={"index": i},
        )
        for i in range(3)
    ]


# ===================================================================
# Test Isolation Fixtures
# ===================================================================


@pytest.fixture
def outbox_repo() -> MagicMock:
    """Provide a mock OutboxRepository for test isolation.

    Uses unittest.mock.MagicMock to avoid production InMemory test doubles.
    """
    from src.domain.ports.outbox import OutboxRepository

    mock = MagicMock(spec=OutboxRepository)
    mock.get_unpublished.return_value = []
    return mock


@pytest.fixture
def event_store() -> Generator[InMemoryEventStore, None, None]:
    """Provide a fresh InMemoryEventStore instance per test."""
    store = InMemoryEventStore()
    yield store
    store.clear()  # cleanup (defensive)


@pytest.fixture
def idempotency_checker(mock_redis: fakeredis.aioredis.FakeRedis) -> IdempotencyChecker:
    """Provide IdempotencyChecker backed by fakeredis."""
    return IdempotencyChecker(redis_client=mock_redis)


@pytest.fixture
def retry_policy() -> RetryPolicy:
    """Provide a RetryPolicy with fast delays for testing."""
    return RetryPolicy(base_delay=0.01, max_delay=0.1, max_retries=3)


# ===================================================================
# Real Service Fixtures (for end-to-end integration tests)
# ===================================================================
# These fixtures connect to actual deployed services.
# Tests using these fixtures will be skipped if services are unavailable.


@pytest.fixture
async def real_redis() -> AsyncGenerator[redis.Redis, None]:
    """Provide a real Redis connection.

    Uses get_test_env() for standardized test environment configuration.

    Note: 使用 function scope 确保每个测试独立，避免状态污染
    """
    config = get_test_env()

    client = redis.Redis(
        host=config.redis.host,
        port=config.redis.port,
        password=config.redis.password,
        decode_responses=True,
    )

    # Verify connection
    try:
        await client.ping()
    except Exception as e:
        await client.close()
        pytest.skip(f"Redis not available: {e}")

    yield client

    # Cleanup: close connection
    await client.close()


@pytest.fixture
async def redis_session_storage(real_redis: redis.Redis):
    """Provide RedisSessionStorage with real Redis connection."""
    from src.infrastructure.storage.redis.session_storage import RedisSessionStorage

    return RedisSessionStorage(redis_client=real_redis)


@pytest.fixture
async def redis_semantic_cache(real_redis: redis.Redis):
    """Provide RedisSemanticCache with real Redis connection."""
    from src.infrastructure.monitoring.event_metrics import EventMetricsCollector
    from src.infrastructure.storage.redis.semantic_cache import RedisSemanticCache

    metrics = EventMetricsCollector()
    return RedisSemanticCache(redis_client=real_redis, embedding_dim=1024, metrics_collector=metrics)


@pytest.fixture
async def redis_public_blackboard(real_redis: redis.Redis):
    """Provide RedisPublicBlackboard with real Redis connection."""
    from src.infrastructure.storage.redis.public_blackboard import RedisPublicBlackboard

    return RedisPublicBlackboard(redis_client=real_redis)


# ===================================================================
# PostgreSQL Real Instance Fixtures
# ===================================================================


@pytest.fixture
async def real_postgres_engine():
    """Provide a real PostgreSQL engine connection.

    Uses get_test_env() for standardized test environment configuration.

    Note: 使用 function scope (非 session) 确保每个测试独立，避免状态污染
    """
    from src.infrastructure.config.postgresql import PostgreSQLConfig
    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager

    config = get_test_env()

    pg_config = PostgreSQLConfig(
        host=config.postgres.host,
        port=config.postgres.port,
        database=config.postgres.database,
        username=config.postgres.username,
        password=config.postgres.password,
    )

    engine = PostgreSQLManager(pg_config)

    # Verify connection
    try:
        async with AsyncSession(engine.get_async_engine()) as session:
            await session.execute("SELECT 1")
    except Exception as e:
        pytest.skip(f"PostgreSQL not available: {e}")

    yield engine

    engine.close()


@pytest.fixture
async def postgres_session(real_postgres_engine):
    """Provide an AsyncSession for PostgreSQL tests."""
    async with AsyncSession(real_postgres_engine.get_async_engine()) as session:
        yield session


# ===================================================================
# Qdrant Real Instance Fixtures
# ===================================================================


@pytest.fixture
async def real_qdrant_client():
    """Provide a real Qdrant client connection.

    Uses get_test_env() for standardized test environment configuration.

    Note: 使用 function scope (非 session) 确保每个测试独立，避免状态污染
    """
    config = get_test_env()

    from src.infrastructure.storage.qdrant.qdrant_manager import QdrantManager

    wrapper = QdrantManager(
        host=config.qdrant.host,
        port=config.qdrant.port,
        grpc_port=config.qdrant.grpc_port,
        api_key=config.qdrant.api_key,
        https=False,
        timeout=30.0,
        max_retries=3,
    )

    # Verify connection
    try:
        async with wrapper.get_async_client() as client:
            await client.get_collections()
    except Exception as e:
        pytest.skip(f"Qdrant not available: {e}")

    yield wrapper


# ===================================================================
# MinIO Real Instance Fixtures
# ===================================================================


@pytest.fixture
async def real_minio_client():
    """Provide a real MinIO client connection.

    Uses get_test_env() for standardized test environment configuration.

    Note: 使用 function scope (非 session) 确保每个测试独立，避免状态污染
    """
    config = get_test_env()

    from src.infrastructure.config.minio import MinIOConfig
    from src.infrastructure.storage.minio.minio_manager import MinioManager

    minio_config = MinIOConfig(
        endpoint=f"{config.minio.endpoint}",
        access_key=config.minio.access_key,
        secret_key=config.minio.secret_key,
        bucket=config.minio.bucket,
        region=config.minio.region,
        secure=config.minio.secure,
    )
    wrapper = MinioManager(minio_config)

    # Verify connection
    try:
        await wrapper.health_check()
    except Exception as e:
        pytest.skip(f"MinIO not available: {e}")

    yield wrapper


# ===================================================================
# Neo4j Real Instance Fixtures
# ===================================================================


@pytest.fixture
async def real_neo4j_driver():
    """Provide a real Neo4j driver connection.

    Uses get_test_env() for standardized test environment configuration.

    Note: 使用 function scope (非 session) 确保每个测试独立，避免状态污染
    """
    config = get_test_env()

    from src.infrastructure.storage.neo4j.neo4j_manager import Neo4jManager

    wrapper = Neo4jManager(
        host=config.neo4j.host,
        http_port=config.neo4j.http_port,
        bolt_port=config.neo4j.bolt_port,
        username=config.neo4j.username,
        password=config.neo4j.password,
        max_pool_size=50,
        connect_timeout=30.0,
    )

    # Verify connection
    try:
        await wrapper.verify_connectivity()
    except Exception as e:
        pytest.skip(f"Neo4j not available: {e}")

    yield wrapper

    wrapper.close()


# ===================================================================
# Story 4.4 — 沙箱容器清理安全网(对齐 tests/acceptance/conftest.py 先例)
# ===================================================================


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """会话结束后强制清理残留 sisys-sandbox-* 容器(CI runner 防泄漏安全网)

    按容器名前缀精确过滤,不影响非本系统容器;daemon 不可用时静默跳过。
    xdist 下每 worker/controller 各触发一次,docker rm -f 幂等无害。
    """
    import os
    import subprocess

    # xdist 下仅 controller 进程执行(worker 提前结束会误删其他 worker 在用容器)
    if os.environ.get("PYTEST_XDIST_WORKER"):
        return

    try:
        result = subprocess.run(
            ["docker", "ps", "-aq", "--filter", "name=sisys-sandbox-"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        container_ids = [cid for cid in result.stdout.split() if cid]
        if container_ids:
            subprocess.run(["docker", "rm", "-f", *container_ids], capture_output=True, timeout=30)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass  # daemon 不可用静默跳过


@pytest.fixture
async def real_crawler() -> AsyncGenerator[Any, None]:
    """真实 Crawler 服务客户端（Story 4.1b — 中国国家统计局适配器集成测试）

    探活方式：list_supported_formats() 轻量调用（CrawlerClientPort 无 health_check 方法，
    该调用不消耗任务配额）。crawler 服务不可用时 pytest.skip() 动态跳过
    （禁止写死 @pytest.mark.skip）。
    """
    import os

    from src.infrastructure.crawler.http_crawler_client import HttpCrawlerClient

    base_url = os.getenv("CRAWLER_SERVICE_URL", "http://localhost:8900")
    client = HttpCrawlerClient(base_url=base_url)
    try:
        await client.list_supported_formats()
    except Exception as e:
        await client.close()
        pytest.skip(f"Crawler 服务不可用 ({base_url}): {e}")

    yield client

    # Cleanup: 关闭连接（对齐 real_redis close 模式）
    await client.close()
