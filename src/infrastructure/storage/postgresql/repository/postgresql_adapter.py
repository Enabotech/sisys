"""基础设施层 PostgreSQL 适配器模块

L2RdbPort 领域仓储的泛型基类，使用 SQLAlchemy AsyncSession 实现
Session 从 ContextVar 读取（非构造器注入），子类只需实现 _to_entity/_to_model

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar, cast
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.ports.l2_rdb import L2RdbPort
from src.infrastructure.storage.postgresql.models import Base
from src.infrastructure.storage.postgresql.session_context import get_session

TEntity = TypeVar("TEntity")
TModel = TypeVar("TModel", bound=Base)


class PostgreSQLAdapter(L2RdbPort[TEntity], Generic[TEntity, TModel]):
    """领域仓储泛型基类，实现 L2RdbPort[TEntity] 与 ORM 转换

    子类必须实现：
    - _to_entity(model: TModel) -> TEntity
    - _to_model(entity: TEntity) -> TModel
    - pk_column: str = "id"（可覆写为 "memory_id" 等）

    Session 通过 ContextVar 从 session_context 模块获取
    """

    pk_column: str = "id"
    soft_delete_column: str | None = None

    def __init__(self, model_class: type[TModel]) -> None:
        """初始化 PostgreSQL 适配器

        Args:
            model_class: SQLAlchemy 模型类
        """
        self._model_class: type[TModel] = model_class

    @property
    def _session(self) -> AsyncSession:
        """从 ContextVar 获取 AsyncSession。"""
        return get_session()

    def _to_entity(self, model: TModel) -> TEntity:
        """将 ORM 模型转换为领域实体（子类必须覆写）。"""
        raise NotImplementedError

    def _to_model(self, entity: TEntity) -> TModel:
        """将领域实体转换为 ORM 模型（子类必须覆写）。"""
        raise NotImplementedError

    async def get_by_id(self, id: UUID) -> TEntity | None:
        """根据主键获取实体

        Args:
            id: 实体主键

        Returns:
            领域实体，未找到返回 None
        """
        stmt = select(self._model_class).where(cast("Any", self._model_class).__table__.c[self.pk_column] == id)
        stmt = self._apply_soft_delete_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def save(self, entity: TEntity) -> TEntity:
        """保存实体（插入或更新）

        Args:
            entity: 领域实体

        Returns:
            持久化后的领域实体（含数据库生成的 id、时间戳等）
        """
        model = self._to_model(entity)
        await self._do_save(model, entity)
        return self._to_entity(model)

    async def delete(self, id: UUID) -> None:
        """删除实体（硬删除或软删除）

        Args:
            id: 实体主键
        """
        if self.soft_delete_column:
            await self._soft_delete(id)
        else:
            await self._hard_delete(id)

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[TEntity]:
        """获取实体列表

        Args:
            skip: 跳过的记录数
            limit: 最大返回记录数

        Returns:
            领域实体列表
        """
        stmt = select(self._model_class).offset(skip).limit(limit)
        stmt = self._apply_soft_delete_filter(stmt)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def count(self) -> int:
        """获取实体总数

        Returns:
            实体总数
        """
        result = await self._session.execute(select(func.count()).select_from(self._model_class))
        return int(result.scalar() or 0)

    async def _do_save(self, model: TModel, entity: TEntity) -> None:
        """保存钩子 — 默认简单插入，子类可覆写实现 UPSERT。"""
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)

    def _apply_soft_delete_filter(self, stmt: Any) -> Any:
        """应用软删除过滤条件。"""
        if self.soft_delete_column:
            col = cast("Any", self._model_class).__table__.c[self.soft_delete_column]
            return stmt.where(col.is_(None))
        return stmt

    async def _soft_delete(self, id: UUID) -> None:
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

    async def _hard_delete(self, id: UUID) -> None:
        """硬删除 — 物理移除记录。"""
        stmt = select(self._model_class).where(cast("Any", self._model_class).__table__.c[self.pk_column] == id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model:
            await self._session.delete(model)
            await self._session.flush()
