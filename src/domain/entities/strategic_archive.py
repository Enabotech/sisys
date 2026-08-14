"""领域层战略档案实体模块

定义战略档案实体，用于永久存储 SP/BP 的关键假设变量、决策依据、实际执行偏差。
实体遵循六边形架构零依赖原则，仅使用 Python 标准库。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from src.domain.exceptions import EntityBusinessRuleError, EntityValidationError


class ArchiveType(str, Enum):
    """战略档案类型枚举

    Attributes:
        ASSUMPTION: 关键假设变量
        DECISION: 决策依据
        DEVIATION: 实际执行偏差
        EVIDENCE_PACKAGE: 证据包
    """

    ASSUMPTION = "assumption"
    DECISION = "decision"
    DEVIATION = "deviation"
    EVIDENCE_PACKAGE = "evidence_package"


@dataclass
class StrategicArchive:
    """战略档案实体

    封装 SP/BP 战略规划归档数据，携带六层存储引用（L2+L3+L4+L5）。
    档案创建后不可修改（不可变记录），元数据可通过 metadata 扩展字段为后续 Story 预留。

    不变量约束:
    - archive_id 必须为有效 UUID
    - archive_type 必须为有效 ArchiveType
    - created_at 必须早于或等于 archived_at
    - archive_type 为 ASSUMPTION/DECISION/DEVIATION 时，plan_id 不能为空
    """

    archive_id: uuid.UUID
    plan_id: uuid.UUID | None = None
    plan_type: str = ""
    archive_type: ArchiveType = ArchiveType.ASSUMPTION
    created_by: uuid.UUID | None = None
    version: int = 1
    assumptions: dict[str, Any] = field(default_factory=dict)
    decision_basis: dict[str, Any] = field(default_factory=dict)
    execution_deviation: dict[str, Any] = field(default_factory=dict)
    metadata_ref: str = ""
    embedding_ref: str | None = None
    blob_ref: str | None = None
    graph_ref: str | None = None
    created_at: datetime | None = None
    archived_at: datetime | None = None
    deleted_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> bool:
        """验证实体不变量约束

        Returns:
            所有不变量满足时返回 True

        Raises:
            EntityValidationError: 不变量验证失败时抛出
            EntityBusinessRuleError: 业务规则违反时抛出
        """
        if not isinstance(self.archive_id, uuid.UUID):
            raise EntityValidationError(
                message="archive_id must be a valid UUID",
                context={"entity": "StrategicArchive", "field": "archive_id"},
            )
        if not isinstance(self.archive_type, ArchiveType):
            raise EntityValidationError(
                message="archive_type must be a valid ArchiveType",
                context={"entity": "StrategicArchive", "field": "archive_type"},
            )
        if self.plan_type not in ("SP", "BP", ""):
            raise EntityValidationError(
                message="plan_type must be 'SP' or 'BP'",
                context={"entity": "StrategicArchive", "field": "plan_type"},
            )
        if self.version < 1:
            raise EntityValidationError(
                message="version must be >= 1",
                context={"entity": "StrategicArchive", "field": "version"},
            )
        if self.created_at is not None and self.archived_at is not None:
            if self.created_at > self.archived_at:
                raise EntityBusinessRuleError(
                    message="created_at must be before or equal to archived_at",
                    context={"entity": "StrategicArchive", "rule": "timestamp_ordering"},
                )
        # deleted_at 晚于 created_at 和 archived_at
        if self.deleted_at is not None:
            if self.created_at is not None and self.deleted_at < self.created_at:
                raise EntityBusinessRuleError(
                    message="deleted_at must be after created_at",
                    context={"entity": "StrategicArchive", "rule": "deleted_at_after_created_at"},
                )
            if self.archived_at is not None and self.deleted_at < self.archived_at:
                raise EntityBusinessRuleError(
                    message="deleted_at must be after archived_at",
                    context={"entity": "StrategicArchive", "rule": "deleted_at_after_archived_at"},
                )
        # 非证据包类型必须有 plan_id
        if self.archive_type in (ArchiveType.ASSUMPTION, ArchiveType.DECISION, ArchiveType.DEVIATION):
            if self.plan_id is None:
                raise EntityBusinessRuleError(
                    message="plan_id must not be None for ASSUMPTION/DECISION/DEVIATION archive types",
                    context={"entity": "StrategicArchive", "rule": "plan_id_required"},
                )
        return True


__all__ = [
    "ArchiveType",
    "StrategicArchive",
]
