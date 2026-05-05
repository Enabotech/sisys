"""AuthService Port - 认证服务端口.

领域层接口，定义认证服务的契约。
遵循六边形架构：领域层零依赖，仅使用 ABC + 标准库。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.value_objects.token_payload import TokenPayload


class AuthenticationError(Exception):
    """认证失败异常（领域层异常，无需导入外部库）."""

    pass


class AuthServicePort(ABC):
    """认证服务端口（领域层定义，仅使用 ABC + 标准库）.

    定义用户认证和 JWT 令牌管理的接口。
    实现类位于 infrastructure 层（可导入 python-jose 等外部库）。
    """

    @abstractmethod
    async def authenticate(self, username: str, password: str) -> str:
        """用户认证。

        Args:
            username: 用户名
            password: 密码（明文）

        Returns:
            JWT access token 字符串

        Raises:
            AuthenticationError: 认证失败时抛出
                - 用户不存在
                - 密码错误
                - 账户已锁定
                - 账户未激活
        """
        ...

    @abstractmethod
    async def verify_token(self, token: str) -> TokenPayload:
        """验证 JWT token。

        Args:
            token: JWT token 字符串

        Returns:
            TokenPayload 领域值对象，包含 user_id, username, roles, exp

        Raises:
            AuthenticationError: token 无效、过期或被撤销
        """
        ...

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> str:
        """刷新 JWT access token。

        Args:
            refresh_token: JWT refresh token 字符串

        Returns:
            新的 access token 字符串

        Raises:
            AuthenticationError: refresh token 无效或过期
        """
        ...

    @abstractmethod
    async def logout(self, token: str) -> None:
        """用户登出，撤销 JWT token。

        Args:
            token: 要撤销的 JWT access token
        """
        ...
