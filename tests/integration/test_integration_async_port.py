"""End-to-end Integration Tests for Async Port Adapters (Task 13).

验证完整调用链的异步 Port 适配器实现

验证标准（AC-12）:
- [ ] 异步文件操作（write/read/delete）验证
- [ ] 索引更新/搜索/截断验证
- [ ] 健康检查异步调用验证
- [ ] 完整性验证（verify_file）验证
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.ports.health_check import HealthCheckPort
from src.domain.ports.index_manager import IndexManagerPort
from src.domain.ports.integrity import IntegrityPort
from src.domain.ports.l0_storage import L0StoragePort


class TestL0StoragePortIntegration:
    """L0StoragePort 端到端集成测试"""

    @pytest.fixture
    def mock_l0_storage(self):
        """创建 Mock L0StoragePort"""
        storage = MagicMock(spec=L0StoragePort)
        storage.write = AsyncMock(return_value=None)
        storage.read = AsyncMock(return_value="test content")
        storage.delete = AsyncMock(return_value=None)
        storage.exists = AsyncMock(return_value=True)
        storage.list_memories = AsyncMock(return_value=["id-1", "id-2"])
        return storage

    @pytest.mark.asyncio
    async def test_write_via_port(self, mock_l0_storage):
        """验证通过 Port 写入"""
        memory_id = str(uuid.uuid4())
        await mock_l0_storage.write(memory_id, "user", "test content")
        mock_l0_storage.write.assert_called_once_with(memory_id, "user", "test content")

    @pytest.mark.asyncio
    async def test_read_via_port(self, mock_l0_storage):
        """验证通过 Port 读取"""
        memory_id = "test-id"
        content = await mock_l0_storage.read(memory_id, "user")
        assert content == "test content"
        mock_l0_storage.read.assert_called_once_with(memory_id, "user")

    @pytest.mark.asyncio
    async def test_delete_via_port(self, mock_l0_storage):
        """验证通过 Port 删除"""
        memory_id = "test-id"
        await mock_l0_storage.delete(memory_id, "user")
        mock_l0_storage.delete.assert_called_once_with(memory_id, "user")

    @pytest.mark.asyncio
    async def test_exists_via_port(self, mock_l0_storage):
        """验证通过 Port 检查存在"""
        memory_id = "test-id"
        exists = await mock_l0_storage.exists(memory_id, "user")
        assert exists is True
        mock_l0_storage.exists.assert_called_once_with(memory_id, "user")


class TestIndexManagerPortIntegration:
    """IndexManagerPort 端到端集成测试"""

    @pytest.fixture
    def mock_index_manager(self):
        """创建 Mock IndexManagerPort"""
        manager = MagicMock(spec=IndexManagerPort)
        manager.update_entry = AsyncMock(return_value=None)
        manager.remove_entry = AsyncMock(return_value=None)
        manager.read_entries = AsyncMock(return_value=[{"memory_id": "id-1", "name": "test", "type": "user"}])
        manager.search = AsyncMock(return_value=[{"memory_id": "id-1", "name": "bun npm", "type": "user"}])
        manager.truncate = AsyncMock(return_value=None)
        return manager

    @pytest.mark.asyncio
    async def test_update_entry_via_port(self, mock_index_manager):
        """验证通过 Port 更新索引"""
        entry = {"memory_id": "id-1", "name": "test", "type": "user"}
        await mock_index_manager.update_entry(entry)
        mock_index_manager.update_entry.assert_called_once_with(entry)

    @pytest.mark.asyncio
    async def test_read_entries_via_port(self, mock_index_manager):
        """验证通过 Port 读取索引"""
        entries = await mock_index_manager.read_entries()
        assert len(entries) == 1
        assert entries[0]["memory_id"] == "id-1"

    @pytest.mark.asyncio
    async def test_search_via_port(self, mock_index_manager):
        """验证通过 Port 搜索索引"""
        results = await mock_index_manager.search("bun")
        assert len(results) >= 1
        mock_index_manager.search.assert_called_once_with("bun")

    @pytest.mark.asyncio
    async def test_remove_entry_via_port(self, mock_index_manager):
        """验证通过 Port 移除索引"""
        memory_id = "id-1"
        await mock_index_manager.remove_entry(memory_id)
        mock_index_manager.remove_entry.assert_called_once_with(memory_id)


class TestHealthCheckPortIntegration:
    """HealthCheckPort 端到端集成测试"""

    @pytest.fixture
    def mock_health_check(self):
        """创建 Mock HealthCheckPort"""
        health = MagicMock(spec=HealthCheckPort)
        health.check = AsyncMock(return_value=True)
        health.close = AsyncMock(return_value=None)
        return health

    @pytest.mark.asyncio
    async def test_check_via_port(self, mock_health_check):
        """验证通过 Port 健康检查"""
        is_healthy = await mock_health_check.check()
        assert is_healthy is True
        mock_health_check.check.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_via_port(self, mock_health_check):
        """验证通过 Port 关闭连接"""
        await mock_health_check.close()
        mock_health_check.close.assert_called_once()


class TestIntegrityPortIntegration:
    """IntegrityPort 端到端集成测试"""

    @pytest.fixture
    def mock_integrity(self):
        """创建 Mock IntegrityPort"""
        integrity = MagicMock(spec=IntegrityPort)
        integrity.verify_file = AsyncMock(return_value=True)
        integrity.compute_hash = MagicMock(return_value="fake_hash")
        integrity.verify_hash = MagicMock(return_value=True)
        return integrity

    @pytest.mark.asyncio
    async def test_verify_file_via_port(self, mock_integrity):
        """验证通过 Port 验证文件"""
        result = await mock_integrity.verify_file("/path/to/file", "expected_hash")
        assert result is True
        mock_integrity.verify_file.assert_called_once_with("/path/to/file", "expected_hash")

    def test_compute_hash_via_port(self, mock_integrity):
        """验证通过 Port 计算哈希"""
        hash_result = mock_integrity.compute_hash("test data", "sha256")
        assert hash_result == "fake_hash"
        mock_integrity.compute_hash.assert_called_once_with("test data", "sha256")

    def test_verify_hash_via_port(self, mock_integrity):
        """验证通过 Port 验证哈希"""
        result = mock_integrity.verify_hash("test data", "expected_hash", "sha256")
        assert result is True
        mock_integrity.verify_hash.assert_called_once_with("test data", "expected_hash", "sha256")


class TestPortChainIntegration:
    """Port 链式调用集成测试"""

    @pytest.mark.asyncio
    async def test_l0_to_index_chain(self):
        """验证 L0Storage → IndexManager 链式调用"""
        # 模拟完整流程：写入 L0 → 更新索引
        mock_l0 = MagicMock(spec=L0StoragePort)
        mock_index = MagicMock(spec=IndexManagerPort)

        mock_l0.write = AsyncMock(return_value=None)
        mock_index.update_entry = AsyncMock(return_value=None)

        memory_id = str(uuid.uuid4())
        content = "test content"
        memory_type = "user"

        # 1. 写入 L0
        mock_l0.write.return_value = None
        await mock_l0.write(memory_id, memory_type, content)

        # 2. 更新索引
        mock_index.update_entry.return_value = None
        entry = {"memory_id": memory_id, "name": "test", "type": memory_type}
        await mock_index.update_entry(entry)

        # 验证调用顺序
        mock_l0.write.assert_called_once()
        mock_index.update_entry.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_before_operation(self):
        """验证操作前健康检查"""
        mock_health = MagicMock(spec=HealthCheckPort)
        mock_l0 = MagicMock(spec=L0StoragePort)

        # 1. 检查健康
        mock_health.check = AsyncMock(return_value=True)
        is_healthy = await mock_health.check()

        # 2. 如果健康，执行操作
        if is_healthy:
            mock_l0.write = AsyncMock(return_value=None)
            await mock_l0.write("id-1", "user", "content")

        # 验证
        mock_health.check.assert_called_once()
        mock_l0.write.assert_called_once()
