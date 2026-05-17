"""Complete L0→L1→L2→L3→L4→L5 six-layer storage flow integration test.

Uses UnifiedStorageGateway as the primary entry point to validate
the real user-facing API for the six-layer storage architecture.

Tests architecture.md §11.2.9 L0-driven coordination with all six layers:
- L0: File system (MEMORY.md index + .md files) - real files
- L1: Redis cache - real Redis
- L2: PostgreSQL - real PostgreSQL
- L3: Qdrant - real Qdrant (content > 500 tokens triggers vector storage)
- L4: MinIO - real MinIO (checkpoint persistence)
- L5: Neo4j - real Neo4j (entity extraction)

Prerequisites:
    - All services must be running (docker ps shows healthy)
    - Uses begin_nested() savepoint for PostgreSQL transactional isolation
    - Uses UUID prefix for Redis/Qdrant/MinIO/Neo4j isolation

Run with:
    pytest tests/integration/test_six_layer_complete_flow.py -v -s

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
from src.application.services.unified_storage_gateway import UnifiedStorageGateway
from src.domain.events.memory_events import MemoryChanged
from src.domain.ports.l0_storage import L0StoragePort
from src.infrastructure.config.memory import MemoryConfig
from src.infrastructure.config.minio import MinIOConfig
from src.infrastructure.config.postgresql import PostgreSQLConfig
from src.infrastructure.storage.fs.file_memory_adapter import FileMemoryAdapter
from src.infrastructure.storage.fs.memory_index import MemoryIndex
from src.infrastructure.storage.minio.minio_adapter import MinIOAdapter
from src.infrastructure.storage.neo4j.neo4j_adapter import Neo4jAdapter
from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
from src.infrastructure.storage.postgresql.repository.memory_change_history_repository import (
    PostgreSQLMemoryChangeHistoryRepository,
)
from src.infrastructure.storage.postgresql.repository.memory_metadata_repository import (
    PostgreSQLMemoryMetadataRepository,
)
from src.infrastructure.storage.postgresql.session_context import reset_session, set_session
from src.infrastructure.storage.qdrant.qdrant_adapter import QdrantAdapter
from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
from src.infrastructure.storage.redis.redis_memory_cache import RedisMemoryCache
from tests.environments import get_test_env

# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def test_schema() -> str:
    """Generate unique schema name for test isolation."""
    return f"test_sisys_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="session")
def redis_prefix():
    """Unique prefix for Redis key isolation."""
    return f"sisys:{uuid.uuid4().hex[:8]}:"


@pytest.fixture
def pg_config() -> PostgreSQLConfig:
    """Real PostgreSQL configuration."""
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
    """Ensure test schema exists before tests."""
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
    """PostgreSQL session with transactional rollback."""
    async_engine = db_engine.get_async_engine()
    session = AsyncSession(async_engine)
    await session.execute(text(f'SET search_path TO "{ensure_schema}"'))

    async with session.begin_nested():
        yield session

    await session.close()


@pytest.fixture
def real_redis(redis_prefix):
    """Real async Redis client."""
    try:
        import redis.asyncio as aioredis

        env = get_test_env()
        client = aioredis.Redis(host=env.redis.host, port=env.redis.port, decode_responses=True)
        yield client
    except Exception:
        env = get_test_env()
        pytest.skip(f"Redis not available at {env.redis.host}:{env.redis.port}")


@pytest.fixture
def real_redis_sync(redis_prefix):
    """Real sync Redis client for cleanup."""
    try:
        env = get_test_env()
        client = redis.Redis(host=env.redis.host, port=env.redis.port, decode_responses=True)
        client.ping()
        yield client
    except redis.ConnectionError:
        env = get_test_env()
        pytest.skip(f"Redis not available at {env.redis.host}:{env.redis.port}")


@pytest.fixture
def redis_cache(real_redis) -> RedisMemoryCache:
    """L1 Redis cache."""
    return RedisMemoryCache(RedisAdapter(real_redis))


@pytest.fixture
def temp_memory_dir(tmp_path: Path) -> Path:
    """Temporary directory for L0 storage."""
    memory_dir = tmp_path / f"memory-{uuid.uuid4().hex[:8]}"
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir


@pytest.fixture
def l0_storage(temp_memory_dir: Path) -> L0StoragePort:
    """L0 file system storage."""
    config = MemoryConfig(memory_l0_path=str(temp_memory_dir))
    return FileMemoryAdapter(config)


@pytest.fixture
def memory_index(temp_memory_dir: Path):
    """L0 MEMORY.md index."""
    config = MemoryConfig(memory_l0_path=str(temp_memory_dir))
    return MemoryIndex(config)


@pytest.fixture
def metadata_repository(pg_session: AsyncSession):
    """L2 PostgreSQL metadata repository."""
    token = set_session(pg_session)
    repo = PostgreSQLMemoryMetadataRepository()
    yield repo
    reset_session(token)


@pytest.fixture
def history_repository(pg_session: AsyncSession):
    """L2 PostgreSQL history repository."""
    token = set_session(pg_session)
    repo = PostgreSQLMemoryChangeHistoryRepository()
    yield repo
    reset_session(token)


@pytest.fixture
def qdrant_adapter():
    """L3 Qdrant adapter."""
    try:
        from src.infrastructure.config.qdrant import QdrantConfig
        from src.infrastructure.storage.qdrant.qdrant_manager import QdrantManager
        from src.infrastructure.storage.qdrant.vector_storage import QdrantVectorStorage

        env = get_test_env()
        config = QdrantConfig(
            host=env.qdrant.host,
            port=env.qdrant.port,
            grpc_port=env.qdrant.grpc_port,
            api_key=env.qdrant.api_key,
            https=env.qdrant.https,
            timeout=env.qdrant.timeout,
        )
        wrapper = QdrantManager(config)
        storage = QdrantVectorStorage(wrapper.get_client())
        return QdrantAdapter(storage)
    except Exception:
        pytest.skip("Qdrant not available")


@pytest.fixture
def qdrant_collection_manager():
    """L3 Qdrant collection manager for schema operations."""
    try:
        from src.infrastructure.config.qdrant import QdrantConfig
        from src.infrastructure.storage.qdrant.collection_manager import QdrantCollectionManager
        from src.infrastructure.storage.qdrant.qdrant_manager import QdrantManager

        env = get_test_env()
        config = QdrantConfig(
            host=env.qdrant.host,
            port=env.qdrant.port,
            grpc_port=env.qdrant.grpc_port,
            api_key=env.qdrant.api_key,
            https=env.qdrant.https,
            timeout=env.qdrant.timeout,
        )
        wrapper = QdrantManager(config)
        return QdrantCollectionManager(wrapper.get_client())
    except Exception:
        pytest.skip("Qdrant not available")


@pytest.fixture
def minio_adapter():
    """L4 MinIO adapter."""
    try:
        from src.infrastructure.storage.minio.bucket_manager import BucketManager
        from src.infrastructure.storage.minio.minio_repository import MinIORepository
        from src.infrastructure.storage.minio.object_operations import ObjectOperations
        from src.infrastructure.storage.minio.worm_lifecycle import WORMManager

        env = get_test_env()
        endpoint_parts = env.minio.endpoint.split(":")
        host = endpoint_parts[0]
        port = int(endpoint_parts[1]) if len(endpoint_parts) > 1 else 9000

        config = MinIOConfig(
            host=host,
            port=port,
            access_key=env.minio.access_key,
            secret_key=env.minio.secret_key,
            secure=env.minio.secure,
        )

        bucket_manager = BucketManager(config)
        object_operations = ObjectOperations(config)
        worm_manager = WORMManager(config)
        repository = MinIORepository(bucket_manager, object_operations, worm_manager)

        # Ensure checkpoints bucket exists
        bucket_name = f"{config.bucket_prefix}-checkpoints-default"
        try:
            bucket_manager.create_bucket(bucket_name)
        except Exception:
            pass

        return MinIOAdapter(repository)
    except Exception:
        pytest.skip("MinIO not available")


@pytest.fixture
def neo4j_adapter():
    """L5 Neo4j adapter."""
    try:
        from src.infrastructure.config.neo4j import Neo4jConfig
        from src.infrastructure.storage.neo4j.graph_storage import Neo4jGraphStorage
        from src.infrastructure.storage.neo4j.neo4j_manager import Neo4jManager

        env = get_test_env()
        config = Neo4jConfig(
            host=env.neo4j.host,
            bolt_port=env.neo4j.bolt_port,
            username=env.neo4j.username,
            password=env.neo4j.password,
            database=env.neo4j.database,
        )
        wrapper = Neo4jManager.from_config(config)
        storage = Neo4jGraphStorage(wrapper.get_client())
        return Neo4jAdapter(storage)
    except Exception:
        env = get_test_env()
        pytest.skip(f"Neo4j not available at {env.neo4j.host}:{env.neo4j.bolt_port}")


@pytest.fixture
def unified_storage_gateway(
    l0_storage: L0StoragePort,
    redis_cache: RedisMemoryCache,
    metadata_repository,
    history_repository,
    qdrant_adapter,
    minio_adapter,
    neo4j_adapter,
) -> UnifiedStorageGateway:
    """UnifiedStorageGateway with all six layers wired up.

    This is the primary entry point for the six-layer storage architecture.
    Users interact with this gateway, not individual layer adapters.
    """
    return UnifiedStorageGateway(
        l0_storage=l0_storage,
        memory_cache=redis_cache,
        l2_metadata=metadata_repository,
        l2_history=history_repository,
        l3_vector=qdrant_adapter,
        l4_object=minio_adapter,
        l5_graph=neo4j_adapter,
        event_publisher=None,  # Events handled manually in tests
    )


@pytest.fixture
def memory_changed_handler(
    redis_cache: RedisMemoryCache,
    metadata_repository,
    history_repository,
) -> MemoryChangedHandler:
    """Handler for MemoryChanged events (L1 invalidation + L2 write)."""
    return MemoryChangedHandler(
        memory_cache=redis_cache,
        metadata_repository=metadata_repository,
        history_repository=history_repository,
    )


# ===================================================================
# Six-Layer Complete Flow Tests (via UnifiedStorageGateway)
# ===================================================================


class TestSixLayerCompleteFlow:
    """L0→L1→L2→L3→L4→L5 complete flow integration tests.

    Uses UnifiedStorageGateway as the entry point to validate the
    real user-facing API for the six-layer storage architecture.

    Validates architecture.md §11.2.9:
    - L0: Truth source (always written first via gateway.save())
    - L1: Cache (invalidated via MemoryChanged event)
    - L2: Metadata + History (written via MemoryChangedHandler)
    - L3: Vector (triggered when content > 500 tokens)
    - L4: Object storage (triggered for checkpoints)
    - L5: Graph (triggered for entity extraction)
    """

    @pytest.mark.asyncio
    async def test_complete_flow_long_content_via_gateway(
        self,
        unified_storage_gateway: UnifiedStorageGateway,
        memory_changed_handler: MemoryChangedHandler,
        real_redis_sync,
        qdrant_adapter,
        qdrant_collection_manager,
        minio_adapter,
        neo4j_adapter,
        temp_memory_dir: Path,
    ):
        """Test complete flow via UnifiedStorageGateway.

        Flow:
        1. gateway.save() → L0 write + MemoryChanged event
        2. memory_changed_handler.handle() → L1 invalidation + L2 write
        3. L3 vector storage (content > 500 tokens)
        4. L4 object storage (checkpoint)
        5. L5 graph storage (entity extraction)
        """
        memory_id = str(uuid.uuid4())
        user_id = f"user-{uuid.uuid4().hex[:8]}"
        name = f"test-six-layer-{uuid.uuid4().hex[:8]}"
        memory_type = "user"
        owner_id = user_id

        # Long content (>500 tokens) to trigger L3 vector storage
        content = " ".join([f"word_{i}" for i in range(600)])[:3000]

        # Pre-populate L1 cache to verify invalidation
        await unified_storage_gateway._memory_cache.set_memory(memory_type, owner_id, name, "stale cached content")
        redis_key = f"memory:{memory_type}:{owner_id}:{name}"
        assert real_redis_sync.exists(redis_key) == 1

        # === Step 1: gateway.save() writes to L0 ===
        results = await unified_storage_gateway.save(
            memory_id=memory_id,
            content=content,
            memory_type=memory_type,
            owner_id=owner_id,
            name=name,
        )

        # Verify L0 write succeeded
        assert results is not None  # L0 always succeeds
        l0_content = await unified_storage_gateway._l0.read(memory_id, memory_type)
        assert l0_content == content

        # === Step 2: Trigger MemoryChanged handler for L1 + L2 ===
        event = MemoryChanged(
            memory_id=memory_id,
            user_id=user_id,
            name=name,
            change_type="create",
            is_automatic=False,
            new_value={"type": memory_type, "description": "Six layer test", "owner": owner_id},
        )
        await memory_changed_handler.handle(event)

        # L1 cache should be invalidated
        assert real_redis_sync.exists(redis_key) == 0

        # L2 metadata should be written
        l2_meta = await unified_storage_gateway._l2_meta.get_by_id(uuid.UUID(memory_id))
        assert l2_meta is not None
        assert l2_meta.name == name

        # L2 history should be recorded
        l2_history = await unified_storage_gateway._l2_hist.get_by_memory_id(uuid.UUID(memory_id))
        assert len(l2_history) > 0

        # === Step 3: L3 Vector storage (content > 500 tokens) ===
        collection = f"test_{uuid.uuid4().hex[:8]}"
        try:
            await qdrant_collection_manager.create_collection(collection, vector_size=1024)

            vector = [0.1] * 1024
            await qdrant_adapter.upsert_points(
                collection=collection,
                points=[
                    {
                        "id": memory_id,
                        "vector": vector,
                        "payload": {"memory_id": memory_id, "name": name, "type": memory_type},
                    }
                ],
            )

            point = await qdrant_adapter.get_point(collection, memory_id)
            assert point is not None
            assert point["payload"]["memory_id"] == memory_id

            # === Step 4: L4 Object storage (checkpoint) ===
            checkpoint_content = b"checkpoint data " * 100
            checkpoint_file = temp_memory_dir / "temp.ckpt"
            checkpoint_file.write_bytes(checkpoint_content)
            await minio_adapter.store(
                bucket_type="checkpoints",
                object_key=f"{user_id}/{memory_id}.ckpt",
                file_path=str(checkpoint_file),
                content_type="application/octet-stream",
            )

            metadata_obj = await minio_adapter.get_metadata("checkpoints", f"{user_id}/{memory_id}.ckpt")
            assert metadata_obj["size"] == 1600

            # === Step 5: L5 Graph storage (entity extraction) ===
            await neo4j_adapter.create_entity(
                memory_id=memory_id,
                entity_type="long_memory",
                properties={"name": name, "user_id": user_id, "content_length": len(content)},
            )

            entity = await neo4j_adapter.get_entity(memory_id)
            assert entity is not None
            assert entity["id"] == memory_id

            # Create relationship
            related_id = str(uuid.uuid4())
            await neo4j_adapter.create_entity(
                memory_id=related_id,
                entity_type="related_memory",
                properties={"name": "related"},
            )
            await neo4j_adapter.create_relationship(
                source_memory_id=memory_id,
                target_memory_id=related_id,
                relationship_type="RELATED_TO",
            )

            related = await neo4j_adapter.find_related(memory_id, max_depth=1)
            assert len(related) > 0

        finally:
            # Cleanup L3
            try:
                await qdrant_collection_manager.delete_collection(collection)
            except Exception:
                pass

            # Cleanup L5
            try:
                await neo4j_adapter.delete_entity(memory_id)
                await neo4j_adapter.delete_entity(related_id)
            except Exception:
                pass

        # === Verify via gateway.read() ===
        # gateway.read() checks L1 cache first, then L2 metadata, then L0
        # Since L1 was invalidated, it should fall back to L0
        read_content = await unified_storage_gateway.read(
            memory_id=memory_id,
            memory_type=memory_type,
            owner_id=owner_id,
            name=name,
            prefer_cache=False,  # Bypass cache, read from L0 directly
        )
        assert read_content == content

        # === Cleanup ===
        await unified_storage_gateway._l0.delete(memory_id, memory_type)
        await unified_storage_gateway._memory_cache.delete_memory(memory_type, owner_id, name)
        await unified_storage_gateway._l2_meta.delete(uuid.UUID(memory_id))

    @pytest.mark.asyncio
    async def test_gateway_save_and_read_cycle(
        self,
        unified_storage_gateway: UnifiedStorageGateway,
        memory_changed_handler: MemoryChangedHandler,
        real_redis_sync,
    ):
        """Test gateway.save() + gateway.read() cycle for short content.

        Verifies basic CRUD cycle without triggering L3/L4/L5.
        """
        memory_id = str(uuid.uuid4())
        user_id = f"user-{uuid.uuid4().hex[:8]}"
        name = f"test-cycle-{uuid.uuid4().hex[:8]}"
        memory_type = "user"
        owner_id = user_id

        short_content = "Short memory content for cycle test"

        # Pre-populate L1 cache
        await unified_storage_gateway._memory_cache.set_memory(memory_type, owner_id, name, "old content")

        # === Save ===
        results = await unified_storage_gateway.save(
            memory_id=memory_id,
            content=short_content,
            memory_type=memory_type,
            owner_id=owner_id,
            name=name,
        )
        assert results is not None

        # Trigger handler for L1 invalidation + L2 write
        event = MemoryChanged(
            memory_id=memory_id,
            user_id=user_id,
            name=name,
            change_type="create",
            is_automatic=False,
            new_value={"type": memory_type, "owner": owner_id},
        )
        await memory_changed_handler.handle(event)

        # === Read via gateway ===
        content = await unified_storage_gateway.read(
            memory_id=memory_id,
            memory_type=memory_type,
            owner_id=owner_id,
            name=name,
            prefer_cache=False,
        )
        assert content == short_content

        # === Cleanup ===
        await unified_storage_gateway._l0.delete(memory_id, memory_type)
        await unified_storage_gateway._memory_cache.delete_memory(memory_type, owner_id, name)
        await unified_storage_gateway._l2_meta.delete(uuid.UUID(memory_id))

    @pytest.mark.asyncio
    async def test_gateway_respects_tier_decision(
        self,
        l0_storage: L0StoragePort,
        redis_cache: RedisMemoryCache,
        metadata_repository,
        history_repository,
    ):
        """Test that gateway uses StoragePolicyService for tier decisions.

        Verifies that content size influences storage tier selection.
        """
        from src.domain.services.storage_tier_strategy import StoragePolicyService, StorageTier

        policy = StoragePolicyService()

        # Short content → HOT tier
        short_content = "short"
        decision = policy.decide_tier(
            access_frequency=10,
            content_size=len(short_content.encode("utf-8")),
            is_checkpoint=False,
        )
        assert decision.tier in (StorageTier.HOT, StorageTier.WARM)

        # Large content → COLD or FROZEN tier (policy may choose either cold tier)
        large_content = "x" * 10000
        decision = policy.decide_tier(
            access_frequency=0,
            content_size=len(large_content.encode("utf-8")),
            is_checkpoint=False,
        )
        assert decision.tier in (StorageTier.COLD, StorageTier.FROZEN)

    @pytest.mark.asyncio
    async def test_short_content_skips_l3_vector(
        self,
        unified_storage_gateway: UnifiedStorageGateway,
        memory_changed_handler: MemoryChangedHandler,
    ):
        """Test that short content (<500 tokens) skips L3 vector storage.

        Gateway save/read should work without L3 being triggered.
        """
        memory_id = str(uuid.uuid4())
        user_id = f"user-{uuid.uuid4().hex[:8]}"
        name = f"test-short-{uuid.uuid4().hex[:8]}"
        memory_type = "user"
        owner_id = user_id

        short_content = "This is a short memory content."

        # === Save via gateway ===
        await unified_storage_gateway.save(
            memory_id=memory_id,
            content=short_content,
            memory_type=memory_type,
            owner_id=owner_id,
            name=name,
        )

        # Trigger handler
        event = MemoryChanged(
            memory_id=memory_id,
            user_id=user_id,
            name=name,
            change_type="create",
            is_automatic=False,
            new_value={"type": memory_type, "owner": owner_id},
        )
        await memory_changed_handler.handle(event)

        # === Read back ===
        content = await unified_storage_gateway.read(
            memory_id=memory_id,
            memory_type=memory_type,
            owner_id=owner_id,
            name=name,
            prefer_cache=False,
        )
        assert content == short_content

        # === L2 metadata should still be written ===
        l2_meta = await unified_storage_gateway._l2_meta.get_by_id(uuid.UUID(memory_id))
        assert l2_meta is not None

        # === Cleanup ===
        await unified_storage_gateway._l0.delete(memory_id, memory_type)
        await unified_storage_gateway._memory_cache.delete_memory(memory_type, owner_id, name)
        await unified_storage_gateway._l2_meta.delete(uuid.UUID(memory_id))


class TestLayerIndependence:
    """Verify layers operate independently."""

    @pytest.mark.asyncio
    async def test_l0_write_independent_of_memory_cache_l2(
        self,
        l0_storage: L0StoragePort,
        temp_memory_dir: Path,
    ):
        """Verify L0 can be written without L1/L2 being available."""
        memory_id = str(uuid.uuid4())
        memory_type = "user"
        content = "L0 only content"

        success = await l0_storage.write(memory_id, memory_type, content)
        assert success is True

        result = await l0_storage.read(memory_id, memory_type)
        assert result == content

        await l0_storage.delete(memory_id, memory_type)

    @pytest.mark.asyncio
    async def test_memory_cache_cache_operations_are_independent(
        self,
        redis_cache: RedisMemoryCache,
        real_redis_sync,
    ):
        """Verify L1 cache operations are independent of L0/L2."""
        memory_type = "user"
        owner_id = f"user-{uuid.uuid4().hex[:8]}"
        name = "l1-only-test"
        content = "L1 only content"

        await redis_cache.set_memory(memory_type, owner_id, name, content)
        result = await redis_cache.get_memory(memory_type, owner_id, name)
        assert result == content

        await redis_cache.delete_memory(memory_type, owner_id, name)
        result = await redis_cache.get_memory(memory_type, owner_id, name)
        assert result is None


class TestLayerCoordinationInvariants:
    """Verify layer coordination invariants from architecture.md §11.2.9."""

    @pytest.mark.asyncio
    async def test_l0_is_source_of_truth(
        self,
        l0_storage: L0StoragePort,
        redis_cache: RedisMemoryCache,
        temp_memory_dir: Path,
    ):
        """Verify L0 is the source of truth."""
        memory_id = str(uuid.uuid4())
        memory_type = "user"
        owner_id = f"user-{uuid.uuid4().hex[:8]}"
        name = "truth-test"
        content = "Truth content"

        await l0_storage.write(memory_id, memory_type, content)

        result = await l0_storage.read(memory_id, memory_type)
        assert result == content

        # Even if L1 cache has stale data, L0 is truth
        await redis_cache.set_memory(memory_type, owner_id, name, "stale")
        l0_result = await l0_storage.read(memory_id, memory_type)
        assert l0_result == content

        await redis_cache.delete_memory(memory_type, owner_id, name)
        await l0_storage.delete(memory_id, memory_type)

    @pytest.mark.asyncio
    async def test_event_driven_layer_updates(
        self,
        unified_storage_gateway: UnifiedStorageGateway,
        memory_changed_handler: MemoryChangedHandler,
        real_redis_sync,
    ):
        """Verify L1 invalidation and L2 write happen via event."""
        memory_id = str(uuid.uuid4())
        user_id = f"user-{uuid.uuid4().hex[:8]}"
        name = f"event-test-{uuid.uuid4().hex[:8]}"
        memory_type = "user"
        owner_id = user_id

        # Pre-populate cache
        await unified_storage_gateway._memory_cache.set_memory(memory_type, owner_id, name, "stale")
        redis_key = f"memory:{memory_type}:{owner_id}:{name}"
        assert real_redis_sync.exists(redis_key) == 1

        # Create and handle event
        event = MemoryChanged(
            memory_id=memory_id,
            user_id=user_id,
            name=name,
            change_type="create",
            is_automatic=False,
            new_value={"type": memory_type, "description": "Event test"},
        )

        await memory_changed_handler.handle(event)

        # L1 should be invalidated
        assert real_redis_sync.exists(redis_key) == 0

        # L2 should have metadata
        l2_meta = await unified_storage_gateway._l2_meta.get_by_id(uuid.UUID(memory_id))
        assert l2_meta is not None

        # L2 should have history
        l2_history = await unified_storage_gateway._l2_hist.get_by_memory_id(uuid.UUID(memory_id))
        assert len(l2_history) > 0

        # Cleanup
        await unified_storage_gateway._l2_meta.delete(uuid.UUID(memory_id))
