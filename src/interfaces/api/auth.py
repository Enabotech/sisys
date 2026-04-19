"""Authentication and Authorization API endpoints.

FastAPI routes for:
- POST /api/v1/auth/login - User login
- POST /api/v1/auth/refresh - Refresh token
- GET /api/v1/auth/me - Get current user info

Role management:
- POST /api/v1/roles - Create role
- GET /api/v1/roles - List roles
- GET /api/v1/roles/{role_id} - Get role
- PUT /api/v1/roles/{role_id} - Update role
- DELETE /api/v1/roles/{role_id} - Delete role
- POST /api/v1/roles/{role_id}/permissions - Assign permission
- DELETE /api/v1/roles/{role_id}/permissions/{permission} - Revoke permission
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Form, HTTPException, status
from pydantic import BaseModel, Field

from src.infrastructure.security.auth_service import (
    AccountLockedError,
    AuthServiceImpl,
    InvalidCredentialsError,
    UserInactiveError,
)
from src.infrastructure.security.encryption_service import EncryptionService
from src.infrastructure.security.jwt_service import InvalidTokenError
from src.infrastructure.security.permission_middleware import (
    get_current_user,
    require_role,
)
from src.infrastructure.security.role_service import RoleAlreadyExistsError, RoleNotFoundError, RoleService
from src.infrastructure.storage.postgresql.engine import DatabaseEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["authentication"])


# =============================================================================
# Request/Response Models
# =============================================================================


class LoginRequest(BaseModel):
    """Login request body."""

    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """Token response body."""

    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    """User info response."""

    id: str
    username: str
    email: str
    roles: list[str]
    is_active: bool


class LoginResponse(BaseModel):
    """Login response body."""

    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class RoleCreate(BaseModel):
    """Role creation request."""

    name: str = Field(..., min_length=1, max_length=50)
    description: str | None = None
    permissions: list[str] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    """Role update request."""

    name: str | None = None
    description: str | None = None


class RoleResponse(BaseModel):
    """Role response."""

    id: str
    name: str
    description: str | None
    permissions: list[str]
    is_active: bool
    created_at: datetime | None
    updated_at: datetime | None


class PermissionAssign(BaseModel):
    """Permission assignment request."""

    permission: str = Field(..., pattern=r"^[^:]+:[^:]+$")


class ErrorResponse(BaseModel):
    """Error response."""

    detail: str


# =============================================================================
# Authentication Endpoints
# =============================================================================


# Global database engine instance for dependency injection
_db_engine: DatabaseEngine | None = None


def get_database_engine() -> DatabaseEngine:
    """Get the global DatabaseEngine instance for dependency injection.

    Returns:
        DatabaseEngine: The global database engine instance.
    """
    global _db_engine
    if _db_engine is None:
        _db_engine = DatabaseEngine()
    return _db_engine


def get_db_session():
    """Get database session for dependency injection."""
    engine = get_database_engine()
    return engine.get_async_session()


@router.post(
    "/auth/login",
    response_model=LoginResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
        423: {"model": ErrorResponse, "description": "Account locked"},
    },
    summary="User login",
    description="Authenticate user with username and password, returns JWT tokens.",
)
async def login(
    request: LoginRequest,
    session=Depends(get_db_session),
) -> LoginResponse:
    """Authenticate user and return JWT tokens.

    Args:
        request: Login credentials.
        session: Database session.

    Returns:
        LoginResponse: Access token, refresh token, and user info.

    Raises:
        HTTPException: 401 if credentials invalid, 423 if account locked.
    """
    from src.infrastructure.storage.postgresql.role_repository import RoleRepository
    from src.infrastructure.storage.postgresql.user_repository import UserRepository

    async with session:
        user_repo = UserRepository(session)
        role_repo = RoleRepository(session)

        auth_service = AuthServiceImpl(user_repo, role_repo)

        try:
            result = await auth_service.authenticate(request.username, request.password)

            return LoginResponse(
                access_token=result["access_token"],
                refresh_token=result.get("refresh_token"),
                token_type=result["token_type"],
                expires_in=result["expires_in"],
                user=UserResponse(**result["user"]),
            )

        except InvalidCredentialsError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
            ) from e
        except AccountLockedError as e:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=str(e),
            ) from e
        except UserInactiveError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
            ) from e


@router.post(
    "/auth/refresh",
    response_model=TokenResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid refresh token"},
    },
    summary="Refresh access token",
    description="Use refresh token to get new access token.",
)
async def refresh_token(
    refresh_token: str = Form(..., description="Valid refresh token"),
    session=Depends(get_db_session),
) -> TokenResponse:
    """Refresh access token using refresh token.

    Args:
        refresh_token: Valid refresh token from login response.
        session: Database session.

    Returns:
        TokenResponse: New access token and optional refresh token.

    Raises:
        HTTPException: 401 if refresh token invalid.
    """
    from src.infrastructure.storage.postgresql.role_repository import RoleRepository
    from src.infrastructure.storage.postgresql.user_repository import UserRepository

    async with session:
        user_repo = UserRepository(session)
        role_repo = RoleRepository(session)

        auth_service = AuthServiceImpl(user_repo, role_repo)

        try:
            result = await auth_service.refresh_token(refresh_token)

            return TokenResponse(
                access_token=result["access_token"],
                refresh_token=result.get("refresh_token"),
                token_type=result["token_type"],
                expires_in=result["expires_in"],
            )

        except InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
            ) from e


@router.get(
    "/auth/me",
    response_model=UserResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
    summary="Get current user",
    description="Get current authenticated user's information.",
)
async def get_me(
    current_user: dict = Depends(get_current_user),
    session=Depends(get_db_session),
) -> UserResponse:
    """Get current authenticated user's information.

    Args:
        current_user: Current user from JWT.
        session: Database session.

    Returns:
        UserResponse: Current user's information.
    """
    from uuid import UUID

    from src.infrastructure.storage.postgresql.role_repository import RoleRepository
    from src.infrastructure.storage.postgresql.user_repository import UserRepository

    async with session:
        user_repo = UserRepository(session)
        role_repo = RoleRepository(session)

        auth_service = AuthServiceImpl(user_repo, role_repo)

        user_id = UUID(current_user["user_id"])
        user_info = await auth_service.get_user_by_id(user_id)

        if user_info is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        return UserResponse(**user_info)


# =============================================================================
# Role Management Endpoints
# =============================================================================


@router.post(
    "/roles",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        409: {"model": ErrorResponse, "description": "Role already exists"},
    },
    summary="Create role",
    description="Create a new role (admin only).",
)
async def create_role(
    request: RoleCreate,
    current_user: dict = Depends(require_role("admin")),
    session=Depends(get_db_session),
) -> RoleResponse:
    """Create a new role.

    Args:
        request: Role creation data.
        current_user: Current authenticated admin user.
        session: Database session.

    Returns:
        RoleResponse: Created role information.

    Raises:
        HTTPException: 403 if not admin, 409 if role exists.
    """
    async with session:
        role_service = RoleService(session)

        try:
            role = await role_service.create_role(
                name=request.name,
                description=request.description,
                permissions=request.permissions,
            )

            return RoleResponse(
                id=str(role.id),
                name=role.name,
                description=role.description,
                permissions=role.permissions,
                is_active=role.is_active,
                created_at=role.created_at,
                updated_at=role.updated_at,
            )

        except RoleAlreadyExistsError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            ) from e


@router.get(
    "/roles",
    response_model=list[RoleResponse],
    summary="List roles",
    description="Get all roles.",
)
async def list_roles(
    current_user: dict = Depends(get_current_user),
    session=Depends(get_db_session),
) -> list[RoleResponse]:
    """Get all roles.

    Args:
        current_user: Current authenticated user.
        session: Database session.

    Returns:
        list[RoleResponse]: List of all roles.
    """
    async with session:
        role_service = RoleService(session)

        roles = await role_service.get_all_roles()

        return [
            RoleResponse(
                id=str(role.id),
                name=role.name,
                description=role.description,
                permissions=role.permissions,
                is_active=role.is_active,
                created_at=role.created_at,
                updated_at=role.updated_at,
            )
            for role in roles
        ]


@router.get(
    "/roles/{role_id}",
    response_model=RoleResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Role not found"},
    },
    summary="Get role",
    description="Get a specific role by ID.",
)
async def get_role(
    role_id: UUID,
    current_user: dict = Depends(get_current_user),
    session=Depends(get_db_session),
) -> RoleResponse:
    """Get a specific role by ID.

    Args:
        role_id: Role's UUID.
        current_user: Current authenticated user.
        session: Database session.

    Returns:
        RoleResponse: Role information.

    Raises:
        HTTPException: 404 if role not found.
    """
    async with session:
        role_service = RoleService(session)

        role = await role_service.get_role_by_id(role_id)

        if role is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role '{role_id}' not found",
            )

        return RoleResponse(
            id=str(role.id),
            name=role.name,
            description=role.description,
            permissions=role.permissions,
            is_active=role.is_active,
            created_at=role.created_at,
            updated_at=role.updated_at,
        )


@router.put(
    "/roles/{role_id}",
    response_model=RoleResponse,
    responses={
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Role not found"},
        409: {"model": ErrorResponse, "description": "Role name conflict"},
    },
    summary="Update role",
    description="Update a role (admin only).",
)
async def update_role(
    role_id: UUID,
    request: RoleUpdate,
    current_user: dict = Depends(require_role("admin")),
    session=Depends(get_db_session),
) -> RoleResponse:
    """Update a role.

    Args:
        role_id: Role's UUID.
        request: Role update data.
        current_user: Current authenticated admin user.
        session: Database session.

    Returns:
        RoleResponse: Updated role information.

    Raises:
        HTTPException: 403 if not admin, 404 if role not found, 409 if name conflict.
    """
    async with session:
        role_service = RoleService(session)

        try:
            role = await role_service.update_role(
                role_id=role_id,
                name=request.name,
                description=request.description,
            )

            return RoleResponse(
                id=str(role.id),
                name=role.name,
                description=role.description,
                permissions=role.permissions,
                is_active=role.is_active,
                created_at=role.created_at,
                updated_at=role.updated_at,
            )

        except RoleNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            ) from e
        except RoleAlreadyExistsError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            ) from e


@router.delete(
    "/roles/{role_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Role not found"},
    },
    summary="Delete role",
    description="Soft delete a role (admin only).",
)
async def delete_role(
    role_id: UUID,
    current_user: dict = Depends(require_role("admin")),
    session=Depends(get_db_session),
) -> None:
    """Soft delete a role.

    Args:
        role_id: Role's UUID.
        current_user: Current authenticated admin user.
        session: Database session.

    Raises:
        HTTPException: 403 if not admin, 404 if role not found.
    """
    async with session:
        role_service = RoleService(session)

        try:
            await role_service.delete_role(role_id)

        except RoleNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            ) from e


@router.post(
    "/roles/{role_id}/permissions",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Role not found"},
    },
    summary="Assign permission to role",
    description="Assign a permission to a role (admin only).",
)
async def assign_permission(
    role_id: UUID,
    request: PermissionAssign,
    current_user: dict = Depends(require_role("admin")),
    session=Depends(get_db_session),
) -> None:
    """Assign a permission to a role.

    Args:
        role_id: Role's UUID.
        request: Permission assignment data.
        current_user: Current authenticated admin user.
        session: Database session.

    Raises:
        HTTPException: 403 if not admin, 404 if role not found.
    """
    async with session:
        role_service = RoleService(session)

        try:
            await role_service.assign_permission_to_role(role_id, request.permission)

        except RoleNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            ) from e


@router.delete(
    "/roles/{role_id}/permissions/{permission}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Role not found"},
    },
    summary="Revoke permission from role",
    description="Revoke a permission from a role (admin only).",
)
async def revoke_permission(
    role_id: UUID,
    permission: str,
    current_user: dict = Depends(require_role("admin")),
    session=Depends(get_db_session),
) -> None:
    """Revoke a permission from a role.

    Args:
        role_id: Role's UUID.
        permission: Permission string to revoke.
        current_user: Current authenticated admin user.
        session: Database session.

    Raises:
        HTTPException: 403 if not admin, 404 if role not found.
    """
    async with session:
        role_service = RoleService(session)

        try:
            await role_service.revoke_permission_from_role(role_id, permission)

        except RoleNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            ) from e


# =============================================================================
# Password Validation Endpoint
# =============================================================================


@router.post(
    "/auth/validate-password",
    response_model=dict[str, Any],
    summary="Validate password strength",
    description="Check if password meets complexity requirements.",
)
async def validate_password(
    password: str = Body(..., min_length=1),
) -> dict[str, Any]:
    """Validate password strength.

    Args:
        password: Password to validate.

    Returns:
        dict: Validation result with errors if any.
    """
    encryption_service = EncryptionService()

    errors = encryption_service.validate_password_strength(password)

    return {
        "valid": len(errors) == 0,
        "errors": errors,
    }
