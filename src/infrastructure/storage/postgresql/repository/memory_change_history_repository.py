"""PostgreSQLMemoryChangeHistoryRepository — L2 PostgreSQL 持久化实现。

使用 SQLAlchemy AsyncSession，支持：
- 多用户并行：会话级别隔离
- 线程安全：异步操作，依赖数据库事务
- append-only：只允许新增，不允许修改或删除

架构来源: architecture.md §11.2.5

重构说明（Phase 3）：
- 继承 PostgreSQLAdapter[MemoryChangeHistory, MemoryChangeHistoryModel]
- 覆写 delete 抛出 NotImplementedError（append-only）
- 自动获得父类 get_by_id/save/list_all

Session 来源：
- Session 通过 ContextVar 由 middleware 或 test fixture 提供
- 无需构造器注入 session 参数
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from src.domain.entities.memory_change_history import MemoryChangeHistory
from src.domain.ports.memory_repository import L2ChangeHistoryRepositoryPort
from src.infrastructure.storage.postgresql.models.memory import MemoryChangeHistoryModel
from src.infrastructure.storage.postgresql.repository.base_repository import PostgreSQLAdapter


class PostgreSQLMemoryChangeHistoryRepository(
    PostgreSQLAdapter[MemoryChangeHistory, MemoryChangeHistoryModel],
    L2ChangeHistoryRepositoryPort,
):
    """PostgreSQL 记忆变更历史仓储。

    继承 PostgreSQLAdapter，覆写 delete 为抛出异常。
    append-only 模式：只允许新增记录，不允许修改或删除。
    """
    def __init__(self) -> None:
        super().__init__(MemoryChangeHistoryModel)

    async def delete(self, id: UUID) -> None:
        """删除实体 — append-only 禁止删除。

        Raises:
            NotImplementedError: 变更历史不可删除
        """
        raise NotImplementedError("Change history is append-only, cannot delete")

    async def save(self, history: MemoryChangeHistory) -> MemoryChangeHistory:
        """保存历史记录（append-only）。

        使用父类 save 实现（简单插入）。

        Args:
            history: 变更历史记录

        Returns:
            保存后的变更历史记录
        """
        model = self._to_model(history)
        self._session.add(model)
        await self._session.flush()
        return history

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
