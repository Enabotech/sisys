"""UnifiedStorageGateway RBAC 测试

验证 UnifiedStorageGateway 的权限校验逻辑（AC-2: Private/Group 记忆分离）
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest


class TestUnifiedStorageGatewayRBAC:
    """UnifiedStorageGateway RBAC 校验测试"""

    @pytest.fixture
    def mock_l0_storage(self):
        mock = MagicMock()
        mock.write = AsyncMock(return_value=True)
        mock.read = AsyncMock(return_value="memory content")
        mock.delete = AsyncMock(return_value=True)
        mock.exists = AsyncMock(return_value=True)
        return mock

    @pytest.fixture
    def mock_l1_cache(self):
        mock = MagicMock()
        mock.get = AsyncMock(return_value=None)
        mock.set = AsyncMock(return_value=True)
        mock.delete = AsyncMock(return_value=True)
        return mock

    @pytest.fixture
    def mock_l2_metadata(self):
        return MagicMock()

    @pytest.fixture
    def mock_l2_history(self):
        return MagicMock()

    @pytest.fixture
    def mock_l2_group_member(self):
        mock = MagicMock()
        mock.is_group_member = AsyncMock(return_value=False)
        mock.is_group_admin = AsyncMock(return_value=False)
        return mock

    @pytest.fixture
    def gateway(self, mock_l0_storage, mock_l1_cache, mock_l2_metadata, mock_l2_history, mock_l2_group_member):
        from src.application.services.unified_storage_gateway import UnifiedStorageGateway

        return UnifiedStorageGateway(
            l0_storage=mock_l0_storage,
            memory_cache=mock_l1_cache,
            l2_metadata=mock_l2_metadata,
            l2_history=mock_l2_history,
            l2_group_member=mock_l2_group_member,
        )

    async def test_private_memory_owner_can_read(self, gateway, mock_l2_metadata):
        """Private 记忆：owner 可以读取"""
        memory_id = UUID("12345678-1234-1234-1234-123456789abc")
        owner_id = "user123"

        # Private 记忆：group_id=None
        mock_metadata = MagicMock()
        mock_metadata.owner = owner_id
        mock_metadata.group_id = None
        mock_l2_metadata.get_by_id = AsyncMock(return_value=mock_metadata)

        # 验证：owner 可以读取
        result = await gateway.read(
            memory_id=str(memory_id),
            memory_type="private",
            owner_id=owner_id,
            name="test-memory",
            prefer_cache=False,
        )

        assert result == "memory content"

    async def test_private_memory_non_owner_cannot_read(self, gateway, mock_l2_metadata, mock_l0_storage):
        """Private 记忆：非 owner 不能读取"""
        memory_id = UUID("12345678-1234-1234-1234-123456789abc")
        owner_id = "user123"
        other_user = "user456"

        # Private 记忆：group_id=None
        mock_metadata = MagicMock()
        mock_metadata.owner = owner_id
        mock_metadata.group_id = None
        mock_l2_metadata.get_by_id = AsyncMock(return_value=mock_metadata)
        mock_l0_storage.read.return_value = "secret content"

        # 验证：非 owner 不能读取
        result = await gateway.read(
            memory_id=str(memory_id),
            memory_type="private",
            owner_id=other_user,  # 不是 owner
            name="test-memory",
            prefer_cache=False,
        )

        assert result is None

    async def test_group_memory_owner_can_read(self, gateway, mock_l2_metadata):
        """Group 记忆：owner 可以读取"""
        memory_id = UUID("12345678-1234-1234-1234-123456789abc")
        owner_id = "user123"
        group_id = "group-abc"

        # Group 记忆：group_id 不为空
        mock_metadata = MagicMock()
        mock_metadata.owner = owner_id
        mock_metadata.group_id = group_id
        mock_l2_metadata.get_by_id = AsyncMock(return_value=mock_metadata)

        # 验证：owner 可以读取
        result = await gateway.read(
            memory_id=str(memory_id),
            memory_type="group",
            owner_id=owner_id,
            name="test-memory",
            prefer_cache=False,
        )

        assert result == "memory content"

    async def test_group_memory_member_can_read(self, gateway, mock_l2_metadata, mock_l2_group_member):
        """Group 记忆：group 成员可以读取（非 owner）"""
        memory_id = UUID("12345678-1234-1234-1234-123456789abc")
        owner_id = "user123"
        group_member = "user456"
        group_id = "group-abc"

        # Group 记忆：group_id 不为空
        mock_metadata = MagicMock()
        mock_metadata.owner = owner_id
        mock_metadata.group_id = group_id
        mock_l2_metadata.get_by_id = AsyncMock(return_value=mock_metadata)

        # 模拟 group 成员验证通过
        mock_l2_group_member.is_group_member = AsyncMock(return_value=True)

        result = await gateway.read(
            memory_id=str(memory_id),
            memory_type="group",
            owner_id=group_member,  # 不是 owner，但是 group 成员
            name="test-memory",
            prefer_cache=False,
        )

        # 验证：group 成员可以读取
        assert result == "memory content"

    async def test_group_memory_non_member_cannot_read(self, gateway, mock_l2_metadata, mock_l0_storage, mock_l2_group_member):
        """Group 记忆：非 group 成员不能读取"""
        memory_id = UUID("12345678-1234-1234-1234-123456789abc")
        owner_id = "user123"
        non_member = "user789"
        group_id = "group-abc"

        # Group 记忆：group_id 不为空
        mock_metadata = MagicMock()
        mock_metadata.owner = owner_id
        mock_metadata.group_id = group_id
        mock_l2_metadata.get_by_id = AsyncMock(return_value=mock_metadata)
        mock_l0_storage.read.return_value = "group content"

        # 模拟 group 成员验证失败
        mock_l2_group_member.is_group_member = AsyncMock(return_value=False)

        # 验证：非 group 成员不能读取
        result = await gateway.read(
            memory_id=str(memory_id),
            memory_type="group",
            owner_id=non_member,  # 不是 owner，也不是 group 成员
            name="test-memory",
            prefer_cache=False,
        )

        assert result is None, "non-group-member should not be able to read group memory"
