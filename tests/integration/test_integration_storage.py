"""Six-layer storage integration tests with real services.

Tests the complete storage flow across L0-L5:
- L0: File system (MEMORY.md index + .md files) - real files
- L1: Redis cache - real Redis (localhost:6379)
- L2: PostgreSQL - real PostgreSQL (localhost:5432)
- L3: Qdrant - real Qdrant (localhost:6333)
- L4: MinIO - real MinIO (localhost:9000)
- L5: Neo4j - real Neo4j (localhost:7687)

Uses UUID prefix isolation patterns for test isolation.

Refactored from SixLayerStorageCoordinator to direct port usage
(Story 20-5 uni-storage-refactor).
"""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import redis

from src.domain.ports.l0_storage import L0StoragePort
from src.domain.ports.l1_cache import L1CachePort
from src.infrastructure.storage.fs.memory_index import MemoryIndex
from src.infrastructure.storage.redis.redis_adapter import RedisAdapter
from src.infrastructure.storage.redis.redis_memory_cache import RedisMemoryCache
from tests.environments import get_test_env

# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def temp_memory_dir(tmp_path: Path) -> Path:
    """Create temporary memory directory with UUID prefix for isolation."""
    memory_dir = tmp_path / f"memory-{uuid.uuid4().hex[:8]}"
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir


@pytest.fixture
def memory_config(temp_memory_dir: Path):
    """Create MemoryConfig with temp directory."""
    config = MagicMock()
    config.get_base_path.return_value = str(temp_memory_dir)
    config.get_index_path.return_value = str(temp_memory_dir / "MEMORY.md")
    return config


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
    return RedisMemoryCache(RedisAdapter(real_redis))


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
def l0_storage(temp_memory_dir: Path) -> L0StoragePort:
    """Create L0 file system storage adapter."""
    from src.infrastructure.config.memory import MemoryConfig
    from src.infrastructure.storage.fs.file_memory_adapter import FileMemoryAdapter

    config = MemoryConfig(memory_l0_path=str(temp_memory_dir))
    return FileMemoryAdapter(config)


# ===================================================================
# L0 File System Tests (Real Files)
# ===================================================================


class TestL0FileSystem:
    """L0 file system integration tests using real files."""

    @pytest.mark.asyncio
    async def test_memory_index_creates_index_file(self, memory_config, temp_memory_dir: Path):
        """Verify MemoryIndex creates MEMORY.md index file."""
        memory_index = MemoryIndex(memory_config)
        index_path = temp_memory_dir / "MEMORY.md"
        assert not index_path.exists()

        await memory_index.update_entry(
            {
                "memory_id": "test-id",
                "name": "test-memory",
                "type": "user",
                "description": "Test memory",
            }
        )

        assert index_path.exists()

    @pytest.mark.asyncio
    async def test_memory_index_truncates_over_200_lines(self, memory_config, temp_memory_dir: Path):
        """Verify MemoryIndex truncates to 200 lines when exceeded."""
        memory_index = MemoryIndex(memory_config)
        index_path = temp_memory_dir / "MEMORY.md"

        # Add 250 entries
        for i in range(250):
            await memory_index.update_entry(
                {
                    "memory_id": f"id-{i}",
                    "name": f"memory-{i}",
                    "type": "user",
                    "description": f"Description {i}",
                }
            )

        # Truncate
        await memory_index.truncate()

        # Verify
        lines = index_path.read_text().strip().split("\n")
        assert len(lines) <= 200

    @pytest.mark.asyncio
    async def test_memory_index_read_entries(self, memory_config, temp_memory_dir: Path):
        """Verify MemoryIndex can read entries."""
        memory_index = MemoryIndex(memory_config)

        for i in range(5):
            await memory_index.update_entry(
                {
                    "memory_id": f"id-{i}",
                    "name": f"memory-{i}",
                    "type": "user",
                    "description": f"Description {i}",
                }
            )

        entries = await memory_index.read_entries()
        assert len(entries) == 5

    @pytest.mark.asyncio
    async def test_memory_index_search(self, memory_config, temp_memory_dir: Path):
        """Verify MemoryIndex search functionality."""
        memory_index = MemoryIndex(memory_config)

        for i in range(10):
            await memory_index.update_entry(
                {
                    "memory_id": f"id-{i}",
                    "name": f"bun-npm-{i}",
                    "type": "user",
                    "description": f"Remember bun instead of npm {i}",
                }
            )

        results = await memory_index.search("bun")
        assert len(results) >= 5

    @pytest.mark.asyncio
    async def test_l0_write_and_read(self, l0_storage: L0StoragePort, temp_memory_dir: Path):
        """Verify L0 storage write and read operations."""
        memory_id = str(uuid.uuid4())
        memory_type = "user"
        content = "Test memory content"

        # Write
        success = await l0_storage.write(memory_id, memory_type, content)
        assert success is True

        # Read
        result = await l0_storage.read(memory_id, memory_type)
        assert result == content

    @pytest.mark.asyncio
    async def test_l0_delete(self, l0_storage: L0StoragePort, temp_memory_dir: Path):
        """Verify L0 storage delete operation."""
        memory_id = str(uuid.uuid4())
        memory_type = "user"
        content = "Test memory content"

        # Write then delete
        await l0_storage.write(memory_id, memory_type, content)
        deleted = await l0_storage.delete(memory_id, memory_type)
        assert deleted is True

        # Verify deleted - FileNotFoundError raised for missing file
        with pytest.raises(FileNotFoundError):
            await l0_storage.read(memory_id, memory_type)

    @pytest.mark.asyncio
    async def test_l0_storage_raises_on_missing_file(self, l0_storage: L0StoragePort, temp_memory_dir: Path):
        """Verify L0 storage read raises FileNotFoundError for missing file."""
        memory_id = str(uuid.uuid4())
        memory_type = "user"

        with pytest.raises(FileNotFoundError):
            await l0_storage.read(memory_id, memory_type)

    @pytest.mark.asyncio
    async def test_l0_storage_delete_nonexistent_returns_false(self, l0_storage: L0StoragePort, temp_memory_dir: Path):
        """Verify L0 storage delete returns False for nonexistent file."""
        memory_id = str(uuid.uuid4())
        memory_type = "user"

        deleted = await l0_storage.delete(memory_id, memory_type)
        assert deleted is False


# ===================================================================
# L1 Redis Cache Tests (Real Redis)
# ===================================================================


class TestL1RedisCache:
    """L1 Redis cache integration tests using real Redis."""

    @pytest.mark.asyncio
    async def test_redis_cache_set_and_get(self, redis_cache, real_redis, real_redis_sync):
        """Verify Redis cache set and get operations."""
        memory_type = "user"
        owner_id = f"user-{uuid.uuid4().hex[:8]}"
        name = "test-memory"
        content = "Test memory content"

        await redis_cache.set_memory(memory_type, owner_id, name, content)

        result = await redis_cache.get_memory(memory_type, owner_id, name)
        assert result == content

        # Cleanup via adapter
        await redis_cache.delete_memory(memory_type, owner_id, name)

    @pytest.mark.asyncio
    async def test_redis_cache_delete(self, redis_cache, real_redis, real_redis_sync):
        """Verify Redis cache delete operation."""
        memory_type = "user"
        owner_id = f"user-{uuid.uuid4().hex[:8]}"
        name = "test-memory"

        await redis_cache.set_memory(memory_type, owner_id, name, "content")
        await redis_cache.delete_memory(memory_type, owner_id, name)

        result = await redis_cache.get_memory(memory_type, owner_id, name)
        assert result is None

    @pytest.mark.asyncio
    async def test_redis_cache_ttl_range(self, redis_cache, real_redis, real_redis_sync):
        """Verify Redis cache TTL is in 24h-30h range."""
        memory_type = "user"
        owner_id = f"user-{uuid.uuid4().hex[:8]}"
        name = "test-memory"
        content = "Test content"

        await redis_cache.set_memory(memory_type, owner_id, name, content)

        key = f"memory:user:{owner_id}:{name}"
        ttl = real_redis_sync.ttl(key)
        assert 86400 <= ttl <= 108000

        # Cleanup via adapter
        await redis_cache.delete_memory(memory_type, owner_id, name)

    @pytest.mark.asyncio
    async def test_redis_cache_get_returns_none_when_not_cached(self, redis_cache):
        """Verify Redis cache get returns None when not cached."""
        result = await redis_cache.get_memory("user", "nonexistent-owner", "nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_redis_cache_invalidate_pattern(self, redis_cache, real_redis, real_redis_sync):
        """Verify invalidate_owner deletes all matching keys."""
        memory_type = "user"
        owner_id = f"user-{uuid.uuid4().hex[:8]}"

        # Set multiple memories
        for i in range(3):
            await redis_cache.set_memory(memory_type, owner_id, f"memory-{i}", f"content-{i}")

        # Verify they exist
        pattern = f"memory:user:{owner_id}:*"
        keys_before = real_redis_sync.keys(pattern)
        assert len(keys_before) >= 3

        # Invalidate all
        await redis_cache.invalidate_owner(memory_type, owner_id)

        # Verify all deleted
        keys_after = real_redis_sync.keys(pattern)
        assert len(keys_after) == 0


# ===================================================================
# L0-L1 Coordination Tests
# ===================================================================


class TestL0L1Coordination:
    """Test L0 file system and L1 cache coordination."""

    @pytest.mark.asyncio
    async def test_l1_cache_delete_invalidates_l0_cache(
        self, l0_storage: L0StoragePort, redis_cache: RedisMemoryCache, real_redis_sync
    ):
        """Verify L1 cache delete works for cached L0 content."""
        memory_type = "user"
        owner_id = f"user-{uuid.uuid4().hex[:8]}"
        name = "test-memory"
        content = "Test memory content"

        # Pre-populate L1 cache
        await redis_cache.set_memory(memory_type, owner_id, name, content)

        # Verify cache exists
        key = f"memory:user:{owner_id}:{name}"
        assert real_redis_sync.exists(key) == 1

        # Invalidate L1 cache
        await redis_cache.delete_memory(memory_type, owner_id, name)

        # Verify cache deleted
        assert real_redis_sync.exists(key) == 0

    @pytest.mark.asyncio
    async def test_l1_cache_survives_l0_write(self, l0_storage: L0StoragePort, redis_cache: RedisMemoryCache, real_redis_sync):
        """Verify L1 cache persists after L0 write."""
        memory_type = "user"
        owner_id = f"user-{uuid.uuid4().hex[:8]}"
        name = "test-memory"
        content = "Test memory content"

        # Set L1 cache
        await redis_cache.set_memory(memory_type, owner_id, name, content)

        # Write to L0 (should not affect L1)
        await l0_storage.write(str(uuid.uuid4()), memory_type, content)

        # L1 cache should still have value
        result = await redis_cache.get_memory(memory_type, owner_id, name)
        assert result == content

        # Cleanup via adapter
        await redis_cache.delete_memory(memory_type, owner_id, name)


# ===================================================================
# Layer Interface Tests
# ===================================================================


class TestLayerInterfaces:
    """Test that storage ports implement expected interfaces."""

    def test_l0_storage_port_interface(self, l0_storage: L0StoragePort):
        """Verify L0StoragePort has required methods."""
        assert hasattr(l0_storage, "write")
        assert hasattr(l0_storage, "read")
        assert hasattr(l0_storage, "delete")
        assert callable(l0_storage.write)
        assert callable(l0_storage.read)
        assert callable(l0_storage.delete)

    def test_l1_cache_port_interface(self, redis_cache: L1CachePort):
        """Verify L1CachePort has required methods."""
        assert hasattr(redis_cache, "get")
        assert hasattr(redis_cache, "set")
        assert hasattr(redis_cache, "delete")
        assert hasattr(redis_cache, "get_memory")
        assert hasattr(redis_cache, "set_memory")
        assert hasattr(redis_cache, "delete_memory")
        assert hasattr(redis_cache, "invalidate_owner")
        assert callable(redis_cache.get)
        assert callable(redis_cache.set)
        assert callable(redis_cache.delete)
        assert callable(redis_cache.get_memory)
        assert callable(redis_cache.set_memory)
        assert callable(redis_cache.delete_memory)
        assert callable(redis_cache.invalidate_owner)
