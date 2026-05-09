"""PostgreSQLMemoryChangeHistoryRepository — L2 PostgreSQL 持久化实现。

使用 SQLAlchemy AsyncSession，支持：
- 多用户并行：会话级别隔离
- 线程安全：异步操作，依赖数据库事务
- append-only：只允许新增，不允许修改或删除

架构来源: architecture.md §11.2.5
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.memory_change_history import MemoryChangeHistory
from src.domain.ports.l2_rdb import L2ChangeHistoryRepositoryPort
from src.infrastructure.storage.postgresql.models.memory import MemoryChangeHistoryModel


class PostgreSQLMemoryChangeHistoryRepository(L2ChangeHistoryRepositoryPort):
    """PostgreSQL 记忆变更历史仓储。

    使用 AsyncSession 提供异步、线程安全的数据库操作。
    append-only 模式：只允许新增记录，不允许修改或删除。

    delete 操作会创建新记录（change_type='delete'），而非真正删除历史。
    """

    def __init__(self, session: AsyncSession):
        """初始化 PostgreSQLMemoryChangeHistoryRepository。

        Args:
            session: SQLAlchemy 异步会话（非线程共享，会话绑定到特定连接）
        """
        self._session = session

    def _to_model(self, entity: MemoryChangeHistory) -> MemoryChangeHistoryModel:
        """将领域实体转换为数据库模型。"""
        return MemoryChangeHistoryModel(
            id=entity.id,
            memory_id=entity.memory_id,
            version=entity.version,
            changed_at=entity.changed_at,
            changed_by=entity.changed_by,
            change_type=entity.change_type,
            changed_fields=entity.changed_fields,
            diff_summary=entity.diff_summary,
            archived_ref=entity.archived_ref,
        )

    def _to_entity(self, model: MemoryChangeHistoryModel) -> MemoryChangeHistory:
        """将数据库模型转换为领域实体。"""
        return MemoryChangeHistory(
            id=model.id,
            memory_id=model.memory_id,
            version=model.version,
            changed_at=model.changed_at,
            changed_by=model.changed_by or "",
            change_type=model.change_type,
            changed_fields=model.changed_fields or {},
            diff_summary=model.diff_summary or "",
            archived_ref=model.archived_ref or "",
        )

    async def save(self, history: MemoryChangeHistory) -> None:
        """保存历史记录（append-only）。

        每次调用都会创建新记录，不允许修改或删除历史。

        Args:
            history: 变更历史记录
        """
        model = self._to_model(history)
        self._session.add(model)
        await self._session.flush()

    async def get_by_memory_id(self, memory_id: UUID) -> list[MemoryChangeHistory]:
        """获取记忆的所有历史记录。

        按 changed_at 升序排序（时间顺序）。

        Args:
            memory_id: 记忆 ID

        Returns:
            变更历史列表（按时间排序）
        """
        result = await self._session.execute(
            select(MemoryChangeHistoryModel)
            .where(MemoryChangeHistoryModel.memory_id == memory_id)
            .order_by(MemoryChangeHistoryModel.changed_at.asc())
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def get_by_id(self, history_id: UUID) -> MemoryChangeHistory | None:
        """通过 ID 获取历史记录。

        Args:
            history_id: 历史记录 ID

        Returns:
            MemoryChangeHistory 如果存在，否则 None
        """
        result = await self._session.execute(select(MemoryChangeHistoryModel).where(MemoryChangeHistoryModel.id == history_id))
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_entity(model)
