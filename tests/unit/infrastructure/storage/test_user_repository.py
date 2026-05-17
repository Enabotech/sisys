"""UserRepository 单元测试。"""

from __future__ import annotations

import uuid
from unittest import mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.user import User
from src.infrastructure.storage.postgresql.repository.user_repository import UserRepository
from src.infrastructure.storage.postgresql.session_context import reset_session, set_session


def _make_user_model_mock(**overrides):
    """Create a mock that mimics UserModel fields for _to_entity conversion."""
    defaults = {
        "id": uuid.uuid4(),
        "username": "testuser",
        "email": "test@example.com",
        "hashed_password": "$2b$12$hash",
        "is_active": True,
        "is_locked": False,
        "created_at": None,
        "updated_at": None,
    }
    defaults.update(overrides)
    return mock.Mock(**defaults)


@pytest.fixture
def mock_session():
    return mock.AsyncMock(spec=AsyncSession)


@pytest.fixture
def repository(mock_session):
    token = set_session(mock_session)
    repo = UserRepository()
    yield repo
    reset_session(token)


class TestUserRepository:
    """UserRepository 测试。"""

    @pytest.mark.asyncio
    async def test_get_by_username(self, repository, mock_session):
        """测试根据用户名获取用户。"""
        model = _make_user_model_mock()
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_username("testuser")

        assert isinstance(result, User)
        assert result.id == model.id
        assert result.username == model.username
        assert result.email == model.email

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
        model = _make_user_model_mock()
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_email("test@example.com")

        assert isinstance(result, User)
        assert result.email == model.email
