"""Pytest fixtures for real storage service integration tests.

Provides fixtures that connect to real Redis/PostgreSQL/Qdrant/MinIO/Neo4j instances.
Use this conftest for end-to-end tests with actual deployments.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import redis.asyncio as redis
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.config.postgresql import PostgreSQLConfig
from src.infrastructure.storage.postgresql.engine import DatabaseEngine

# Use tests/environments.py for standardized test environment configuration (AC-6 R1)
from tests.environments import get_test_env  # noqa: E402

# Load environment variables from .env file
load_dotenv(Path(__file__).parent.parent.parent / ".env")

# ===================================================================
# Redis Fixtures (Real Instance)
# ===================================================================


@pytest.fixture
async def real_redis() -> AsyncGenerator[redis.Redis, None]:
    """Provide a real Redis connection.

    Uses get_test_env() for standardized test environment configuration (AC-6 R1, R7).

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
    from src.infrastructure.config.redis import RedisConfig
    from src.infrastructure.storage.redis.session_storage import RedisSessionStorage

    config = RedisConfig()
    storage = RedisSessionStorage(config)
    storage._pool = real_redis.connection_pool
    return storage


@pytest.fixture
async def redis_semantic_cache(real_redis: redis.Redis):
    """Provide RedisSemanticCache with real Redis connection."""
    from src.infrastructure.config.redis import RedisConfig
    from src.infrastructure.monitoring.event_metrics import EventMetricsCollector
    from src.infrastructure.storage.redis.semantic_cache import RedisSemanticCache

    config = RedisConfig()
    metrics = EventMetricsCollector()
    cache = RedisSemanticCache(config, metrics_collector=metrics)
    cache._pool = real_redis.connection_pool
    return cache


@pytest.fixture
async def redis_public_blackboard(real_redis: redis.Redis):
    """Provide RedisPublicBlackboard with real Redis connection."""
    from src.infrastructure.config.redis import RedisConfig
    from src.infrastructure.storage.redis.public_blackboard import RedisPublicBlackboard

    config = RedisConfig()
    board = RedisPublicBlackboard(config)
    board._pool = real_redis.connection_pool
    return board


# ===================================================================
# PostgreSQL Fixtures (Real Instance)
# ===================================================================


@pytest.fixture
async def real_postgres_engine():
    """Provide a real PostgreSQL engine connection.

    Uses get_test_env() for standardized test environment configuration (AC-6 R1, R2, R7).

    Note: 使用 function scope (非 session) 确保每个测试独立，避免状态污染 (AC-6 R2)。
    """
    config = get_test_env()

    pg_config = PostgreSQLConfig(
        host=config.postgres.host,
        port=config.postgres.port,
        database=config.postgres.database,
        username=config.postgres.username,
        password=config.postgres.password,
    )

    engine = DatabaseEngine(pg_config)

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
# Qdrant Fixtures (Real Instance)
# ===================================================================


@pytest.fixture
async def real_qdrant_client():
    """Provide a real Qdrant client connection.

    Uses get_test_env() for standardized test environment configuration (AC-6 R1, R2, R4, R7).

    Note: 使用 function scope (非 session) 确保每个测试独立，避免状态污染 (AC-6 R2)。
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
# MinIO Fixtures (Real Instance)
# ===================================================================


@pytest.fixture
async def real_minio_client():
    """Provide a real MinIO client connection.

    Uses get_test_env() for standardized test environment configuration (AC-6 R1, R2, R5, R7).

    Note: 使用 function scope (非 session) 确保每个测试独立，避免状态污染 (AC-6 R2)。
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
# Neo4j Fixtures (Real Instance)
# ===================================================================


@pytest.fixture
async def real_neo4j_driver():
    """Provide a real Neo4j driver connection.

    Uses get_test_env() for standardized test environment configuration (AC-6 R1, R2, R3, R7).

    Note: 使用 function scope (非 session) 确保每个测试独立，避免状态污染 (AC-6 R2)。
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
