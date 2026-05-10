"""AuthService Port - 认证服务端口.

领域层接口，定义认证服务的契约。
遵循六边形架构：领域层零依赖，仅使用 ABC + 标准库。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.domain.exceptions import AuthenticationError
from src.domain.value_objects.token_payload import TokenPayload

__all__ = ["AuthenticationError"]


@dataclass(frozen=True)
class AuthTokens:
    """认证令牌领域值对象（不可变）."""

    access_token: str
    refresh_token: str


class AuthServicePort(Protocol):
    """认证服务端口（领域层定义，仅使用 ABC + 标准库）.

    定义用户认证和 JWT 令牌管理的接口。
    实现类位于 infrastructure 层（可导入 python-jose 等外部库）。
    """

    async def authenticate(self, username: str, password: str) -> AuthTokens:
        """用户认证。

        Args:
            username: 用户名
            password: 密码（明文）

        Returns:
            AuthTokens 包含 access_token 和 refresh_token

        Raises:
            AuthenticationError: 认证失败时抛出
                - 用户不存在
                - 密码错误
                - 账户已锁定
                - 账户未激活
        """

    async def verify_token(self, token: str) -> TokenPayload:
        """验证 JWT token。

        Args:
            token: JWT token 字符串

        Returns:
            TokenPayload 领域值对象，包含 user_id, username, roles, exp

        Raises:
            AuthenticationError: token 无效、过期或被撤销
        """

    async def refresh_token(self, refresh_token: str) -> str:
        """刷新 JWT access token。

        Args:
            refresh_token: JWT refresh token 字符串

        Returns:
            新的 access token 字符串

        Raises:
            AuthenticationError: refresh token 无效或过期
        """

    async def logout(self, token: str, refresh_token: str | None = None) -> None:
        """用户登出，撤销 JWT token。

        Args:
            token: 要撤销的 JWT access token
            refresh_token: 要撤销的 refresh token（可选）
        """
