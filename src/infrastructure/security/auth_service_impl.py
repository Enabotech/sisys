"""Auth Service Implementation - 认证服务实现.

实现 AuthServicePort 接口，提供用户认证功能。
遵循六边形架构：基础设施层实现，可以导入外部库。
"""

from __future__ import annotations

from uuid import UUID

from src.domain.ports.auth_service import AuthenticationError, AuthServicePort
from src.domain.value_objects.token_payload import TokenPayload
from src.infrastructure.security.encryption_service import EncryptionService
from src.infrastructure.security.jwt_service import JWTService


class AuthServiceImpl(AuthServicePort):
    """认证服务实现.

    负责用户认证和 JWT 令牌管理。
    """

    def __init__(
        self,
        jwt_service: JWTService,
        encryption_service: EncryptionService,
        user_repository,  # UserRepositoryPort
        user_role_repository,  # UserRoleRepositoryPort
        login_attempt_repository=None,  # LoginAttemptRepositoryPort (optional)
        token_blacklist=None,  # Redis blacklist store (optional)
        refresh_token_store=None,  # Redis refresh token rotation store (optional)
    ):
        """初始化认证服务.

        Args:
            jwt_service: JWT 服务
            encryption_service: 加密服务
            user_repository: 用户仓储端口
            user_role_repository: 用户角色关联仓储端口
            login_attempt_repository: 登录尝试仓储端口（可选）
            token_blacklist: Token 黑名单存储（可选，用于 logout）
            refresh_token_store: Refresh token 存储（可选，用于 rotation）
        """
        self._jwt_service = jwt_service
        self._encryption_service = encryption_service
        self._user_repo = user_repository
        self._user_role_repo = user_role_repository
        self._login_attempt_repo = login_attempt_repository
        self._token_blacklist = token_blacklist
        self._refresh_token_store = refresh_token_store

    async def authenticate(
        self,
        username: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> str:
        """用户认证.

        Args:
            username: 用户名
            password: 密码（明文）
            ip_address: IP 地址（可选，用于记录）
            user_agent: 用户代理（可选，用于记录）

        Returns:
            JWT access token 字符串

        Raises:
            AuthenticationError: 认证失败时抛出
        """
        # 获取用户
        user = await self._user_repo.get_by_username(username)

        if not user:
            # 用户不存在，也记录尝试（即使没有 user_id）
            await self._record_attempt(username, False, "user_not_found", None, ip_address, user_agent)
            raise AuthenticationError("Invalid credentials")

        # 检查账户是否激活
        if not user.is_active:
            await self._record_attempt(username, False, "account_inactive", user.id, ip_address, user_agent)
            raise AuthenticationError("Account is inactive")

        # 检查账户是否被系统锁定（is_locked 字段）
        if user.is_locked:
            await self._record_attempt(username, False, "account_locked", user.id, ip_address, user_agent)
            raise AuthenticationError("Account is locked")

        # 检查账户是否被动态锁定（连续失败达到阈值）- 使用原子操作
        if self._login_attempt_repo:
            is_locked, remaining = await self._login_attempt_repo.record_attempt_and_check_lockout(
                username=username,
                success=False,
                failure_reason=None,
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            if is_locked:
                raise AuthenticationError(
                    f"Account is locked due to multiple failed attempts. Try again in {remaining} minutes."
                )

        # 验证密码
        if not self._encryption_service.verify_password(password, user.hashed_password):
            await self._record_attempt(username, False, "invalid_password", user.id, ip_address, user_agent)
            raise AuthenticationError("Invalid credentials")

        # 登录成功，清除失败记录
        if self._login_attempt_repo:
            await self._login_attempt_repo.clear_attempts(username)

        # 获取用户角色
        roles = await self._get_user_roles(user.id)

        # 生成 JWT token
        access_token = self._jwt_service.create_access_token(
            user_id=user.id,
            username=user.username,
            roles=roles,
        )
        return access_token

    async def _record_attempt(
        self,
        username: str,
        success: bool,
        failure_reason: str | None = None,
        user_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """记录登录尝试。

        Args:
            username: 用户名
            success: 是否成功
            failure_reason: 失败原因
            user_id: 用户 UUID
            ip_address: IP 地址
            user_agent: 用户代理
        """
        if self._login_attempt_repo:
            await self._login_attempt_repo.record_attempt(
                username=username,
                success=success,
                failure_reason=failure_reason,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )

    async def verify_token(self, token: str) -> TokenPayload:
        """验证 JWT token.

        Args:
            token: JWT token 字符串

        Returns:
            TokenPayload 领域值对象

        Raises:
            AuthenticationError: token 无效、过期或被撤销
        """
        # 检查 token 是否在黑名单中
        if self._token_blacklist and await self._token_blacklist.is_blacklisted(token):
            from src.domain.ports.auth_service import AuthenticationError

            raise AuthenticationError("Token has been revoked")
        return self._jwt_service.verify_token(token)

    async def refresh_token(self, refresh_token: str) -> str:
        """刷新 JWT access token.

        Args:
            refresh_token: JWT refresh token 字符串

        Returns:
            新的 access token 字符串

        Raises:
            AuthenticationError: refresh token 无效或过期
        """
        user_id = self._jwt_service.verify_refresh_token(refresh_token)

        # 检查 refresh token 是否已被使用（rotation 检查）
        jti = self._jwt_service.get_refresh_token_jti(refresh_token)
        if jti and self._refresh_token_store:
            is_used = await self._refresh_token_store.is_used(jti)
            if is_used:
                # Token 被重用，可能是攻击，撤销该用户的所有 token
                if self._token_blacklist:
                    # 通知用户 token 被泄露，需要重新登录
                    pass
                from src.domain.ports.auth_service import AuthenticationError

                raise AuthenticationError("Refresh token reuse detected - possible attack")
            # 标记 jti 为已使用
            await self._refresh_token_store.mark_used(jti)

        # 获取用户信息
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            raise AuthenticationError("User not found")

        if not user.is_active:
            raise AuthenticationError("Account is inactive")

        if user.is_locked:
            raise AuthenticationError("Account is locked")

        if self._login_attempt_repo:
            is_locked = await self._login_attempt_repo.is_account_locked(user.username)
            if is_locked:
                raise AuthenticationError("Account is locked due to multiple failed attempts")

        # 获取用户角色
        roles = await self._get_user_roles(user_id)

        # 生成新的 access token
        return self._jwt_service.create_access_token(
            user_id=user.id,
            username=user.username,
            roles=roles,
        )

    async def logout(self, token: str) -> None:
        """用户登出，撤销 JWT token.

        Args:
            token: 要撤销的 JWT access token
        """
        if self._token_blacklist:
            await self._token_blacklist.add(token)

    async def _get_user_roles(self, user_id: UUID) -> list[str]:
        """获取用户的角色列表。

        Args:
            user_id: 用户 UUID

        Returns:
            角色名称列表
        """
        roles = await self._user_role_repo.get_user_roles(user_id)
        return [role.name for role in roles]
