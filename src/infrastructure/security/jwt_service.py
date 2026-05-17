"""SISYS 基础设施层 JWT 令牌服务模块。

基于 python-jose 库实现 JWT 令牌的创建、验证和刷新功能。

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from jose import JWTError, jwt

from src.domain.value_objects.token_payload import TokenPayload
from src.infrastructure.config.auth import AuthConfig


class JWTService:
    """JWT 令牌服务，负责令牌的生成、验证和刷新。

    Attributes:
        _config: AuthConfig 认证配置实例
        _algorithm: JWT 签名算法
        _secret_key: JWT 签名密钥
    """

    def __init__(self, config: AuthConfig):
        """初始化 JWT 服务。

        Args:
            config: AuthConfig 配置实例
        """
        self._config = config
        self._algorithm = config.jwt_algorithm
        self._secret_key = config.jwt_secret_key

    def create_access_token(
        self,
        user_id: UUID,
        username: str,
        roles: list[str],
        expires_delta: timedelta | None = None,
    ) -> str:
        """创建 JWT access token。

        Args:
            user_id: 用户 UUID
            username: 用户名
            roles: 角色列表
            expires_delta: 过期时间增量（默认使用配置值）

        Returns:
            JWT token 字符串
        """
        if expires_delta is None:
            expires_delta = timedelta(hours=self._config.jwt_expiration_hours)

        now = datetime.now(UTC)
        expire = now + expires_delta

        payload = {
            "sub": str(user_id),
            "username": username,
            "roles": roles,
            "iat": now,
            "exp": expire,
        }

        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def create_refresh_token(
        self,
        user_id: UUID,
        expires_delta: timedelta | None = None,
    ) -> str:
        """创建 JWT refresh token。

        Args:
            user_id: 用户 UUID
            expires_delta: 过期时间增量（默认使用配置值）

        Returns:
            JWT refresh token 字符串
        """
        if expires_delta is None:
            expires_delta = timedelta(days=self._config.jwt_refresh_expiration_days)

        now = datetime.now(UTC)
        expire = now + expires_delta

        payload = {
            "sub": str(user_id),
            "type": "refresh",
            "jti": str(uuid4()),  # JWT ID for rotation tracking
            "iat": now,
            "exp": expire,
        }

        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def verify_token(self, token: str) -> TokenPayload:
        """验证 JWT token 并返回 TokenPayload。

        Args:
            token: JWT token 字符串

        Returns:
            TokenPayload 领域值对象

        Raises:
            AuthenticationError: token 无效或过期
        """
        from src.domain.ports.auth_service import AuthenticationError

        try:
            claims = jwt.decode(token, self._secret_key, algorithms=[self._algorithm])

            # 检查 token 类型（如果是 refresh token，拒绝用于 access）
            if claims.get("type") == "refresh":
                raise AuthenticationError("Refresh token cannot be used for access")

            return TokenPayload.from_jwt_claims(claims)

        except JWTError as e:
            raise AuthenticationError(f"Invalid token: {e}")

    def verify_refresh_token(self, token: str) -> UUID:
        """验证 JWT refresh token 并返回 user_id。

        Args:
            token: JWT refresh token 字符串

        Returns:
            用户 UUID

        Raises:
            AuthenticationError: refresh token 无效或过期
        """
        from src.domain.ports.auth_service import AuthenticationError

        try:
            claims = jwt.decode(token, self._secret_key, algorithms=[self._algorithm])

            # 检查 token 类型
            if claims.get("type") != "refresh":
                raise AuthenticationError("Not a refresh token")

            user_id_str = claims.get("sub")
            if not user_id_str:
                raise AuthenticationError("Missing sub claim")

            return UUID(user_id_str)

        except JWTError as e:
            raise AuthenticationError(f"Invalid refresh token: {e}")

    def get_refresh_token_jti(self, token: str) -> str | None:
        """从 refresh token 中提取 jti。

        Args:
            token: JWT refresh token 字符串

        Returns:
            jti 字符串，如果不存在返回 None
        """
        try:
            claims = jwt.decode(token, self._secret_key, algorithms=[self._algorithm])
            return claims.get("jti")
        except JWTError:
            return None
