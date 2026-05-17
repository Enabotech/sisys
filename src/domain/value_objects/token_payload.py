"""SISYS 领域层令牌载荷值对象模块

不可变值对象，封装 JWT Token 解码后的载荷信息
遵循六边形架构：领域层零依赖，仅使用标准库

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class TokenPayload:
    """JWT Token 载荷领域值对象（不可变）

    Attributes:
        user_id: 用户 UUID
        username: 用户名
        roles: 角色元组（不可变）
        exp: 过期时间（UTC）
        iat: 签发时间（UTC，可选）
    """

    user_id: UUID
    username: str
    roles: tuple[str, ...]  # tuple 不可变，替代 list
    exp: datetime
    iat: datetime | None = None

    def is_expired(self) -> bool:
        """检查令牌是否已过期."""
        return datetime.now(UTC) > self.exp

    def has_role(self, role: str) -> bool:
        """检查用户是否拥有指定角色."""
        return role in self.roles

    def has_any_role(self, *roles: str) -> bool:
        """检查用户是否拥有任一指定角色."""
        return any(role in self.roles for role in roles)

    @classmethod
    def from_jwt_claims(cls, claims: dict[str, Any]) -> TokenPayload:
        """从 JWT claims 字典创建 TokenPayload.

        Args:
            claims: JWT 解码后的 claims 字典
                - sub: 用户 ID (str 或 UUID)
                - username: 用户名
                - roles: 角色列表
                - exp: 过期时间（Unix 时间戳）
                - iat: 签发时间（Unix 时间戳，可选）

        Returns:
            TokenPayload 实例

        Raises:
            ValueError: claims 缺少必需字段或格式错误
        """
        # 解析 user_id
        sub = claims.get("sub")
        if not sub:
            raise ValueError("Missing required claim: sub")
        try:
            user_id = UUID(str(sub))
        except ValueError:
            raise ValueError(f"Invalid user_id format: {sub}")

        # 解析 username
        username = claims.get("username")
        if not username:
            raise ValueError("Missing required claim: username")

        # 解析 roles
        roles_raw = claims.get("roles", [])
        if isinstance(roles_raw, str):
            roles_raw = [roles_raw]
        roles = tuple(str(r) for r in roles_raw)

        # 解析 exp
        exp_timestamp = claims.get("exp")
        if not exp_timestamp:
            raise ValueError("Missing required claim: exp")
        try:
            exp = datetime.fromtimestamp(exp_timestamp, tz=UTC)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid exp format: {exp_timestamp}")

        # 解析 iat（可选）
        iat_timestamp = claims.get("iat")
        iat = None
        if iat_timestamp:
            try:
                iat = datetime.fromtimestamp(iat_timestamp, tz=UTC)
            except (TypeError, ValueError):
                iat = None

        return cls(
            user_id=user_id,
            username=username,
            roles=roles,
            exp=exp,
            iat=iat,
        )
