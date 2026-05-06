"""Tests for AuthServiceImpl."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.domain.ports.auth_service import AuthenticationError
from src.infrastructure.security.auth_service_impl import AuthServiceImpl


class TestAuthServiceImpl:
    """Test AuthServiceImpl authentication logic."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_jwt = MagicMock()
        self.mock_encryption = MagicMock()
        self.mock_user_repo = AsyncMock()
        self.mock_user_role_repo = AsyncMock()
        self.mock_login_attempt_repo = AsyncMock()
        self.mock_token_blacklist = AsyncMock()
        self.mock_refresh_token_store = AsyncMock()

        # Set up record_attempt_and_check_lockout to return tuple
        self.mock_login_attempt_repo.record_attempt_and_check_lockout = AsyncMock(return_value=(False, 0))
        self.mock_login_attempt_repo.is_account_locked = AsyncMock(return_value=False)

        self.service = AuthServiceImpl(
            jwt_service=self.mock_jwt,
            encryption_service=self.mock_encryption,
            user_repository=self.mock_user_repo,
            user_role_repository=self.mock_user_role_repo,
            login_attempt_repository=self.mock_login_attempt_repo,
            token_blacklist=self.mock_token_blacklist,
            refresh_token_store=self.mock_refresh_token_store,
        )

    @pytest.mark.asyncio
    async def test_authenticate_success(self):
        """Valid credentials return access token."""
        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.username = "testuser"
        mock_user.hashed_password = "hashed"  # pragma: allowlist secret
        mock_user.is_active = True
        mock_user.is_locked = False

        self.mock_user_repo.get_by_username.return_value = mock_user
        self.mock_encryption.verify_password.return_value = True
        self.mock_user_role_repo.get_user_roles.return_value = []
        self.mock_jwt.create_access_token.return_value = "access_token"
        self.mock_jwt.create_refresh_token.return_value = "refresh_token"
        # Mock check_and_record_lockout to return (False, 0) - not locked
        self.mock_login_attempt_repo.check_and_record_lockout = AsyncMock(return_value=(False, 0))
        self.mock_login_attempt_repo.clear_attempts = AsyncMock()

        result = await self.service.authenticate("testuser", "password")

        assert result.access_token == "access_token"
        assert result.refresh_token == "refresh_token"
        self.mock_login_attempt_repo.clear_attempts.assert_called_once_with("testuser")

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self):
        """User not found raises AuthenticationError."""
        self.mock_user_repo.get_by_username.return_value = None

        with pytest.raises(AuthenticationError) as exc_info:
            await self.service.authenticate("nonexistent", "password")

        assert "Invalid credentials" in str(exc_info.value)
        # Verify timing attack defense: timing_safe_verify was called
        self.mock_encryption.timing_safe_verify.assert_called_once()
        call_args = self.mock_encryption.timing_safe_verify.call_args
        assert call_args[0][0] == "password"  # First arg is password

    @pytest.mark.asyncio
    async def test_authenticate_inactive_user(self):
        """Inactive user raises AuthenticationError."""
        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.is_active = False

        self.mock_user_repo.get_by_username.return_value = mock_user

        with pytest.raises(AuthenticationError) as exc_info:
            await self.service.authenticate("testuser", "password")

        assert "inactive" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_authenticate_locked_user(self):
        """Locked user raises AuthenticationError."""
        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.is_active = True
        mock_user.is_locked = True

        self.mock_user_repo.get_by_username.return_value = mock_user

        with pytest.raises(AuthenticationError) as exc_info:
            await self.service.authenticate("testuser", "password")

        assert "locked" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_authenticate_wrong_password(self):
        """Wrong password raises AuthenticationError."""
        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.username = "testuser"
        mock_user.hashed_password = "hashed"  # pragma: allowlist secret
        mock_user.is_active = True
        mock_user.is_locked = False

        self.mock_user_repo.get_by_username.return_value = mock_user
        self.mock_encryption.verify_password.return_value = False
        # Mock check_and_record_lockout to return (False, 0) - not locked yet
        self.mock_login_attempt_repo.record_attempt_and_check_lockout = AsyncMock(return_value=(False, 0))

        with pytest.raises(AuthenticationError) as exc_info:
            await self.service.authenticate("testuser", "wrongpassword")

        assert "Invalid credentials" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_verify_token_success(self):
        """Valid token returns TokenPayload."""
        mock_payload = MagicMock()
        self.mock_jwt.verify_token.return_value = mock_payload
        # Token is NOT blacklisted
        self.mock_token_blacklist.is_blacklisted = AsyncMock(return_value=False)

        result = await self.service.verify_token("valid_token")

        assert result == mock_payload

    @pytest.mark.asyncio
    async def test_verify_token_blacklisted(self):
        """Blacklisted token raises AuthenticationError."""
        self.mock_token_blacklist.is_blacklisted.return_value = True

        with pytest.raises(AuthenticationError) as exc_info:
            await self.service.verify_token("blacklisted_token")

        assert "revoked" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_logout_adds_to_blacklist(self):
        """logout() adds token to blacklist."""
        await self.service.logout("token_to_revoke")

        self.mock_token_blacklist.add.assert_called_once_with("token_to_revoke")

    @pytest.mark.asyncio
    async def test_logout_no_blacklist(self):
        """logout() does nothing when no blacklist configured."""
        service_no_blacklist = AuthServiceImpl(
            jwt_service=self.mock_jwt,
            encryption_service=self.mock_encryption,
            user_repository=self.mock_user_repo,
            user_role_repository=self.mock_user_role_repo,
        )

        await service_no_blacklist.logout("token")

        # No error should occur

    @pytest.mark.asyncio
    async def test_refresh_token_success(self):
        """Valid refresh token returns new access token."""
        user_id = uuid4()
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.username = "testuser"
        mock_user.is_active = True
        mock_user.is_locked = False

        self.mock_jwt.verify_refresh_token.return_value = user_id
        self.mock_jwt.get_refresh_token_jti.return_value = "jti_123"
        self.mock_jwt.create_access_token.return_value = "new_access_token"
        # Mock refresh_token_store.is_used to return False (token not used yet)
        self.mock_refresh_token_store.is_used = AsyncMock(return_value=False)
        self.mock_refresh_token_store.mark_used = AsyncMock()
        self.mock_refresh_token_store.get_user_jtis = AsyncMock(return_value=[])
        self.mock_user_repo.get_by_id.return_value = mock_user
        self.mock_user_role_repo.get_user_roles.return_value = []

        result = await self.service.refresh_token("valid_refresh_token")

        assert result == "new_access_token"
        self.mock_refresh_token_store.mark_used.assert_called_once_with("jti_123", user_id)

    @pytest.mark.asyncio
    async def test_refresh_token_reuse_detected(self):
        """Reused refresh token raises AuthenticationError."""
        user_id = uuid4()
        self.mock_jwt.verify_refresh_token.return_value = user_id
        self.mock_jwt.get_refresh_token_jti.return_value = "jti_123"
        self.mock_refresh_token_store.is_used.return_value = True
        self.mock_refresh_token_store.get_user_jtis = AsyncMock(return_value=[])

        with pytest.raises(AuthenticationError) as exc_info:
            await self.service.refresh_token("reused_refresh_token")

        assert "reuse" in str(exc_info.value).lower() or "attack" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_refresh_token_user_not_found(self):
        """Refresh token for non-existent user raises error."""
        user_id = uuid4()
        self.mock_jwt.verify_refresh_token.return_value = user_id
        self.mock_jwt.get_refresh_token_jti.return_value = "jti_123"
        self.mock_refresh_token_store.is_used.return_value = False
        self.mock_refresh_token_store.mark_used = AsyncMock()
        self.mock_refresh_token_store.get_user_jtis = AsyncMock(return_value=[])
        self.mock_user_repo.get_by_id.return_value = None

        with pytest.raises(AuthenticationError) as exc_info:
            await self.service.refresh_token("valid_refresh_token")

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_get_user_roles_returns_role_names(self):
        """_get_user_roles returns list of role names."""
        role1 = MagicMock()
        role1.name = "admin"
        role2 = MagicMock()
        role2.name = "user"

        self.mock_user_role_repo.get_user_roles.return_value = [role1, role2]

        result = await self.service._get_user_roles(uuid4())

        assert result == ["admin", "user"]
