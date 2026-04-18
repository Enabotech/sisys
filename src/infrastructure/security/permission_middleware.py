"""Permission Middleware — FastAPI dependency for permission validation.

Provides FastAPI dependencies for permission checking and authorization.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.infrastructure.security.jwt_service import (
    InvalidTokenError,
    JWTService,
    get_jwt_service,
)
from src.infrastructure.security.permission_service import PermissionServiceImpl
from src.infrastructure.storage.postgresql.engine import DatabaseEngine

if TYPE_CHECKING:
    pass


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


# HTTP Bearer scheme for JWT extraction
bearer_scheme = HTTPBearer(auto_error=False)


class PermissionDeniedError(Exception):
    """Permission denied exception."""

    pass


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    jwt_service: JWTService = Depends(get_jwt_service),
) -> dict[str, Any]:
    """FastAPI dependency to get current authenticated user from JWT.

    Args:
        credentials: HTTP Bearer credentials.
        jwt_service: JWT service instance.

    Returns:
        dict: User information from token payload.

    Raises:
        HTTPException: 401 if token is missing or invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt_service.verify_token(credentials.credentials)
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "user_id": payload.get("sub"),
        "username": payload.get("username"),
        "roles": payload.get("roles", []),
    }


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    jwt_service: JWTService = Depends(get_jwt_service),
) -> dict[str, Any] | None:
    """FastAPI dependency to get current user (optional).

    Unlike get_current_user, this returns None if no token is provided
    instead of raising an exception.

    Args:
        credentials: HTTP Bearer credentials (optional).
        jwt_service: JWT service instance.

    Returns:
        dict | None: User information or None if not authenticated.
    """
    if credentials is None:
        return None

    try:
        payload = jwt_service.verify_token(credentials.credentials)
    except InvalidTokenError:
        return None

    if payload.get("type") != "access":
        return None

    return {
        "user_id": payload.get("sub"),
        "username": payload.get("username"),
        "roles": payload.get("roles", []),
    }


def require_permission(resource: str, action: str) -> Callable:
    """Create a FastAPI dependency that checks a specific permission.

    Args:
        resource: Resource name (e.g., "document", "tool").
        action: Action name (e.g., "read", "write", "delete").

    Returns:
        Callable: FastAPI dependency function.

    Example:
        @app.get("/documents/{doc_id}")
        async def get_document(
            doc_id: str,
            user: dict = Depends(require_permission("document", "read")),
        ):
            ...
    """

    async def permission_check(
        current_user: dict[str, Any] = Depends(get_current_user),
        engine: DatabaseEngine = Depends(get_database_engine),
    ) -> dict[str, Any]:
        """Check if current user has the required permission.

        Args:
            current_user: Current authenticated user from JWT.
            engine: Database engine instance via dependency injection.

        Returns:
            dict: Current user info if permission check passes.

        Raises:
            HTTPException: 403 if permission denied.
        """
        from uuid import UUID

        user_id = UUID(current_user["user_id"])
        roles = current_user.get("roles", [])

        # Admin role has all permissions
        if "admin" in roles:
            return current_user

        async with engine.get_async_session() as session:
            permission_service = PermissionServiceImpl(session)

            if not await permission_service.check_permission(user_id, resource, action):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions: {resource}:{action}",
                )

        return current_user

    return permission_check


def require_role(role_name: str) -> Callable:
    """Create a FastAPI dependency that requires a specific role.

    Args:
        role_name: Required role name.

    Returns:
        Callable: FastAPI dependency function.

    Example:
        @app.post("/roles")
        async def create_role(
            role_data: RoleCreate,
            user: dict = Depends(require_role("admin")),
        ):
            ...
    """

    async def role_check(
        current_user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        """Check if current user has the required role.

        Args:
            current_user: Current authenticated user from JWT.

        Returns:
            dict: Current user info if role check passes.

        Raises:
            HTTPException: 403 if role requirement not met.
        """
        roles = current_user.get("roles", [])

        if role_name not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {role_name}",
            )

        return current_user

    return role_check


def require_any_role(role_names: list[str]) -> Callable:
    """Create a FastAPI dependency that requires any of the specified roles.

    Args:
        role_names: List of acceptable role names.

    Returns:
        Callable: FastAPI dependency function.
    """

    async def role_check(
        current_user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        """Check if current user has any of the required roles.

        Args:
            current_user: Current authenticated user from JWT.

        Returns:
            dict: Current user info if role check passes.

        Raises:
            HTTPException: 403 if no required role is present.
        """
        roles = current_user.get("roles", [])

        if not any(role in roles for role in role_names):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required one of roles: {', '.join(role_names)}",
            )

        return current_user

    return role_check


def require_all_roles(role_names: list[str]) -> Callable:
    """Create a FastAPI dependency that requires all specified roles.

    Args:
        role_names: List of required role names.

    Returns:
        Callable: FastAPI dependency function.
    """

    async def role_check(
        current_user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        """Check if current user has all required roles.

        Args:
            current_user: Current authenticated user from JWT.

        Returns:
            dict: Current user info if all roles are present.

        Raises:
            HTTPException: 403 if any required role is missing.
        """
        roles = current_user.get("roles", [])

        missing_roles = [role for role in role_names if role not in roles]
        if missing_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required roles: {', '.join(missing_roles)}",
            )

        return current_user

    return role_check
