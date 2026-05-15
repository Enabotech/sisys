"""PostgreSQLAdapter[TEntity, TModel] — L2RdbPort domain repository base.

Refactoring notes:
- Session is now read from ContextVar, not constructor injection
- Subclasses only need _to_entity/_to_model and optional pk_column override
- Deprecated BaseRepository alias retained for backward compatibility
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar, cast

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.storage.postgresql.models import Base
from src.infrastructure.storage.postgresql.session_context import get_session

TEntity = TypeVar("TEntity")
TModel = TypeVar("TModel", bound=Base)


class PostgreSQLAdapter(Generic[TEntity, TModel]):
    """Domain repository base — implements L2RdbPort[TEntity] with ORM conversion.

    Subclasses must implement:
    - _to_entity(model: TModel) -> TEntity
    - _to_model(entity: TEntity) -> TModel
    - pk_column: str = "id" (overridable to "memory_id" etc.)

    Session is read from ContextVar via session_context module.
    """

    pk_column: str = "id"
    soft_delete_column: str | None = None

    def __init__(self, model_class: type[TModel]) -> None:
        """Initialize PostgreSQLAdapter.

        Args:
            model_class: SQLAlchemy model class
        """
        self._model_class: type[TModel] = model_class

    @property
    def _session(self) -> AsyncSession:
        """Get AsyncSession from ContextVar."""
        return get_session()

    def _to_entity(self, model: TModel) -> TEntity:
        """ORM model -> domain entity (subclass must override)."""
        raise NotImplementedError

    def _to_model(self, entity: TEntity) -> TModel:
        """Domain entity -> ORM model (subclass must override)."""
        raise NotImplementedError

    async def get_by_id(self, id: Any) -> TEntity | None:
        """Get entity by primary key.

        Args:
            id: Entity primary key

        Returns:
            Domain entity, or None if not found
        """
        stmt = select(self._model_class).where(cast("Any", self._model_class).__table__.c[self.pk_column] == id)
        stmt = self._apply_soft_delete_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def save(self, entity: TEntity) -> TEntity:
        """Save entity (insert or update).

        Args:
            entity: Domain entity

        Returns:
            Persisted domain entity (with DB-generated id, timestamps, etc.).
        """
        model = self._to_model(entity)
        await self._do_save(model, entity)
        return self._to_entity(model)

    async def delete(self, id: Any) -> None:
        """Delete entity (hard delete or soft delete).

        Args:
            id: Entity primary key
        """
        if self.soft_delete_column:
            await self._soft_delete(id)
        else:
            await self._hard_delete(id)

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[TEntity]:
        """Get entity list.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records

        Returns:
            List of domain entities
        """
        stmt = select(self._model_class).offset(skip).limit(limit)
        stmt = self._apply_soft_delete_filter(stmt)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def count(self) -> int:
        """Get total entity count."""
        result = await self._session.execute(select(func.count()).select_from(self._model_class))
        return int(result.scalar() or 0)

    async def _do_save(self, model: TModel, entity: TEntity) -> None:
        """Save hook — default simple insert, subclass can override for UPSERT."""
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)

    def _apply_soft_delete_filter(self, stmt: Any) -> Any:
        """Apply soft delete filter condition."""
        if self.soft_delete_column:
            col = cast("Any", self._model_class).__table__.c[self.soft_delete_column]
            return stmt.where(col.is_(None))
        return stmt

    async def _soft_delete(self, id: Any) -> None:
        """Soft delete — set deleted_at timestamp."""
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
        """Hard delete — physically remove record."""
        stmt = select(self._model_class).where(cast("Any", self._model_class).__table__.c[self.pk_column] == id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model:
            await self._session.delete(model)
            await self._session.flush()


# Deprecated alias — use PostgreSQLAdapter instead
BaseRepository = PostgreSQLAdapter
