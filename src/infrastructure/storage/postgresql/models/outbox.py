"""基础设施层事件发件箱模型模块

定义事件发件箱的 SQLAlchemy ORM 模型和声明式基类，对应 event_outbox 表
实现事件可靠异步发布的发件箱模式
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
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, registry

# 所有 PostgreSQL 模型的注册表
pg_registry = registry()


class Base(DeclarativeBase):
    """所有 PostgreSQL 模型的声明式基类。"""

    registry = pg_registry


class OutboxModel(Base):
    """事件发件箱 SQLAlchemy 模型，对应 event_outbox 表

    存储领域事件用于可靠异步发布（发件箱模式）

    Attributes:
        id: 主键 UUID
        event_id: 事件唯一标识（唯一约束）
        event_type: 事件类型
        payload: JSON 负载
        status: 处理状态（"pending"、"published"、"failed"）
        created_at: 创建时间
        published_at: 发布时间
        retry_count: 重试次数
        max_retries: 最大重试次数
        error_message: 错误消息
    """

    __tablename__ = "event_outbox"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'published', 'failed', 'archived')",
            name="ck_outbox_status_values",
        ),
        CheckConstraint("retry_count >= 0", name="ck_outbox_retry_count_positive"),
        CheckConstraint("max_retries >= 0", name="ck_outbox_max_retries_positive"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(unique=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    def __init__(
        self,
        event_id: UUID,
        event_type: str,
        payload: dict,
        created_at: datetime,
        id: UUID | None = None,
        status: str = "pending",
        retry_count: int = 0,
        max_retries: int = 3,
        published_at: datetime | None = None,
        error_message: str | None = None,
    ) -> None:
        """初始化事件发件箱条目

        Args:
            event_id: 事件唯一标识
            event_type: 事件类型
            payload: JSON 负载
            created_at: 创建时间
            id: 主键 UUID，为 None 时自动生成
            status: 处理状态，默认 "pending"
            retry_count: 重试次数，默认 0
            max_retries: 最大重试次数，默认 3
            published_at: 发布时间，可选
            error_message: 错误消息，可选
        """
        self.id = id or uuid4()
        self.event_id = event_id
        self.event_type = event_type
        self.payload = payload
        self.status = status
        self.created_at = created_at
        self.published_at = published_at
        self.retry_count = retry_count
        self.max_retries = max_retries
        self.error_message = error_message
