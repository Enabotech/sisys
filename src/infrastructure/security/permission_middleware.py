"""基础设施层权限验证中间件模块

提供 FastAPI 依赖注入的权限验证功能，包括用户认证、角色检查和权限控制
"""

from __future__ import annotations

from typing import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, status
from typing_extensions import Annotated

from src.domain.exceptions import ConfigurationError, PermissionDeniedError
from src.domain.ports.permission_service import PermissionServicePort
from src.domain.value_objects.token_payload import TokenPayload
from src.infrastructure.security.jwt_service import JWTService


def get_current_user(
    authorization: str | None = None,
    jwt_service: JWTService | None = None,
) -> TokenPayload:
    """从 Authorization header 提取并验证 JWT token.

    Args:
        authorization: Authorization header 值（Bearer token）
        jwt_service: JWT 服务实例

    Returns:
        TokenPayload 领域值对象

    Raises:
        HTTPException: token 无效或缺失
    """
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 处理空字符串authorization
    if not authorization.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]
    if not jwt_service:
        raise ConfigurationError("JWT service not configured")

    try:
        payload: TokenPayload = jwt_service.verify_token(token)
        return payload
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_permission(
    resource: str,
    action: str,
    permission_service: PermissionServicePort | None = None,
) -> Callable:
    """权限验证装饰器工厂.

    创建检查用户是否拥有指定权限的 FastAPI 依赖

    Args:
        resource: 资源类型（如 "document", "agent"）
        action: 操作类型（如 "read", "write", "execute"）
        permission_service: 权限服务实例（可选，默认从全局获取）

    Returns:
        FastAPI 依赖函数

    Example:
        @router.get("/documents/{doc_id}")
        async def get_document(
            doc_id: str,
            user: TokenPayload = Depends(require_permission("document", "read")),
        ):
            ...
    """

    async def permission_check(
        current_user: Annotated[
            TokenPayload,
            Depends(get_current_user),
        ],
    ) -> TokenPayload:
        """权限检查依赖函数."""
        if permission_service is None:
            raise ConfigurationError("Permission service not configured")

        has_permission = await permission_service.check_permission(
            user_id=current_user.user_id,
            resource=resource,
            action=action,
        )

        if not has_permission:
            raise PermissionDeniedError(f"Permission denied: {resource}:{action}")

        return current_user

    return permission_check


def require_any_role(
    *roles: str,
    get_current_user_fn: Callable | None = None,
) -> Callable:
    """角色验证装饰器工厂.

    创建检查用户是否拥有任一指定角色的 FastAPI 依赖

    Args:
        *roles: 允许的角色名称列表
        get_current_user_fn: 可选的 get_current_user 函数（用于测试注入）

    Returns:
        FastAPI 依赖函数
    """
    # Use provided function or default get_current_user
    actual_get_current_user = get_current_user_fn or get_current_user

    async def role_check(
        current_user: Annotated[
            TokenPayload,
            Depends(actual_get_current_user),
        ],
    ) -> TokenPayload:
        """角色检查依赖函数."""
        if not current_user.has_any_role(*roles):
            raise PermissionDeniedError(f"Required role: one of {roles}")
        return current_user

    return role_check


def require_all_roles(*roles: str) -> Callable:
    """角色验证装饰器工厂（需拥有所有指定角色）.

    创建检查用户是否拥有所有指定角色的 FastAPI 依赖

    Args:
        *roles: 必需的角色名称列表

    Returns:
        FastAPI 依赖函数
    """

    async def role_check(
        current_user: Annotated[
            TokenPayload,
            Depends(get_current_user),
        ],
    ) -> TokenPayload:
        """角色检查依赖函数."""
        missing_roles = [r for r in roles if not current_user.has_role(r)]
        if missing_roles:
            raise PermissionDeniedError(f"Missing required roles: {missing_roles}")
        return current_user

    return role_check


class CurrentUser:
    """当前用户依赖类，提供灵活的用户注入方式

    支持可选或必选模式获取当前用户信息
    """

    @staticmethod
    def optional(
        authorization: str | None = None,
        jwt_service: JWTService | None = None,
    ) -> TokenPayload | None:
        """获取当前用户（可选，不存在返回 None）.

        Args:
            authorization: Authorization header
            jwt_service: JWT 服务

        Returns:
            TokenPayload 或 None
        """
        if not authorization:
            return None

        try:
            return get_current_user(authorization, jwt_service)
        except HTTPException:
            return None

    @staticmethod
    def required(
        authorization: str | None = None,
        jwt_service: JWTService | None = None,
    ) -> TokenPayload:
        """获取当前用户（必选，不存在抛出异常）.

        Args:
            authorization: Authorization header
            jwt_service: JWT 服务

        Returns:
            TokenPayload

        Raises:
            HTTPException: 用户未认证
        """
        return get_current_user(authorization, jwt_service)


class PermissionContext:
    """权限验证上下文，在请求处理过程中传递权限验证相关状态

    Attributes:
        user: 当前用户 token payload
        permission_service: 权限服务实例
    """

    def __init__(
        self,
        user: TokenPayload,
        permission_service: PermissionServicePort,
        resource_id: UUID | None = None,
    ):
        """初始化权限上下文.

        Args:
            user: 当前用户 token payload
            permission_service: 权限服务
            resource_id: 资源实例 ID（可选）
        """
        self.user = user
        self.permission_service = permission_service
        self._resource_id = resource_id

    async def check(self, resource: str, action: str) -> bool:
        """检查当前用户是否有指定权限.

        Args:
            resource: 资源类型
            action: 操作类型

        Returns:
            True 如果有权限
        """
        return await self.permission_service.check_permission(
            user_id=self.user.user_id,
            resource=resource,
            action=action,
            resource_id=self._resource_id,
        )

    async def require(self, resource: str, action: str) -> None:
        """要求当前用户有指定权限，否则抛出异常.

        Args:
            resource: 资源类型
            action: 操作类型

        Raises:
            PermissionDeniedError: 权限不足
        """
        if not await self.check(resource, action):
            raise PermissionDeniedError(f"Permission denied: {resource}:{action}")
