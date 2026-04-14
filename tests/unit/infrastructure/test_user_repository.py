"""UserRepository 单元测试。"""

from __future__ import annotations

from unittest import mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.storage.postgresql.user_repository import UserRepository


@pytest.fixture
def mock_session():
    return mock.AsyncMock(spec=AsyncSession)


@pytest.fixture
def repository(mock_session):
    return UserRepository(mock_session)


class TestUserRepository:
    """UserRepository 测试。"""

    @pytest.mark.asyncio
    async def test_get_by_username(self, repository, mock_session):
        """测试根据用户名获取用户。"""
        user = mock.Mock()
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = user
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_username("testuser")

        assert result == user

    @pytest.mark.asyncio
    async def test_get_by_username_not_found(self, repository, mock_session):
        """测试根据用户名获取不存在的用户。"""
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_username("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_email(self, repository, mock_session):
        """测试根据邮箱获取用户。"""
        user = mock.Mock()
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = user
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_email("test@example.com")

        assert result == user
