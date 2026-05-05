"""RoleRepository Port - 角色仓储端口.

领域层接口，定义角色数据访问的契约。
遵循六边形架构：领域层零依赖，仅使用 ABC + 标准库。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.entities.role import Role


class RoleRepositoryPort(ABC):
    """角色仓储端口（领域层定义，仅使用 ABC + 标准库）

    负责角色的数据访问，不包含业务逻辑。
    """

    @abstractmethod
    async def get_by_id(self, role_id: UUID) -> Role | None:
        """根据 ID 获取角色。

        Args:
            role_id: 角色 UUID

        Returns:
            Role 领域实体，或 None（角色不存在）
        """
        ...

    @abstractmethod
    async def get_by_name(self, name: str) -> Role | None:
        """根据名称获取角色。

        Args:
            name: 角色名称

        Returns:
            Role 领域实体，或 None（角色不存在）
        """
        ...

    @abstractmethod
    async def list_all(self) -> list[Role]:
        """获取所有角色。

        Returns:
            角色列表
        """
        ...

    @abstractmethod
    async def save(self, role: Role) -> Role:
        """保存角色（创建或更新）。

        Args:
            role: Role 领域实体

        Returns:
            保存后的 Role（包含生成的 ID）
        """
        ...

    @abstractmethod
    async def delete(self, role_id: UUID) -> bool:
        """删除角色。

        Args:
            role_id: 角色 UUID

        Returns:
            True 删除成功，False 角色不存在
        """
        ...
