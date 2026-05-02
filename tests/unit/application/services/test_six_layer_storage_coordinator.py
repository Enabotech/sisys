"""Tests for SixLayerStorageCoordinator.

RED PHASE: 验证 SixLayerStorageCoordinator 六层存储协同功能。
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from src.application.services.six_layer_storage_coordinator import (
    SixLayerStorageCoordinator,
)


class TestSixLayerStorageCoordinatorInit:
    """SixLayerStorageCoordinator 初始化验证"""

    def test_init_with_dependencies(self):
        """验证使用依赖初始化"""
        mock_cache = MagicMock()
        mock_l2_repo = MagicMock()
        mock_l3_store = MagicMock()
        mock_l4_store = MagicMock()
        mock_l5_store = MagicMock()

        coordinator = SixLayerStorageCoordinator(
            l1_cache=mock_cache,
            l2_repository=mock_l2_repo,
            l3_vector_store=mock_l3_store,
            l4_object_store=mock_l4_store,
            l5_graph_store=mock_l5_store,
        )

        assert coordinator._l1_cache is not None
        assert coordinator._l2_repository is not None


class TestSixLayerStorageCoordinatorSave:
    """SixLayerStorageCoordinator save 方法验证"""

    def test_save_to_l1_l1_cache(self):
        """验证保存到 L1 Redis 缓存"""
        mock_cache = MagicMock()
        mock_l2_repo = MagicMock()
        mock_l3_store = MagicMock()
        mock_l4_store = MagicMock()
        mock_l5_store = MagicMock()

        coordinator = SixLayerStorageCoordinator(
            l1_cache=mock_cache,
            l2_repository=mock_l2_repo,
            l3_vector_store=mock_l3_store,
            l4_object_store=mock_l4_store,
            l5_graph_store=mock_l5_store,
        )

        memory_id = str(uuid.uuid4())
        owner_id = "user-123"
        name = "test-memory"
        content = "test memory content"
        memory_type = "private"

        coordinator.save(memory_id, content, layer="L1", memory_type=memory_type, owner_id=owner_id, name=name)

        mock_cache.set.assert_called_once_with(memory_type, owner_id, name, content)


class TestSixLayerStorageCoordinatorRead:
    """SixLayerStorageCoordinator read 方法验证"""

    def test_read_from_l1_l1_cache(self):
        """验证从 L1 Redis 缓存读取"""
        mock_cache = MagicMock()
        mock_cache.get.return_value = "cached content"

        mock_l2_repo = MagicMock()
        mock_l3_store = MagicMock()
        mock_l4_store = MagicMock()
        mock_l5_store = MagicMock()

        coordinator = SixLayerStorageCoordinator(
            l1_cache=mock_cache,
            l2_repository=mock_l2_repo,
            l3_vector_store=mock_l3_store,
            l4_object_store=mock_l4_store,
            l5_graph_store=mock_l5_store,
        )

        memory_id = str(uuid.uuid4())
        owner_id = "user-123"
        name = "test-memory"
        result = coordinator.read(memory_id, layer="L1", memory_type="private", owner_id=owner_id, name=name)

        assert result == "cached content"
        mock_cache.get.assert_called_once_with("private", owner_id, name)


class TestSixLayerStorageCoordinatorInvalidate:
    """SixLayerStorageCoordinator invalidate 方法验证"""

    def test_invalidate_l1_cache(self):
        """验证失效 L1 缓存"""
        mock_cache = MagicMock()
        mock_l2_repo = MagicMock()
        mock_l3_store = MagicMock()
        mock_l4_store = MagicMock()
        mock_l5_store = MagicMock()

        coordinator = SixLayerStorageCoordinator(
            l1_cache=mock_cache,
            l2_repository=mock_l2_repo,
            l3_vector_store=mock_l3_store,
            l4_object_store=mock_l4_store,
            l5_graph_store=mock_l5_store,
        )

        memory_id = str(uuid.uuid4())
        owner_id = "user-123"
        name = "test-memory"
        coordinator.invalidate(memory_id, layer="L1", memory_type="private", owner_id=owner_id, name=name)

        mock_cache.delete.assert_called_once_with("private", owner_id, name)


class TestSixLayerStorageCoordinatorLayerStatus:
    """SixLayerStorageCoordinator get_layer_status 方法验证"""

    def test_get_layer_status_all_layers(self):
        """验证获取所有层状态"""
        mock_cache = MagicMock()
        mock_l2_repo = MagicMock()
        mock_l3_store = MagicMock()
        mock_l4_store = MagicMock()
        mock_l5_store = MagicMock()

        coordinator = SixLayerStorageCoordinator(
            l1_cache=mock_cache,
            l2_repository=mock_l2_repo,
            l3_vector_store=mock_l3_store,
            l4_object_store=mock_l4_store,
            l5_graph_store=mock_l5_store,
        )

        memory_id = str(uuid.uuid4())
        status = coordinator.get_layer_status(memory_id, memory_type="private")

        assert "L0" in status
        assert "L1" in status
        assert "L2" in status
