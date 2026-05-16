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
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import fakeredis.aioredis
import pytest
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

# Ensure all domain events are imported so EventRegistry is populated.
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
from src.infrastructure.messaging.message_serializer import InMemoryEventStore
from src.infrastructure.messaging.retry.checker import IdempotencyChecker
from src.infrastructure.messaging.retry.retry_policy import RetryPolicy

# Use tests/environments.py for standardized test environment configuration
from tests.environments import get_test_env  # noqa: E402

# Import reset_test_environment from tests.fixtures for test isolation
# Note: reset_test_environment in tests/fixtures.py is already autouse=True
from tests.fixtures import reset_test_environment  # noqa: F401

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

    Note: 使用 function scope 确保每个测试独立，避免状态污染。
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

    Note: 使用 function scope (非 session) 确保每个测试独立，避免状态污染。
    """
    from src.infrastructure.config.postgresql import PostgreSQLConfig
    from src.infrastructure.storage.postgresql.engine import PostgreSQLAdapter

    config = get_test_env()

    pg_config = PostgreSQLConfig(
        host=config.postgres.host,
        port=config.postgres.port,
        database=config.postgres.database,
        username=config.postgres.username,
        password=config.postgres.password,
    )

    engine = PostgreSQLAdapter(pg_config)

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

    Note: 使用 function scope (非 session) 确保每个测试独立，避免状态污染。
    """
    config = get_test_env()

    from src.infrastructure.storage.qdrant.client import QdrantClientWrapper

    wrapper = QdrantClientWrapper(
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

    Note: 使用 function scope (非 session) 确保每个测试独立，避免状态污染。
    """
    config = get_test_env()

    from src.infrastructure.config.minio import MinIOConfig
    from src.infrastructure.storage.minio.client_adapter import MinioClientAdapter

    minio_config = MinIOConfig(
        endpoint=f"{config.minio.endpoint}",
        access_key=config.minio.access_key,
        secret_key=config.minio.secret_key,
        bucket=config.minio.bucket,
        region=config.minio.region,
        secure=config.minio.secure,
    )
    wrapper = MinioClientAdapter(minio_config)

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

    Note: 使用 function scope (非 session) 确保每个测试独立，避免状态污染。
    """
    config = get_test_env()

    from src.infrastructure.storage.neo4j.client import Neo4jClientWrapper

    wrapper = Neo4jClientWrapper(
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
