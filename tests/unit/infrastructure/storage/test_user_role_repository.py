"""Tests for UserRoleRepository."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.infrastructure.storage.postgresql.user_role_repository import UserRoleRepository


class TestUserRoleRepository:
    """Test UserRoleRepository implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session = AsyncMock()
        self.repository = UserRoleRepository(self.mock_session)

    @pytest.mark.asyncio
    async def test_assign_role_user_not_found(self):
        """assign_role returns False when user doesn't exist."""
        self.mock_session.get.return_value = None  # User not found

        result = await self.repository.assign_role(uuid4(), uuid4())

        assert result is False

    @pytest.mark.asyncio
    async def test_assign_role_role_not_found(self):
        """assign_role returns False when role doesn't exist."""
        mock_user = MagicMock()
        mock_user.id = uuid4()
        # First get() returns user, second returns None (role not found)
        self.mock_session.get.side_effect = [mock_user, None]

        result = await self.repository.assign_role(mock_user.id, uuid4())

        assert result is False

    @pytest.mark.asyncio
    async def test_assign_role_success(self):
        """assign_role returns True when both user and role exist."""
        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_role = MagicMock()
        mock_role.id = uuid4()
        self.mock_session.get.side_effect = [mock_user, mock_role]
        self.mock_session.execute = AsyncMock()
        self.mock_session.flush = AsyncMock()

        result = await self.repository.assign_role(mock_user.id, mock_role.id)

        assert result is True

    @pytest.mark.asyncio
    async def test_revoke_role_success(self):
        """revoke_role returns True when delete succeeds."""
        mock_result = MagicMock()
        mock_result.rowcount = 1  # row deleted
        mock_execute = AsyncMock(return_value=mock_result)
        self.mock_session.execute = mock_execute
        self.mock_session.flush = AsyncMock()

        result = await self.repository.revoke_role(uuid4(), uuid4())

        assert result is True

    @pytest.mark.asyncio
    async def test_revoke_role_not_found(self):
        """revoke_role returns False when no association exists."""
        mock_result = MagicMock()
        mock_result.rowcount = 0  # no row deleted
        mock_execute = AsyncMock(return_value=mock_result)
        self.mock_session.execute = mock_execute
        self.mock_session.flush = AsyncMock()

        result = await self.repository.revoke_role(uuid4(), uuid4())

        assert result is False

    @pytest.mark.asyncio
    async def test_get_role_users_returns_user_ids(self):
        """get_role_users returns list of user UUIDs."""
        user_id_1 = uuid4()
        user_id_2 = uuid4()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(user_id_1,), (user_id_2,)]
        mock_execute = AsyncMock(return_value=mock_result)
        self.mock_session.execute = mock_execute

        result = await self.repository.get_role_users(uuid4())

        assert len(result) == 2
        assert user_id_1 in result
        assert user_id_2 in result

    @pytest.mark.asyncio
    async def test_get_role_users_empty_when_no_users(self):
        """get_role_users returns empty list when no users have role."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_execute = AsyncMock(return_value=mock_result)
        self.mock_session.execute = mock_execute

        result = await self.repository.get_role_users(uuid4())

        assert result == []

    @pytest.mark.asyncio
    async def test_get_user_roles_returns_role_list(self):
        """get_user_roles returns list of Role entities."""
        role_id_1 = uuid4()
        role_id_2 = uuid4()
        mock_role_1 = MagicMock()
        mock_role_1.id = role_id_1
        mock_role_1.name = "admin"
        mock_role_1.description = "Admin role"
        mock_role_1.is_system_reserved = True
        mock_role_1.is_active = True
        mock_role_1.created_at = datetime.now(UTC)
        mock_role_1.updated_at = None

        mock_role_2 = MagicMock()
        mock_role_2.id = role_id_2
        mock_role_2.name = "user"
        mock_role_2.description = "User role"
        mock_role_2.is_system_reserved = False
        mock_role_2.is_active = True
        mock_role_2.created_at = datetime.now(UTC)
        mock_role_2.updated_at = None

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_role_1, mock_role_2]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_execute = AsyncMock(return_value=mock_result)
        self.mock_session.execute = mock_execute

        result = await self.repository.get_user_roles(uuid4())

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_user_roles_empty_when_no_roles(self):
        """get_user_roles returns empty list when user has no roles."""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_execute = AsyncMock(return_value=mock_result)
        self.mock_session.execute = mock_execute

        result = await self.repository.get_user_roles(uuid4())

        assert result == []
