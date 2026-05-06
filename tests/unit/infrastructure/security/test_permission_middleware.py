"""Tests for PermissionMiddleware."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.domain.value_objects.token_payload import TokenPayload
from src.infrastructure.security.permission_middleware import (
    CurrentUser,
    PermissionContext,
    get_current_user,
)


class TestGetCurrentUser:
    """Test get_current_user function."""

    def test_missing_authorization_header(self):
        """Missing authorization header raises 401."""
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(authorization=None)

        assert exc_info.value.status_code == 401
        assert "Missing authorization header" in str(exc_info.value.detail)

    def test_invalid_authorization_header_format(self):
        """Invalid format raises 401."""
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(authorization="InvalidFormat")

        assert exc_info.value.status_code == 401
        assert "Invalid authorization header format" in str(exc_info.value.detail)

    def test_invalid_authorization_header_not_bearer(self):
        """Non-Bearer auth raises 401."""
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(authorization="Basic sometoken")

        assert exc_info.value.status_code == 401
        assert "Invalid authorization header format" in str(exc_info.value.detail)

    def test_missing_jwt_service(self):
        """Missing jwt_service raises 500."""
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(authorization="Bearer sometoken", jwt_service=None)

        assert exc_info.value.status_code == 500
        assert "JWT service not configured" in str(exc_info.value.detail)

    def test_empty_string_authorization_header(self):
        """Empty string authorization header raises 401."""
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(authorization="")

        assert exc_info.value.status_code == 401
        assert "Invalid authorization header format" in str(exc_info.value.detail)

    def test_whitespace_only_authorization_header(self):
        """Whitespace-only authorization header raises 401."""
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(authorization="   ")

        assert exc_info.value.status_code == 401
        assert "Invalid authorization header format" in str(exc_info.value.detail)

    def test_bearer_with_empty_token(self):
        """Bearer with empty token raises 401."""
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(authorization="Bearer ")

        assert exc_info.value.status_code == 401
        assert "Invalid authorization header format" in str(exc_info.value.detail)

    def test_invalid_token(self):
        """Invalid token raises 401."""
        mock_jwt = MagicMock()
        mock_jwt.verify_token.side_effect = Exception("Invalid token")

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(authorization="Bearer invalidtoken", jwt_service=mock_jwt)

        assert exc_info.value.status_code == 401
        assert "Invalid or expired token" in str(exc_info.value.detail)

    def test_valid_token_returns_payload(self):
        """Valid token returns TokenPayload."""
        mock_jwt = MagicMock()
        mock_payload = MagicMock(spec=TokenPayload)
        mock_jwt.verify_token.return_value = mock_payload

        result = get_current_user(authorization="Bearer validtoken", jwt_service=mock_jwt)

        assert result == mock_payload


class TestCurrentUser:
    """Test CurrentUser dependency class."""

    def test_optional_no_authorization_returns_none(self):
        """Optional user with no auth returns None."""
        result = CurrentUser.optional(authorization=None)

        assert result is None

    def test_optional_invalid_token_returns_none(self):
        """Optional user with invalid token returns None."""
        mock_jwt = MagicMock()
        mock_jwt.verify_token.side_effect = Exception("Invalid")

        result = CurrentUser.optional(authorization="Bearer invalid", jwt_service=mock_jwt)

        assert result is None

    def test_optional_valid_token_returns_user(self):
        """Optional user with valid token returns payload."""
        mock_jwt = MagicMock()
        mock_payload = MagicMock(spec=TokenPayload)
        mock_jwt.verify_token.return_value = mock_payload

        result = CurrentUser.optional(authorization="Bearer valid", jwt_service=mock_jwt)

        assert result == mock_payload

    def test_required_missing_authorization_raises(self):
        """Required user with no auth raises 401."""
        with pytest.raises(HTTPException) as exc_info:
            CurrentUser.required(authorization=None)

        assert exc_info.value.status_code == 401

    def test_required_valid_token_returns_user(self):
        """Required user with valid token returns payload."""
        mock_jwt = MagicMock()
        mock_payload = MagicMock(spec=TokenPayload)
        mock_jwt.verify_token.return_value = mock_payload

        result = CurrentUser.required(authorization="Bearer valid", jwt_service=mock_jwt)

        assert result == mock_payload


class TestPermissionContext:
    """Test PermissionContext class."""

    @pytest.mark.asyncio
    async def test_check_has_permission(self):
        """check() returns True when user has permission."""
        mock_user = MagicMock(spec=TokenPayload)
        mock_user.user_id = uuid4()

        mock_perm_service = AsyncMock()
        mock_perm_service.check_permission.return_value = True

        ctx = PermissionContext(mock_user, mock_perm_service, resource_id=uuid4())

        result = await ctx.check("document", "read")

        assert result is True
        mock_perm_service.check_permission.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_no_permission(self):
        """check() returns False when user lacks permission."""
        mock_user = MagicMock(spec=TokenPayload)
        mock_user.user_id = uuid4()

        mock_perm_service = AsyncMock()
        mock_perm_service.check_permission.return_value = False

        ctx = PermissionContext(mock_user, mock_perm_service)

        result = await ctx.check("document", "delete")

        assert result is False

    @pytest.mark.asyncio
    async def test_require_has_permission(self):
        """require() succeeds when user has permission."""
        mock_user = MagicMock(spec=TokenPayload)
        mock_user.user_id = uuid4()

        mock_perm_service = AsyncMock()
        mock_perm_service.check_permission.return_value = True

        ctx = PermissionContext(mock_user, mock_perm_service)

        # Should not raise
        await ctx.require("document", "read")

    @pytest.mark.asyncio
    async def test_require_no_permission_raises_403(self):
        """require() raises 403 when user lacks permission."""
        mock_user = MagicMock(spec=TokenPayload)
        mock_user.user_id = uuid4()

        mock_perm_service = AsyncMock()
        mock_perm_service.check_permission.return_value = False

        ctx = PermissionContext(mock_user, mock_perm_service)

        with pytest.raises(HTTPException) as exc_info:
            await ctx.require("document", "delete")

        assert exc_info.value.status_code == 403
        assert "Permission denied" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_require_uses_resource_id(self):
        """require() passes resource_id to permission service."""
        mock_user = MagicMock(spec=TokenPayload)
        mock_user.user_id = uuid4()
        resource_id = uuid4()

        mock_perm_service = AsyncMock()
        mock_perm_service.check_permission.return_value = True

        ctx = PermissionContext(mock_user, mock_perm_service, resource_id=resource_id)

        await ctx.require("document", "read")

        mock_perm_service.check_permission.assert_called_once_with(
            user_id=mock_user.user_id,
            resource="document",
            action="read",
            resource_id=resource_id,
        )
