"""Token Blacklist Port - Token 黑名单仓储端口.

领域层接口，定义 Token 黑名单数据访问的契约。
遵循六边形架构：领域层零依赖，仅使用 ABC + 标准库。
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class TokenBlacklistPort(ABC):
    """Token 黑名单仓储端口（领域层定义，仅使用 ABC + 标准库）

    负责存储已撤销的 JWT token。
    """

    @abstractmethod
    async def add(self, token: str) -> None:
        """将 token 加入黑名单。

        Args:
            token: JWT token 字符串
        """
        ...

    @abstractmethod
    async def is_blacklisted(self, token: str) -> bool:
        """检查 token 是否在黑名单中。

        Args:
            token: JWT token 字符串

        Returns:
            True 如果 token 已被撤销
        """
        ...
