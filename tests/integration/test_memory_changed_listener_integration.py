"""MemoryChangedListener integration tests with real Redis services.

Tests the complete event handling flow:
- L1 Redis cache invalidation (synchronous, immediate)
- L2 PostgreSQL write (via repository) - mocked for isolation
- L3/L5 (on demand) - mocked

Uses UUID prefix isolation patterns for test isolation.

Run with: pytest tests/integration/test_memory_changed_listener_integration.py -v
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
import redis

from src.application.services.six_layer_storage_coordinator import (
    SixLayerStorageCoordinator,
)
from src.domain.events.memory_events import MemoryChanged
from src.infrastructure.cache.redis_memory_cache import RedisMemoryCache
from src.interfaces.event_listeners.memory_changed_listener import MemoryChangedListener

if TYPE_CHECKING:
    pass


# ===================================================================
# Fixtures
# ===================================================================


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
def storage_coordinator(redis_cache) -> SixLayerStorageCoordinator:
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


@pytest.fixture
def listener(storage_coordinator) -> MemoryChangedListener:
    """Create MemoryChangedListener with real L1 coordinator."""
    mock_metadata_repo = MagicMock()
    mock_history_repo = MagicMock()
    return MemoryChangedListener(
        storage_coordinator=storage_coordinator,
        metadata_repository=mock_metadata_repo,
        history_repository=mock_history_repo,
    )


# ===================================================================
# L1 Cache Tests (Real Redis)
# ===================================================================


class TestMemoryChangedListenerL1Integration:
    """L1 Redis cache invalidation integration tests using real Redis."""

    def test_handle_invalidates_l1_cache_for_create(self, listener, redis_cache, real_redis):
        """Verify handle() invalidates L1 cache for create event."""
        memory_id = str(uuid.uuid4())
        owner_id = f"user-{uuid.uuid4().hex[:8]}"
        name = f"test-memory-{uuid.uuid4().hex[:8]}"
        # private memory uses "user" prefix in Redis key
        memory_type = "private"

        # Pre-populate cache (Redis key format: memory:user:{owner_id}:{name})
        redis_cache.set(memory_type, owner_id, name, "test content")
        key = f"memory:user:{owner_id}:{name}"
        assert real_redis.exists(key) == 1

        # Create event
        event = MemoryChanged(
            memory_id=memory_id,
            user_id=owner_id,
            name=name,
            change_type="create",
            is_automatic=False,
            new_value={"type": memory_type, "description": "Test"},
        )

        # Handle event
        listener.handle(event)

        # Verify cache was invalidated
        assert real_redis.exists(key) == 0

    def test_handle_invalidates_l1_cache_for_update(self, listener, redis_cache, real_redis):
        """Verify handle() invalidates L1 cache for update event."""
        memory_id = str(uuid.uuid4())
        owner_id = f"user-{uuid.uuid4().hex[:8]}"
        name = f"test-memory-{uuid.uuid4().hex[:8]}"
        memory_type = "private"

        # Pre-populate cache
        redis_cache.set(memory_type, owner_id, name, "old content")
        key = f"memory:user:{owner_id}:{name}"
        assert real_redis.exists(key) == 1

        # Update event
        event = MemoryChanged(
            memory_id=memory_id,
            user_id=owner_id,
            name=name,
            change_type="update",
            is_automatic=False,
            new_value={"type": memory_type, "description": "Updated"},
        )

        # Handle event
        listener.handle(event)

        # Verify cache was invalidated
        assert real_redis.exists(key) == 0

    def test_handle_invalidates_l1_cache_for_delete(self, listener, redis_cache, real_redis):
        """Verify handle() invalidates L1 cache for delete event."""
        memory_id = str(uuid.uuid4())
        owner_id = f"user-{uuid.uuid4().hex[:8]}"
        name = f"test-memory-{uuid.uuid4().hex[:8]}"
        memory_type = "private"

        # Pre-populate cache
        redis_cache.set(memory_type, owner_id, name, "deleted content")
        key = f"memory:user:{owner_id}:{name}"
        assert real_redis.exists(key) == 1

        # Delete event
        event = MemoryChanged(
            memory_id=memory_id,
            user_id=owner_id,
            name=name,
            change_type="delete",
            is_automatic=False,
            old_value={"type": memory_type},
        )

        # Handle event
        listener.handle(event)

        # Verify cache was invalidated
        assert real_redis.exists(key) == 0

    def test_handle_with_group_memory_type(self, listener, redis_cache, real_redis):
        """Verify handle() works with group memory type."""
        memory_id = str(uuid.uuid4())
        owner_id = f"group-{uuid.uuid4().hex[:8]}"
        name = f"test-memory-{uuid.uuid4().hex[:8]}"
        memory_type = "group"

        # Pre-populate cache (Redis key format: memory:group:{owner_id}:{name})
        redis_cache.set(memory_type, owner_id, name, "group content")
        key = f"memory:group:{owner_id}:{name}"
        assert real_redis.exists(key) == 1

        # Create event
        event = MemoryChanged(
            memory_id=memory_id,
            user_id=owner_id,
            name=name,
            change_type="create",
            is_automatic=False,
            new_value={"type": memory_type, "description": "Group memory"},
        )

        # Handle event
        listener.handle(event)

        # Verify cache was invalidated
        assert real_redis.exists(key) == 0

    def test_handle_without_storage_coordinator(self, real_redis):
        """Verify handle() works without storage coordinator (no-op)."""
        listener = MemoryChangedListener(
            storage_coordinator=None,
            metadata_repository=None,
            history_repository=None,
        )

        event = MemoryChanged(
            memory_id=str(uuid.uuid4()),
            user_id="user-123",
            name="test-memory",
            change_type="create",
            is_automatic=False,
            new_value={"type": "private"},
        )

        # Should not raise
        listener.handle(event)


# ===================================================================
# Layer Status Tests
# ===================================================================


class TestLayerStatus:
    """Layer status integration tests."""

    def test_get_layer_status_returns_all_layers(self, storage_coordinator):
        """Verify get_layer_status returns status for all layers."""
        memory_id = str(uuid.uuid4())

        status = storage_coordinator.get_layer_status(memory_id, memory_type="private")

        assert "L0" in status
        assert "L1" in status
        assert "L2" in status
        assert "L3" in status
        assert "L4" in status
        assert "L5" in status

    def test_layer_status_l0_always_true(self, storage_coordinator):
        """Verify L0 is always reported as existing (file system)."""
        memory_id = str(uuid.uuid4())

        status = storage_coordinator.get_layer_status(memory_id, memory_type="private")

        assert status["L0"] is True
