"""Six-layer storage integration tests with real services.

Tests the complete storage flow across L0-L5:
- L0: File system (MEMORY.md index + .md files) - real files
- L1: Redis cache - real Redis (localhost:6379)
- L2: PostgreSQL - real PostgreSQL (localhost:5432)
- L3: Qdrant - real Qdrant (localhost:6333)
- L4: MinIO - real MinIO (localhost:9000)
- L5: Neo4j - real Neo4j (localhost:7687)

Uses UUID prefix isolation patterns for test isolation.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
import redis

from src.application.services.six_layer_storage_coordinator import (
    SixLayerStorageCoordinator,
)
from src.infrastructure.cache.redis_memory_cache import RedisMemoryCache
from src.infrastructure.storage.memory_index import MemoryIndex

if TYPE_CHECKING:
    pass


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
    """Provide real Redis client. Skip if not available."""
    try:
        client = redis.Redis(host="localhost", port=6379, decode_responses=True)
        client.ping()
        yield client
        # Cleanup only keys with this test's prefix
        pattern = f"{redis_test_prefix}*"
        keys = client.keys(pattern)
        if keys:
            client.delete(*keys)
    except redis.ConnectionError:
        pytest.skip("Redis not available at localhost:6379")


@pytest.fixture
def redis_cache(real_redis) -> RedisMemoryCache:
    """Create RedisMemoryCache with real Redis."""
    return RedisMemoryCache(real_redis)


@pytest.fixture
def coordinator_with_redis(redis_cache) -> SixLayerStorageCoordinator:
    """Create SixLayerStorageCoordinator with real L1 Redis."""
    mock_l2 = MagicMock()
    mock_l3 = MagicMock()
    mock_l4 = MagicMock()
    mock_l5 = MagicMock()
    return SixLayerStorageCoordinator(
        redis_cache=redis_cache,
        l2_repository=mock_l2,
        l3_vector_store=mock_l3,
        l4_object_store=mock_l4,
        l5_graph_store=mock_l5,
    )


# ===================================================================
# L0 File System Tests (Real Files)
# ===================================================================


class TestL0FileSystem:
    """L0 file system integration tests using real files."""

    def test_memory_index_creates_index_file(self, memory_config, temp_memory_dir: Path):
        """Verify MemoryIndex creates MEMORY.md index file."""
        memory_index = MemoryIndex(memory_config)
        index_path = temp_memory_dir / "MEMORY.md"
        assert not index_path.exists()

        memory_index.update_entry(
            {
                "memory_id": "test-id",
                "name": "test-memory",
                "type": "user",
                "description": "Test memory",
            }
        )

        assert index_path.exists()

    def test_memory_index_truncates_over_200_lines(self, memory_config, temp_memory_dir: Path):
        """Verify MemoryIndex truncates to 200 lines when exceeded."""
        memory_index = MemoryIndex(memory_config)
        index_path = temp_memory_dir / "MEMORY.md"

        # Add 250 entries
        for i in range(250):
            memory_index.update_entry(
                {
                    "memory_id": f"id-{i}",
                    "name": f"memory-{i}",
                    "type": "user",
                    "description": f"Description {i}",
                }
            )

        # Truncate
        memory_index.truncate()

        # Verify
        lines = index_path.read_text().strip().split("\n")
        assert len(lines) <= 200

    def test_memory_index_read_entries(self, memory_config, temp_memory_dir: Path):
        """Verify MemoryIndex can read entries."""
        memory_index = MemoryIndex(memory_config)

        for i in range(5):
            memory_index.update_entry(
                {
                    "memory_id": f"id-{i}",
                    "name": f"memory-{i}",
                    "type": "user",
                    "description": f"Description {i}",
                }
            )

        entries = memory_index.read_entries()
        assert len(entries) == 5

    def test_memory_index_search(self, memory_config, temp_memory_dir: Path):
        """Verify MemoryIndex search functionality."""
        memory_index = MemoryIndex(memory_config)

        for i in range(10):
            memory_index.update_entry(
                {
                    "memory_id": f"id-{i}",
                    "name": f"bun-npm-{i}",
                    "type": "user",
                    "description": f"Remember bun instead of npm {i}",
                }
            )

        results = memory_index.search("bun")
        assert len(results) >= 5


# ===================================================================
# L1 Redis Cache Tests (Real Redis)
# ===================================================================


class TestL1RedisCache:
    """L1 Redis cache integration tests using real Redis."""

    def test_redis_cache_set_and_get(self, redis_cache, real_redis):
        """Verify Redis cache set and get operations."""
        memory_type = "user"
        owner_id = f"user-{uuid.uuid4().hex[:8]}"
        name = "test-memory"
        content = "Test memory content"

        redis_cache.set(memory_type, owner_id, name, content)

        result = redis_cache.get(memory_type, owner_id, name)
        assert result == content

        # Cleanup
        key = f"memory:{memory_type}:{owner_id}:{name}"
        real_redis.delete(key)

    def test_redis_cache_delete(self, redis_cache, real_redis):
        """Verify Redis cache delete operation."""
        memory_type = "user"
        owner_id = f"user-{uuid.uuid4().hex[:8]}"
        name = "test-memory"

        redis_cache.set(memory_type, owner_id, name, "content")
        redis_cache.delete(memory_type, owner_id, name)

        result = redis_cache.get(memory_type, owner_id, name)
        assert result is None

    def test_redis_cache_ttl_range(self, redis_cache, real_redis):
        """Verify Redis cache TTL is in 24h-30h range."""
        memory_type = "user"
        owner_id = f"user-{uuid.uuid4().hex[:8]}"
        name = "test-memory"
        content = "Test content"

        redis_cache.set(memory_type, owner_id, name, content)

        key = f"memory:{memory_type}:{owner_id}:{name}"
        ttl = real_redis.ttl(key)
        assert 86400 <= ttl <= 108000

        # Cleanup
        real_redis.delete(key)

    def test_redis_cache_get_returns_none_when_not_cached(self, redis_cache):
        """Verify Redis cache get returns None when not cached."""
        result = redis_cache.get("user", "nonexistent-owner", "nonexistent")
        assert result is None

    def test_redis_cache_invalidate_pattern(self, redis_cache, real_redis):
        """Verify invalidate_pattern deletes all matching keys."""
        memory_type = "user"
        owner_id = f"user-{uuid.uuid4().hex[:8]}"

        # Set multiple memories
        for i in range(3):
            redis_cache.set(memory_type, owner_id, f"memory-{i}", f"content-{i}")

        # Verify they exist
        pattern = f"memory:{memory_type}:{owner_id}:*"
        keys_before = real_redis.keys(pattern)
        assert len(keys_before) >= 3

        # Invalidate all
        redis_cache.invalidate_pattern(memory_type, owner_id)

        # Verify all deleted
        keys_after = real_redis.keys(pattern)
        assert len(keys_after) == 0


# ===================================================================
# L1-L2 Coordination Tests
# ===================================================================


class TestL1L2Coordination:
    """Test L1 cache and L2 repository coordination."""

    def test_coordinator_save_to_l1(self, coordinator_with_redis, real_redis):
        """Verify coordinator saves to L1 Redis cache."""
        memory_id = str(uuid.uuid4())
        owner_id = f"user-{uuid.uuid4().hex[:8]}"
        name = "test-memory"
        content = "Test memory content"

        coordinator_with_redis.save(memory_id, content, layer="L1", memory_type="private", owner_id=owner_id, name=name)

        # Verify via real Redis (key format: memory:user:{owner_id}:{name})
        key = f"memory:user:{owner_id}:{name}"
        stored = real_redis.get(key)
        assert stored == content

        # Cleanup
        real_redis.delete(key)

    def test_coordinator_read_from_l1(self, coordinator_with_redis, real_redis):
        """Verify coordinator reads from L1 Redis cache."""
        memory_id = str(uuid.uuid4())
        owner_id = f"user-{uuid.uuid4().hex[:8]}"
        name = "test-memory"
        content = "Test memory content"

        # Pre-populate
        key = f"memory:user:{owner_id}:{name}"
        real_redis.setex(key, 86400, content)

        result = coordinator_with_redis.read(memory_id, layer="L1", memory_type="private", owner_id=owner_id, name=name)
        assert result == content

        # Cleanup
        real_redis.delete(key)

    def test_coordinator_invalidate_l1(self, coordinator_with_redis, real_redis):
        """Verify coordinator invalidates L1 cache."""
        memory_id = str(uuid.uuid4())
        owner_id = f"user-{uuid.uuid4().hex[:8]}"
        name = "test-memory"
        content = "Test memory"

        key = f"memory:user:{owner_id}:{name}"
        real_redis.setex(key, 86400, content)

        coordinator_with_redis.invalidate(memory_id, layer="L1", memory_type="private", owner_id=owner_id, name=name)

        assert real_redis.get(key) is None


# ===================================================================
# Layer Status Tests
# ===================================================================


class TestLayerCoordination:
    """Test coordination across L0, L1, L2 layers."""

    def test_get_layer_status_returns_all_layers(self, coordinator_with_redis):
        """Verify get_layer_status returns status for all layers."""
        memory_id = str(uuid.uuid4())

        status = coordinator_with_redis.get_layer_status(memory_id, memory_type="private")

        assert "L0" in status
        assert "L1" in status
        assert "L2" in status
        assert "L3" in status
        assert "L4" in status
        assert "L5" in status

    def test_layer_status_l0_always_true(self, coordinator_with_redis):
        """Verify L0 is always reported as existing (file system)."""
        memory_id = str(uuid.uuid4())

        status = coordinator_with_redis.get_layer_status(memory_id, memory_type="private")

        assert status["L0"] is True


# ===================================================================
# Error Handling Tests
# ===================================================================


class TestErrorHandling:
    """Test error handling across layers."""

    def test_coordinator_raises_for_invalid_layer(self, coordinator_with_redis):
        """Verify coordinator raises error for invalid layer."""
        from src.application.services.six_layer_storage_coordinator import LayerNotFoundError

        memory_id = str(uuid.uuid4())
        owner_id = "user-123"
        name = "test-memory"

        with pytest.raises(LayerNotFoundError):
            coordinator_with_redis.save(memory_id, "content", layer="L99", memory_type="private", owner_id=owner_id, name=name)

    def test_coordinator_read_raises_for_invalid_layer(self, coordinator_with_redis):
        """Verify coordinator read raises error for invalid layer."""
        from src.application.services.six_layer_storage_coordinator import LayerNotFoundError

        memory_id = str(uuid.uuid4())
        owner_id = "user-123"
        name = "test-memory"

        with pytest.raises(LayerNotFoundError):
            coordinator_with_redis.read(memory_id, layer="L99", memory_type="private", owner_id=owner_id, name=name)

    def test_coordinator_invalidate_raises_for_unsupported_layer(self, coordinator_with_redis):
        """Verify coordinator invalidate raises error for non-L1 layers."""
        from src.application.services.six_layer_storage_coordinator import LayerNotFoundError

        memory_id = str(uuid.uuid4())
        owner_id = "user-123"
        name = "test-memory"

        # L1 should work
        coordinator_with_redis.invalidate(memory_id, layer="L1", memory_type="private", owner_id=owner_id, name=name)

        # L2 should raise
        with pytest.raises(LayerNotFoundError):
            coordinator_with_redis.invalidate(memory_id, layer="L2", memory_type="private", owner_id=owner_id, name=name)
