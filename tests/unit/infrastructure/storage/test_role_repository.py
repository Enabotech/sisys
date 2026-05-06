"""RoleRepository 单元测试。"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest import mock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.use_cases.role_management import RoleAlreadyExistsError, RoleNotFoundError
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
    async def test_get_by_name_not_found(self, repository, mock_session):
        """测试根据名称获取不存在的角色。"""
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_name("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_name_found(self, repository, mock_session):
        """测试根据名称获取存在的角色。"""
        role_id = uuid4()
        mock_model = mock.Mock()
        mock_model.id = role_id
        mock_model.name = "admin"
        mock_model.description = "Admin role"
        mock_model.is_system_reserved = False
        mock_model.is_active = True
        mock_model.created_at = datetime.now(UTC)
        mock_model.updated_at = None

        # First execute call returns model (scalar_one_or_none), second returns permissions
        mock_model_result = mock.Mock()
        mock_model_result.scalar_one_or_none.return_value = mock_model

        mock_perm_result = mock.Mock()
        mock_perm_result.fetchall.return_value = [("doc:read",)]

        mock_session.execute.side_effect = [mock_model_result, mock_perm_result]

        result = await repository.get_by_name("admin")

        assert result is not None
        assert result.name == "admin"
        assert result.id == role_id

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

    @pytest.mark.asyncio
    async def test_delete_role_not_found(self, repository, mock_session):
        """测试删除不存在的角色抛出异常。"""
        mock_session.get.return_value = None

        with pytest.raises(RoleNotFoundError):
            await repository.delete(uuid4())

    @pytest.mark.asyncio
    async def test_delete_role_success(self, repository, mock_session):
        """测试删除存在的角色。"""
        mock_model = mock.Mock()
        mock_session.get.return_value = mock_model

        result = await repository.delete(uuid4())

        assert result is True
        mock_session.delete.assert_called_once_with(mock_model)
        mock_session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_role_integrity_error(self, repository, mock_session):
        """测试保存角色时唯一约束违反。"""
        from src.domain.entities.role import Role

        role = Role(
            id=None,
            name="existingrole",
            description="Existing role",
            permissions=(),
            is_system_reserved=False,
            is_active=True,
            created_at=None,
            updated_at=None,
        )

        mock_session.flush.side_effect = IntegrityError(None, None, None)

        with pytest.raises(RoleAlreadyExistsError):
            await repository.save(role)

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repository, mock_session):
        """测试根据 ID 获取不存在的角色。"""
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_id(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_found(self, repository, mock_session):
        """测试根据 ID 获取存在的角色。"""
        role_id = uuid4()
        mock_model = mock.Mock()
        mock_model.id = role_id
        mock_model.name = "admin"
        mock_model.description = "Admin role"
        mock_model.is_system_reserved = False
        mock_model.is_active = True
        mock_model.created_at = datetime.now(UTC)
        mock_model.updated_at = None

        mock_model_result = mock.Mock()
        mock_model_result.scalar_one_or_none.return_value = mock_model

        mock_perm_result = mock.Mock()
        mock_perm_result.fetchall.return_value = []

        mock_session.execute.side_effect = [mock_model_result, mock_perm_result]

        result = await repository.get_by_id(role_id)

        assert result is not None
        assert result.name == "admin"
        assert result.id == role_id

    @pytest.mark.asyncio
    async def test_list_all_empty(self, repository, mock_session):
        """测试列出所有角色为空。"""
        mock_scalars = mock.Mock()
        mock_scalars.all.return_value = []
        mock_result = mock.Mock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await repository.list_all()

        assert result == []

    @pytest.mark.asyncio
    async def test_list_all_with_roles(self, repository, mock_session):
        """测试列出所有角色。"""
        role_id = uuid4()
        mock_model = mock.Mock()
        mock_model.id = role_id
        mock_model.name = "admin"
        mock_model.description = "Admin role"
        mock_model.is_system_reserved = False
        mock_model.is_active = True
        mock_model.created_at = datetime.now(UTC)
        mock_model.updated_at = None

        mock_scalars = mock.Mock()
        mock_scalars.all.return_value = [mock_model]
        mock_list_result = mock.Mock()
        mock_list_result.scalars.return_value = mock_scalars

        mock_perm_result = mock.Mock()
        mock_perm_result.fetchall.return_value = [("doc:read",)]

        mock_session.execute.side_effect = [mock_list_result, mock_perm_result]

        result = await repository.list_all()

        assert len(result) == 1
        assert result[0].name == "admin"
        assert result[0].id == role_id
