"""SISYS 基础设施层认证服务模块

基于 AuthServicePort 接口实现用户认证、JWT 令牌管理和登录尝试记录功能

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from uuid import UUID

from src.domain.ports.auth_service import AuthenticationError, AuthServicePort, AuthTokens
from src.domain.value_objects.token_payload import TokenPayload
from src.infrastructure.security.encryption_service import EncryptionService
from src.infrastructure.security.jwt_service import JWTService


class AuthServiceImpl(AuthServicePort):
    """认证服务实现，负责用户认证和 JWT 令牌管理

    Attributes:
        _jwt_service: JWT 令牌服务实例
        _encryption_service: 加密服务实例
        _user_repo: 用户仓储端口
        _user_role_repo: 用户角色关联仓储端口
        _login_attempt_repo: 登录尝试仓储端口（可选）
        _token_blacklist: Token 黑名单存储（可选）
        _refresh_token_store: Refresh token 存储用于 rotation（可选）
        _event_publisher: 事件发布器（可选）
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
        event_publisher=None,  # EventPublisher (optional, for audit events)
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
            event_publisher: 事件发布器（可选，用于审计事件）
        """
        self._jwt_service = jwt_service
        self._encryption_service = encryption_service
        self._user_repo = user_repository
        self._user_role_repo = user_role_repository
        self._login_attempt_repo = login_attempt_repository
        self._token_blacklist = token_blacklist
        self._refresh_token_store = refresh_token_store
        self._event_publisher = event_publisher

    async def authenticate(
        self,
        username: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthTokens:
        """用户认证.

        Args:
            username: 用户名
            password: 密码（明文）
            ip_address: IP 地址（可选，用于记录）
            user_agent: 用户代理（可选，用于记录）

        Returns:
            AuthTokens 包含 access_token 和 refresh_token

        Raises:
            AuthenticationError: 认证失败时抛出
        """
        # 获取用户
        user = await self._user_repo.get_by_username(username)

        if not user:
            # 防御timing attack: 即使用户不存在也执行伪哈希计算
            # 确保无论用户存在与否，响应时间都相似
            # 使用 timing_safe_verify 方法，每次使用随机 salt，确保完整 bcrypt 计算
            self._encryption_service.timing_safe_verify(password)
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
        if not self._encryption_service.verify_password(password, user.password_hash):
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

        # 生成 refresh token
        refresh_token = self._jwt_service.create_refresh_token(user_id=user.id)

        # 发布审计事件 - 登录成功
        await self._publish_audit_event(
            action_type="authentication:login",
            actor=str(user.id),
            target_resource="/api/v1/auth/login",
            old_value=None,
            new_value={"username": username, "ip_address": ip_address, "user_agent": user_agent},
        )

        return AuthTokens(access_token=access_token, refresh_token=refresh_token)

    async def _publish_audit_event(
        self,
        action_type: str,
        actor: str,
        target_resource: str,
        old_value: dict | None = None,
        new_value: dict | None = None,
    ) -> None:
        """发布审计事件

        Args:
            action_type: 操作类型
            actor: 操作用户 ID
            target_resource: 目标资源
            old_value: 操作前状态
            new_value: 操作后状态
        """
        if self._event_publisher is None:
            return

        try:
            from src.domain.events.audit_events import AuditEvent

            event = AuditEvent(
                actor=actor,
                action_type=action_type,
                target_resource=target_resource,
                old_value=old_value or {},
                new_value=new_value or {},
            )
            await self._event_publisher.publish(event)
        except Exception:
            # 审计事件发布失败不应影响主流程
            pass

    async def _record_attempt(
        self,
        username: str,
        success: bool,
        failure_reason: str | None = None,
        user_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """记录登录尝试

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

        # 发布审计事件 - 登录失败
        if not success:
            await self._publish_audit_event(
                action_type="authentication:failed",
                actor=str(user_id) if user_id else username,
                target_resource="/api/v1/auth/login",
                old_value=None,
                new_value={
                    "username": username,
                    "failure_reason": failure_reason,
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                },
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
                    # 获取用户的所有 token family 并全部撤销
                    await self._revoke_user_token_family(user_id)
                raise AuthenticationError("Refresh token reuse detected - possible attack")
            # 标记 jti 为已使用（带 user_id 用于 token family 追踪）
            await self._refresh_token_store.mark_used(jti, user_id)

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

    async def logout(self, token: str, refresh_token: str | None = None) -> None:
        """用户登出，撤销 JWT token

        Args:
            token: 要撤销的 JWT access token
            refresh_token: 要撤销的 refresh token（可选）
        """
        if self._token_blacklist:
            await self._token_blacklist.add(token)
            if refresh_token:
                await self._token_blacklist.add(refresh_token)

        # 发布审计事件 - 登出
        await self._publish_audit_event(
            action_type="authentication:logout",
            actor="system",  # Will be overridden by actual user ID if available
            target_resource="/api/v1/auth/logout",
            old_value={"token_revoked": True},
            new_value={"refresh_token_revoked": refresh_token is not None},
        )

    async def _revoke_user_token_family(self, user_id: UUID) -> None:
        """撤销用户的所有 token（token family）

        当检测到 refresh token 被重用时，调用此方法撤销该用户的所有 token
        这确保攻击者无法使用该用户任何其他的 refresh token

        Args:
            user_id: 用户 UUID
        """
        if not self._refresh_token_store:
            return

        try:
            # 获取用户的所有 jti 并标记为已使用
            user_jtis = await self._refresh_token_store.get_user_jtis(user_id)
            for jti in user_jtis:
                await self._refresh_token_store.mark_used(jti, user_id)
        except (AttributeError, NotImplementedError):
            # 如果 refresh_token_store 不支持 token family，store 不具备此能力
            # 向后兼容：标记当前 jti 已被使用
            pass

    async def _get_user_roles(self, user_id: UUID) -> list[str]:
        """获取用户的角色列表

        Args:
            user_id: 用户 UUID

        Returns:
            角色名称列表
        """
        roles = await self._user_role_repo.get_user_roles(user_id)
        return [role.name for role in roles]
