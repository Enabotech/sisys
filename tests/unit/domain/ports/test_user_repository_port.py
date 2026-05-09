"""UserRepositoryPort Protocol Interface Tests."""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock
from uuid import UUID

from src.domain.ports.user_repository import UserRepositoryPort


class TestUserRepositoryPortSignature:
    """Structural signature tests — verify async contract."""

    def test_methods_are_async(self) -> None:
        """get_by_username and get_by_id should be async."""
        assert inspect.iscoroutinefunction(UserRepositoryPort.get_by_username), "get_by_username must be async"
        assert inspect.iscoroutinefunction(UserRepositoryPort.get_by_id), "get_by_id must be async"


class TestUserRepositoryPortMockBehavior:
    """Mock behavior tests — verify Protocol contract via spec约束."""

    async def test_mock_get_by_username_verified(self):
        """Mock get_by_username should be verifiable."""
        mock = AsyncMock(spec=UserRepositoryPort)
        mock.get_by_username.return_value = {"user_id": "123", "username": "alice"}

        result = await mock.get_by_username("alice")
        assert result["username"] == "alice"
        mock.get_by_username.assert_called_once_with("alice")

    async def test_mock_get_by_id_verified(self):
        """Mock get_by_id should be verifiable."""
        mock = AsyncMock(spec=UserRepositoryPort)
        user_id = UUID("550e8400-e29b-41d4-a716-446655440000")
        mock.get_by_id.return_value = {"user_id": str(user_id), "username": "alice"}

        result = await mock.get_by_id(user_id)
        assert result["username"] == "alice"
        mock.get_by_id.assert_called_once_with(user_id)
