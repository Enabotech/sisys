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

# Load environment variables from .env file
load_dotenv(Path(__file__).parent.parent.parent / ".env")

# ===================================================================
# Redis Fixtures (Real Instance)
# ===================================================================


@pytest.fixture
async def real_redis() -> AsyncGenerator[redis.Redis, None]:
    """Provide a real Redis connection.

    Assumes Redis is running at localhost:6379.
    Uses REDIS_HOST/REDIS_PORT/REDIS_PASSWORD from environment.

    Note: 使用 function scope 确保每个测试独立，避免状态污染。
    """
    import os

    client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
        password=os.getenv("REDIS_PASSWORD") or None,
        decode_responses=True,
    )

    # Verify connection
    try:
        await client.ping()
    except Exception as e:
        await client.close()
        pytest.skip(f"Redis not available at localhost:6379: {e}")

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


@pytest.fixture(scope="session")
async def real_postgres_engine():
    """Provide a real PostgreSQL engine connection.

    Assumes PostgreSQL is running at localhost:5432.
    """
    import os

    config = PostgreSQLConfig(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DATABASE", "sisys"),
        username=os.getenv("POSTGRES_USERNAME", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
    )

    engine = DatabaseEngine(config)

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


@pytest.fixture(scope="session")
async def real_qdrant_client():
    """Provide a real Qdrant client connection.

    Assumes Qdrant is running at localhost:6333.
    """
    import os

    from src.infrastructure.storage.qdrant.client import QdrantClientWrapper

    api_key = os.getenv("QDRANT_API_KEY")

    wrapper = QdrantClientWrapper(
        host=os.getenv("QDRANT_HOST", "localhost"),
        port=int(os.getenv("QDRANT_PORT", "6333")),
        grpc_port=int(os.getenv("QDRANT_GRPC_PORT", "6334")),
        api_key=api_key,
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


@pytest.fixture(scope="session")
async def real_minio_client():
    """Provide a real MinIO client connection.

    Assumes MinIO is running at localhost:9000.
    """
    from src.infrastructure.config.minio import MinIOConfig
    from src.infrastructure.storage.minio.client_adapter import MinioClientAdapter

    config = MinIOConfig.from_env()
    wrapper = MinioClientAdapter(config)

    # Verify connection
    try:
        await wrapper.health_check()
    except Exception as e:
        pytest.skip(f"MinIO not available: {e}")

    yield wrapper


# ===================================================================
# Neo4j Fixtures (Real Instance)
# ===================================================================


@pytest.fixture(scope="session")
async def real_neo4j_driver():
    """Provide a real Neo4j driver connection.

    Assumes Neo4j is running at localhost:7687 (Bolt) or localhost:7474 (HTTP).
    """
    import os

    from src.infrastructure.storage.neo4j.client import Neo4jClientWrapper

    wrapper = Neo4jClientWrapper(
        host=os.getenv("NEO4J_HOST", "localhost"),
        http_port=int(os.getenv("NEO4J_HTTP_PORT", "7474")),
        bolt_port=int(os.getenv("NEO4J_BOLT_PORT", "7687")),
        username=os.getenv("NEO4J_USERNAME", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "password123"),
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
