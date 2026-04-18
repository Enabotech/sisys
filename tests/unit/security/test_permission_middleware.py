"""Tests for Permission Middleware.

TDD Red phase - tests should fail before implementation.
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.infrastructure.security.permission_middleware import (
    get_current_user,
    get_current_user_optional,
    require_all_roles,
    require_any_role,
    require_role,
)


class TestGetCurrentUser:
    """Tests for get_current_user dependency."""

    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self):
        """Should return user info for valid token."""
        from src.infrastructure.config.auth import AuthConfig
        from src.infrastructure.security.jwt_service import JWTService

        config = AuthConfig(
            jwt_secret_key="test-secret",  # pragma: allowlist secret
            jwt_algorithm="HS256",
        )
        jwt_service = JWTService(config)

        user_id = uuid4()
        token = jwt_service.create_access_token(
            user_id=user_id,
            username="testuser",
            roles=["admin"],
        )

        credentials = MagicMock()
        credentials.credentials = token

        user = await get_current_user(credentials, jwt_service)

        assert user["user_id"] == str(user_id)
        assert user["username"] == "testuser"
        assert user["roles"] == ["admin"]

    @pytest.mark.asyncio
    async def test_get_current_user_no_credentials(self):
        """Should raise 401 when no credentials provided."""
        from fastapi import HTTPException

        jwt_service = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(None, jwt_service)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self):
        """Should raise 401 for invalid token."""
        from src.infrastructure.security.jwt_service import InvalidTokenError

        jwt_service = MagicMock()
        jwt_service.verify_token = MagicMock(side_effect=InvalidTokenError("Invalid"))

        credentials = MagicMock()
        credentials.credentials = "invalid.token"

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials, jwt_service)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_wrong_token_type(self):
        """Should raise 401 for refresh token used as access token."""
        from src.infrastructure.config.auth import AuthConfig
        from src.infrastructure.security.jwt_service import JWTService

        config = AuthConfig(
            jwt_secret_key="test-secret",  # pragma: allowlist secret
            jwt_algorithm="HS256",
        )
        jwt_service = JWTService(config)

        user_id = uuid4()
        token = jwt_service.create_refresh_token(user_id)  # Refresh token

        credentials = MagicMock()
        credentials.credentials = token

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials, jwt_service)

        assert exc_info.value.status_code == 401


class TestGetCurrentUserOptional:
    """Tests for get_current_user_optional dependency."""

    @pytest.mark.asyncio
    async def test_get_current_user_optional_valid(self):
        """Should return user info for valid token."""
        from src.infrastructure.config.auth import AuthConfig
        from src.infrastructure.security.jwt_service import JWTService

        config = AuthConfig(
            jwt_secret_key="test-secret",  # pragma: allowlist secret
            jwt_algorithm="HS256",
        )
        jwt_service = JWTService(config)

        user_id = uuid4()
        token = jwt_service.create_access_token(
            user_id=user_id,
            username="testuser",
            roles=["admin"],
        )

        credentials = MagicMock()
        credentials.credentials = token

        user = await get_current_user_optional(credentials, jwt_service)

        assert user is not None
        assert user["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_get_current_user_optional_no_credentials(self):
        """Should return None when no credentials."""
        jwt_service = MagicMock()

        user = await get_current_user_optional(None, jwt_service)

        assert user is None

    @pytest.mark.asyncio
    async def test_get_current_user_optional_invalid_token(self):
        """Should return None for invalid token (not raise)."""
        from src.infrastructure.security.jwt_service import InvalidTokenError

        jwt_service = MagicMock()
        jwt_service.verify_token = MagicMock(side_effect=InvalidTokenError("Invalid"))

        credentials = MagicMock()
        credentials.credentials = "invalid.token"

        user = await get_current_user_optional(credentials, jwt_service)

        assert user is None


class TestRequireRole:
    """Tests for require_role dependency."""

    @pytest.mark.asyncio
    async def test_require_role_success(self):
        """Should return user when role matches."""
        current_user = {"user_id": str(uuid4()), "roles": ["admin"]}

        result = await require_role("admin")(current_user)

        assert result == current_user

    @pytest.mark.asyncio
    async def test_require_role_failure(self):
        """Should raise 403 when role doesn't match."""
        from fastapi import HTTPException

        current_user = {"user_id": str(uuid4()), "roles": ["viewer"]}

        with pytest.raises(HTTPException) as exc_info:
            await require_role("admin")(current_user)

        assert exc_info.value.status_code == 403


class TestRequireAnyRole:
    """Tests for require_any_role dependency."""

    @pytest.mark.asyncio
    async def test_require_any_role_success(self):
        """Should return user when any role matches."""
        current_user = {"user_id": str(uuid4()), "roles": ["viewer"]}

        result = await require_any_role(["admin", "editor", "viewer"])(current_user)

        assert result == current_user

    @pytest.mark.asyncio
    async def test_require_any_role_failure(self):
        """Should raise 403 when no role matches."""
        from fastapi import HTTPException

        current_user = {"user_id": str(uuid4()), "roles": ["guest"]}

        with pytest.raises(HTTPException) as exc_info:
            await require_any_role(["admin", "editor"])(current_user)

        assert exc_info.value.status_code == 403


class TestRequireAllRoles:
    """Tests for require_all_roles dependency."""

    @pytest.mark.asyncio
    async def test_require_all_roles_success(self):
        """Should return user when all roles present."""
        current_user = {"user_id": str(uuid4()), "roles": ["admin", "editor"]}

        result = await require_all_roles(["admin", "editor"])(current_user)

        assert result == current_user

    @pytest.mark.asyncio
    async def test_require_all_roles_partial(self):
        """Should raise 403 when only some roles present."""
        from fastapi import HTTPException

        current_user = {"user_id": str(uuid4()), "roles": ["admin"]}

        with pytest.raises(HTTPException) as exc_info:
            await require_all_roles(["admin", "editor"])(current_user)

        assert exc_info.value.status_code == 403
