"""AuditOutboxModel — SQLAlchemy model for audit_outbox table.

Reference: Story 1.10 SDD规范定义
Reference: architecture.md - ADR-003 Transactional Outbox Pattern
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
    """SQLAlchemy model for the audit_outbox table.

    Stores audit events for reliable async publishing via the
    Transactional Outbox Pattern. Events are written in the same
    transaction as the business operation, then processed by a
    background processor.

    Fields:
        id: Auto-increment primary key
        event_id: UUID of the audit event
        event_type: Type discriminator ("AuditEvent")
        payload: JSON payload containing audit data
        status: Processing status ("pending", "published", "failed")
        created_at: When the event was written to outbox
        processed_at: When the event was successfully published
        retry_count: Number of publishing attempts
        max_retries: Maximum allowed attempts
        error_message: Last error message if failed
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
        """Initialize an audit outbox entry.

        Args:
            event_id: UUID of the audit event.
            payload: JSON payload containing audit data.
            event_type: Type discriminator (default: "AuditEvent").
            status: Processing status (default: "pending").
            created_at: When the event was written.
            processed_at: When successfully published.
            retry_count: Number of attempts.
            max_retries: Maximum allowed attempts.
            error_message: Last error message.
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
        """Mark this entry as successfully published."""
        self.status = "published"
        self.processed_at = datetime.now(UTC)

    def mark_failed(self, error: str) -> None:
        """Mark this entry as failed with an error message.

        Args:
            error: Error message describing the failure.
        """
        self.status = "failed"
        self.error_message = error
        self.retry_count += 1

    def can_retry(self) -> bool:
        """Check if this entry can be retried.

        Returns:
            bool: True if retry_count < max_retries.
        """
        return self.retry_count < self.max_retries

    def to_dict(self) -> dict:
        """Convert to dictionary representation.

        Returns:
            dict: Dictionary with all outbox fields.
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
