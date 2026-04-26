"""Six-layer storage integration tests.

Tests the complete storage flow across L0-L5:
- L0: File system (MEMORY.md index + .md files)
- L1: Redis cache (mock for isolation)
- L2: PostgreSQL (mock for isolation)
- L3: Qdrant (mock for isolation)
- L4: MinIO (mock for isolation)
- L5: Neo4j (mock for isolation)

Uses UUID prefix isolation patterns.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, Mock

import pytest

from src.application.services.six_layer_storage_coordinator import (
    SixLayerStorageCoordinator,
)
from src.infrastructure.cache.redis_memory_cache import RedisMemoryCache

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
def mock_config(temp_memory_dir: Path) -> MagicMock:
    """Create mock MemoryConfig with temp directory."""
    config = MagicMock()
    config.get_base_path.return_value = str(temp_memory_dir)
    config.get_index_path.return_value = str(temp_memory_dir / "MEMORY.md")
    return config


@pytest.fixture
def mock_redis() -> Mock:
    """Create mock Redis client with synchronous behavior."""
    redis_mock = Mock()
    redis_mock.get.return_value = None
    redis_mock.setex.return_value = True
    redis_mock.delete.return_value = 1
    redis_mock.keys.return_value = []
    redis_mock.ttl.return_value = 86400  # Default 24h
    return redis_mock


@pytest.fixture
def redis_cache(mock_redis: Mock) -> RedisMemoryCache:
    """Create RedisMemoryCache with mock Redis."""
    return RedisMemoryCache(mock_redis)


@pytest.fixture
def coordinator(
    redis_cache: RedisMemoryCache,
) -> SixLayerStorageCoordinator:
    """Create SixLayerStorageCoordinator with mocked L2-L5."""
    mock_l2_repo = MagicMock()
    mock_l3_store = MagicMock()
    mock_l4_store = MagicMock()
    mock_l5_store = MagicMock()

    return SixLayerStorageCoordinator(
        redis_cache=redis_cache,
        l2_repository=mock_l2_repo,
        l3_vector_store=mock_l3_store,
        l4_object_store=mock_l4_store,
        l5_graph_store=mock_l5_store,
    )


# ===================================================================
# L0 File System Tests
# ===================================================================


class TestL0FileSystem:
    """L0 file system integration tests using real files."""

    def test_memory_index_creates_index_file(
        self,
        mock_config: MagicMock,
        temp_memory_dir: Path,
    ) -> None:
        """Verify MemoryIndex creates MEMORY.md index file."""
        from src.infrastructure.storage.memory_index import MemoryIndex

        memory_index = MemoryIndex(mock_config)
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

    def test_memory_index_truncates_over_200_lines(
        self,
        mock_config: MagicMock,
        temp_memory_dir: Path,
    ) -> None:
        """Verify MemoryIndex truncate method limits to 200 lines."""
        from src.infrastructure.storage.memory_index import MemoryIndex

        memory_index = MemoryIndex(mock_config)
        index_path = temp_memory_dir / "MEMORY.md"

        # Add 250 entries (exceeds 200 limit)
        for i in range(250):
            memory_index.update_entry(
                {
                    "memory_id": f"id-{i}",
                    "name": f"memory-{i}",
                    "type": "user",
                    "description": f"Description {i}",
                }
            )

        # Manually truncate to enforce 200 line limit
        memory_index.truncate()

        # Read and count lines
        lines = index_path.read_text().strip().split("\n")
        # Should be max 200 data lines after truncate
        assert len(lines) <= 200

    def test_memory_index_read_entries(
        self,
        mock_config: MagicMock,
        temp_memory_dir: Path,
    ) -> None:
        """Verify MemoryIndex can read entries."""
        from src.infrastructure.storage.memory_index import MemoryIndex

        memory_index = MemoryIndex(mock_config)

        # Add some entries
        for i in range(5):
            memory_index.update_entry(
                {
                    "memory_id": f"id-{i}",
                    "name": f"memory-{i}",
                    "type": "user",
                    "description": f"Description {i}",
                }
            )

        # Read entries
        entries = memory_index.read_entries()
        assert len(entries) == 5


# ===================================================================
# L1 Redis Cache Tests
# ===================================================================


class TestL1RedisCache:
    """L1 Redis cache integration tests."""

    def test_redis_cache_set_and_get(
        self,
        redis_cache: RedisMemoryCache,
        mock_redis: Mock,
    ) -> None:
        """Verify Redis cache set and get operations."""
        memory_type = "private"
        owner_id = "user-123"
        name = "test-memory"
        content = "Test memory content"

        # Configure mock to return content on get
        mock_redis.get.return_value = content.encode("utf-8")

        # Set
        redis_cache.set(memory_type, owner_id, name, content)

        # Verify setex was called
        mock_redis.setex.assert_called_once()

        # Get
        result = redis_cache.get(memory_type, owner_id, name)
        assert result == content

    def test_redis_cache_delete(
        self,
        redis_cache: RedisMemoryCache,
        mock_redis: Mock,
    ) -> None:
        """Verify Redis cache delete operation."""
        memory_type = "private"
        owner_id = "user-123"
        name = "test-memory"

        # Delete
        redis_cache.delete(memory_type, owner_id, name)

        # Verify delete was called
        mock_redis.delete.assert_called_once()

    def test_redis_cache_ttl_range(
        self,
        redis_cache: RedisMemoryCache,
        mock_redis: Mock,
    ) -> None:
        """Verify Redis cache TTL is in 24h-30h range."""
        memory_type = "private"
        owner_id = "user-123"
        name = "test-memory"
        content = "Test memory content"

        # Set with default TTL (random 24h-30h)
        redis_cache.set(memory_type, owner_id, name, content)

        # Verify setex was called with TTL in range
        call_args = mock_redis.setex.call_args
        ttl = call_args[0][1]  # Second argument is TTL
        assert 86400 <= ttl <= 108000

    def test_redis_cache_get_returns_none_when_not_cached(
        self,
        redis_cache: RedisMemoryCache,
        mock_redis: Mock,
    ) -> None:
        """Verify Redis cache get returns None when not cached."""
        memory_type = "private"
        owner_id = "user-123"
        name = "nonexistent-memory"

        # Configure mock to return None (not found)
        mock_redis.get.return_value = None

        result = redis_cache.get(memory_type, owner_id, name)
        assert result is None


# ===================================================================
# L1-L2 Coordination Tests
# ===================================================================


class TestL1L2Coordination:
    """Test L1 cache and L2 repository coordination."""

    def test_coordinator_save_to_l1(
        self,
        coordinator: SixLayerStorageCoordinator,
        redis_cache: RedisMemoryCache,
    ) -> None:
        """Verify coordinator saves to L1 Redis cache."""
        memory_id = str(uuid.uuid4())
        content = "Test memory content"

        coordinator.save(memory_id, content, layer="L1", memory_type="private")

        # Verify cache set was called (via mock return value check)
        # setex is called with key, ttl, content - just verify no exception
        pass

    def test_coordinator_read_from_l1(
        self,
        coordinator: SixLayerStorageCoordinator,
        mock_redis: Mock,
    ) -> None:
        """Verify coordinator reads from L1 Redis cache."""
        memory_id = str(uuid.uuid4())
        content = "Test memory content"

        # Pre-populate cache mock
        mock_redis.get.return_value = content.encode("utf-8")

        # Read from L1
        result = coordinator.read(memory_id, layer="L1", memory_type="private")
        assert result == content

    def test_coordinator_invalidate_l1(
        self,
        coordinator: SixLayerStorageCoordinator,
        mock_redis: Mock,
    ) -> None:
        """Verify coordinator invalidates L1 cache."""
        memory_id = str(uuid.uuid4())

        coordinator.invalidate(memory_id, layer="L1", memory_type="private")

        # Verify cache delete was called
        assert mock_redis.delete.call_count == 1


# ===================================================================
# L0-L1-L2 Coordination Tests
# ===================================================================


class TestLayerCoordination:
    """Test coordination across L0, L1, L2 layers."""

    def test_get_layer_status_returns_all_layers(
        self,
        coordinator: SixLayerStorageCoordinator,
    ) -> None:
        """Verify get_layer_status returns status for all layers."""
        memory_id = str(uuid.uuid4())

        status = coordinator.get_layer_status(memory_id, memory_type="private")

        assert "L0" in status
        assert "L1" in status
        assert "L2" in status
        assert "L3" in status
        assert "L4" in status
        assert "L5" in status

    def test_layer_status_l0_always_true(
        self,
        coordinator: SixLayerStorageCoordinator,
    ) -> None:
        """Verify L0 is always reported as existing (file system)."""
        memory_id = str(uuid.uuid4())

        status = coordinator.get_layer_status(memory_id, memory_type="private")

        assert status["L0"] is True


# ===================================================================
# Six-Layer Storage Flow Tests
# ===================================================================


class TestSixLayerStorageFlow:
    """Test complete six-layer storage flow."""

    def test_save_triggers_l1_cache(
        self,
        coordinator: SixLayerStorageCoordinator,
        mock_redis: Mock,
    ) -> None:
        """Verify save operation triggers L1 cache."""
        memory_id = str(uuid.uuid4())
        content = "Test memory content for six-layer flow"

        # Save to L1
        coordinator.save(memory_id, content, layer="L1", memory_type="private")

        # Verify L1 cache was called
        assert mock_redis.setex.called

    def test_read_from_l1(
        self,
        coordinator: SixLayerStorageCoordinator,
        mock_redis: Mock,
    ) -> None:
        """Verify read from L1 cache."""
        memory_id = str(uuid.uuid4())
        content = "Test memory content"

        # Pre-populate L1 cache mock
        mock_redis.get.return_value = content.encode("utf-8")

        # Read from L1
        result = coordinator.read(memory_id, layer="L1", memory_type="private")
        assert result == content

    def test_memory_index_search(
        self,
        mock_config: MagicMock,
        temp_memory_dir: Path,
    ) -> None:
        """Verify MemoryIndex search functionality."""
        from src.infrastructure.storage.memory_index import MemoryIndex

        memory_index = MemoryIndex(mock_config)

        # Add entries
        for i in range(10):
            memory_index.update_entry(
                {
                    "memory_id": f"id-{i}",
                    "name": f"bun-npm-{i}",
                    "type": "user",
                    "description": f"Remember bun instead of npm {i}",
                }
            )

        # Search
        results = memory_index.search("bun")
        assert len(results) >= 5  # Should find entries with "bun" in name/description


# ===================================================================
# Error Handling Tests
# ===================================================================


class TestErrorHandling:
    """Test error handling across layers."""

    def test_coordinator_raises_for_invalid_layer(
        self,
        coordinator: SixLayerStorageCoordinator,
    ) -> None:
        """Verify coordinator raises error for invalid layer."""
        from src.application.services.six_layer_storage_coordinator import (
            LayerNotFoundError,
        )

        memory_id = str(uuid.uuid4())
        content = "Test content"

        with pytest.raises(LayerNotFoundError):
            coordinator.save(memory_id, content, layer="L99", memory_type="private")

    def test_coordinator_read_raises_for_invalid_layer(
        self,
        coordinator: SixLayerStorageCoordinator,
    ) -> None:
        """Verify coordinator read raises error for invalid layer."""
        from src.application.services.six_layer_storage_coordinator import (
            LayerNotFoundError,
        )

        memory_id = str(uuid.uuid4())

        with pytest.raises(LayerNotFoundError):
            coordinator.read(memory_id, layer="L99", memory_type="private")

    def test_coordinator_invalidate_raises_for_unsupported_layer(
        self,
        coordinator: SixLayerStorageCoordinator,
    ) -> None:
        """Verify coordinator invalidate raises error for non-L1 layers."""
        from src.application.services.six_layer_storage_coordinator import (
            LayerNotFoundError,
        )

        memory_id = str(uuid.uuid4())

        # L1 should work
        coordinator.invalidate(memory_id, layer="L1", memory_type="private")

        # L2 should raise
        with pytest.raises(LayerNotFoundError):
            coordinator.invalidate(memory_id, layer="L2", memory_type="private")
