"""领域层 L2 关系数据库统一基础端口模块

泛型 async CRUD 基座，所有 L2 仓储端口的基础
领域层零外部依赖

重构说明：
- BaseRepository[T] 重命名为 L2RdbPort[T]（sync→async）
- BaseRepository 保留为 deprecated 别名
"""

from __future__ import annotations

from typing import Generic, Protocol, TypeVar, runtime_checkable
from uuid import UUID

T = TypeVar("T")


@runtime_checkable
class L2RdbPort(Generic[T], Protocol):
    """L2 关系数据库统一基础端口 — 泛型 async CRUD

    所有 L2 仓储端口继承此基座，自动获得 get_by_id/save/delete/list_all
    """

    async def get_by_id(self, id: UUID) -> T | None:
        """通过 ID 获取实体（async）

        Args:
            id: 实体唯一标识

        Returns:
            实体实例，不存在则返回 None
        """

    async def save(self, entity: T) -> T:
        """保存实体（insert or update，async）

        Args:
            entity: 要保存的实体

        Returns:
            持久化后的实体（含 DB 生成的字段如 id、timestamps）
        """

    async def delete(self, id: UUID) -> None:
        """删除实体（async）

        Args:
            id: 要删除的实体 ID
        """

    async def list_all(self) -> list[T]:
        """列出所有实体（async）

        Returns:
            所有实体列表
        """


# DEPRECATED: 请使用 L2RdbPort 替代，BaseRepository 仅为向后兼容保留
BaseRepository = L2RdbPort
