"""UserRepository Port - 用户仓储端口.

领域层接口，定义用户数据访问的契约。
遵循六边形架构：领域层零依赖，仅使用 ABC + 标准库。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.entities.user import User


class UserRepositoryPort(ABC):
    """用户仓储端口（领域层定义，仅使用 ABC + 标准库）"""

    @abstractmethod
    async def get_by_username(self, username: str) -> User | None:
        """根据用户名获取用户。

        Args:
            username: 用户名

        Returns:
            User 领域实体，或 None（用户不存在）
        """
        ...

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None:
        """根据 ID 获取用户。

        Args:
            user_id: 用户 UUID

        Returns:
            User 领域实体，或 None（用户不存在）
        """
        ...
