"""领域层 Schema 验证记录实体模块

定义 SchemaValidationRecord 聚合根 + SchemaValidationRecordQuery 查询值对象,
用于持久化 Tool 输入/输出 Schema 验证历史。

设计依据：Story 4.3 AC-5
- 11 字段聚合根：record_id / execution_id / tool_id / tenant_id / validation_phase /
  is_valid / violations / retry_attempt / validated_at / schema_version / failure_reason
- Query Object 模式(CLAUDE.md §4)：多字段组合 + 分页 → frozen dataclass
- 与 ToolChainRun / ToolExecution 聚合根严格对齐 EntityValidationError 校验惯例
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from src.domain.exceptions import EntityValidationError
from src.domain.services.schema_validator import SchemaViolation

ValidationPhase = Literal["INPUT", "OUTPUT", "COMPATIBILITY"]


@dataclass(frozen=True)
class SchemaValidationRecordQuery:
    """SchemaValidationRecord 查询值对象（Query Object 模式,CLAUDE.md §4）

    Attributes:
        tenant_id: 多租户隔离（可选）
        tool_id: 按工具过滤（可选）
        execution_id: 按执行 ID 过滤（可选）
        validation_phase: 按校验阶段过滤（可选）
        is_valid: 按校验结果过滤（可选）
        offset: 分页偏移（默认 0）
        limit: 分页大小（默认 100）
    """

    tenant_id: uuid.UUID | None = None
    tool_id: uuid.UUID | None = None
    execution_id: uuid.UUID | None = None
    validation_phase: ValidationPhase | None = None
    is_valid: bool | None = None
    offset: int = 0
    limit: int = 100


@dataclass(frozen=True)
class SchemaValidationRecord:
    """Schema 验证记录聚合根（Story 4.3 AC-5,11 字段）

    Attributes:
        record_id: 记录主键（UUID）
        execution_id: 关联 ToolExecution ID
        tool_id: 工具 ID
        tenant_id: 多租户隔离
        validation_phase: 校验阶段（INPUT / OUTPUT / COMPATIBILITY）
        is_valid: 是否通过
        violations: 违规列表（SchemaViolation 元组）
        retry_attempt: 当前重试次数（1-based）
        validated_at: 校验时间戳
        schema_version: Tool.version 快照（用于 4.6 兼容性追踪）
        failure_reason: 失败原因（人类可读）
    """

    record_id: uuid.UUID
    execution_id: uuid.UUID
    tool_id: uuid.UUID
    tenant_id: uuid.UUID
    validation_phase: ValidationPhase
    is_valid: bool
    violations: tuple[SchemaViolation, ...] = ()
    retry_attempt: int = 1
    validated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    schema_version: str = "1.0.0"
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        """构造时强制校验所有不变量(沿用 ToolChainRun / ToolExecution 模式)"""
        self.validate()

    def validate(self) -> bool:
        """验证字段不变量

        Raises:
            EntityValidationError: 任何不变量违反
        """
        if not isinstance(self.record_id, uuid.UUID):
            raise EntityValidationError(
                message="record_id must be a valid UUID",
                context={"entity": "SchemaValidationRecord", "field": "record_id"},
            )
        if not isinstance(self.execution_id, uuid.UUID):
            raise EntityValidationError(
                message="execution_id must be a valid UUID",
                context={"entity": "SchemaValidationRecord", "field": "execution_id"},
            )
        if not isinstance(self.tool_id, uuid.UUID):
            raise EntityValidationError(
                message="tool_id must be a valid UUID",
                context={"entity": "SchemaValidationRecord", "field": "tool_id"},
            )
        if not isinstance(self.tenant_id, uuid.UUID):
            raise EntityValidationError(
                message="tenant_id must be a valid UUID",
                context={"entity": "SchemaValidationRecord", "field": "tenant_id"},
            )
        if self.validation_phase not in ("INPUT", "OUTPUT", "COMPATIBILITY"):
            raise EntityValidationError(
                message="validation_phase 必须为 INPUT / OUTPUT / COMPATIBILITY",
                context={
                    "entity": "SchemaValidationRecord",
                    "field": "validation_phase",
                    "value": self.validation_phase,
                },
            )
        if self.retry_attempt < 1:
            raise EntityValidationError(
                message="retry_attempt 必须 ≥ 1",
                context={
                    "entity": "SchemaValidationRecord",
                    "field": "retry_attempt",
                    "value": self.retry_attempt,
                },
            )
        if not self.is_valid and not self.violations:
            raise EntityValidationError(
                message="is_valid=False 时 violations 必须非空",
                context={
                    "entity": "SchemaValidationRecord",
                    "field": "violations",
                    "is_valid": self.is_valid,
                },
            )
        if self.validated_at.tzinfo is None:
            raise EntityValidationError(
                message="validated_at 必须为 timezone-aware",
                context={
                    "entity": "SchemaValidationRecord",
                    "field": "validated_at",
                },
            )
        return True

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict（供事件 payload / 日志 / API 响应使用）"""
        return {
            "record_id": str(self.record_id),
            "execution_id": str(self.execution_id),
            "tool_id": str(self.tool_id),
            "tenant_id": str(self.tenant_id),
            "validation_phase": self.validation_phase,
            "is_valid": self.is_valid,
            "violations": [v.to_dict() for v in self.violations],
            "retry_attempt": self.retry_attempt,
            "validated_at": self.validated_at.isoformat(),
            "schema_version": self.schema_version,
            "failure_reason": self.failure_reason,
        }


__all__ = [
    "SchemaValidationRecord",
    "SchemaValidationRecordQuery",
]
