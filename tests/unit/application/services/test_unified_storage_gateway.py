"""UnifiedStorageGateway 实现测试。

验证 UnifiedStorageGateway 实现了 UnifiedStoragePort 接口。
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest


class TestUnifiedStorageGatewayUnifiedStoragePortCompliance:
    """验证 UnifiedStorageGateway 实现了 UnifiedStoragePort 接口。"""

    def test_gateway_implements_unified_storage_port(self) -> None:
        """UnifiedStorageGateway 应实现 UnifiedStoragePort。"""
        from src.application.services.unified_storage_gateway import UnifiedStorageGateway
        from src.domain.ports.unified_storage import UnifiedStoragePort

        mock_l0 = MagicMock()
        mock_l1 = MagicMock()
        mock_l2_meta = MagicMock()
        mock_l2_hist = MagicMock()

        gateway = UnifiedStorageGateway(
            l0_storage=mock_l0,
            l1_cache=mock_l1,
            l2_metadata=mock_l2_meta,
            l2_history=mock_l2_hist,
        )

        assert isinstance(gateway, UnifiedStoragePort)

    def test_gateway_has_all_required_methods(self) -> None:
        """UnifiedStorageGateway 应有 UnifiedStoragePort 的所有方法。"""
        from src.application.services.unified_storage_gateway import UnifiedStorageGateway
        from src.domain.ports.unified_storage import UnifiedStoragePort

        mock_l0 = MagicMock()
        mock_l1 = MagicMock()
        mock_l2_meta = MagicMock()
        mock_l2_hist = MagicMock()

        gateway = UnifiedStorageGateway(
            l0_storage=mock_l0,
            l1_cache=mock_l1,
            l2_metadata=mock_l2_meta,
            l2_history=mock_l2_hist,
        )

        for method_name in ["save", "read", "delete", "exists"]:
            assert hasattr(gateway, method_name)
            assert hasattr(UnifiedStoragePort, method_name)

    def test_all_methods_are_async(self) -> None:
        """所有方法应为 async def。"""
        from src.application.services.unified_storage_gateway import UnifiedStorageGateway

        mock_l0 = MagicMock()
        mock_l1 = MagicMock()
        mock_l2_meta = MagicMock()
        mock_l2_hist = MagicMock()

        gateway = UnifiedStorageGateway(
            l0_storage=mock_l0,
            l1_cache=mock_l1,
            l2_metadata=mock_l2_meta,
            l2_history=mock_l2_hist,
        )

        for method_name in ["save", "read", "delete", "exists"]:
            method = getattr(gateway, method_name)
            assert asyncio.iscoroutinefunction(method), f"{method_name} should be async"


class TestUnifiedStorageGatewayBehavior:
    """UnifiedStorageGateway 行为测试。"""

    @pytest.fixture
    def mock_l0_storage(self):
        """创建模拟的 L0 存储。"""
        mock = MagicMock()
        mock.write = AsyncMock(return_value=None)
        mock.read = AsyncMock(return_value="memory content")
        mock.delete = AsyncMock(return_value=True)
        mock.exists = AsyncMock(return_value=True)
        return mock

    @pytest.fixture
    def mock_l1_cache(self):
        """创建模拟的 L1 缓存。"""
        mock = MagicMock()
        mock.get = AsyncMock(return_value=None)
        mock.set = AsyncMock(return_value=True)
        mock.delete = AsyncMock(return_value=True)
        return mock

    @pytest.fixture
    def mock_l2_metadata(self):
        """创建模拟的 L2 元数据仓储。"""
        mock = MagicMock()
        mock.get_by_id = AsyncMock(
            return_value=MagicMock(
                id=UUID("12345678-1234-1234-1234-123456789abc"),
                type="private",
                owner="user123",
                group_id=None,
            )
        )
        mock.save = AsyncMock(return_value=None)
        mock.delete = AsyncMock(return_value=None)
        return mock

    @pytest.fixture
    def mock_l2_history(self):
        """创建模拟的 L2 历史仓储。"""
        mock = MagicMock()
        mock.append = AsyncMock(return_value=None)
        return mock

    @pytest.fixture
    def gateway(self, mock_l0_storage, mock_l1_cache, mock_l2_metadata, mock_l2_history):
        """创建 UnifiedStorageGateway 实例。"""
        from src.application.services.unified_storage_gateway import UnifiedStorageGateway

        return UnifiedStorageGateway(
            l0_storage=mock_l0_storage,
            l1_cache=mock_l1_cache,
            l2_metadata=mock_l2_metadata,
            l2_history=mock_l2_history,
        )

    @pytest.mark.asyncio
    async def test_save_writes_to_l0(self, gateway, mock_l0_storage) -> None:
        """save 应写入 L0 文件系统。"""
        result = await gateway.save(
            memory_id="12345678-1234-1234-1234-123456789abc",
            content="test content",
            memory_type="private",
            owner_id="user123",
            name="test-memory",
        )

        mock_l0_storage.write.assert_called_once()
        # Check that L0_FILE key exists in result (using enum, not string)
        assert any(k.value == "l0_file" for k in result.keys())

    @pytest.mark.asyncio
    async def test_read_with_cache_miss_falls_back_to_l0(self, gateway, mock_l0_storage) -> None:
        """缓存未命中时应回退到 L0。"""
        mock_l0_storage.read.return_value = "memory from L0"

        result = await gateway.read(
            memory_id="12345678-1234-1234-1234-123456789abc",
            memory_type="private",
            owner_id="user123",
            name="test-memory",
            prefer_cache=True,
        )

        assert result == "memory from L0"
        mock_l0_storage.read.assert_called_once()

    @pytest.mark.asyncio
    async def test_read_with_cache_hit_returns_cached(self, gateway, mock_l1_cache, mock_l0_storage) -> None:
        """缓存命中时应直接返回。"""
        mock_l1_cache.get.return_value = "cached content"

        result = await gateway.read(
            memory_id="12345678-1234-1234-1234-123456789abc",
            memory_type="private",
            owner_id="user123",
            name="test-memory",
            prefer_cache=True,
        )

        assert result == "cached content"
        mock_l0_storage.read.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_removes_from_l0(self, gateway, mock_l0_storage) -> None:
        """delete 应从 L0 删除。"""
        result = await gateway.delete(
            memory_id="12345678-1234-1234-1234-123456789abc",
            memory_type="private",
            owner_id="user123",
            name="test-memory",
        )

        mock_l0_storage.delete.assert_called_once()
        assert any(k.value == "l0_file" for k in result.keys())

    @pytest.mark.asyncio
    async def test_exists_checks_l0(self, gateway, mock_l0_storage, mock_l2_metadata) -> None:
        """exists 应检查 L0。"""
        mock_l0_storage.exists.return_value = True

        result = await gateway.exists(
            memory_id="12345678-1234-1234-1234-123456789abc",
            memory_type="private",
            owner_id="user123",
            name="test-memory",
        )

        mock_l0_storage.exists.assert_called_once()
        assert any(k.value == "l0_file" for k in result.keys())


class TestUnifiedStorageGatewayWithOptionalLayers:
    """带有可选 L3-L5 层的 UnifiedStorageGateway 测试。"""

    @pytest.fixture
    def mock_l0_storage(self):
        mock = MagicMock()
        mock.write = AsyncMock(return_value=None)
        mock.read = AsyncMock(return_value="content")
        mock.delete = AsyncMock(return_value=True)
        mock.exists = AsyncMock(return_value=True)
        return mock

    @pytest.fixture
    def mock_l1_cache(self):
        mock = MagicMock()
        mock.get = AsyncMock(return_value=None)
        mock.set = AsyncMock(return_value=True)
        return mock

    @pytest.fixture
    def mock_l2_metadata(self):
        mock = MagicMock()
        mock.get_by_id = AsyncMock(
            return_value=MagicMock(
                id=UUID("12345678-1234-1234-1234-123456789abc"),
                type="private",
                owner="user123",
                group_id=None,
            )
        )
        return mock

    @pytest.fixture
    def mock_l2_history(self):
        return MagicMock()

    @pytest.fixture
    def mock_l3_vector(self):
        mock = MagicMock()
        mock.upsert_points = AsyncMock(return_value=True)
        return mock

    @pytest.fixture
    def mock_l4_object(self):
        mock = MagicMock()
        mock.store = AsyncMock(return_value="version-id")
        return mock

    @pytest.fixture
    def mock_l5_graph(self):
        mock = MagicMock()
        mock.create_entity = AsyncMock(return_value=True)
        return mock

    def test_gateway_accepts_optional_layers(
        self,
        mock_l0_storage,
        mock_l1_cache,
        mock_l2_metadata,
        mock_l2_history,
        mock_l3_vector,
        mock_l4_object,
        mock_l5_graph,
    ) -> None:
        """UnifiedStorageGateway 应接受可选的 L3-L5 层。"""
        from src.application.services.unified_storage_gateway import UnifiedStorageGateway

        gateway = UnifiedStorageGateway(
            l0_storage=mock_l0_storage,
            l1_cache=mock_l1_cache,
            l2_metadata=mock_l2_metadata,
            l2_history=mock_l2_history,
            l3_vector=mock_l3_vector,
            l4_object=mock_l4_object,
            l5_graph=mock_l5_graph,
        )

        assert gateway._l3 is not None
        assert gateway._l4 is not None
        assert gateway._l5 is not None
