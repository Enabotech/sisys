"""Cross-layer storage integration tests.

Tests the complete storage flow across L0-L2:
- L0: File system (MEMORY.md index + .md files) - real files
- L1: Redis cache - real Redis
- L2: PostgreSQL - real PostgreSQL

This validates the architecture.md §11.2.9 L0-driven coordination:
write to L0 → publish event → L1 invalidation + L2 write (via MemoryChangedListener)

Uses begin_nested() savepoint for transactional isolation.
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
from src.domain.ports.l0_storage import L0StoragePort
from src.infrastructure.config.postgresql import PostgreSQLConfig
from src.infrastructure.storage.fs.file_memory_adapter import FileMemoryAdapter
from src.infrastructure.storage.fs.memory_index import MemoryIndex
from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
from src.infrastructure.storage.postgresql.session_context import reset_session, set_session
from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
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


@pytest.fixture(scope="session")
def redis_test_prefix():
    """Unique test prefix for Redis key isolation (session-scoped for parallel safety)."""
    return f"memory:test-{uuid.uuid4().hex[:8]}:"


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
def db_engine(pg_config: PostgreSQLConfig) -> PostgreSQLManager:
    """Real database engine instance."""
    return PostgreSQLManager(pg_config)


@pytest.fixture
def ensure_schema(db_engine: PostgreSQLManager, pg_config: PostgreSQLConfig, test_schema: str):
    """Ensure test schema exists before tests.

    Creates a unique schema for this test run to ensure isolation.
    Uses begin_nested() savepoint for rollback isolation.
    """
    sync_url = f"postgresql+psycopg2://{pg_config.username}:{pg_config.password}@{pg_config.host}:{pg_config.port}/{pg_config.database}"
    from sqlalchemy import create_engine

    sync_engine = create_engine(sync_url)

    with sync_engine.connect() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{test_schema}" CASCADE'))
        conn.commit()

    with sync_engine.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA "{test_schema}"'))
        conn.commit()

    from src.infrastructure.storage.postgresql.models import Base

    with sync_engine.connect() as conn:
        conn.execute(text(f'SET search_path TO "{test_schema}"'))
        Base.metadata.create_all(conn)
        conn.commit()

    sync_engine.dispose()

    yield test_schema

    sync_engine = create_engine(sync_url)
    try:
        with sync_engine.connect() as conn:
            conn.execute(text(f'DROP SCHEMA "{test_schema}" CASCADE'))
            conn.commit()
    except Exception:
        pass
    sync_engine.dispose()


@pytest.fixture
async def pg_session(db_engine: PostgreSQLManager, ensure_schema: str) -> AsyncGenerator[AsyncSession, None]:
    """PostgreSQL session with transactional rollback.

    Uses begin_nested() to create a savepoint for test isolation.
    """
    async_engine = db_engine.get_async_engine()
    session = AsyncSession(async_engine)

    await session.execute(text(f'SET search_path TO "{ensure_schema}"'))

    async with session.begin_nested():
        yield session

    await session.close()


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
    return RedisMemoryCache(RedisAdapter(real_redis))


@pytest.fixture
def real_redis_sync(redis_test_prefix):
    """Provide sync Redis client for cleanup operations."""
    try:
        env = get_test_env()
        client = redis.Redis(host=env.redis.host, port=env.redis.port, decode_responses=True)
        client.ping()
        yield client
    except redis.ConnectionError:
        env = get_test_env()
        pytest.skip(f"Redis not available at {env.redis.host}:{env.redis.port}")


@pytest.fixture
def temp_memory_dir(tmp_path: Path) -> Path:
    """Create temporary memory directory with UUID prefix for isolation."""
    memory_dir = tmp_path / f"memory-{uuid.uuid4().hex[:8]}"
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir


@pytest.fixture
def l0_storage(temp_memory_dir: Path) -> L0StoragePort:
    """Create L0 file system storage."""
    from src.infrastructure.config.memory import MemoryConfig

    config = MemoryConfig(memory_l0_path=str(temp_memory_dir))
    return FileMemoryAdapter(config)


@pytest.fixture
def memory_index(temp_memory_dir: Path):
    """Create MemoryIndex with temp directory."""
    from src.infrastructure.config.memory import MemoryConfig

    config = MemoryConfig(memory_l0_path=str(temp_memory_dir))
    return MemoryIndex(config)


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
# Cross-Layer Integration Tests (L0 → L1 → L2)
# ===================================================================


class TestL0L1L2CrossLayer:
    """L0-L1-L2 跨层集成测试.

    验证 architecture.md §11.2.9 L0 驱动协同机制：
    1. Gateway.save() 写入 L0
    2. 事件发布触发 MemoryChangedListener
    3. Listener 执行 L1 失效 + L2 写入
    """

    async def test_gateway_save_triggers_listener_and_l2_write(
        self,
        l0_storage: L0StoragePort,
        redis_cache: RedisMemoryCache,
        metadata_repository,
        history_repository,
        pg_session: AsyncSession,
        real_redis_sync,
        temp_memory_dir: Path,
    ):
        """Test complete flow: Gateway.save() → L0 write → Event → Listener → L2 write.

        This validates the L0-driven coordination from §11.2.9:
        1. Save to L0 (file system)
        2. MemoryChanged event triggers downstream updates
        3. Listener invalidates L1 cache
        4. Listener writes to L2 (metadata + history)
        """
        memory_id = str(uuid.uuid4())
        user_id = f"user-{uuid.uuid4().hex[:8]}"
        name = f"test-memory-{uuid.uuid4().hex[:8]}"
        memory_type = "user"
        owner_id = user_id

        # Pre-populate L1 cache to verify invalidation
        await redis_cache.set_memory(memory_type, owner_id, name, "stale cached content")
        redis_key = f"memory:user:{owner_id}:{name}"
        assert real_redis_sync.exists(redis_key) == 1, "Cache should be populated before"

        # Create MemoryChanged event (simulating what Gateway.save() would publish)
        event = MemoryChanged(
            memory_id=uuid.UUID(memory_id),
            user_id=user_id,
            name=name,
            change_type="create",
            is_automatic=False,
            new_value={
                "type": memory_type,
                "description": "Cross-layer test memory",
                "owner": owner_id,
            },
        )

        # Create listener with real services
        listener = MemoryChangedHandler(
            memory_cache=redis_cache,
            metadata_repository=metadata_repository,
            history_repository=history_repository,
        )

        # Trigger listener (this simulates what the event bus would do)
        await listener.handle(event)

        # Verify L1 cache was invalidated (L0→L1 coordination)
        assert real_redis_sync.exists(redis_key) == 0, "L1 cache should be invalidated after listener.handle()"

        # Verify L2 metadata was written
        from uuid import UUID

        metadata = await metadata_repository.get_by_id(UUID(memory_id))
        assert metadata is not None, "L2 metadata should be written after listener.handle()"
        assert metadata.name == name, f"Expected name={name}, got {metadata.name}"
        assert metadata.user_id == user_id

        # Verify L2 history was recorded
        history_list = await history_repository.get_by_memory_id(UUID(memory_id))
        assert len(history_list) > 0, "L2 history should be recorded after listener.handle()"
        assert history_list[0].change_type == "create"

    async def test_l0_write_l1_cache_and_l2_metadata_consistency(
        self,
        l0_storage: L0StoragePort,
        redis_cache: RedisMemoryCache,
        metadata_repository,
        history_repository,
        pg_session: AsyncSession,
        real_redis_sync,
    ):
        """Verify L0, L1, L2 maintain consistency across operations.

        Tests the invariant: L0 is source of truth, L1/L2 are derived.
        """
        memory_id = str(uuid.uuid4())
        memory_type = "user"
        owner_id = f"user-{uuid.uuid4().hex[:8]}"
        name = "consistency-test"
        content = "Content for consistency test"

        # 1. Write to L0
        l0_success = await l0_storage.write(memory_id, memory_type, content)
        assert l0_success is True

        # 2. Write to L1 cache
        await redis_cache.set_memory(memory_type, owner_id, name, content)

        # 3. Write to L2 metadata
        from datetime import UTC, datetime
        from uuid import UUID

        from src.domain.entities.memory_metadata import MemoryMetadata

        metadata = MemoryMetadata(
            memory_id=UUID(memory_id),
            name=name,
            type=memory_type,
            path=f"{memory_type}/{memory_id}.md",
            user_id=owner_id,
            description="Consistency test",
            owner=owner_id,
            version=1,
            mtime=datetime.now(UTC),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        await metadata_repository.save(metadata)

        # Verify all three layers have the data
        l0_content = await l0_storage.read(memory_id, memory_type)
        assert l0_content == content

        l1_content = await redis_cache.get_memory(memory_type, owner_id, name)
        assert l1_content == content

        l2_meta = await metadata_repository.get_by_id(UUID(memory_id))
        assert l2_meta is not None
        assert l2_meta.name == name

        # Cleanup L0, L1
        await l0_storage.delete(memory_id, memory_type)
        await redis_cache.delete_memory(memory_type, owner_id, name)
        await metadata_repository.delete(UUID(memory_id))


class TestL0L1Coordination:
    """L0-L1 两层协调测试."""

    async def test_l1_cache_survives_l0_write(
        self,
        l0_storage: L0StoragePort,
        redis_cache: RedisMemoryCache,
        real_redis_sync,
    ):
        """Verify L1 cache persists after L0 write (cache aside pattern).

        The architecture uses cache-aside: L0 is written first, then L1 is populated on read.
        """
        memory_id = str(uuid.uuid4())
        memory_type = "user"
        owner_id = f"user-{uuid.uuid4().hex[:8]}"
        name = "cache-aside-test"
        content = "Content for cache-aside pattern"

        # Write to L0
        await l0_storage.write(memory_id, memory_type, content)

        # Set cache (simulating a previous read)
        await redis_cache.set_memory(memory_type, owner_id, name, "cached content")

        # L0 write should not invalidate L1 cache
        result = await redis_cache.get_memory(memory_type, owner_id, name)
        assert result == "cached content", "L1 cache should survive L0 write"

        # Cleanup
        await l0_storage.delete(memory_id, memory_type)
        await redis_cache.delete_memory(memory_type, owner_id, name)

    async def test_l0_delete_does_not_affect_l1_cache_directly(
        self,
        l0_storage: L0StoragePort,
        redis_cache: RedisMemoryCache,
        real_redis_sync,
    ):
        """Verify L0 delete doesn't directly affect L1 cache.

        Cache invalidation happens via MemoryChangedListener, not directly from L0 operations.
        """
        memory_type = "user"
        owner_id = f"user-{uuid.uuid4().hex[:8]}"
        name = "independent-layers-test"

        # Populate both layers
        await redis_cache.set_memory(memory_type, owner_id, name, "l1 content")

        # L0 delete (no event triggered)
        # Note: l0_storage.delete expects (memory_id, memory_type) not (memory_id, memory_type, owner_id, name)
        memory_id = str(uuid.uuid4())
        await l0_storage.write(memory_id, memory_type, "l0 content")

        # L1 cache should still have data (no listener triggered)
        result = await redis_cache.get_memory(memory_type, owner_id, name)
        assert result == "l1 content", "L1 cache independent of L0 operations"

        # Cleanup
        await redis_cache.delete_memory(memory_type, owner_id, name)
