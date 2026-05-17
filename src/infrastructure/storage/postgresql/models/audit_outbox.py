"""基础设施层审计发件箱模型模块

定义审计发件箱的 SQLAlchemy ORM 模型，对应 audit_outbox 表
遵循事务发件箱模式（ADR-003）实现可靠异步发布

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.storage.postgresql.models.outbox import Base


class AuditOutboxModel(Base):
    """审计发件箱 SQLAlchemy 模型，对应 audit_outbox 表

    通过事务发件箱模式存储审计事件，确保可靠异步发布
    事件在与业务操作相同的事务中写入，然后由后台处理器处理

    Attributes:
        id: 自增主键
        event_id: 审计事件的 UUID
        event_type: 类型判别器（"AuditEvent"）
        payload: 包含审计数据的 JSON 负载
        status: 处理状态（"pending"、"published"、"failed"）
        created_at: 事件写入发件箱的时间
        processed_at: 事件成功发布的时间
        retry_count: 发布尝试次数
        max_retries: 最大允许尝试次数
        error_message: 失败时的最后一条错误消息
    """

    __tablename__ = "audit_outbox"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'published', 'failed')",
            name="ck_audit_outbox_status_values",
        ),
        CheckConstraint("retry_count >= 0", name="ck_audit_outbox_retry_count_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[UUID] = mapped_column(PG_UUID, unique=True, nullable=False, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, default="AuditEvent")
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    def __init__(
        self,
        event_id: UUID,
        payload: dict,
        event_type: str = "AuditEvent",
        status: str = "pending",
        created_at: datetime | None = None,
        processed_at: datetime | None = None,
        retry_count: int = 0,
        max_retries: int = 3,
        error_message: str | None = None,
    ) -> None:
        """初始化审计发件箱条目

        Args:
            event_id: 审计事件的 UUID
            payload: 包含审计数据的 JSON 负载
            event_type: 类型判别器（默认 "AuditEvent"）
            status: 处理状态（默认 "pending"）
            created_at: 事件写入时间
            processed_at: 成功发布时间
            retry_count: 尝试次数
            max_retries: 最大允许尝试次数
            error_message: 最后一条错误消息
        """
        self.event_id = event_id
        self.event_type = event_type
        self.payload = payload
        self.status = status
        self.created_at = created_at or datetime.now(UTC)
        self.processed_at = processed_at
        self.retry_count = retry_count
        self.max_retries = max_retries
        self.error_message = error_message

    def mark_published(self) -> None:
        """标记此条目为已成功发布。"""
        self.status = "published"
        self.processed_at = datetime.now(UTC)

    def mark_failed(self, error: str) -> None:
        """标记此条目为失败并记录错误消息

        Args:
            error: 描述失败的错误消息
        """
        self.status = "failed"
        self.error_message = error
        self.retry_count += 1

    def can_retry(self) -> bool:
        """检查此条目是否可以重试

        Returns:
            retry_count 小于 max_retries 时返回 True
        """
        return self.retry_count < self.max_retries

    def to_dict(self) -> dict:
        """转换为字典表示

        Returns:
            包含所有发件箱字段的字典
        """
        return {
            "id": self.id,
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "payload": self.payload,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "error_message": self.error_message,
        }
