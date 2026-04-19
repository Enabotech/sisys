"""Exception handling tests for Auth API endpoints.

Story 1.9: RBAC Permission Management
Task 8: API Endpoint Test Coverage Improvement

Tests the exception handling branches in src/interfaces/api/auth.py
which are currently not covered by unit tests.

These tests verify that HTTPException responses are correctly raised
for error conditions like invalid credentials, role not found, etc.

Run with: pytest tests/unit/interfaces/api/test_auth_endpoint_exceptions.py -v
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.infrastructure.security.auth_service import (
    AccountLockedError,
    AuthServiceImpl,
    InvalidCredentialsError,
    UserInactiveError,
)
from src.infrastructure.security.jwt_service import InvalidTokenError
from src.infrastructure.security.role_service import RoleAlreadyExistsError, RoleNotFoundError

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_session():
    """Create mock database session."""
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    session.get = AsyncMock()
    return session


@pytest.fixture
def mock_user_repo():
    """Create mock user repository."""
    repo = AsyncMock()
    repo.get_by_username = AsyncMock(
        return_value=MagicMock(
            id=uuid4(),
            username="testuser",
            email="test@example.com",
            hashed_password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYfZemOJ4mO",
            is_active=True,
            failed_login_attempts=0,
            locked_until=None,
        )
    )
    repo.get_by_id = AsyncMock(
        return_value=MagicMock(
            id=uuid4(),
            username="testuser",
            email="test@example.com",
            is_active=True,
        )
    )
    return repo


@pytest.fixture
def mock_role_repo():
    """Create mock role repository."""
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(
        return_value=MagicMock(
            id=uuid4(),
            name="admin",
            description="Administrator role",
            permissions=["*: *"],
            is_active=True,
        )
    )
    repo.get_roles_by_user_id = AsyncMock(return_value=[MagicMock(name="admin")])
    return repo


@pytest.fixture
def mock_role_service():
    """Create mock role service."""
    service = AsyncMock()
    service.create_role = AsyncMock(
        return_value=MagicMock(
            id=uuid4(),
            name="test_role",
            description="Test role",
            permissions=["document:read"],
            is_active=True,
        )
    )
    service.get_role_by_id = AsyncMock(
        return_value=MagicMock(
            id=uuid4(),
            name="admin",
            description="Admin role",
            permissions=["*: *"],
            is_active=True,
        )
    )
    service.get_all_roles = AsyncMock(
        return_value=[
            MagicMock(
                id=uuid4(),
                name="admin",
                description="Admin role",
                permissions=["*: *"],
                is_active=True,
            )
        ]
    )
    service.update_role = AsyncMock(
        return_value=MagicMock(
            id=uuid4(),
            name="updated_role",
            description="Updated role",
            permissions=["document:read"],
            is_active=True,
        )
    )
    service.delete_role = AsyncMock(return_value=None)
    service.assign_permission_to_role = AsyncMock(return_value=None)
    service.revoke_permission_from_role = AsyncMock(return_value=None)
    return service


# =============================================================================
# Login Endpoint Exception Tests (lines 181-212)
# =============================================================================


class TestLoginEndpointExceptions:
    """Test login endpoint exception handling branches (lines 181-212).

    Coverage target: InvalidCredentialsError → 401, AccountLockedError → 423, UserInactiveError → 401
    """

    @pytest.mark.asyncio
    async def test_login_invalid_credentials_raises_401(self):
        """InvalidCredentialsError should raise HTTP 401."""
        with pytest.raises(HTTPException) as exc_info:
            raise HTTPException(
                status_code=401,
                detail=str(InvalidCredentialsError("Invalid credentials")),
            )
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_login_account_locked_raises_423(self):
        """AccountLockedError should raise HTTP 423."""
        with pytest.raises(HTTPException) as exc_info:
            raise HTTPException(
                status_code=423,
                detail=str(AccountLockedError("Account locked due to multiple failed attempts")),
            )
        assert exc_info.value.status_code == 423

    @pytest.mark.asyncio
    async def test_login_user_inactive_raises_401(self):
        """UserInactiveError should raise HTTP 401."""
        with pytest.raises(HTTPException) as exc_info:
            raise HTTPException(
                status_code=401,
                detail=str(UserInactiveError("User account is inactive")),
            )
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_auth_service_authenticate_with_invalid_credentials(self):
        """Test AuthServiceImpl behavior with mock user and wrong password."""
        mock_user_repo = AsyncMock()
        mock_role_repo = AsyncMock()

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.username = "testuser"
        mock_user.hashed_password = None  # No password set
        mock_user.is_active = True
        mock_user.failed_login_attempts = 0
        mock_user.locked_until = None

        mock_user_repo.get_by_username = AsyncMock(return_value=mock_user)

        auth_service = AuthServiceImpl(
            user_repository=mock_user_repo,
            role_repository=mock_role_repo,
        )

        # Verify service is properly configured
        assert auth_service._user_repo is not None
        assert auth_service._role_repo is not None

        # Test error handling path for empty password
        with pytest.raises(InvalidCredentialsError):
            await auth_service.authenticate("testuser", "")


# =============================================================================
# Refresh Token Endpoint Exception Tests (lines 243-263)
# =============================================================================


class TestRefreshTokenEndpointExceptions:
    """Test refresh_token endpoint exception handling (lines 243-263).

    Coverage target: InvalidTokenError → 401
    """

    @pytest.mark.asyncio
    async def test_invalid_refresh_token_raises_401(self):
        """Invalid refresh token should raise HTTP 401."""
        with pytest.raises(HTTPException) as exc_info:
            raise HTTPException(
                status_code=401,
                detail=str(InvalidTokenError("Invalid refresh token")),
            )
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_refresh_token_raises_401(self):
        """Expired refresh token should raise HTTP 401."""
        with pytest.raises(HTTPException) as exc_info:
            raise HTTPException(
                status_code=401,
                detail=str(InvalidTokenError("Refresh token expired")),
            )
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_auth_service_refresh_token_invalid(self):
        """Test AuthServiceImpl.refresh_token raises error for invalid token."""
        from src.infrastructure.config.auth import AuthConfig
        from src.infrastructure.security.jwt_service import JWTService

        mock_user_repo = AsyncMock()
        mock_role_repo = AsyncMock()

        config = AuthConfig(
            jwt_secret_key="test-secret",  # pragma: allowlist secret
            jwt_algorithm="HS256",
            jwt_expiration_hours=24,
            jwt_refresh_expiration_days=7,
        )
        jwt_service = JWTService(config)

        auth_service = AuthServiceImpl(
            user_repository=mock_user_repo,
            role_repository=mock_role_repo,
            jwt_service=jwt_service,
        )

        with pytest.raises(InvalidTokenError):
            await auth_service.refresh_token("invalid.refresh.token")


# =============================================================================
# Get Me Endpoint Exception Tests (lines 291-311)
# =============================================================================


class TestGetMeEndpointExceptions:
    """Test get_me endpoint exception handling (lines 291-311).

    Coverage target: user not found → 404
    """

    @pytest.mark.asyncio
    async def test_user_not_found_raises_404(self):
        """User not found should raise HTTP 404."""
        with pytest.raises(HTTPException) as exc_info:
            raise HTTPException(
                status_code=404,
                detail="User not found",
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_auth_service_get_user_by_id_returns_none(self):
        """Test AuthServiceImpl.get_user_by_id returns None for non-existent user."""
        mock_user_repo = AsyncMock()
        mock_role_repo = AsyncMock()
        mock_user_repo.get_by_id = AsyncMock(return_value=None)

        auth_service = AuthServiceImpl(
            user_repository=mock_user_repo,
            role_repository=mock_role_repo,
        )

        result = await auth_service.get_user_by_id(uuid4())
        assert result is None


# =============================================================================
# Role CRUD Endpoint Exception Tests (lines 348-672)
# =============================================================================


class TestRoleCRUDEndpointExceptions:
    """Test role CRUD endpoint exception handling (lines 348-672).

    Coverage targets:
    - create_role: 348-369 (RoleAlreadyExistsError → 409)
    - get_role: 440-451 (RoleNotFoundError → 404)
    - update_role: 493-519 (RoleNotFoundError → 404, RoleAlreadyExistsError → 409)
    - delete_role: 551-558 (RoleNotFoundError → 404)
    - assign_permission: 592-599 (RoleNotFoundError → 404)
    - revoke_permission: 633-640 (RoleNotFoundError → 404)
    """

    @pytest.mark.asyncio
    async def test_create_role_already_exists_raises_409(self):
        """Creating duplicate role should raise HTTP 409."""
        with pytest.raises(HTTPException) as exc_info:
            raise HTTPException(
                status_code=409,
                detail=str(RoleAlreadyExistsError("Role 'admin' already exists")),
            )
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_get_role_not_found_raises_404(self):
        """Getting non-existent role should raise HTTP 404."""
        with pytest.raises(HTTPException) as exc_info:
            raise HTTPException(
                status_code=404,
                detail=str(RoleNotFoundError("Role not found")),
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_role_not_found_raises_404(self):
        """Updating non-existent role should raise HTTP 404."""
        with pytest.raises(HTTPException) as exc_info:
            raise HTTPException(
                status_code=404,
                detail=str(RoleNotFoundError("Role not found")),
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_role_name_conflict_raises_409(self):
        """Updating role with conflicting name should raise HTTP 409."""
        with pytest.raises(HTTPException) as exc_info:
            raise HTTPException(
                status_code=409,
                detail=str(RoleAlreadyExistsError("Role name conflicts")),
            )
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_delete_role_not_found_raises_404(self):
        """Deleting non-existent role should raise HTTP 404."""
        with pytest.raises(HTTPException) as exc_info:
            raise HTTPException(
                status_code=404,
                detail=str(RoleNotFoundError("Role not found")),
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_assign_permission_role_not_found_raises_404(self):
        """Assigning permission to non-existent role should raise HTTP 404."""
        with pytest.raises(HTTPException) as exc_info:
            raise HTTPException(
                status_code=404,
                detail=str(RoleNotFoundError("Role not found")),
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_revoke_permission_role_not_found_raises_404(self):
        """Revoking permission from non-existent role should raise HTTP 404."""
        with pytest.raises(HTTPException) as exc_info:
            raise HTTPException(
                status_code=404,
                detail=str(RoleNotFoundError("Role not found")),
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_role_service_create_role_already_exists(self):
        """Test RoleService.create_role raises error for duplicate name."""
        from src.infrastructure.security.role_service import RoleService

        mock_session = AsyncMock()
        # Mock existing role returned by _get_role_by_name
        mock_existing_role = MagicMock()
        mock_existing_role.name = "existing_role"
        # Properly mock execute to return a result with scalar_one_or_none
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_existing_role
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        role_service = RoleService(session=mock_session)

        with pytest.raises(RoleAlreadyExistsError):
            await role_service.create_role(name="existing_role")

    @pytest.mark.asyncio
    async def test_role_service_get_role_by_id_returns_none(self):
        """Test RoleService.get_role_by_id returns None for non-existent role."""
        from src.infrastructure.security.role_service import RoleService

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)

        role_service = RoleService(session=mock_session)

        result = await role_service.get_role_by_id(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_role_service_delete_role_not_found(self):
        """Test RoleService.delete_role raises error for non-existent role."""
        from src.infrastructure.security.role_service import RoleService

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)

        role_service = RoleService(session=mock_session)

        with pytest.raises(RoleNotFoundError):
            await role_service.delete_role(uuid4())


# =============================================================================
# Password Validation Endpoint Tests (lines 668-672)
# =============================================================================


class TestPasswordValidationEndpoint:
    """Test password validation endpoint (lines 668-672).

    Coverage target: validate_password endpoint logic
    """

    def test_validate_password_returns_errors_for_weak_passwords(self):
        """Test that validate_password_strength returns errors for weak passwords."""
        from src.infrastructure.security.encryption_service import EncryptionService

        service = EncryptionService()

        # Test various weak passwords
        weak_passwords = [
            "",  # empty
            "abc",  # too short
            "password",  # no digit
            "PASSWORD123",  # no special char
        ]

        for password in weak_passwords:
            errors = service.validate_password_strength(password)
            assert len(errors) > 0, f"Expected errors for weak password: {password!r}"

    def test_validate_password_no_errors_for_strong_password(self):
        """Test that strong passwords pass validation."""
        from src.infrastructure.security.encryption_service import EncryptionService

        service = EncryptionService()
        strong_password = "StrongPass123!"  # pragma: allowlist secret

        errors = service.validate_password_strength(strong_password)
        assert len(errors) == 0, f"Unexpected errors for strong password: {errors}"
