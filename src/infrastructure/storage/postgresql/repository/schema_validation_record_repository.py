"""基础设施层 PostgreSQL SchemaValidationRecord 仓储

实现 SchemaValidationRecordRepositoryPort（Story 4.3 AC-5 + 4.3 后续技术债清理）：
- 继承 PostgreSQLAdapter[SchemaValidationRecord, SchemaValidationRecordModel]
- violations JSONB ↔ tuple[SchemaViolation, ...] 双向序列化
- 4 复合索引优化（与 migration 013 对齐）：
  * (tenant_id, execution_id)
  * (tenant_id, tool_id, validated_at DESC)
  * (tenant_id, validation_phase, is_valid)
  * (tenant_id, is_valid, validated_at DESC)
- 支持 SchemaValidationRecordQuery 多字段过滤

设计依据：Story 4.3 后续技术债清理(路径 2: SQLAlchemy ORM 风格)
- 与现有 archive_repository.py 模式一致
- 通过 _to_entity / _to_model 隔离领域层与 ORM 层
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select

from src.domain.entities.schema_validation_record import (
    SchemaValidationRecord,
    SchemaValidationRecordQuery,
)
from src.domain.exceptions import EntityValidationError
from src.domain.services.schema_validator import SchemaViolation
from src.infrastructure.storage.postgresql.models.schema_validation import (
    SchemaValidationRecordModel,
)
from src.infrastructure.storage.postgresql.repository.postgresql_adapter import (
    PostgreSQLAdapter,
)

logger = logging.getLogger(__name__)

_VALID_PHASES: frozenset[str] = frozenset({"INPUT", "OUTPUT", "COMPATIBILITY"})


class PostgreSQLSchemaValidationRecordRepository(PostgreSQLAdapter[SchemaValidationRecord, SchemaValidationRecordModel]):
    """Schema 验证记录仓储实现（SQLAlchemy ORM 风格）

    关键设计：
    - violations JSONB ↔ tuple[SchemaViolation, ...] 双向序列化
    - validation_phase 字符串值(INPUT/OUTPUT/COMPATIBILITY)严格校验
    - 4 复合索引由 Alembic migration 013 创建,query 自动命中
    """

    pk_column: str = "record_id"

    def __init__(self) -> None:
        super().__init__(SchemaValidationRecordModel)

    # ------------------------------------------------------------------
    # 实体/模型转换（violations JSONB ↔ tuple[SchemaViolation, ...]）
    # ------------------------------------------------------------------

    def _to_entity(self, model: SchemaValidationRecordModel) -> SchemaValidationRecord:
        """将 ORM 模型转换为领域实体

        Args:
            model: SQLAlchemy SchemaValidationRecordModel 实例

        Returns:
            SchemaValidationRecord 领域实体
        """
        violations_data: list[dict[str, Any]] = model.violations or []
        violations = tuple(self._deserialize_violation(v) for v in violations_data)
        # validation_phase 严格校验(防 DB 漂移 + CHECK 约束兜底)
        # 遵守 CLAUDE.md §5 红线(禁止 raise ValueError),改用 EntityValidationError (EXCEPTION_242)
        if model.validation_phase not in _VALID_PHASES:
            raise EntityValidationError(
                message=(
                    f"Invalid validation_phase in DB for record {model.record_id}: "
                    f"{model.validation_phase!r} not in {sorted(_VALID_PHASES)}"
                ),
                context={
                    "entity": "SchemaValidationRecord",
                    "field": "validation_phase",
                    "record_id": str(model.record_id),
                    "invalid_value": model.validation_phase,
                    "allowed_values": sorted(_VALID_PHASES),
                },
            )
        phase: Any = model.validation_phase  # Literal["INPUT", "OUTPUT", "COMPATIBILITY"]
        return SchemaValidationRecord(
            record_id=model.record_id,
            execution_id=model.execution_id,
            tool_id=model.tool_id,
            tenant_id=model.tenant_id,
            validation_phase=phase,
            is_valid=model.is_valid,
            violations=violations,
            retry_attempt=model.retry_attempt,
            validated_at=model.validated_at,
            schema_version=model.schema_version,
            failure_reason=model.failure_reason,
        )

    def _to_model(self, entity: SchemaValidationRecord) -> SchemaValidationRecordModel:
        """将领域实体转换为 ORM 模型

        Args:
            entity: SchemaValidationRecord 领域实体

        Returns:
            SQLAlchemy SchemaValidationRecordModel 实例
        """
        violations_data = [self._serialize_violation(v) for v in entity.violations]
        return SchemaValidationRecordModel(
            record_id=entity.record_id,
            execution_id=entity.execution_id,
            tool_id=entity.tool_id,
            tenant_id=entity.tenant_id,
            validation_phase=entity.validation_phase,
            is_valid=entity.is_valid,
            violations=violations_data,
            retry_attempt=entity.retry_attempt,
            validated_at=entity.validated_at,
            schema_version=entity.schema_version,
            failure_reason=entity.failure_reason,
        )

    @staticmethod
    def _serialize_violation(violation: SchemaViolation) -> dict[str, Any]:
        """SchemaViolation → dict（JSONB 元素）

        Args:
            violation: 不可变 SchemaViolation 实体

        Returns:
            可序列化为 JSONB 的 dict（actual 字段已经脱敏）
        """
        # 使用 SchemaViolation 自身的 to_dict() 复用脱敏逻辑
        return violation.to_dict()

    @staticmethod
    def _deserialize_violation(data: dict[str, Any]) -> SchemaViolation:
        """dict → SchemaViolation（JSONB 元素反序列化）

        Args:
            data: JSONB dict（来自 PG rows）

        Returns:
            SchemaViolation 不可变实体
        """
        return SchemaViolation(
            path=data["path"],
            expected=data["expected"],
            actual=data["actual"],
            message=data["message"],
        )

    # ------------------------------------------------------------------
    # SchemaValidationRecordRepositoryPort 实现
    # ------------------------------------------------------------------

    def _apply_filters(
        self,
        stmt: Any,
        query: SchemaValidationRecordQuery,
    ) -> Any:
        """应用 SchemaValidationRecordQuery 过滤条件到 statement

        Args:
            stmt: SQLAlchemy select/count statement
            query: 查询条件

        Returns:
            添加过滤条件后的 statement
        """
        if query.tenant_id is not None:
            stmt = stmt.where(SchemaValidationRecordModel.tenant_id == query.tenant_id)
        if query.tool_id is not None:
            stmt = stmt.where(SchemaValidationRecordModel.tool_id == query.tool_id)
        if query.execution_id is not None:
            stmt = stmt.where(SchemaValidationRecordModel.execution_id == query.execution_id)
        if query.validation_phase is not None:
            stmt = stmt.where(SchemaValidationRecordModel.validation_phase == query.validation_phase)
        if query.is_valid is not None:
            stmt = stmt.where(SchemaValidationRecordModel.is_valid == query.is_valid)
        return stmt

    async def list_by_query(
        self,
        query: SchemaValidationRecordQuery,
    ) -> list[SchemaValidationRecord]:
        """通过 Query Object 查询 SchemaValidationRecord 列表

        Args:
            query: 查询条件

        Returns:
            符合条件的记录列表（按 validated_at DESC + offset/limit）
        """
        stmt = select(SchemaValidationRecordModel)
        stmt = self._apply_filters(stmt, query)
        stmt = stmt.order_by(SchemaValidationRecordModel.validated_at.desc()).offset(query.offset).limit(query.limit)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def count(self, query: SchemaValidationRecordQuery | None = None) -> int:
        """统计符合条件的 SchemaValidationRecord 数量

        Args:
            query: 查询条件（None 时统计全量,兼容父类 PostgreSQLAdapter.count() 无参签名）

        Returns:
            数量
        """
        if query is None:
            query = SchemaValidationRecordQuery()
        stmt = select(func.count()).select_from(SchemaValidationRecordModel)
        stmt = self._apply_filters(stmt, query)
        result = await self._session.execute(stmt)
        return int(result.scalar() or 0)


__all__ = [
    "PostgreSQLSchemaValidationRecordRepository",
]
