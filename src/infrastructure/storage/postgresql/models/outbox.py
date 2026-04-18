"""OutboxModel — SQLAlchemy model for event_outbox table."""

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

# Registry for all PostgreSQL models
pg_registry = registry()


class Base(DeclarativeBase):
    """Base class for all PostgreSQL models."""

    registry = pg_registry


class OutboxModel(Base):
    """SQLAlchemy model for the event_outbox table.

    Stores domain events for reliable async publishing (Outbox pattern).
    """

    __tablename__ = "event_outbox"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'published', 'failed')",
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
