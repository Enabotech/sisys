"""基础设施层工具版本 PostgreSQL 仓储（Story 4-6）

PostgreSQLToolVersionRepository：
- 继承 PostgreSQLAdapter[ToolVersion, ToolVersionModel] 泛型基类
  （SchemaValidationRecordRepository 先例——list_by_query/_apply_filters 扩展）
- IntegrityError → 领域异常转换（document_repository:156 等先例）：
  * (tool_id, version) 唯一冲突 → ToolVersionAlreadyExistsError (431)
  * 单 STABLE/单 CANARY partial unique index 冲突 → ToolVersionTrafficWeightError (432)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from src.domain.entities.tool_version import ToolVersion, ToolVersionStatus
from src.domain.exceptions.tool_version_exceptions import (
    ToolVersionAlreadyExistsError,
    ToolVersionTrafficWeightError,
)
from src.domain.ports.tool_version_repository import (
    ToolVersionQuery,
    ToolVersionRepositoryPort,
)
from src.infrastructure.storage.postgresql.models.tool_version import ToolVersionModel
from src.infrastructure.storage.postgresql.repository.postgresql_adapter import (
    PostgreSQLAdapter,
)

# partial unique index 名（IntegrityError 诊断转换的判别依据）
_SINGLE_STABLE_INDEX = "uq_tool_versions_single_stable"
_SINGLE_CANARY_INDEX = "uq_tool_versions_single_canary"


class PostgreSQLToolVersionRepository(PostgreSQLAdapter[ToolVersion, ToolVersionModel], ToolVersionRepositoryPort):
    """工具版本 PostgreSQL 仓储（PG 主实现，migration 016）。"""

    pk_column = "version_id"

    def __init__(self) -> None:
        """初始化仓储（绑定 ToolVersionModel）。"""
        super().__init__(ToolVersionModel)

    # ---- ORM 转换钩子 ----

    def _to_entity(self, model: ToolVersionModel) -> ToolVersion:
        """ORM 模型 → 领域实体。"""
        return ToolVersion(
            version_id=model.version_id,
            tool_id=model.tool_id,
            version=model.version,
            input_schema=dict(model.input_schema or {}),
            output_schema=dict(model.output_schema or {}),
            status=ToolVersionStatus(model.status),
            traffic_weight=model.traffic_weight,
            required_rollout_mode=model.required_rollout_mode,
            last_stable_at=model.last_stable_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: ToolVersion) -> ToolVersionModel:
        """领域实体 → ORM 模型。"""
        return ToolVersionModel(
            version_id=entity.version_id,
            tool_id=entity.tool_id,
            version=entity.version,
            input_schema=dict(entity.input_schema),
            output_schema=dict(entity.output_schema),
            status=entity.status.value,
            traffic_weight=entity.traffic_weight,
            required_rollout_mode=entity.required_rollout_mode,
            last_stable_at=entity.last_stable_at,
            created_at=entity.created_at,
            updated_at=datetime.now(UTC),
        )

    # ---- 保存（IntegrityError → 领域异常转换） ----

    async def save(self, entity: ToolVersion) -> ToolVersion:
        """保存版本（唯一约束冲突转换为 431/432 领域异常）。

        Args:
            entity: 版本实体

        Returns:
            持久化后的实体

        Raises:
            ToolVersionAlreadyExistsError: (tool_id, version) 唯一冲突（431）
            ToolVersionTrafficWeightError: 单活跃不变量并发破坏（432 并存冲突族）
        """
        entity.validate()
        try:
            return await super().save(entity)
        except IntegrityError as exc:
            error_text = f"{exc.statement or ''} {exc}"
            if _SINGLE_STABLE_INDEX in error_text or "single_stable" in error_text:
                raise ToolVersionTrafficWeightError(
                    tool_id=str(entity.tool_id),
                    version=entity.version,
                    conflict_reason="单 STABLE 不变量并发破坏（partial unique index）",
                    cause=exc,
                ) from exc
            if _SINGLE_CANARY_INDEX in error_text or "single_canary" in error_text:
                raise ToolVersionTrafficWeightError(
                    tool_id=str(entity.tool_id),
                    version=entity.version,
                    conflict_reason="单活跃 CANARY 不变量并发破坏（partial unique index）",
                    cause=exc,
                ) from exc
            raise ToolVersionAlreadyExistsError(
                tool_id=str(entity.tool_id),
                version=entity.version,
                cause=exc,
            ) from exc

    # ---- 领域扩展方法 ----

    async def get_by_tool_and_version(
        self,
        tool_id: uuid.UUID,
        version: str,
    ) -> ToolVersion | None:
        """按 (tool_id, version) 精确查找。"""
        model_cls = cast("Any", self._model_class)
        stmt = select(self._model_class).where(
            model_cls.__table__.c.tool_id == tool_id,
            model_cls.__table__.c.version == version,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_by_query(self, query: ToolVersionQuery) -> list[ToolVersion]:
        """Query Object 多字段过滤（注册时间升序 + offset/limit 分页）。"""
        stmt = select(self._model_class)
        stmt = self._apply_filters(stmt, query)
        model_cls = cast("Any", self._model_class)
        stmt = stmt.order_by(model_cls.__table__.c.created_at.asc())
        stmt = stmt.offset(query.offset).limit(query.limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def count(self, query: ToolVersionQuery | None = None) -> int:
        """统计符合条件的版本数量（无参调用兼容基类形态）。"""
        stmt = select(func.count()).select_from(self._model_class)
        if query is not None:
            stmt = self._apply_filters(stmt, query)
        result = await self._session.execute(stmt)
        return int(result.scalar() or 0)

    async def list_active(self, tool_id: uuid.UUID) -> list[ToolVersion]:
        """查询工具的活跃版本（CANARY + STABLE）。"""
        model_cls = cast("Any", self._model_class)
        stmt = select(self._model_class).where(
            model_cls.__table__.c.tool_id == tool_id,
            model_cls.__table__.c.status.in_(("canary", "stable")),
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    def _apply_filters(self, stmt: Any, query: ToolVersionQuery) -> Any:
        """逐字段过滤（None 跳过——SchemaValidationRecordRepository 先例）。"""
        model_cls = cast("Any", self._model_class)
        cols = model_cls.__table__.c
        if query.tool_id is not None:
            stmt = stmt.where(cols.tool_id == query.tool_id)
        if query.status is not None:
            stmt = stmt.where(cols.status == query.status.value)
        if query.version is not None:
            stmt = stmt.where(cols.version == query.version)
        if query.created_after is not None:
            stmt = stmt.where(cols.created_at >= query.created_after)
        if query.created_before is not None:
            stmt = stmt.where(cols.created_at < query.created_before)
        return stmt


__all__ = ["PostgreSQLToolVersionRepository"]
