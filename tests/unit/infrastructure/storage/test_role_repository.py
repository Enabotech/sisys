"""RoleRepository 单元测试。"""

from __future__ import annotations

from unittest import mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.storage.postgresql.role_repository import RoleRepository


@pytest.fixture
def mock_session():
    return mock.AsyncMock(spec=AsyncSession)


@pytest.fixture
def repository(mock_session):
    return RoleRepository(mock_session)


class TestRoleRepository:
    """RoleRepository 测试。"""

    @pytest.mark.asyncio
    async def test_get_by_name(self, repository, mock_session):
        """测试根据名称获取角色。"""
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = None  # Role not found
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_name("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_permissions_for_role(self, repository, mock_session):
        """测试获取角色的权限列表。"""
        permissions = [mock.Mock(), mock.Mock()]
        mock_scalars = mock.Mock()
        mock_scalars.all.return_value = permissions
        mock_result = mock.Mock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await repository.get_permissions_for_role("role-id")

        assert len(result) == 2
