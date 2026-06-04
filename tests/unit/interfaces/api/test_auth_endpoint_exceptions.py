"""Tests for Auth Endpoint Exception Handling - 认证端点异常处理测试.

使用 dependency_overrides 正确注入 mock 服务
测试实际的 endpoint 代码路径
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.application.use_cases.role_management import RoleService
from src.domain.ports.auth_service import AuthenticationError, AuthServicePort
from src.domain.value_objects.token_payload import TokenPayload
from src.interfaces.api.exception_handlers import register_exception_handlers
from src.interfaces.api.middleware.exception_context import ExceptionContextMiddleware


def create_test_app(
    auth_service: AuthServicePort,
    role_service: RoleService | None = None,
) -> tuple[FastAPI, TestClient]:
    """Create test FastAPI app with injected mock services.

    Args:
        auth_service: Mock auth service (passed directly to router)
        role_service: Mock role service (optional, a mock will be created if not provided)

    Returns:
        Tuple of (FastAPI app, TestClient)
    """
    from src.interfaces.api.auth import create_auth_router

    app = FastAPI()
    app.add_middleware(ExceptionContextMiddleware)
    register_exception_handlers(app)

    # Create mock role_service if not provided
    if role_service is None:
        role_service = MagicMock(spec=RoleService)

    # Mock get_current_user that bypasses actual auth
    async def mock_get_current_user():
        return TokenPayload(
            user_id=uuid4(),
            username="testuser",
            roles=("admin",),
            exp=datetime.now(UTC) + timedelta(hours=24),
        )

    # Create router with injected mock services and mock auth dependency
    router = create_auth_router(
        auth_service,
        role_service,
        None,
        get_current_user_override=mock_get_current_user,
    )
    app.include_router(router)

    return app, TestClient(app)


class TestLoginEndpointExceptions:
    """Test Login endpoint exception handling."""

    def test_login_invalid_credentials_returns_401(self):
        """Invalid credentials should return 401."""
        mock_service = MagicMock(spec=AuthServicePort)
        mock_service.authenticate = AsyncMock(side_effect=AuthenticationError("Invalid credentials"))
        mock_service.verify_token = AsyncMock(
            return_value=TokenPayload(
                user_id=uuid4(),
                username="testuser",
                roles=(),
                exp=datetime.now(UTC) + timedelta(hours=24),
            )
        )

        app, client = create_test_app(mock_service)

        response = client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "wrongpassword"},  # pragma: allowlist secret
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_account_locked_returns_423(self):
        """Locked account should return 423."""
        mock_service = MagicMock(spec=AuthServicePort)
        mock_service.authenticate = AsyncMock(side_effect=AuthenticationError("Account is locked", context={"locked": True}))

        app, client = create_test_app(mock_service)

        response = client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "password"},  # pragma: allowlist secret
        )

        assert response.status_code == 423

    def test_login_user_inactive_returns_401(self):
        """Inactive user should return 401."""
        mock_service = MagicMock(spec=AuthServicePort)
        mock_service.authenticate = AsyncMock(side_effect=AuthenticationError("Account is inactive"))

        app, client = create_test_app(mock_service)

        response = client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "password"},  # pragma: allowlist secret
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestRefreshTokenEndpointExceptions:
    """Test RefreshToken endpoint exception handling."""

    def test_refresh_token_invalid_returns_401(self):
        """Invalid refresh token should return 401."""
        mock_service = MagicMock(spec=AuthServicePort)
        mock_service.refresh_token = AsyncMock(side_effect=AuthenticationError("Invalid refresh token"))
        mock_service.verify_token = AsyncMock(
            return_value=TokenPayload(
                user_id=uuid4(),
                username="testuser",
                roles=(),
                exp=datetime.now(UTC) + timedelta(hours=24),
            )
        )

        app, client = create_test_app(mock_service)

        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestRoleEndpointExceptions:
    """Test Role CRUD endpoint exception handling."""

    def test_create_role_conflict_returns_409(self):
        """Duplicate role name should return 409."""
        from src.application.use_cases.role_management import RoleAlreadyExistsError

        mock_service = MagicMock(spec=AuthServicePort)
        role_service = MagicMock(spec=RoleService)
        role_service.create_role = AsyncMock(side_effect=RoleAlreadyExistsError("admin"))

        app, client = create_test_app(mock_service, role_service)

        response = client.post(
            "/api/v1/roles",
            json={"name": "admin", "permissions": ["*:*"]},
        )

        assert response.status_code == status.HTTP_409_CONFLICT

    def test_get_role_not_found_returns_404(self):
        """Role not found should return 404."""
        mock_service = MagicMock(spec=AuthServicePort)
        role_service = MagicMock(spec=RoleService)
        role_service.get_role = AsyncMock(return_value=None)

        app, client = create_test_app(mock_service, role_service)

        response = client.get(f"/api/v1/roles/{uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_role_not_found_returns_404(self):
        """Update non-existent role should return 404."""
        from src.application.use_cases.role_management import RoleNotFoundError

        mock_service = MagicMock(spec=AuthServicePort)
        role_service = MagicMock(spec=RoleService)
        role_service.update_role = AsyncMock(side_effect=RoleNotFoundError(uuid4()))

        app, client = create_test_app(mock_service, role_service)

        response = client.put(
            f"/api/v1/roles/{uuid4()}",
            json={"name": "newname"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_role_not_found_returns_404(self):
        """Delete non-existent role should return 404."""
        from src.application.use_cases.role_management import RoleNotFoundError

        mock_service = MagicMock(spec=AuthServicePort)
        role_service = MagicMock(spec=RoleService)
        role_service.delete_role = AsyncMock(side_effect=RoleNotFoundError(uuid4()))

        app, client = create_test_app(mock_service, role_service)

        response = client.delete(f"/api/v1/roles/{uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestPermissionEndpointExceptions:
    """Test Permission endpoint exception handling."""

    def test_assign_permission_role_not_found_returns_404(self):
        """Assign permission to non-existent role should return 404."""
        mock_service = MagicMock(spec=AuthServicePort)
        role_service = MagicMock(spec=RoleService)
        role_service.get_role = AsyncMock(return_value=None)

        app, client = create_test_app(mock_service, role_service)

        response = client.post(
            f"/api/v1/roles/{uuid4()}/permissions",
            json={"role_id": str(uuid4()), "permissions": ["document:read"]},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_revoke_permission_role_not_found_returns_404(self):
        """Revoke permission from non-existent role should return 404."""
        mock_service = MagicMock(spec=AuthServicePort)
        role_service = MagicMock(spec=RoleService)
        role_service.get_role = AsyncMock(return_value=None)

        app, client = create_test_app(mock_service, role_service)

        response = client.delete(f"/api/v1/roles/{uuid4()}/permissions/document:read")

        assert response.status_code == status.HTTP_404_NOT_FOUND
