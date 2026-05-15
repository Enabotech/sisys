"""PostgreSQLMemoryGroupMemberRepository — L2 群组成员关系持久化实现。

使用 SQLAlchemy AsyncSession，支持：
- 多用户并行：会话级别隔离
- 线程安全：异步操作，依赖数据库事务

架构来源: architecture.md §11.2.9 AC-2 RBAC 校验

Session 来源：
- Session 通过 ContextVar 由 middleware 或 test fixture 提供
- 无需构造器注入 session 参数
"""

from __future__ import annotations

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.ports.memory_repository import L2GroupMemberRepositoryPort
from src.infrastructure.storage.postgresql.models.memory import MemoryGroupMemberModel
from src.infrastructure.storage.postgresql.session_context import get_session


class PostgreSQLMemoryGroupMemberRepository(L2GroupMemberRepositoryPort):
    """PostgreSQL 群组成员关系仓储。

    使用 AsyncSession 提供异步、线程安全的数据库操作。
    支持多用户并发的会话级别隔离。
    """

    @property
    def _session(self) -> AsyncSession:
        return get_session()

    async def is_group_member(self, group_id: str, user_id: str) -> bool:
        """检查用户是否是群组成员。

        Args:
            group_id: 群组 ID
            user_id: 用户 ID

        Returns:
            True 如果用户是群组成员，否则 False
        """
        stmt = select(MemoryGroupMemberModel).where(
            and_(
                MemoryGroupMemberModel.group_id == group_id,
                MemoryGroupMemberModel.user_id == user_id,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def is_group_admin(self, group_id: str, user_id: str) -> bool:
        """检查用户是否是群组管理员。

        Args:
            group_id: 群组 ID
            user_id: 用户 ID

        Returns:
            True 如果用户是群组管理员，否则 False
        """
        stmt = select(MemoryGroupMemberModel).where(
            and_(
                MemoryGroupMemberModel.group_id == group_id,
                MemoryGroupMemberModel.user_id == user_id,
                MemoryGroupMemberModel.role == "admin",
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def add_member(self, group_id: str, user_id: str, role: str = "member") -> None:
        """添加群组成员。

        Args:
            group_id: 群组 ID
            user_id: 用户 ID
            role: 角色（member/admin）
        """
        member = MemoryGroupMemberModel(
            group_id=group_id,
            user_id=user_id,
            role=role,
        )
        self._session.add(member)
        await self._session.flush()

    async def remove_member(self, group_id: str, user_id: str) -> None:
        """移除群组成员。

        Args:
            group_id: 群组 ID
            user_id: 用户 ID
        """
        stmt = delete(MemoryGroupMemberModel).where(
            and_(
                MemoryGroupMemberModel.group_id == group_id,
                MemoryGroupMemberModel.user_id == user_id,
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()
