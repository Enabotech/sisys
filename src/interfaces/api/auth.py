"""Auth API Routes - 认证授权 API 路由.

提供用户认证、角色管理的 REST API 端点。
遵循六边形架构：接口层仅依赖应用层用例和领域端口。
"""

from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field

from src.application.use_cases.role_management import (
    CannotDeleteSystemRoleError,
    RoleAlreadyExistsError,
    RoleNotFoundError,
    RoleService,
)
from src.domain.ports.auth_service import AuthenticationError, AuthServicePort
from src.domain.ports.permission_service import PermissionServicePort
from src.domain.value_objects.token_payload import TokenPayload


# Request/Response Models
class LoginRequest(BaseModel):
    """登录请求模型."""

    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """Token 响应模型."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserResponse"


class UserResponse(BaseModel):
    """用户信息响应模型."""

    id: str
    username: str
    roles: list[str]


class RefreshTokenRequest(BaseModel):
    """刷新 Token 请求模型."""

    refresh_token: str


class CreateRoleRequest(BaseModel):
    """创建角色请求模型."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="")
    permissions: list[str] = Field(default_factory=list)
    is_system_reserved: bool = False


class UpdateRoleRequest(BaseModel):
    """更新角色请求模型."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    permissions: list[str] | None = None
    is_active: bool | None = None


class RoleResponse(BaseModel):
    """角色响应模型."""

    id: str
    name: str
    description: str
    permissions: list[str]
    is_system_reserved: bool
    is_active: bool
    created_at: str | None = None
    updated_at: str | None = None


class AssignPermissionRequest(BaseModel):
    """分配权限请求模型."""

    role_id: str
    permissions: list[str]


class ErrorResponse(BaseModel):
    """错误响应模型."""

    detail: str


# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user_dependency(
    auth_service: AuthServicePort,
) -> Callable:
    """创建 get_current_user 依赖工厂.

    Args:
        auth_service: 认证服务实例

    Returns:
        依赖函数
    """

    async def get_current_user(
        token: str | None = Depends(oauth2_scheme),
    ) -> TokenPayload:
        """获取当前认证用户.

        Args:
            token: OAuth2 Bearer token

        Returns:
            TokenPayload 领域值对象

        Raises:
            HTTPException: 用户未认证
        """
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            return await auth_service.verify_token(token)
        except AuthenticationError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return get_current_user


def create_auth_router(
    auth_service: AuthServicePort,
    role_service: RoleService,
    permission_service: PermissionServicePort | None = None,
    get_current_user_override: Callable | None = None,
) -> APIRouter:
    """创建认证路由。

    Args:
        auth_service: 认证服务
        role_service: 角色服务
        permission_service: 权限服务（可选，当前未使用）
        get_current_user_override: 可选的 get_current_user 依赖覆盖（用于测试）

    Returns:
        APIRouter
    """
    router = APIRouter(prefix="/api/v1", tags=["authentication"])

    # Create get_current_user dependency with injected auth_service
    # Use override if provided (for testing), otherwise use real implementation
    get_current_user = get_current_user_override or get_current_user_dependency(auth_service)

    # Auth endpoints
    @router.post(
        "/auth/login",
        response_model=TokenResponse,
        responses={
            401: {"model": ErrorResponse, "description": "Invalid credentials"},
            423: {"model": ErrorResponse, "description": "Account locked"},
        },
    )
    async def login(request: LoginRequest) -> TokenResponse:
        """用户登录。

        Args:
            request: 登录请求（username, password）

        Returns:
            Token 响应（access_token, token_type, expires_in, user）

        Raises:
            HTTPException 401: 无效凭证
            HTTPException 423: 账户已锁定
        """
        try:
            access_token = await auth_service.authenticate(
                request.username,
                request.password,
            )
            # Verify token to get user info
            payload = await auth_service.verify_token(access_token)
            return TokenResponse(
                access_token=access_token,
                token_type="bearer",
                expires_in=86400,  # 24 hours
                user=UserResponse(
                    id=str(payload.user_id),
                    username=payload.username,
                    roles=list(payload.roles),
                ),
            )
        except AuthenticationError as e:
            error_msg = str(e)
            if "locked" in error_msg.lower():
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail=error_msg,
                )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error_msg,
            )

    @router.post(
        "/auth/refresh",
        response_model=TokenResponse,
        responses={
            401: {"model": ErrorResponse, "description": "Invalid refresh token"},
        },
    )
    async def refresh_token(request: RefreshTokenRequest) -> TokenResponse:
        """刷新访问令牌。

        Args:
            request: 刷新令牌请求

        Returns:
            新的 Token 响应

        Raises:
            HTTPException 401: 刷新令牌无效
        """
        try:
            access_token = await auth_service.refresh_token(request.refresh_token)
            payload = await auth_service.verify_token(access_token)
            return TokenResponse(
                access_token=access_token,
                token_type="bearer",
                expires_in=86400,
                user=UserResponse(
                    id=str(payload.user_id),
                    username=payload.username,
                    roles=list(payload.roles),
                ),
            )
        except AuthenticationError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

    @router.post(
        "/auth/logout",
        status_code=status.HTTP_204_NO_CONTENT,
        response_model=None,
    )
    async def logout(token: str = Depends(oauth2_scheme)) -> None:
        """用户登出。

        Args:
            token: 当前用户的 access token

        Returns:
            204 No Content
        """
        if token:
            await auth_service.logout(token)

    @router.get(
        "/auth/me",
        response_model=UserResponse,
        responses={
            401: {"model": ErrorResponse, "description": "Not authenticated"},
        },
    )
    async def get_me(current_user: TokenPayload = Depends(get_current_user)) -> UserResponse:
        """获取当前用户信息。

        Args:
            current_user: 当前认证用户

        Returns:
            用户信息
        """
        return UserResponse(
            id=str(current_user.user_id),
            username=current_user.username,
            roles=list(current_user.roles),
        )

    # Role management endpoints
    @router.post(
        "/roles",
        response_model=RoleResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            409: {"model": ErrorResponse, "description": "Role already exists"},
        },
    )
    async def create_role(
        request: CreateRoleRequest,
        current_user: TokenPayload = Depends(get_current_user),
    ) -> RoleResponse:
        """创建新角色。

        Args:
            request: 创建角色请求
            current_user: 当前认证用户

        Returns:
            创建的角色

        Raises:
            HTTPException 409: 角色名已存在
        """
        try:
            role = await role_service.create_role(
                name=request.name,
                permissions=request.permissions,
                description=request.description,
                is_system_reserved=request.is_system_reserved,
            )
            return RoleResponse(
                id=str(role.id) if role.id else "",
                name=role.name,
                description=role.description,
                permissions=list(role.permissions),
                is_system_reserved=role.is_system_reserved,
                is_active=role.is_active,
                created_at=role.created_at.isoformat() if role.created_at else None,
                updated_at=role.updated_at.isoformat() if role.updated_at else None,
            )
        except RoleAlreadyExistsError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Role '{request.name}' already exists",
            )

    @router.get("/roles", response_model=list[RoleResponse])
    async def list_roles(
        current_user: TokenPayload = Depends(get_current_user),
    ) -> list[RoleResponse]:
        """获取所有角色。

        Args:
            current_user: 当前认证用户

        Returns:
            角色列表
        """
        roles = await role_service.list_roles()
        return [
            RoleResponse(
                id=str(role.id) if role.id else "",
                name=role.name,
                description=role.description,
                permissions=list(role.permissions),
                is_system_reserved=role.is_system_reserved,
                is_active=role.is_active,
                created_at=role.created_at.isoformat() if role.created_at else None,
                updated_at=role.updated_at.isoformat() if role.updated_at else None,
            )
            for role in roles
        ]

    @router.get(
        "/roles/{role_id}",
        response_model=RoleResponse,
        responses={
            404: {"model": ErrorResponse, "description": "Role not found"},
        },
    )
    async def get_role(
        role_id: str,
        current_user: TokenPayload = Depends(get_current_user),
    ) -> RoleResponse:
        """获取角色详情。

        Args:
            role_id: 角色 UUID
            current_user: 当前认证用户

        Returns:
            角色详情

        Raises:
            HTTPException 404: 角色不存在
        """
        from uuid import UUID

        role = await role_service.get_role(UUID(role_id))
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role '{role_id}' not found",
            )
        return RoleResponse(
            id=str(role.id) if role.id else "",
            name=role.name,
            description=role.description,
            permissions=list(role.permissions),
            is_system_reserved=role.is_system_reserved,
            is_active=role.is_active,
            created_at=role.created_at.isoformat() if role.created_at else None,
            updated_at=role.updated_at.isoformat() if role.updated_at else None,
        )

    @router.put(
        "/roles/{role_id}",
        response_model=RoleResponse,
        responses={
            404: {"model": ErrorResponse, "description": "Role not found"},
            409: {"model": ErrorResponse, "description": "Role name conflict"},
        },
    )
    async def update_role(
        role_id: str,
        request: UpdateRoleRequest,
        current_user: TokenPayload = Depends(get_current_user),
    ) -> RoleResponse:
        """更新角色。

        Args:
            role_id: 角色 UUID
            request: 更新角色请求
            current_user: 当前认证用户

        Returns:
            更新后的角色

        Raises:
            HTTPException 404: 角色不存在
            HTTPException 409: 角色名冲突
        """
        from uuid import UUID

        try:
            role = await role_service.update_role(
                UUID(role_id),
                name=request.name,
                description=request.description,
                permissions=request.permissions,
                is_active=request.is_active,
            )
            return RoleResponse(
                id=str(role.id) if role.id else "",
                name=role.name,
                description=role.description,
                permissions=list(role.permissions),
                is_system_reserved=role.is_system_reserved,
                is_active=role.is_active,
                created_at=role.created_at.isoformat() if role.created_at else None,
                updated_at=role.updated_at.isoformat() if role.updated_at else None,
            )
        except RoleNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role '{role_id}' not found",
            )
        except RoleAlreadyExistsError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Role name '{request.name}' already exists",
            )

    @router.delete(
        "/roles/{role_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        response_model=None,
        responses={
            404: {"model": ErrorResponse, "description": "Role not found"},
            403: {"model": ErrorResponse, "description": "Cannot delete system role"},
        },
    )
    async def delete_role(
        role_id: str,
        current_user: TokenPayload = Depends(get_current_user),
    ) -> None:
        """删除角色（软删除）。

        Args:
            role_id: 角色 UUID
            current_user: 当前认证用户

        Raises:
            HTTPException 404: 角色不存在
            HTTPException 403: 不能删除系统保留角色
        """
        from uuid import UUID

        try:
            await role_service.delete_role(UUID(role_id))
        except RoleNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role '{role_id}' not found",
            )
        except CannotDeleteSystemRoleError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete system-reserved role",
            )

    # Permission endpoints
    @router.post(
        "/roles/{role_id}/permissions",
        response_model=RoleResponse,
        responses={
            404: {"model": ErrorResponse, "description": "Role not found"},
        },
    )
    async def assign_permissions(
        role_id: str,
        request: AssignPermissionRequest,
        current_user: TokenPayload = Depends(get_current_user),
    ) -> RoleResponse:
        """为角色分配权限。

        Args:
            role_id: 角色 UUID
            request: 权限分配请求
            current_user: 当前认证用户

        Returns:
            更新后的角色

        Raises:
            HTTPException 404: 角色不存在
        """
        from uuid import UUID

        role = await role_service.get_role(UUID(role_id))
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role '{role_id}' not found",
            )

        # Add new permissions
        current_perms = list(role.permissions)
        for perm in request.permissions:
            if perm not in current_perms:
                current_perms.append(perm)

        updated_role = await role_service.update_role(
            UUID(role_id),
            permissions=current_perms,
        )
        return RoleResponse(
            id=str(updated_role.id) if updated_role.id else "",
            name=updated_role.name,
            description=updated_role.description,
            permissions=list(updated_role.permissions),
            is_system_reserved=updated_role.is_system_reserved,
            is_active=updated_role.is_active,
            created_at=updated_role.created_at.isoformat() if updated_role.created_at else None,
            updated_at=updated_role.updated_at.isoformat() if updated_role.updated_at else None,
        )

    @router.delete(
        "/roles/{role_id}/permissions/{permission}",
        response_model=RoleResponse,
        responses={
            404: {"model": ErrorResponse, "description": "Role not found"},
        },
    )
    async def revoke_permission(
        role_id: str,
        permission: str,
        current_user: TokenPayload = Depends(get_current_user),
    ) -> RoleResponse:
        """撤销角色的指定权限。

        Args:
            role_id: 角色 UUID
            permission: 权限字符串（如 "document:read"）
            current_user: 当前认证用户

        Returns:
            更新后的角色

        Raises:
            HTTPException 404: 角色不存在
        """
        from uuid import UUID

        role = await role_service.get_role(UUID(role_id))
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role '{role_id}' not found",
            )

        # Remove permission
        current_perms = [p for p in role.permissions if p != permission]

        updated_role = await role_service.update_role(
            UUID(role_id),
            permissions=current_perms,
        )
        return RoleResponse(
            id=str(updated_role.id) if updated_role.id else "",
            name=updated_role.name,
            description=updated_role.description,
            permissions=list(updated_role.permissions),
            is_system_reserved=updated_role.is_system_reserved,
            is_active=updated_role.is_active,
            created_at=updated_role.created_at.isoformat() if updated_role.created_at else None,
            updated_at=updated_role.updated_at.isoformat() if updated_role.updated_at else None,
        )

    return router
