"""L2 关系型数据库存储端口协议定义（领域层）。

依赖倒置：领域层定义接口，基础设施层实现。
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.domain.entities.memory_change_history import MemoryChangeHistory
from src.domain.entities.memory_metadata import MemoryMetadata


class L2MetadataRepositoryPort(Protocol):
    """L2 记忆元数据仓储端口。

    领域层定义接口，基础设施层实现。
    MVP 阶段使用 InMemoryMemoryMetadataRepository，
    生产环境替换为 PostgreSQL 实现。
    """

    async def save(self, metadata: MemoryMetadata) -> None:
        """保存或更新记忆元数据（UPSERT）。

        Args:
            metadata: 记忆元数据

        Raises:
            Exception: 版本冲突时抛出
        """

    async def get_by_id(self, memory_id: UUID) -> MemoryMetadata | None:
        """通过 ID 获取记忆元数据。

        Args:
            memory_id: 记忆 ID

        Returns:
            MemoryMetadata 如果存在，否则 None
        """

    async def get_by_name(self, name: str) -> MemoryMetadata | None:
        """通过名称获取记忆元数据。

        Args:
            name: 记忆名称

        Returns:
            MemoryMetadata 如果存在，否则 None
        """

    async def delete(self, memory_id: UUID) -> None:
        """删除记忆元数据。

        Args:
            memory_id: 记忆 ID
        """

    async def list_by_user(self, user_id: str) -> list[MemoryMetadata]:
        """列出用户的所有记忆元数据。

        Args:
            user_id: 用户 ID

        Returns:
            记忆元数据列表
        """

    async def list_by_type(self, memory_type: str) -> list[MemoryMetadata]:
        """列出指定类型的所有记忆元数据。

        Args:
            memory_type: 记忆类型

        Returns:
            记忆元数据列表
        """

    async def list_all(self) -> list[MemoryMetadata]:
        """列出所有记忆元数据。

        Returns:
            所有记忆元数据列表
        """


class L2ChangeHistoryRepositoryPort(Protocol):
    """L2 记忆变更历史仓储端口。

    领域层定义接口，基础设施层实现。
    """

    async def save(self, history: MemoryChangeHistory) -> None:
        """保存历史记录（append-only）。

        Args:
            history: 变更历史记录
        """

    async def get_by_memory_id(self, memory_id: UUID) -> list[MemoryChangeHistory]:
        """获取记忆的所有历史记录。

        Args:
            memory_id: 记忆 ID

        Returns:
            变更历史列表（按时间排序）
        """

    async def get_by_id(self, history_id: UUID) -> MemoryChangeHistory | None:
        """通过 ID 获取历史记录。

        Args:
            history_id: 历史记录 ID

        Returns:
            MemoryChangeHistory 如果存在，否则 None
        """


class L2GroupMemberRepositoryPort(Protocol):
    """L2 群组成员关系仓储端口。

    领域层定义接口，基础设施层实现。
    用于验证 group 记忆的访问权限。
    """

    async def is_group_member(self, group_id: str, user_id: str) -> bool:
        """检查用户是否是群组成员。

        Args:
            group_id: 群组 ID
            user_id: 用户 ID

        Returns:
            True 如果用户是群组成员，否则 False
        """

    async def is_group_admin(self, group_id: str, user_id: str) -> bool:
        """检查用户是否是群组管理员。

        Args:
            group_id: 群组 ID
            user_id: 用户 ID

        Returns:
            True 如果用户是群组管理员，否则 False
        """

    async def add_member(self, group_id: str, user_id: str, role: str = "member") -> None:
        """添加群组成员。

        Args:
            group_id: 群组 ID
            user_id: 用户 ID
            role: 角色（member/admin）
        """

    async def remove_member(self, group_id: str, user_id: str) -> None:
        """移除群组成员。

        Args:
            group_id: 群组 ID
            user_id: 用户 ID
        """
