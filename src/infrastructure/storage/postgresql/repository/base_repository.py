"""PostgreSQLAdapter[TEntity, TModel] — L2RdbPort 领域仓储基座。

重构说明：
- 原 BaseRepository[T] 重命名为 PostgreSQLAdapter[TEntity, TModel]
- BaseRepository 保留为 deprecated 别名
- 提供领域实体/ORM模型转换层（_to_entity/_to_model）
- 提供可配置 pk_column/soft_delete_column
- 提供 _do_save 钩子（UPSERT/append-only）
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar, cast

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.storage.postgresql.models import Base

TEntity = TypeVar("TEntity")
TModel = TypeVar("TModel", bound=Base)


class PostgreSQLAdapter(Generic[TEntity, TModel]):
    """领域仓储基座 — 实现 L2RdbPort[TEntity]，提供 ORM↔Entity 转换。

    子类只需实现:
    - _to_entity(model: TModel) -> TEntity
    - _to_model(entity: TEntity) -> TModel
    - pk_column: str = "id"（可覆写为 "memory_id" 等）
    """

    pk_column: str = "id"
    soft_delete_column: str | None = None

    def __init__(self, model_class: type[TModel], session: AsyncSession):
        """初始化 PostgreSQLAdapter。

        Args:
            model_class: SQLAlchemy 模型类
            session: 异步数据库会话
        """
        self._model_class: type[TModel] = model_class
        self._session = session

    def _to_entity(self, model: TModel) -> TEntity:
        """ORM 模型 → 领域实体（子类必须覆写）。"""
        raise NotImplementedError

    def _to_model(self, entity: TEntity) -> TModel:
        """领域实体 → ORM 模型（子类必须覆写）。"""
        raise NotImplementedError

    async def get_by_id(self, id: Any) -> TEntity | None:
        """根据 ID 获取实体。

        Args:
            id: 实体主键

        Returns:
            领域实体，不存在则返回 None
        """
        stmt = select(self._model_class).where(
            cast("Any", self._model_class).__table__.c[self.pk_column] == id
        )
        stmt = self._apply_soft_delete_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def save(self, entity: TEntity) -> TEntity:
        """保存实体（insert or update）。

        Args:
            entity: 领域实体

        Returns:
            持久化后的领域实体（含 DB 生成的 id、timestamps 等字段）。
        """
        model = self._to_model(entity)
        await self._do_save(model, entity)
        return self._to_entity(model)

    async def delete(self, id: Any) -> None:
        """删除实体（硬删除或软删除）。

        Args:
            id: 实体主键
        """
        if self.soft_delete_column:
            await self._soft_delete(id)
        else:
            await self._hard_delete(id)

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[TEntity]:
        """获取实体列表。

        Args:
            skip: 跳过数量
            limit: 返回数量上限

        Returns:
            领域实体列表
        """
        stmt = select(self._model_class).offset(skip).limit(limit)
        stmt = self._apply_soft_delete_filter(stmt)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def count(self) -> int:
        """获取实体总数。"""
        result = await self._session.execute(select(func.count()).select_from(self._model_class))
        return int(result.scalar() or 0)

    async def _do_save(self, model: TModel, entity: TEntity) -> None:
        """保存钩子 — 默认简单插入，子类可覆写为 UPSERT/乐观锁。"""
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)

    def _apply_soft_delete_filter(self, stmt: Any) -> Any:
        """应用软删除过滤条件。"""
        if self.soft_delete_column:
            col = cast("Any", self._model_class).__table__.c[self.soft_delete_column]
            return stmt.where(col.is_(None))
        return stmt

    async def _soft_delete(self, id: Any) -> None:
        """软删除 — 设置 deleted_at 时间戳。"""
        from datetime import datetime, timezone

        col_name = self.soft_delete_column
        if col_name is None:
            return
        stmt = (
            update(self._model_class)
            .where(cast("Any", self._model_class).__table__.c[self.pk_column] == id)
            .values(**{col_name: datetime.now(timezone.utc)})
        )
        stmt = self._apply_soft_delete_filter(stmt)
        await self._session.execute(stmt)
        await self._session.flush()

    async def _hard_delete(self, id: Any) -> None:
        """硬删除 — 物理删除记录。"""
        stmt = select(self._model_class).where(
            cast("Any", self._model_class).__table__.c[self.pk_column] == id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model:
            await self._session.delete(model)
            await self._session.flush()


# Deprecated alias — use PostgreSQLAdapter instead
BaseRepository = PostgreSQLAdapter
