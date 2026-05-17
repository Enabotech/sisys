"""PermissionRepository 单元测试"""

from __future__ import annotations

import uuid
from unittest import mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.permission import Permission
from src.infrastructure.storage.postgresql.repository.permission_repository import PermissionRepository
from src.infrastructure.storage.postgresql.session_context import reset_session, set_session


def _make_permission_model_mock(**overrides):
    """Create a mock that mimics PermissionModel fields for _to_entity conversion."""
    defaults = {
        "id": uuid.uuid4(),
        "name": "read:document",
        "resource": "document",
        "action": "read",
        "created_at": None,
    }
    defaults.update(overrides)
    return mock.Mock(**defaults)


@pytest.fixture
def mock_session():
    return mock.AsyncMock(spec=AsyncSession)


@pytest.fixture
def repository(mock_session):
    token = set_session(mock_session)
    repo = PermissionRepository()
    yield repo
    reset_session(token)


class TestPermissionRepository:
    """PermissionRepository 测试"""

    @pytest.mark.asyncio
    async def test_get_by_name(self, repository, mock_session):
        """测试根据名称获取权限"""
        model = _make_permission_model_mock()
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_name("read:document")

        assert isinstance(result, Permission)
        assert result.id == model.id
        assert result.name == model.name

    @pytest.mark.asyncio
    async def test_get_by_name_not_found(self, repository, mock_session):
        """测试根据名称获取不存在的权限"""
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_name("nonexistent")

        assert result is None
