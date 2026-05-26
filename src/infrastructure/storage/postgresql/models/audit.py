"""基础设施层审计日志模型模块

定义审计日志的 SQLAlchemy ORM 模型，对应 audit_log 表
遵循 FR-SC-02 统一审计日志规范和 FR-SC-04 多维度搜索扩展
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.storage.postgresql.models.outbox import Base


class AuditLogModel(Base):
    """审计日志 SQLAlchemy 模型，对应 audit_log 表

    存储审计日志条目，遵循 FR-SC-02 规范

    Attributes:
        id: 自增主键
        log_id: 外部引用的 UUID 标识符
        timestamp: 审计操作发生时间
        actor: 用户 ID 或系统组件
        action_type: 执行的操作类型
        target_resource: 被操作的资源
        old_value: 操作前的状态（JSON）
        new_value: 操作后的状态（JSON）
        correction_level: 修正级别（L0-L3），用于追溯相关事件
        checksum: 用于完整性校验的 SHA256 校验和
        created_at: 记录创建时间戳
        archived: 是否已归档至 WORM
        archived_at: 归档时间
        correlation_id: 用于追踪的关联 ID
    """

    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint(
            "correction_level IS NULL OR (correction_level >= 0 AND correction_level <= 3)",
            name="ck_audit_correction_level_range",
        ),
        Index("ix_audit_timestamp", "timestamp"),
        Index("ix_audit_actor", "actor"),
        Index("ix_audit_action_type", "action_type"),
        Index("ix_audit_correction_level", "correction_level"),
        Index("ix_audit_timestamp_actor", "timestamp", "actor"),
        Index("ix_audit_timestamp_action_type", "timestamp", "action_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    log_id: Mapped[UUID] = mapped_column(PG_UUID, unique=True, nullable=False, default=uuid4)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    actor: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    action_type: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    target_resource: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    old_value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    new_value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    correction_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    archived: Mapped[bool] = mapped_column(default=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    def __init__(
        self,
        log_id: UUID,
        timestamp: datetime,
        actor: str,
        action_type: str,
        target_resource: str,
        old_value: dict,
        new_value: dict,
        correction_level: int | None = None,
        correlation_id: str | None = None,
        checksum: str | None = None,
        archived: bool = False,
        archived_at: datetime | None = None,
        created_at: datetime | None = None,
    ) -> None:
        """初始化审计日志条目

        Args:
            log_id: 审计日志条目的 UUID 标识符
            timestamp: 审计操作发生的时间
            actor: 用户 ID 或系统组件
            action_type: 执行的操作类型
            target_resource: 被操作的资源
            old_value: 操作前的状态
            new_value: 操作后的状态
            correction_level: 修正级别（L0-L3，可选）
            correlation_id: 用于追踪的关联 ID（可选）
            checksum: SHA256 校验和（为 None 时自动计算）
            archived: 是否已归档至 WORM
            archived_at: 归档时间
            created_at: 记录创建时间
        """
        self.log_id = log_id
        self.timestamp = timestamp
        self.actor = actor
        self.action_type = action_type
        self.target_resource = target_resource
        self.old_value = old_value
        self.new_value = new_value
        self.correction_level = correction_level
        self.correlation_id = correlation_id
        self.archived = archived
        self.archived_at = archived_at
        self.created_at = created_at or datetime.now(UTC)

        # Auto-compute checksum if not provided
        if checksum is None:
            self.checksum = self._compute_checksum()
        else:
            self.checksum = checksum

    def _compute_checksum(self) -> str:
        """计算 SHA256 校验和用于完整性验证

        Returns:
            记录关键字段的 SHA256 十六进制摘要
        """
        content = json.dumps(
            {
                "log_id": str(self.log_id),
                "timestamp": self.timestamp.isoformat() if self.timestamp else "",
                "actor": self.actor,
                "action_type": self.action_type,
                "target_resource": self.target_resource,
                "old_value": self.old_value,
                "new_value": self.new_value,
                "correction_level": self.correction_level,
            },
            sort_keys=True,
        )
        return hashlib.sha256(content.encode()).hexdigest()

    def verify_checksum(self) -> bool:
        """验证审计日志条目的完整性

        Returns:
            校验和匹配返回 True，被篡改返回 False
        """
        return self.checksum == self._compute_checksum()

    def to_dict(self) -> dict:
        """转换为字典表示

        Returns:
            包含所有审计日志字段的字典
        """
        return {
            "id": self.id,
            "log_id": str(self.log_id),
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "actor": self.actor,
            "action_type": self.action_type,
            "target_resource": self.target_resource,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "correction_level": self.correction_level,
            "checksum": self.checksum,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "archived": self.archived,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
            "correlation_id": self.correlation_id,
            "integrity_verified": self.verify_checksum(),
        }
