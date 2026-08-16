"""领域层战略档案实体模块

定义战略档案实体，用于永久存储 SP/BP 的关键假设变量、决策依据、实际执行偏差。
实体遵循六边形架构零依赖原则，仅使用 Python 标准库。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from src.domain.exceptions import EntityBusinessRuleError, EntityValidationError


# 模块级时钟函数，支持测试注入
# 默认使用 datetime.now(UTC)，测试中可整体替换
def _now() -> datetime:
    """获取当前 UTC 时间，支持测试注入"""
    return datetime.now(UTC)


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
    valid_from: datetime | None = None
    valid_until: datetime | None = None
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
        # valid_from 不能晚于 valid_until（两者均非 None 时校验）
        if self.valid_from is not None and self.valid_until is not None and self.valid_from > self.valid_until:
            raise EntityValidationError(
                message="valid_from must be before or equal to valid_until",
                context={"entity": "StrategicArchive", "field": "valid_from"},
            )
        return True

    def is_valid(self) -> bool:
        """检查当前时间是否在有效期内

        valid_from 为 None 时仅检查 valid_until；
        valid_until 为 None 时仅检查 valid_from；
        两者均为 None 时返回 True（视为永久有效）。

        Returns:
            当前时间在有效期内返回 True，否则返回 False
        """
        now = _now()
        if self.valid_from is not None and self.valid_from > now:
            return False
        if self.valid_until is not None and self.valid_until < now:
            return False
        return True

    def is_expired(self) -> bool:
        """检查是否已过期

        Returns:
            valid_until 非 None 且当前时间晚于 valid_until 时返回 True
        """
        if self.valid_until is None:
            return False
        return _now() > self.valid_until

    def days_until_expiry(self) -> int | None:
        """计算距离过期的天数

        Returns:
            valid_until 为 None 时返回 None；
            已过期时返回负数；
            正常时返回剩余天数（向下取整）
        """
        if self.valid_until is None:
            return None
        delta = self.valid_until - _now()
        return delta.days

    def is_stale(self, ref_date: datetime | None = None) -> bool:
        """检查实体是否陈旧

        统一陈旧判定标准：
        - valid_until 非 None 时：valid_until < ref_date 为陈旧
        - valid_until 为 None 且 archived_at 非 None 时：archived_at < ref_date - 12个月 为陈旧
        - 两者均为 None 时返回 False

        Args:
            ref_date: 参考时间，None 时使用 _now()

        Returns:
            陈旧返回 True，否则返回 False
        """
        now = ref_date or _now()
        if self.valid_until is not None:
            return self.valid_until < now
        if self.archived_at is not None:
            return self.archived_at < now - timedelta(days=365)
        return False


__all__ = [
    "ArchiveType",
    "StrategicArchive",
    "_now",
]
