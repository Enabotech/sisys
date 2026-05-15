"""MemoryChangedListener integration tests with real PostgreSQL + Redis.

Tests the complete event handling flow with REAL services:
- L1 Redis cache invalidation (real Redis)
- L2 PostgreSQL write (real PostgreSQL via repository)

Uses UUID prefix isolation patterns for test isolation.
Uses begin_nested() savepoint for transactional isolation.

Run with: pytest tests/integration/test_memory_changed_listener_with_real_postgresql.py -v
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.event_handlers.memory_changed_handler import MemoryChangedHandler
from src.domain.events.memory_events import MemoryChanged
from src.infrastructure.config.postgresql import PostgreSQLConfig
from src.infrastructure.storage.memory_index import MemoryIndex
from src.infrastructure.storage.postgresql.engine import DatabaseEngine
from src.infrastructure.storage.postgresql.session_context import reset_session, set_session
from src.infrastructure.storage.redis.redis_memory_cache import RedisMemoryCache
from tests.environments import get_test_env

# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def context() -> dict:
    """Share state between steps."""
    return {}


@pytest.fixture
def test_schema() -> str:
    """Generate unique schema name for test isolation."""
    return f"test_sisys_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def pg_config() -> PostgreSQLConfig:
    """Real PostgreSQL configuration from environment."""
    env = get_test_env()
    return PostgreSQLConfig(
        host=env.postgres.host,
        port=env.postgres.port,
        database=env.postgres.database,
        username=env.postgres.username,
        password=env.postgres.password,
        pool_size=5,
        max_overflow=10,
    )


@pytest.fixture
def db_engine(pg_config: PostgreSQLConfig) -> DatabaseEngine:
    """Real database engine instance."""
    return DatabaseEngine(pg_config)


@pytest.fixture
def ensure_schema(db_engine: DatabaseEngine, pg_config: PostgreSQLConfig, test_schema: str):
    """Ensure test schema exists before tests.

    Creates a unique schema for this test run to ensure isolation.
    Uses sync engine for DDL to avoid async issues.
    """
    sync_url = f"postgresql+psycopg2://{pg_config.username}:{pg_config.password}@{pg_config.host}:{pg_config.port}/{pg_config.database}"
    from sqlalchemy import create_engine

    sync_engine = create_engine(sync_url)

    # Create schema
    with sync_engine.connect() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{test_schema}" CASCADE'))
        conn.commit()

    with sync_engine.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA "{test_schema}"'))
        conn.commit()

    # Create tables in schema
    from src.infrastructure.storage.postgresql.models import Base

    with sync_engine.connect() as conn:
        conn.execute(text(f'SET search_path TO "{test_schema}"'))
        Base.metadata.create_all(conn)
        conn.commit()

    sync_engine.dispose()

    yield test_schema

    # Cleanup - drop schema after test
    sync_engine = create_engine(sync_url)
    try:
        with sync_engine.connect() as conn:
            conn.execute(text(f'DROP SCHEMA "{test_schema}" CASCADE'))
            conn.commit()
    except Exception:
        pass
    sync_engine.dispose()


@pytest.fixture
async def pg_session(db_engine: DatabaseEngine, ensure_schema: str) -> AsyncGenerator[AsyncSession, None]:
    """PostgreSQL session with transactional rollback.

    Uses begin_nested() to create a savepoint for test isolation.
    After test completes, the nested transaction is rolled back.
    """
    async_engine = db_engine.get_async_engine()
    session = AsyncSession(async_engine)

    # Set search_path for this session
    await session.execute(text(f'SET search_path TO "{ensure_schema}"'))

    # Start a nested transaction (savepoint) for rollback isolation
    async with session.begin_nested():
        yield session

    await session.close()


@pytest.fixture(scope="session")
def redis_test_prefix():
    """Unique test prefix for Redis key isolation (session-scoped for parallel safety)."""
    return f"memory:test-{uuid.uuid4().hex[:8]}:"


@pytest.fixture
def real_redis(redis_test_prefix):
    """Provide real async Redis client. Skip if not available."""
    try:
        import redis.asyncio as aioredis

        env = get_test_env()
        client = aioredis.Redis(host=env.redis.host, port=env.redis.port, decode_responses=True)
        yield client
    except Exception:
        env = get_test_env()
        pytest.skip(f"Redis not available at {env.redis.host}:{env.redis.port}")


@pytest.fixture
def redis_cache(real_redis) -> RedisMemoryCache:
    """Create RedisMemoryCache with real Redis."""
    return RedisMemoryCache(real_redis)


@pytest.fixture
def real_redis_sync(redis_test_prefix):
    """Provide sync Redis client for cleanup operations. Skip if not available."""
    try:
        env = get_test_env()
        client = redis.Redis(host=env.redis.host, port=env.redis.port, decode_responses=True)
        client.ping()
        yield client
    except redis.ConnectionError:
        env = get_test_env()
        pytest.skip(f"Redis not available at {env.redis.host}:{env.redis.port}")


@pytest.fixture
def memory_index(temp_memory_dir: Path):
    """Create MemoryIndex with temp directory."""
    from src.infrastructure.config.memory import MemoryConfig

    config = MemoryConfig(memory_l0_path=str(temp_memory_dir))
    return MemoryIndex(config)


@pytest.fixture
def temp_memory_dir(tmp_path: Path) -> Path:
    """Create temporary memory directory with UUID prefix for isolation."""
    memory_dir = tmp_path / f"memory-{uuid.uuid4().hex[:8]}"
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir


# ===================================================================
# L2 Repository Fixtures (Real PostgreSQL)
# ===================================================================


@pytest.fixture
def metadata_repository(pg_session: AsyncSession):
    """Create real PostgreSQL MemoryMetadataRepository."""
    from src.infrastructure.storage.postgresql.repository.memory_metadata_repository import (
        PostgreSQLMemoryMetadataRepository,
    )

    token = set_session(pg_session)
    repo = PostgreSQLMemoryMetadataRepository()
    yield repo
    reset_session(token)


@pytest.fixture
def history_repository(pg_session: AsyncSession):
    """Create real PostgreSQL MemoryChangeHistoryRepository."""
    from src.infrastructure.storage.postgresql.repository.memory_change_history_repository import (
        PostgreSQLMemoryChangeHistoryRepository,
    )

    token = set_session(pg_session)
    repo = PostgreSQLMemoryChangeHistoryRepository()
    yield repo
    reset_session(token)


# ===================================================================
# Listener with Real Services
# ===================================================================


@pytest.fixture
def listener_with_real_services(redis_cache, metadata_repository, history_repository, memory_index):
    """Create MemoryChangedListener with REAL L1 + L2 services."""
    return MemoryChangedHandler(
        l1_cache=redis_cache,
        metadata_repository=metadata_repository,
        history_repository=history_repository,
    )


# ===================================================================
# AC-3: MemoryChanged Listener L2 Write Tests (Real PostgreSQL)
# ===================================================================


class TestMemoryChangedListenerL2WriteRealPostgreSQL:
    """L2 PostgreSQL write tests using real repository."""

    @pytest.mark.asyncio
    async def test_listener_writes_metadata_to_postgresql(self, listener_with_real_services, metadata_repository, pg_session):
        """Verify listener writes metadata to PostgreSQL after handle()."""
        memory_id = str(uuid.uuid4())
        user_id = f"user-{uuid.uuid4().hex[:8]}"
        name = f"test-memory-{uuid.uuid4().hex[:8]}"
        owner_id = user_id
        memory_type = "user"

        # Create event
        event = MemoryChanged(
            memory_id=memory_id,
            user_id=user_id,
            name=name,
            change_type="create",
            is_automatic=False,
            new_value={
                "type": memory_type,
                "description": "Test memory",
                "owner": owner_id,
            },
        )

        # Handle event (async call, blocks until complete)
        await listener_with_real_services.handle(event)

        # Verify metadata was written to PostgreSQL
        from uuid import UUID

        metadata = await metadata_repository.get_by_id(UUID(memory_id))
        assert metadata is not None, "Metadata should be written after listener.handle()"
        assert metadata.name == name, f"Expected name={name}, got {metadata.name}"
        assert metadata.user_id == user_id, f"Expected user_id={user_id}, got {metadata.user_id}"
        assert metadata.type == memory_type, f"Expected type={memory_type}, got {metadata.type}"

    @pytest.mark.asyncio
    async def test_listener_writes_history_to_postgresql(self, listener_with_real_services, history_repository, pg_session):
        """Verify listener writes history to PostgreSQL after handle()."""
        memory_id = str(uuid.uuid4())
        user_id = f"user-{uuid.uuid4().hex[:8]}"
        name = f"test-memory-{uuid.uuid4().hex[:8]}"
        memory_type = "user"

        # Create event
        event = MemoryChanged(
            memory_id=memory_id,
            user_id=user_id,
            name=name,
            change_type="create",
            is_automatic=False,
            new_value={"type": memory_type, "description": "Test memory"},
        )

        # Handle event (async call, blocks until complete)
        await listener_with_real_services.handle(event)

        # Verify history was written to PostgreSQL
        from uuid import UUID

        history_list = await history_repository.get_by_memory_id(UUID(memory_id))
        assert len(history_list) > 0, "History should be written after listener.handle()"
        history = history_list[0]
        assert history.change_type == "create", f"Expected change_type=create, got {history.change_type}"


# ===================================================================
# AC-3: Complete Flow Integration Test
# ===================================================================


class TestMemoryChangedListenerCompleteFlow:
    """Complete flow integration test with real PostgreSQL + Redis."""

    @pytest.mark.asyncio
    async def test_save_memory_triggers_listener_and_l2_write(
        self,
        listener_with_real_services,
        metadata_repository,
        history_repository,
        pg_session,
        redis_cache,
        real_redis_sync,
        temp_memory_dir,
    ):
        """Test complete flow: MemoryService.save() -> MemoryChanged -> Listener -> L2 write.

        This test verifies the complete event-driven architecture:
        1. User saves memory (simulated via event)
        2. MemoryChanged event is published
        3. Listener.handle() is called
        4. L1 cache is invalidated (verified via real Redis)
        5. L2 metadata is written (verified via real PostgreSQL)
        6. L2 history is recorded (verified via real PostgreSQL)
        """
        memory_id = str(uuid.uuid4())
        user_id = f"user-{uuid.uuid4().hex[:8]}"
        name = f"test-memory-{uuid.uuid4().hex[:8]}"
        owner_id = user_id
        memory_type = "user"

        # Step 1: Pre-populate L1 cache
        await redis_cache.set(memory_type, owner_id, name, "test content")
        redis_key = f"memory:user:{owner_id}:{name}"
        assert real_redis_sync.exists(redis_key) == 1, "Cache should be populated before listener"

        # Step 2: Create MemoryChanged event (simulating what MemoryService.save() would publish)
        event = MemoryChanged(
            memory_id=memory_id,
            user_id=user_id,
            name=name,
            change_type="create",
            is_automatic=False,
            new_value={
                "type": memory_type,
                "description": "Test memory for complete flow",
                "owner": owner_id,
            },
        )

        # Step 3: Call listener.handle() - this triggers L1 invalidation + L2 write
        await listener_with_real_services.handle(event)

        # Step 4: Verify L1 cache was invalidated
        assert real_redis_sync.exists(redis_key) == 0, "L1 cache should be invalidated after listener.handle()"

        # Step 5: Verify L2 metadata was written (query the database directly)
        from uuid import UUID

        metadata = await metadata_repository.get_by_id(UUID(memory_id))
        assert metadata is not None, "L2 metadata should be written after listener.handle()"
        assert metadata.name == name, f"Expected name={name}, got {metadata.name}"

        # Step 6: Verify L2 history was recorded
        from uuid import UUID

        history_list = await history_repository.get_by_memory_id(UUID(memory_id))
        assert len(history_list) > 0, "L2 history should be recorded after listener.handle()"
        history = history_list[0]
        assert history.change_type == "create", f"Expected change_type=create, got {history.change_type}"
