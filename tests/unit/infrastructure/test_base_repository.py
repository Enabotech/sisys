"""BaseRepository 单元测试。

测试 CRUD 操作和事务回滚。
"""

from __future__ import annotations

from unittest import mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.storage.postgresql.base_repository import BaseRepository
from src.infrastructure.storage.postgresql.models import UserModel


@pytest.fixture
def mock_session():
    """创建模拟数据库会话。"""
    return mock.AsyncMock(spec=AsyncSession)


@pytest.fixture
def repository(mock_session):
    """创建 BaseRepository 实例。"""
    return BaseRepository(UserModel, mock_session)


class TestBaseRepository:
    """BaseRepository 测试。"""

    @pytest.mark.asyncio
    async def test_get_by_id_exists(self, repository, mock_session):
        """测试获取存在的实体。"""
        user = mock.Mock()
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = user
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_id("test-id")

        assert result == user
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repository, mock_session):
        """测试获取不存在的实体。"""
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_id("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_save_insert(self, repository, mock_session):
        """测试插入实体。"""
        user = mock.Mock()
        mock_session.flush = mock.AsyncMock()
        mock_session.refresh = mock.AsyncMock()

        result = await repository.save(user)

        mock_session.add.assert_called_once_with(user)
        mock_session.flush.assert_called_once()
        mock_session.refresh.assert_called_once_with(user)
        assert result == user

    @pytest.mark.asyncio
    async def test_delete_exists(self, repository, mock_session):
        """测试删除存在的实体。"""
        user = mock.Mock()
        mock_session.execute = mock.AsyncMock()
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = user
        mock_session.execute.return_value = mock_result
        mock_session.delete = mock.AsyncMock()
        mock_session.flush = mock.AsyncMock()

        await repository.delete("test-id")

        mock_session.delete.assert_called_once_with(user)
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_not_found(self, repository, mock_session):
        """测试删除不存在的实体（无操作）。"""
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await repository.delete("nonexistent")

        mock_session.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_all(self, repository, mock_session):
        """测试获取实体列表。"""
        users = [mock.Mock(), mock.Mock()]
        mock_scalars = mock.Mock()
        mock_scalars.all.return_value = users
        mock_result = mock.Mock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await repository.list_all(skip=0, limit=10)

        assert result == users
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_count(self, repository, mock_session):
        """测试获取实体总数。"""
        mock_result = mock.Mock()
        mock_result.scalar.return_value = 5
        mock_session.execute.return_value = mock_result

        result = await repository.count()

        assert result == 5
