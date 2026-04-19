"""Integration tests for Auth API endpoints using FastAPI TestClient.

Story 1.9: RBAC Permission Management
Task 8: API Endpoint Test Coverage Improvement

Uses FastAPI TestClient to test the actual endpoint code paths.
Uses dependency_overrides for test isolation and auto-cleanup.

Run with: pytest tests/unit/interfaces/api/test_auth_api_integration.py -v
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.infrastructure.security.permission_middleware import get_current_user
from src.interfaces.api.auth import router

# =============================================================================
# Mock Role Object for endpoint attribute access
# =============================================================================


@dataclass
class MockRole:
    """Mock role object with attributes expected by RoleResponse."""

    id: str
    name: str
    description: str
    permissions: list[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class MockUser:
    """Mock user object with attributes expected by UserResponse."""

    id: str
    username: str
    email: str
    roles: list[str]
    is_active: bool


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_admin_user() -> dict[str, Any]:
    """Create mock admin user for dependency override."""
    return {
        "user_id": str(uuid4()),
        "username": "admin",
        "email": "admin@example.com",
        "roles": ["admin"],
        "is_active": True,
    }


@pytest.fixture
def mock_regular_user() -> dict[str, Any]:
    """Create mock regular user for dependency override."""
    return {
        "user_id": str(uuid4()),
        "username": "regularuser",
        "email": "user@example.com",
        "roles": ["user"],
        "is_active": True,
    }


@pytest.fixture
def app() -> FastAPI:
    """Create FastAPI app with auth router."""
    application = FastAPI()
    application.include_router(router)
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create TestClient for API calls (no auth override)."""
    return TestClient(app)


# =============================================================================
# Login Endpoint Integration Tests (lines 155-216)
# =============================================================================


class TestLoginEndpointIntegration:
    """Test login endpoint with TestClient exercising lines 155-216."""

    def test_login_success_with_test_client(self, app, mock_admin_user):
        """Test successful login through TestClient."""
        from src.infrastructure.security.auth_service import AuthServiceImpl

        async def override_get_current_user():
            return mock_admin_user

        app.dependency_overrides[get_current_user] = override_get_current_user
        client = TestClient(app)

        with patch("src.interfaces.api.auth.get_db_session") as mock_session_fn:
            mock_session_fn.return_value.__aenter__ = AsyncMock(return_value=mock_session_fn.return_value)
            mock_session_fn.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch.object(AuthServiceImpl, "authenticate", new_callable=AsyncMock) as mock_auth:
                mock_auth.return_value = {
                    "access_token": "test_access_token",
                    "refresh_token": "test_refresh_token",
                    "token_type": "bearer",
                    "expires_in": 86400,
                    "user": {
                        "id": str(uuid4()),
                        "username": mock_admin_user["username"],
                        "email": mock_admin_user["email"],
                        "roles": mock_admin_user["roles"],
                        "is_active": True,
                    },
                }

                response = client.post(
                    "/api/v1/auth/login",
                    json={"username": "testuser", "password": "password123"},  # pragma: allowlist secret
                )
                assert response.status_code == 200

        app.dependency_overrides.clear()

    def test_login_invalid_credentials_triggers_401(self, app):
        """Test login with invalid credentials triggers 401."""
        from src.infrastructure.security.auth_service import AuthServiceImpl, InvalidCredentialsError

        client = TestClient(app)

        with patch("src.interfaces.api.auth.get_db_session") as mock_session_fn:
            mock_session_fn.return_value.__aenter__ = AsyncMock(return_value=mock_session_fn.return_value)
            mock_session_fn.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch.object(AuthServiceImpl, "authenticate", new_callable=AsyncMock) as mock_auth:
                mock_auth.side_effect = InvalidCredentialsError("Invalid credentials")

                response = client.post(
                    "/api/v1/auth/login",
                    json={"username": "testuser", "password": "wrongpassword"},  # pragma: allowlist secret
                )
                assert response.status_code == 401

    def test_login_account_locked_triggers_423(self, app):
        """Test login with locked account triggers 423."""
        from src.infrastructure.security.auth_service import AccountLockedError, AuthServiceImpl

        client = TestClient(app)

        with patch("src.interfaces.api.auth.get_db_session") as mock_session_fn:
            mock_session_fn.return_value.__aenter__ = AsyncMock(return_value=mock_session_fn.return_value)
            mock_session_fn.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch.object(AuthServiceImpl, "authenticate", new_callable=AsyncMock) as mock_auth:
                mock_auth.side_effect = AccountLockedError("Account locked")

                response = client.post(
                    "/api/v1/auth/login",
                    json={"username": "testuser", "password": "password123"},  # pragma: allowlist secret
                )
                assert response.status_code == 423

    def test_login_user_inactive_triggers_401(self, app):
        """Test login with inactive user triggers 401."""
        from src.infrastructure.security.auth_service import AuthServiceImpl, UserInactiveError

        client = TestClient(app)

        with patch("src.interfaces.api.auth.get_db_session") as mock_session_fn:
            mock_session_fn.return_value.__aenter__ = AsyncMock(return_value=mock_session_fn.return_value)
            mock_session_fn.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch.object(AuthServiceImpl, "authenticate", new_callable=AsyncMock) as mock_auth:
                mock_auth.side_effect = UserInactiveError("User inactive")

                response = client.post(
                    "/api/v1/auth/login",
                    json={"username": "testuser", "password": "password123"},  # pragma: allowlist secret
                )
                assert response.status_code == 401


# =============================================================================
# Refresh Token Endpoint Integration Tests (lines 218-263)
# =============================================================================


class TestRefreshTokenEndpointIntegration:
    """Test refresh_token endpoint with TestClient exercising lines 218-263."""

    def test_refresh_token_success(self, app, mock_admin_user):
        """Test successful refresh token through TestClient."""
        from src.infrastructure.security.auth_service import AuthServiceImpl

        async def override_get_current_user():
            return mock_admin_user

        app.dependency_overrides[get_current_user] = override_get_current_user
        client = TestClient(app)

        with patch("src.interfaces.api.auth.get_db_session") as mock_session_fn:
            mock_session_fn.return_value.__aenter__ = AsyncMock(return_value=mock_session_fn.return_value)
            mock_session_fn.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch.object(AuthServiceImpl, "refresh_token", new_callable=AsyncMock) as mock_refresh:
                mock_refresh.return_value = {
                    "access_token": "new_access_token",
                    "token_type": "bearer",
                    "expires_in": 86400,
                }

                response = client.post(
                    "/api/v1/auth/refresh",
                    data={"refresh_token": "valid_refresh_token"},
                )
                assert response.status_code == 200

        app.dependency_overrides.clear()

    def test_refresh_token_invalid_triggers_401(self, app):
        """Test refresh with invalid token triggers 401."""
        from src.infrastructure.security.auth_service import AuthServiceImpl
        from src.infrastructure.security.jwt_service import InvalidTokenError

        client = TestClient(app)

        with patch("src.interfaces.api.auth.get_db_session") as mock_session_fn:
            mock_session_fn.return_value.__aenter__ = AsyncMock(return_value=mock_session_fn.return_value)
            mock_session_fn.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch.object(AuthServiceImpl, "refresh_token", new_callable=AsyncMock) as mock_refresh:
                mock_refresh.side_effect = InvalidTokenError("Invalid refresh token")

                response = client.post(
                    "/api/v1/auth/refresh",
                    data={"refresh_token": "invalid_token"},
                )
                assert response.status_code == 401


# =============================================================================
# Get Me Endpoint Integration Tests (lines 269-311)
# =============================================================================


class TestGetMeEndpointIntegration:
    """Test get_me endpoint with TestClient exercising lines 269-311."""

    def test_get_me_success(self, app, mock_regular_user):
        """Test successful get_me through TestClient."""
        from src.infrastructure.security.auth_service import AuthServiceImpl

        async def override_get_current_user():
            return mock_regular_user

        app.dependency_overrides[get_current_user] = override_get_current_user
        client = TestClient(app)

        with patch("src.interfaces.api.auth.get_db_session") as mock_session_fn:
            mock_session_fn.return_value.__aenter__ = AsyncMock(return_value=mock_session_fn.return_value)
            mock_session_fn.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch.object(AuthServiceImpl, "get_user_by_id", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = {
                    "id": str(uuid4()),
                    "username": mock_regular_user["username"],
                    "email": mock_regular_user["email"],
                    "roles": mock_regular_user["roles"],
                    "is_active": True,
                }

                response = client.get("/api/v1/auth/me")
                assert response.status_code == 200

        app.dependency_overrides.clear()

    def test_get_me_user_not_found_triggers_404(self, app, mock_regular_user):
        """Test get_me with non-existent user triggers 404."""
        from src.infrastructure.security.auth_service import AuthServiceImpl

        async def override_get_current_user():
            return mock_regular_user

        app.dependency_overrides[get_current_user] = override_get_current_user
        client = TestClient(app)

        with patch("src.interfaces.api.auth.get_db_session") as mock_session_fn:
            mock_session_fn.return_value.__aenter__ = AsyncMock(return_value=mock_session_fn.return_value)
            mock_session_fn.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch.object(AuthServiceImpl, "get_user_by_id", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = None

                response = client.get("/api/v1/auth/me")
                assert response.status_code == 404

        app.dependency_overrides.clear()


# =============================================================================
# Role CRUD Endpoint Integration Tests (admin only endpoints)
# Paths: /api/v1/roles (not /api/v1/auth/roles)
# =============================================================================


class TestRoleCRUDEndpointIntegration:
    """Test role CRUD endpoints with TestClient - admin only."""

    def test_list_roles_success(self, app, mock_admin_user):
        """Test list_roles endpoint success."""
        with patch("src.interfaces.api.auth.RoleService") as mock_role_service:
            mock_service_instance = MagicMock()
            mock_service_instance.get_all_roles = AsyncMock(
                return_value=[
                    MockRole(
                        id=str(uuid4()),
                        name="admin",
                        description="Admin role",
                        permissions=["*: *"],
                        is_active=True,
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    )
                ]
            )
            mock_role_service.return_value = mock_service_instance

            async def override_get_current_user():
                return mock_admin_user

            app.dependency_overrides[get_current_user] = override_get_current_user
            client = TestClient(app)

            with patch("src.interfaces.api.auth.get_db_session") as mock_session_fn:
                mock_session_fn.return_value.__aenter__ = AsyncMock(return_value=mock_session_fn.return_value)
                mock_session_fn.return_value.__aexit__ = AsyncMock(return_value=None)

                response = client.get("/api/v1/roles")
                assert response.status_code == 200

            app.dependency_overrides.clear()

    def test_create_role_success(self, app, mock_admin_user):
        """Test create_role endpoint success."""
        with patch("src.interfaces.api.auth.RoleService") as mock_role_service:
            mock_service_instance = MagicMock()
            mock_service_instance.create_role = AsyncMock(
                return_value=MockRole(
                    id=str(uuid4()),
                    name="new_role",
                    description="New role",
                    permissions=["document:read"],
                    is_active=True,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
            mock_role_service.return_value = mock_service_instance

            async def override_get_current_user():
                return mock_admin_user

            app.dependency_overrides[get_current_user] = override_get_current_user
            client = TestClient(app)

            with patch("src.interfaces.api.auth.get_db_session") as mock_session_fn:
                mock_session_fn.return_value.__aenter__ = AsyncMock(return_value=mock_session_fn.return_value)
                mock_session_fn.return_value.__aexit__ = AsyncMock(return_value=None)

                response = client.post(
                    "/api/v1/roles",
                    json={
                        "name": "new_role",
                        "description": "New role",
                        "permissions": ["document:read"],
                    },
                )
                assert response.status_code == 201

            app.dependency_overrides.clear()

    def test_create_role_conflict_triggers_409(self, app, mock_admin_user):
        """Test create_role with duplicate name triggers 409."""
        from src.infrastructure.security.role_service import RoleAlreadyExistsError

        with patch("src.interfaces.api.auth.RoleService") as mock_role_service:
            mock_service_instance = MagicMock()
            mock_service_instance.create_role = AsyncMock(side_effect=RoleAlreadyExistsError("Role already exists"))
            mock_role_service.return_value = mock_service_instance

            async def override_get_current_user():
                return mock_admin_user

            app.dependency_overrides[get_current_user] = override_get_current_user
            client = TestClient(app)

            with patch("src.interfaces.api.auth.get_db_session") as mock_session_fn:
                mock_session_fn.return_value.__aenter__ = AsyncMock(return_value=mock_session_fn.return_value)
                mock_session_fn.return_value.__aexit__ = AsyncMock(return_value=None)

                response = client.post(
                    "/api/v1/roles",
                    json={
                        "name": "existing_role",
                        "description": "Existing role",
                        "permissions": ["document:read"],
                    },
                )
                assert response.status_code == 409

            app.dependency_overrides.clear()

    def test_get_role_success(self, app, mock_admin_user):
        """Test get_role endpoint success."""
        role_id = uuid4()

        with patch("src.interfaces.api.auth.RoleService") as mock_role_service:
            mock_service_instance = MagicMock()
            mock_service_instance.get_role_by_id = AsyncMock(
                return_value=MockRole(
                    id=str(role_id),
                    name="admin",
                    description="Admin role",
                    permissions=["*: *"],
                    is_active=True,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
            mock_role_service.return_value = mock_service_instance

            async def override_get_current_user():
                return mock_admin_user

            app.dependency_overrides[get_current_user] = override_get_current_user
            client = TestClient(app)

            with patch("src.interfaces.api.auth.get_db_session") as mock_session_fn:
                mock_session_fn.return_value.__aenter__ = AsyncMock(return_value=mock_session_fn.return_value)
                mock_session_fn.return_value.__aexit__ = AsyncMock(return_value=None)

                response = client.get(f"/api/v1/roles/{role_id}")
                assert response.status_code == 200

            app.dependency_overrides.clear()

    def test_get_role_not_found_triggers_404(self, app, mock_admin_user):
        """Test get_role with non-existent role triggers 404."""

        role_id = uuid4()

        async def override_get_current_user():
            return mock_admin_user

        app.dependency_overrides[get_current_user] = override_get_current_user
        client = TestClient(app)

        with patch("src.interfaces.api.auth.get_db_session") as mock_session_fn:
            mock_session_fn.return_value.__aenter__ = AsyncMock(return_value=mock_session_fn.return_value)
            mock_session_fn.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch("src.interfaces.api.auth.RoleService") as mock_role_service:
                mock_service_instance = MagicMock()
                mock_service_instance.get_role_by_id = AsyncMock(return_value=None)
                mock_role_service.return_value = mock_service_instance

                response = client.get(f"/api/v1/roles/{role_id}")
                assert response.status_code == 404

        app.dependency_overrides.clear()

    def test_update_role_success(self, app, mock_admin_user):
        """Test update_role endpoint success."""
        role_id = uuid4()

        with patch("src.interfaces.api.auth.RoleService") as mock_role_service:
            mock_service_instance = MagicMock()
            mock_service_instance.update_role = AsyncMock(
                return_value=MockRole(
                    id=str(role_id),
                    name="updated_role",
                    description="Updated role",
                    permissions=["document:read", "document:write"],
                    is_active=True,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
            mock_role_service.return_value = mock_service_instance

            async def override_get_current_user():
                return mock_admin_user

            app.dependency_overrides[get_current_user] = override_get_current_user
            client = TestClient(app)

            with patch("src.interfaces.api.auth.get_db_session") as mock_session_fn:
                mock_session_fn.return_value.__aenter__ = AsyncMock(return_value=mock_session_fn.return_value)
                mock_session_fn.return_value.__aexit__ = AsyncMock(return_value=None)

                response = client.put(
                    f"/api/v1/roles/{role_id}",
                    json={
                        "name": "updated_role",
                        "description": "Updated role",
                        "permissions": ["document:read", "document:write"],
                    },
                )
                assert response.status_code == 200

            app.dependency_overrides.clear()

    def test_update_role_not_found_triggers_404(self, app, mock_admin_user):
        """Test update_role with non-existent role triggers 404."""
        from src.infrastructure.security.role_service import RoleNotFoundError

        role_id = uuid4()

        with patch("src.interfaces.api.auth.RoleService") as mock_role_service:
            mock_service_instance = MagicMock()
            mock_service_instance.update_role = AsyncMock(side_effect=RoleNotFoundError("Role not found"))
            mock_role_service.return_value = mock_service_instance

            async def override_get_current_user():
                return mock_admin_user

            app.dependency_overrides[get_current_user] = override_get_current_user
            client = TestClient(app)

            with patch("src.interfaces.api.auth.get_db_session") as mock_session_fn:
                mock_session_fn.return_value.__aenter__ = AsyncMock(return_value=mock_session_fn.return_value)
                mock_session_fn.return_value.__aexit__ = AsyncMock(return_value=None)

                response = client.put(
                    f"/api/v1/roles/{role_id}",
                    json={
                        "name": "updated_role",
                        "description": "Updated role",
                        "permissions": ["document:read"],
                    },
                )
                assert response.status_code == 404

            app.dependency_overrides.clear()

    def test_update_role_conflict_triggers_409(self, app, mock_admin_user):
        """Test update_role with name conflict triggers 409."""
        from src.infrastructure.security.role_service import RoleAlreadyExistsError

        role_id = uuid4()

        with patch("src.interfaces.api.auth.RoleService") as mock_role_service:
            mock_service_instance = MagicMock()
            mock_service_instance.update_role = AsyncMock(side_effect=RoleAlreadyExistsError("Role name conflicts"))
            mock_role_service.return_value = mock_service_instance

            async def override_get_current_user():
                return mock_admin_user

            app.dependency_overrides[get_current_user] = override_get_current_user
            client = TestClient(app)

            with patch("src.interfaces.api.auth.get_db_session") as mock_session_fn:
                mock_session_fn.return_value.__aenter__ = AsyncMock(return_value=mock_session_fn.return_value)
                mock_session_fn.return_value.__aexit__ = AsyncMock(return_value=None)

                response = client.put(
                    f"/api/v1/roles/{role_id}",
                    json={
                        "name": "conflicting_name",
                        "description": "Updated role",
                        "permissions": ["document:read"],
                    },
                )
                assert response.status_code == 409

            app.dependency_overrides.clear()

    def test_delete_role_success(self, app, mock_admin_user):
        """Test delete_role endpoint success."""
        role_id = uuid4()

        with patch("src.interfaces.api.auth.RoleService") as mock_role_service:
            mock_service_instance = MagicMock()
            mock_service_instance.delete_role = AsyncMock(return_value=None)
            mock_role_service.return_value = mock_service_instance

            async def override_get_current_user():
                return mock_admin_user

            app.dependency_overrides[get_current_user] = override_get_current_user
            client = TestClient(app)

            with patch("src.interfaces.api.auth.get_db_session") as mock_session_fn:
                mock_session_fn.return_value.__aenter__ = AsyncMock(return_value=mock_session_fn.return_value)
                mock_session_fn.return_value.__aexit__ = AsyncMock(return_value=None)

                response = client.delete(f"/api/v1/roles/{role_id}")
                assert response.status_code == 204

            app.dependency_overrides.clear()

    def test_delete_role_not_found_triggers_404(self, app, mock_admin_user):
        """Test delete_role with non-existent role triggers 404."""
        from src.infrastructure.security.role_service import RoleNotFoundError

        role_id = uuid4()

        with patch("src.interfaces.api.auth.RoleService") as mock_role_service:
            mock_service_instance = MagicMock()
            mock_service_instance.delete_role = AsyncMock(side_effect=RoleNotFoundError("Role not found"))
            mock_role_service.return_value = mock_service_instance

            async def override_get_current_user():
                return mock_admin_user

            app.dependency_overrides[get_current_user] = override_get_current_user
            client = TestClient(app)

            with patch("src.interfaces.api.auth.get_db_session") as mock_session_fn:
                mock_session_fn.return_value.__aenter__ = AsyncMock(return_value=mock_session_fn.return_value)
                mock_session_fn.return_value.__aexit__ = AsyncMock(return_value=None)

                response = client.delete(f"/api/v1/roles/{role_id}")
                assert response.status_code == 404

            app.dependency_overrides.clear()


# =============================================================================
# Permission Assignment Endpoint Integration Tests (admin only)
# Note: assign_permission returns 204 No Content, not 200
# =============================================================================


class TestPermissionEndpointIntegration:
    """Test permission assignment endpoints with TestClient - admin only."""

    def test_assign_permission_success(self, app, mock_admin_user):
        """Test assign_permission endpoint success."""
        role_id = uuid4()

        with patch("src.interfaces.api.auth.RoleService") as mock_role_service:
            mock_service_instance = MagicMock()
            mock_service_instance.assign_permission_to_role = AsyncMock(return_value=None)
            mock_role_service.return_value = mock_service_instance

            async def override_get_current_user():
                return mock_admin_user

            app.dependency_overrides[get_current_user] = override_get_current_user
            client = TestClient(app)

            with patch("src.interfaces.api.auth.get_db_session") as mock_session_fn:
                mock_session_fn.return_value.__aenter__ = AsyncMock(return_value=mock_session_fn.return_value)
                mock_session_fn.return_value.__aexit__ = AsyncMock(return_value=None)

                response = client.post(
                    f"/api/v1/roles/{role_id}/permissions",
                    json={"permission": "document:write"},
                )
                # Endpoint returns 204 No Content
                assert response.status_code == 204

            app.dependency_overrides.clear()

    def test_assign_permission_role_not_found_triggers_404(self, app, mock_admin_user):
        """Test assign_permission to non-existent role triggers 404."""
        from src.infrastructure.security.role_service import RoleNotFoundError

        role_id = uuid4()

        with patch("src.interfaces.api.auth.RoleService") as mock_role_service:
            mock_service_instance = MagicMock()
            mock_service_instance.assign_permission_to_role = AsyncMock(side_effect=RoleNotFoundError("Role not found"))
            mock_role_service.return_value = mock_service_instance

            async def override_get_current_user():
                return mock_admin_user

            app.dependency_overrides[get_current_user] = override_get_current_user
            client = TestClient(app)

            with patch("src.interfaces.api.auth.get_db_session") as mock_session_fn:
                mock_session_fn.return_value.__aenter__ = AsyncMock(return_value=mock_session_fn.return_value)
                mock_session_fn.return_value.__aexit__ = AsyncMock(return_value=None)

                response = client.post(
                    f"/api/v1/roles/{role_id}/permissions",
                    json={"permission": "document:write"},
                )
                assert response.status_code == 404

            app.dependency_overrides.clear()

    def test_revoke_permission_success(self, app, mock_admin_user):
        """Test revoke_permission endpoint success."""
        role_id = uuid4()

        with patch("src.interfaces.api.auth.RoleService") as mock_role_service:
            mock_service_instance = MagicMock()
            mock_service_instance.revoke_permission_from_role = AsyncMock(return_value=None)
            mock_role_service.return_value = mock_service_instance

            async def override_get_current_user():
                return mock_admin_user

            app.dependency_overrides[get_current_user] = override_get_current_user
            client = TestClient(app)

            with patch("src.interfaces.api.auth.get_db_session") as mock_session_fn:
                mock_session_fn.return_value.__aenter__ = AsyncMock(return_value=mock_session_fn.return_value)
                mock_session_fn.return_value.__aexit__ = AsyncMock(return_value=None)

                response = client.delete(
                    f"/api/v1/roles/{role_id}/permissions/document:write",
                )
                assert response.status_code == 204

            app.dependency_overrides.clear()

    def test_revoke_permission_role_not_found_triggers_404(self, app, mock_admin_user):
        """Test revoke_permission from non-existent role triggers 404."""
        from src.infrastructure.security.role_service import RoleNotFoundError

        role_id = uuid4()

        with patch("src.interfaces.api.auth.RoleService") as mock_role_service:
            mock_service_instance = MagicMock()
            mock_service_instance.revoke_permission_from_role = AsyncMock(side_effect=RoleNotFoundError("Role not found"))
            mock_role_service.return_value = mock_service_instance

            async def override_get_current_user():
                return mock_admin_user

            app.dependency_overrides[get_current_user] = override_get_current_user
            client = TestClient(app)

            with patch("src.interfaces.api.auth.get_db_session") as mock_session_fn:
                mock_session_fn.return_value.__aenter__ = AsyncMock(return_value=mock_session_fn.return_value)
                mock_session_fn.return_value.__aexit__ = AsyncMock(return_value=None)

                response = client.delete(
                    f"/api/v1/roles/{role_id}/permissions/document:write",
                )
                assert response.status_code == 404

            app.dependency_overrides.clear()


# =============================================================================
# Password Validation Endpoint Integration Test (lines 651-676)
# =============================================================================


class TestPasswordValidationEndpointIntegration:
    """Test validate-password endpoint with TestClient exercising lines 651-676."""

    def test_validate_password_valid(self, client):
        """Test validate-password with strong password."""
        response = client.post(
            "/api/v1/auth/validate-password",
            data={"password": "StrongPass123!"},  # pragma: allowlist secret
        )
        assert response.status_code == 200

    def test_validate_password_invalid(self, client):
        """Test validate-password with weak password."""
        response = client.post(
            "/api/v1/auth/validate-password",
            data={"password": "weak"},  # pragma: allowlist secret
        )
        assert response.status_code == 200
