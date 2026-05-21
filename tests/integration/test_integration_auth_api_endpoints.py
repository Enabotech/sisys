"""Tests for Auth API Integration - Complete Endpoint Coverage.

Tests complete HTTP request/response flow for all auth endpoints.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.application.use_cases.role_management import Role, RoleService
from src.domain.ports.auth_service import AuthServicePort, AuthTokens
from src.domain.value_objects.token_payload import TokenPayload
from src.interfaces.api.auth import create_auth_router


def create_test_app(
    auth_service: AuthServicePort,
    role_service: RoleService | None = None,
) -> tuple:
    """Create test FastAPI app with injected mock services."""
    from unittest.mock import MagicMock

    app = FastAPI()

    # Create mock role_service if not provided
    if role_service is None:
        role_service = MagicMock(spec=RoleService)

    async def mock_get_current_user():
        return TokenPayload(
            user_id=uuid4(),
            username="testuser",
            roles=("admin",),
            exp=datetime.now(UTC) + timedelta(hours=24),
        )

    router = create_auth_router(
        auth_service,
        role_service,
        None,
        get_current_user_override=mock_get_current_user,
    )
    app.include_router(router)

    return app, TestClient(app)


class TestLoginEndpoint:
    """Test login endpoint happy path."""

    def test_login_success_returns_token(self):
        """Valid credentials return access token."""
        user_id = uuid4()
        mock_service = MagicMock(spec=AuthServicePort)
        mock_service.authenticate = AsyncMock(
            return_value=AuthTokens(access_token="valid_access_token", refresh_token="valid_refresh_token")
        )
        mock_service.verify_token = AsyncMock(
            return_value=TokenPayload(
                user_id=user_id,
                username="testuser",
                roles=("admin",),
                exp=datetime.now(UTC) + timedelta(hours=24),
            )
        )

        app, client = create_test_app(mock_service)

        response = client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "correctpassword"},  # pragma: allowlist secret
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["access_token"] == "valid_access_token"
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 86400
        assert data["user"]["username"] == "testuser"


class TestRefreshTokenEndpoint:
    """Test refresh token endpoint."""

    def test_refresh_token_success(self):
        """Valid refresh token returns new access token."""
        user_id = uuid4()
        mock_service = MagicMock(spec=AuthServicePort)
        mock_service.refresh_token = AsyncMock(return_value="new_access_token")
        mock_service.verify_token = AsyncMock(
            return_value=TokenPayload(
                user_id=user_id,
                username="testuser",
                roles=("admin",),
                exp=datetime.now(UTC) + timedelta(hours=24),
            )
        )

        app, client = create_test_app(mock_service)

        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "valid_refresh_token"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["access_token"] == "new_access_token"


class TestLogoutEndpoint:
    """Test logout endpoint."""

    def test_logout_success_returns_204(self):
        """Logout returns 204 No Content."""
        mock_service = MagicMock(spec=AuthServicePort)
        mock_service.logout = AsyncMock(return_value=None)

        app, client = create_test_app(mock_service)

        response = client.post("/api/v1/auth/logout")

        assert response.status_code == status.HTTP_204_NO_CONTENT


class TestGetMeEndpoint:
    """Test get current user endpoint."""

    def test_get_me_success(self):
        """Authenticated user can get their info."""
        user_id = uuid4()
        mock_service = MagicMock(spec=AuthServicePort)

        async def mock_get_current_user():
            return TokenPayload(
                user_id=user_id,
                username="testuser",
                roles=("admin", "user"),
                exp=datetime.now(UTC) + timedelta(hours=24),
            )

        router = create_auth_router(
            mock_service,
            None,
            None,
            get_current_user_override=mock_get_current_user,
        )

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/api/v1/auth/me")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["username"] == "testuser"
        assert "admin" in data["roles"]


class TestRoleCrudEndpoints:
    """Test role management endpoints."""

    def test_create_role_success(self):
        """Create role returns 201 with role data."""
        from src.application.use_cases.role_management import RoleService

        role_id = uuid4()
        mock_auth = MagicMock(spec=AuthServicePort)
        mock_role_service = MagicMock(spec=RoleService)

        created_role = Role(
            id=role_id,
            name="editor",
            description="Editor role",
            permissions=["document:read", "document:write"],
            is_system_reserved=False,
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_role_service.create_role = AsyncMock(return_value=created_role)

        app, client = create_test_app(mock_auth, mock_role_service)

        response = client.post(
            "/api/v1/roles",
            json={
                "name": "editor",
                "description": "Editor role",
                "permissions": ["document:read", "document:write"],
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "editor"
        assert data["permissions"] == ["document:read", "document:write"]

    def test_list_roles_success(self):
        """List roles returns all roles."""
        from src.application.use_cases.role_management import RoleService

        mock_auth = MagicMock(spec=AuthServicePort)
        mock_role_service = MagicMock(spec=RoleService)

        roles = [
            Role(
                id=uuid4(),
                name="admin",
                description="Admin",
                permissions=["*:*"],
                is_system_reserved=True,
                is_active=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            ),
            Role(
                id=uuid4(),
                name="user",
                description="User",
                permissions=["document:read"],
                is_system_reserved=False,
                is_active=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            ),
        ]
        mock_role_service.list_roles = AsyncMock(return_value=roles)

        app, client = create_test_app(mock_auth, mock_role_service)

        response = client.get("/api/v1/roles")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "admin"
        assert data[1]["name"] == "user"

    def test_get_role_success(self):
        """Get specific role returns role data."""
        from src.application.use_cases.role_management import RoleService

        role_id = uuid4()
        mock_auth = MagicMock(spec=AuthServicePort)
        mock_role_service = MagicMock(spec=RoleService)

        role = Role(
            id=role_id,
            name="admin",
            description="Admin",
            permissions=["*:*"],
            is_system_reserved=True,
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_role_service.get_role = AsyncMock(return_value=role)

        app, client = create_test_app(mock_auth, mock_role_service)

        response = client.get(f"/api/v1/roles/{role_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "admin"

    def test_update_role_success(self):
        """Update role returns updated role data."""
        from src.application.use_cases.role_management import RoleService

        role_id = uuid4()
        mock_auth = MagicMock(spec=AuthServicePort)
        mock_role_service = MagicMock(spec=RoleService)

        updated_role = Role(
            id=role_id,
            name="editor",
            description="Updated editor",
            permissions=["document:read", "document:write", "document:delete"],
            is_system_reserved=False,
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_role_service.update_role = AsyncMock(return_value=updated_role)

        app, client = create_test_app(mock_auth, mock_role_service)

        response = client.put(
            f"/api/v1/roles/{role_id}",
            json={"name": "editor", "permissions": ["document:read", "document:write", "document:delete"]},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "editor"
        assert "document:delete" in data["permissions"]

    def test_delete_role_success(self):
        """Delete role returns 204 No Content."""
        from src.application.use_cases.role_management import RoleService

        role_id = uuid4()
        mock_auth = MagicMock(spec=AuthServicePort)
        mock_role_service = MagicMock(spec=RoleService)
        mock_role_service.delete_role = AsyncMock(return_value=True)

        app, client = create_test_app(mock_auth, mock_role_service)

        response = client.delete(f"/api/v1/roles/{role_id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT


class TestPermissionEndpoints:
    """Test permission assignment endpoints."""

    def test_assign_permissions_success(self):
        """Assign permissions returns updated role."""
        from src.application.use_cases.role_management import RoleService

        role_id = uuid4()
        mock_auth = MagicMock(spec=AuthServicePort)
        mock_role_service = MagicMock(spec=RoleService)

        role = Role(
            id=role_id,
            name="editor",
            description="Editor",
            permissions=["document:read", "document:write"],
            is_system_reserved=False,
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_role_service.get_role = AsyncMock(return_value=role)
        mock_role_service.update_role = AsyncMock(return_value=role)

        app, client = create_test_app(mock_auth, mock_role_service)

        response = client.post(
            f"/api/v1/roles/{role_id}/permissions",
            json={"role_id": str(role_id), "permissions": ["document:read", "document:write", "document:delete"]},
        )

        assert response.status_code == status.HTTP_200_OK

    def test_revoke_permission_success(self):
        """Revoke permission returns updated role."""
        from src.application.use_cases.role_management import RoleService

        role_id = uuid4()
        mock_auth = MagicMock(spec=AuthServicePort)
        mock_role_service = MagicMock(spec=RoleService)

        role = Role(
            id=role_id,
            name="editor",
            description="Editor",
            permissions=["document:read"],
            is_system_reserved=False,
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_role_service.get_role = AsyncMock(return_value=role)
        mock_role_service.update_role = AsyncMock(return_value=role)

        app, client = create_test_app(mock_auth, mock_role_service)

        response = client.delete(f"/api/v1/roles/{role_id}/permissions/document:write")

        assert response.status_code == status.HTTP_200_OK
