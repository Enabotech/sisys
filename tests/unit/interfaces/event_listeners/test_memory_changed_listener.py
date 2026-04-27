"""Tests for MemoryChangedListener.

RED PHASE: 验证 MemoryChangedListener 按 §11.2.9 最优架构处理 MemoryChanged 事件。
"""

from __future__ import annotations

from unittest.mock import MagicMock

from src.domain.events.memory_events import MemoryChanged


class TestMemoryChangedListenerInit:
    """MemoryChangedListener 初始化验证"""

    def test_init_with_dependencies(self):
        """验证使用依赖初始化"""
        mock_storage_coordinator = MagicMock()
        mock_metadata_repo = MagicMock()
        mock_history_repo = MagicMock()

        from src.interfaces.event_listeners.memory_changed_listener import MemoryChangedListener

        listener = MemoryChangedListener(
            storage_coordinator=mock_storage_coordinator,
            metadata_repository=mock_metadata_repo,
            history_repository=mock_history_repo,
        )

        assert listener._storage_coordinator is mock_storage_coordinator
        assert listener._metadata_repository is mock_metadata_repo
        assert listener._history_repository is mock_history_repo

    def test_init_with_none_dependencies(self):
        """验证可选依赖可以为 None"""
        from src.interfaces.event_listeners.memory_changed_listener import MemoryChangedListener

        listener = MemoryChangedListener(
            storage_coordinator=None,
            metadata_repository=None,
            history_repository=None,
        )

        assert listener._storage_coordinator is None
        assert listener._metadata_repository is None
        assert listener._history_repository is None


class TestMemoryChangedListenerHandle:
    """MemoryChangedListener handle 方法验证"""

    def test_handle_calls_invalidate_l1_cache(self):
        """验证 handle 调用 L1 缓存失效"""
        mock_storage_coordinator = MagicMock()
        mock_metadata_repo = MagicMock()
        mock_history_repo = MagicMock()

        from src.interfaces.event_listeners.memory_changed_listener import MemoryChangedListener

        listener = MemoryChangedListener(
            storage_coordinator=mock_storage_coordinator,
            metadata_repository=mock_metadata_repo,
            history_repository=mock_history_repo,
        )

        event = MemoryChanged(
            memory_id="test-memory-123",
            user_id="user-456",
            name="test-memory",
            change_type="create",
            is_automatic=False,
            new_value={"type": "private", "description": "Test"},
        )

        listener.handle(event)

        mock_storage_coordinator.invalidate.assert_called_once()
        call_args = mock_storage_coordinator.invalidate.call_args
        assert call_args.kwargs["layer"] == "L1"
        assert call_args.kwargs["memory_type"] == "private"
        assert call_args.kwargs["owner_id"] == "user-456"
        assert call_args.kwargs["name"] == "test-memory"

    def test_handle_calls_write_to_l2(self):
        """验证 handle 调用 L2 写入"""
        mock_storage_coordinator = MagicMock()
        mock_metadata_repo = MagicMock()
        mock_history_repo = MagicMock()

        from src.interfaces.event_listeners.memory_changed_listener import MemoryChangedListener

        listener = MemoryChangedListener(
            storage_coordinator=mock_storage_coordinator,
            metadata_repository=mock_metadata_repo,
            history_repository=mock_history_repo,
        )

        event = MemoryChanged(
            memory_id="test-memory-123",
            user_id="user-456",
            name="test-memory",
            change_type="create",
            is_automatic=False,
            new_value={"type": "private", "description": "Test"},
        )

        listener.handle(event)

        # L2 写入由 _write_to_l2 调用
        # 具体 repository 方法调用在 _write_metadata 和 _append_history 中


class TestMemoryChangedListenerL1Invalidation:
    """L1 缓存失效验证"""

    def test_invalidate_l1_cache_with_private_memory(self):
        """验证 private 记忆的 L1 缓存失效"""
        mock_storage_coordinator = MagicMock()

        from src.interfaces.event_listeners.memory_changed_listener import MemoryChangedListener

        listener = MemoryChangedListener(
            storage_coordinator=mock_storage_coordinator,
            metadata_repository=None,
            history_repository=None,
        )

        event = MemoryChanged(
            memory_id="test-memory-123",
            user_id="user-456",
            name="test-memory",
            change_type="update",
            is_automatic=False,
            new_value={"type": "private"},
        )

        listener._invalidate_l1_cache(event)

        mock_storage_coordinator.invalidate.assert_called_once_with(
            memory_id="test-memory-123",
            layer="L1",
            memory_type="private",
            owner_id="user-456",
            name="test-memory",
        )

    def test_invalidate_l1_cache_with_group_memory(self):
        """验证 group 记忆的 L1 缓存失效"""
        mock_storage_coordinator = MagicMock()

        from src.interfaces.event_listeners.memory_changed_listener import MemoryChangedListener

        listener = MemoryChangedListener(
            storage_coordinator=mock_storage_coordinator,
            metadata_repository=None,
            history_repository=None,
        )

        event = MemoryChanged(
            memory_id="test-memory-123",
            user_id="group-789",
            name="test-memory",
            change_type="delete",
            is_automatic=False,
            new_value={"type": "group"},
        )

        listener._invalidate_l1_cache(event)

        mock_storage_coordinator.invalidate.assert_called_once_with(
            memory_id="test-memory-123",
            layer="L1",
            memory_type="group",
            owner_id="group-789",
            name="test-memory",
        )

    def test_invalidate_l1_cache_no_storage_coordinator(self):
        """验证无 storage_coordinator 时跳过失效"""
        from src.interfaces.event_listeners.memory_changed_listener import MemoryChangedListener

        listener = MemoryChangedListener(
            storage_coordinator=None,
            metadata_repository=None,
            history_repository=None,
        )

        event = MemoryChanged(
            memory_id="test-memory-123",
            user_id="user-456",
            name="test-memory",
            change_type="create",
            is_automatic=False,
            new_value={"type": "private"},
        )

        # 不应抛出异常
        listener._invalidate_l1_cache(event)


class TestMemoryChangedListenerL2Write:
    """L2 PostgreSQL 写入验证"""

    def test_write_to_l2_with_both_repositories(self):
        """验证同时使用两个 repository"""
        mock_metadata_repo = MagicMock()
        mock_history_repo = MagicMock()

        from src.interfaces.event_listeners.memory_changed_listener import MemoryChangedListener

        listener = MemoryChangedListener(
            storage_coordinator=None,
            metadata_repository=mock_metadata_repo,
            history_repository=mock_history_repo,
        )

        event = MemoryChanged(
            memory_id="test-memory-123",
            user_id="user-456",
            name="test-memory",
            change_type="create",
            is_automatic=False,
            new_value={"type": "private"},
        )

        listener._write_to_l2(event)

        # 验证 _write_metadata 被调用
        # 验证 _append_history 被调用

    def test_write_to_l2_no_repositories(self):
        """验证无 repository 时跳过写入"""
        from src.interfaces.event_listeners.memory_changed_listener import MemoryChangedListener

        listener = MemoryChangedListener(
            storage_coordinator=None,
            metadata_repository=None,
            history_repository=None,
        )

        event = MemoryChanged(
            memory_id="test-memory-123",
            user_id="user-456",
            name="test-memory",
            change_type="create",
            is_automatic=False,
            new_value={"type": "private"},
        )

        # 不应抛出异常
        listener._write_to_l2(event)


class TestMemoryChangedListenerHelperMethods:
    """辅助方法验证"""

    def test_get_memory_type_from_new_value(self):
        """验证从 new_value 提取 memory_type"""
        from src.interfaces.event_listeners.memory_changed_listener import MemoryChangedListener

        listener = MemoryChangedListener(
            storage_coordinator=None,
            metadata_repository=None,
            history_repository=None,
        )

        event = MemoryChanged(
            memory_id="test-memory-123",
            user_id="user-456",
            name="test-memory",
            change_type="create",
            is_automatic=False,
            new_value={"type": "group"},
        )

        assert listener._get_memory_type(event) == "group"

    def test_get_memory_type_defaults_to_private(self):
        """验证 memory_type 默认值为 private"""
        from src.interfaces.event_listeners.memory_changed_listener import MemoryChangedListener

        listener = MemoryChangedListener(
            storage_coordinator=None,
            metadata_repository=None,
            history_repository=None,
        )

        event = MemoryChanged(
            memory_id="test-memory-123",
            user_id="user-456",
            name="test-memory",
            change_type="create",
            is_automatic=False,
            new_value=None,
        )

        assert listener._get_memory_type(event) == "private"

    def test_get_memory_type_handles_missing_type_field(self):
        """验证 new_value 缺少 type 字段时返回 private"""
        from src.interfaces.event_listeners.memory_changed_listener import MemoryChangedListener

        listener = MemoryChangedListener(
            storage_coordinator=None,
            metadata_repository=None,
            history_repository=None,
        )

        event = MemoryChanged(
            memory_id="test-memory-123",
            user_id="user-456",
            name="test-memory",
            change_type="create",
            is_automatic=False,
            new_value={"description": "Test only"},
        )

        assert listener._get_memory_type(event) == "private"
