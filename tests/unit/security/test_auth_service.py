"""Tests for Auth Service.

TDD Red phase - tests should fail before implementation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.infrastructure.security.auth_service import (
    AuthServiceImpl,
    InvalidCredentialsError,
    UserInactiveError,
)


class TestAuthService:
    """Auth Service tests."""

    @pytest.fixture
    def mock_user_repo(self):
        """Create mock user repository."""
        return AsyncMock()

    @pytest.fixture
    def mock_role_repo(self):
        """Create mock role repository."""
        return AsyncMock()

    @pytest.fixture
    def auth_service(self, mock_user_repo, mock_role_repo):
        """Create AuthService instance with mocked dependencies."""
        from src.infrastructure.config.auth import AuthConfig
        from src.infrastructure.security.jwt_service import JWTService

        config = AuthConfig(
            jwt_secret_key="test-secret-key",  # pragma: allowlist secret
            jwt_algorithm="HS256",
            jwt_expiration_hours=24,
            jwt_refresh_expiration_days=7,
        )

        jwt_service = JWTService(config)

        return AuthServiceImpl(
            user_repository=mock_user_repo,
            role_repository=mock_role_repo,
            jwt_service=jwt_service,
            config=config,
        )

    @pytest.mark.asyncio
    async def test_authenticate_success(self, auth_service, mock_user_repo, mock_role_repo):
        """Should authenticate user with valid credentials."""
        user_id = uuid4()

        # Create mock user
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"
        mock_user.hashed_password = auth_service.hash_password("Test123!")
        mock_user.is_active = True
        mock_user.failed_login_attempts = 0
        mock_user.locked_until = None

        mock_user_repo.get_by_username = AsyncMock(return_value=mock_user)

        # Mock role query
        mock_role_result = MagicMock()
        mock_role_result.scalars.return_value.all.return_value = ["admin"]

        # Setup role query mock
        with patch.object(auth_service, "get_user_roles", return_value=["admin"]):
            result = await auth_service.authenticate("testuser", "Test123!")

        assert "access_token" in result
        assert result["token_type"] == "bearer"
        assert result["user"]["username"] == "testuser"
        assert result["user"]["roles"] == ["admin"]

    @pytest.mark.asyncio
    async def test_authenticate_invalid_username(self, auth_service, mock_user_repo):
        """Should raise InvalidCredentialsError for unknown username."""
        mock_user_repo.get_by_username = AsyncMock(return_value=None)

        with pytest.raises(InvalidCredentialsError):
            await auth_service.authenticate("unknownuser", "password")

    @pytest.mark.asyncio
    async def test_authenticate_invalid_password(self, auth_service, mock_user_repo):
        """Should raise InvalidCredentialsError for wrong password."""
        user_id = uuid4()

        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.username = "testuser"
        mock_user.hashed_password = auth_service.hash_password("CorrectPassword!")
        mock_user.is_active = True
        mock_user.failed_login_attempts = 0
        mock_user.locked_until = None

        mock_user_repo.get_by_username = AsyncMock(return_value=mock_user)

        with pytest.raises(InvalidCredentialsError):
            await auth_service.authenticate("testuser", "WrongPassword!")

    @pytest.mark.asyncio
    async def test_authenticate_inactive_user(self, auth_service, mock_user_repo):
        """Should raise UserInactiveError for inactive user."""
        mock_user = MagicMock()
        mock_user.is_active = False

        mock_user_repo.get_by_username = AsyncMock(return_value=mock_user)

        with pytest.raises(UserInactiveError):
            await auth_service.authenticate("inactiveuser", "password")

    def test_hash_password(self, auth_service):
        """Should hash password correctly."""
        password = "TestPassword123!"  # pragma: allowlist secret

        hashed = auth_service.hash_password(password)

        assert hashed != password
        assert hashed.startswith("$2b$")  # bcrypt prefix

    def test_verify_password_correct(self, auth_service):
        """Should verify correct password."""
        password = "TestPassword123!"  # pragma: allowlist secret
        hashed = auth_service.hash_password(password)

        assert auth_service.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self, auth_service):
        """Should return False for incorrect password."""
        password = "TestPassword123!"  # pragma: allowlist secret
        hashed = auth_service.hash_password(password)

        assert auth_service.verify_password("WrongPassword", hashed) is False

    @pytest.mark.asyncio
    async def test_verify_token_success(self, auth_service):
        """Should verify valid token."""
        user_id = uuid4()
        token = auth_service._jwt_service.create_access_token(
            user_id=user_id,
            username="testuser",
            roles=["admin"],
        )

        payload = await auth_service.verify_token(token)

        assert payload["sub"] == str(user_id)
        assert payload["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_verify_token_invalid(self, auth_service):
        """Should raise InvalidTokenError for invalid token."""
        with pytest.raises(Exception):  # InvalidTokenError
            await auth_service.verify_token("invalid.token")

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, auth_service, mock_user_repo):
        """Should refresh token with valid refresh token."""
        user_id = uuid4()

        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.username = "testuser"
        mock_user.is_active = True

        mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)

        # Create refresh token
        refresh_token = auth_service._jwt_service.create_refresh_token(user_id)

        # Mock get_user_roles
        with patch.object(auth_service, "get_user_roles", return_value=["admin"]):
            result = await auth_service.refresh_token(refresh_token)

        assert "access_token" in result
        assert result["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, auth_service):
        """Should raise InvalidTokenError for invalid refresh token."""
        with pytest.raises(Exception):  # InvalidTokenError
            await auth_service.refresh_token("invalid.refresh.token")

    @pytest.mark.asyncio
    async def test_get_user_by_id_success(self, auth_service, mock_user_repo):
        """Should return user info for valid user ID."""
        user_id = uuid4()

        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"
        mock_user.is_active = True

        mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)

        with patch.object(auth_service, "get_user_roles", return_value=["admin"]):
            result = await auth_service.get_user_by_id(user_id)

        assert result["username"] == "testuser"
        assert result["email"] == "test@example.com"
        assert result["roles"] == ["admin"]

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, auth_service, mock_user_repo):
        """Should return None for unknown user ID."""
        mock_user_repo.get_by_id = AsyncMock(return_value=None)

        result = await auth_service.get_user_by_id(uuid4())

        assert result is None
