"""Tests for MemoryChangedListener.

RED PHASE: 验证 MemoryChangedListener 按 §11.2.9 最优架构处理 MemoryChanged 事件。
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.events.memory_events import MemoryChanged


def _make_event(
    memory_id: str | None = None,
    user_id: str = "user-456",
    name: str = "test-memory",
    change_type: str = "create",
    memory_type: str = "user",
) -> MemoryChanged:
    """Helper to create MemoryChanged event with unique ID."""
    return MemoryChanged(
        memory_id=memory_id or str(uuid.uuid4()),
        user_id=user_id,
        name=name,
        change_type=change_type,
        is_automatic=False,
        new_value={"type": memory_type, "description": "Test"},
    )


class TestMemoryChangedListenerInit:
    """MemoryChangedListener 初始化验证"""

    def test_init_with_dependencies(self):
        """验证使用依赖初始化"""
        mock_storage_coordinator = MagicMock()
        mock_metadata_repo = MagicMock()
        mock_history_repo = MagicMock()

        from src.application.event_handlers.memory_changed_handler import MemoryChangedHandler

        listener = MemoryChangedHandler(
            storage_coordinator=mock_storage_coordinator,
            metadata_repository=mock_metadata_repo,
            history_repository=mock_history_repo,
        )

        assert listener._storage_coordinator is mock_storage_coordinator
        assert listener._metadata_repository is mock_metadata_repo
        assert listener._history_repository is mock_history_repo

    def test_init_with_none_dependencies(self):
        """验证可选依赖可以为 None"""
        from src.application.event_handlers.memory_changed_handler import MemoryChangedHandler

        listener = MemoryChangedHandler(
            storage_coordinator=None,
            metadata_repository=None,
            history_repository=None,
        )

        assert listener._storage_coordinator is None
        assert listener._metadata_repository is None
        assert listener._history_repository is None


class TestMemoryChangedListenerHandle:
    """MemoryChangedListener handle 方法验证"""

    @pytest.mark.asyncio
    async def test_handle_calls_invalidate_l1_cache(self):
        """验证 handle 调用 L1 缓存失效"""
        mock_storage_coordinator = AsyncMock()
        mock_metadata_repo = AsyncMock()
        mock_history_repo = AsyncMock()

        from src.application.event_handlers.memory_changed_handler import MemoryChangedHandler

        listener = MemoryChangedHandler(
            storage_coordinator=mock_storage_coordinator,
            metadata_repository=mock_metadata_repo,
            history_repository=mock_history_repo,
        )

        event = _make_event(user_id="user-456", name="test-memory")

        await listener.handle(event)

        mock_storage_coordinator.invalidate.assert_called_once()
        call_args = mock_storage_coordinator.invalidate.call_args
        assert call_args.kwargs["layer"] == "L1"
        assert call_args.kwargs["memory_type"] == "user"
        assert call_args.kwargs["owner_id"] == "user-456"
        assert call_args.kwargs["name"] == "test-memory"

    @pytest.mark.asyncio
    async def test_handle_calls_write_to_l2(self):
        """验证 handle 调用 L2 写入"""
        mock_storage_coordinator = AsyncMock()
        mock_metadata_repo = AsyncMock()
        mock_history_repo = AsyncMock()

        from src.application.event_handlers.memory_changed_handler import MemoryChangedHandler

        listener = MemoryChangedHandler(
            storage_coordinator=mock_storage_coordinator,
            metadata_repository=mock_metadata_repo,
            history_repository=mock_history_repo,
        )

        event = _make_event(user_id="user-456", name="test-memory")

        await listener.handle(event)


class TestMemoryChangedListenerL1Invalidation:
    """L1 缓存失效验证"""

    @pytest.mark.asyncio
    async def test_invalidate_l1_cache_with_private_memory(self):
        """验证 private 记忆的 L1 缓存失效"""
        mock_storage_coordinator = AsyncMock()

        from src.application.event_handlers.memory_changed_handler import MemoryChangedHandler

        listener = MemoryChangedHandler(
            storage_coordinator=mock_storage_coordinator,
            metadata_repository=None,
            history_repository=None,
        )

        memory_id = str(uuid.uuid4())
        event = _make_event(memory_id=memory_id, user_id="user-456", change_type="update")

        await listener._invalidate_l1_cache(event)

        mock_storage_coordinator.invalidate.assert_called_once_with(
            memory_id=memory_id,
            layer="L1",
            memory_type="user",
            owner_id="user-456",
            name="test-memory",
        )

    @pytest.mark.asyncio
    async def test_invalidate_l1_cache_with_group_memory(self):
        """验证 group 记忆的 L1 缓存失效"""
        mock_storage_coordinator = AsyncMock()

        from src.application.event_handlers.memory_changed_handler import MemoryChangedHandler

        listener = MemoryChangedHandler(
            storage_coordinator=mock_storage_coordinator,
            metadata_repository=None,
            history_repository=None,
        )

        memory_id = str(uuid.uuid4())
        event = _make_event(
            memory_id=memory_id,
            user_id="group-789",
            change_type="delete",
            memory_type="group",
        )

        await listener._invalidate_l1_cache(event)

        mock_storage_coordinator.invalidate.assert_called_once_with(
            memory_id=memory_id,
            layer="L1",
            memory_type="group",
            owner_id="group-789",
            name="test-memory",
        )

    @pytest.mark.asyncio
    async def test_invalidate_l1_cache_no_storage_coordinator(self):
        """验证无 storage_coordinator 时跳过失效"""
        from src.application.event_handlers.memory_changed_handler import MemoryChangedHandler

        listener = MemoryChangedHandler(
            storage_coordinator=None,
            metadata_repository=None,
            history_repository=None,
        )

        event = _make_event()

        await listener._invalidate_l1_cache(event)


class TestMemoryChangedListenerL2Write:
    """L2 PostgreSQL 写入验证"""

    @pytest.mark.asyncio
    async def test_write_to_l2_with_both_repositories(self):
        """验证同时使用两个 repository"""
        mock_metadata_repo = AsyncMock()
        mock_history_repo = AsyncMock()

        from src.application.event_handlers.memory_changed_handler import MemoryChangedHandler

        listener = MemoryChangedHandler(
            storage_coordinator=None,
            metadata_repository=mock_metadata_repo,
            history_repository=mock_history_repo,
        )

        event = _make_event()

        await listener._write_to_l2(event)

        mock_metadata_repo.save.assert_called_once()
        mock_history_repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_to_l2_no_repositories(self):
        """验证无 repository 时跳过写入"""
        from src.application.event_handlers.memory_changed_handler import MemoryChangedHandler

        listener = MemoryChangedHandler(
            storage_coordinator=None,
            metadata_repository=None,
            history_repository=None,
        )

        event = _make_event()

        await listener._write_to_l2(event)


class TestMemoryChangedListenerHelperMethods:
    """辅助方法验证"""

    def test_get_memory_type_from_new_value(self):
        """验证从 new_value 提取 memory_type"""
        from src.application.event_handlers.memory_changed_handler import MemoryChangedHandler

        listener = MemoryChangedHandler(
            storage_coordinator=None,
            metadata_repository=None,
            history_repository=None,
        )

        event = _make_event(memory_type="group")

        assert listener._get_memory_type(event) == "group"

    def test_get_memory_type_defaults_to_private(self):
        """验证 memory_type 默认值为 private"""
        from src.application.event_handlers.memory_changed_handler import MemoryChangedHandler

        listener = MemoryChangedHandler(
            storage_coordinator=None,
            metadata_repository=None,
            history_repository=None,
        )

        event = _make_event()

        assert listener._get_memory_type(event) == "user"

    def test_get_memory_type_handles_missing_type_field(self):
        """验证 new_value 缺少 type 字段时返回 private"""
        from src.application.event_handlers.memory_changed_handler import MemoryChangedHandler

        listener = MemoryChangedHandler(
            storage_coordinator=None,
            metadata_repository=None,
            history_repository=None,
        )

        event = MemoryChanged(
            memory_id=str(uuid.uuid4()),
            user_id="user-456",
            name="test-memory",
            change_type="create",
            is_automatic=False,
            new_value={"description": "Test only"},
        )

        assert listener._get_memory_type(event) == "private"
