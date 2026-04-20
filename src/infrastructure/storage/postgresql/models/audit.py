"""AuditLogModel — SQLAlchemy model for audit_log table.

Reference: Story 1.10 SDD规范定义
Reference: FR-SC-02 Unified audit log (log_id/timestamp/actor/action_type/target_resource/old_value/new_value)
Reference: FR-SC-04 Multi-dimensional search extension (correction_level)
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
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, registry

# Registry for all PostgreSQL models
pg_registry = registry()


class Base(DeclarativeBase):
    """Base class for all PostgreSQL models."""

    registry = pg_registry


class AuditLogModel(Base):
    """SQLAlchemy model for the audit_log table.

    Stores audit log entries per FR-SC-02.

    Standard fields (FR-SC-02):
        id: Auto-increment primary key
        log_id: UUID identifier for external reference
        timestamp: When the audited action occurred
        actor: User ID or system component
        action_type: Type of action performed
        target_resource: Resource that was acted upon
        old_value: State before the action (JSON)
        new_value: State after the action (JSON)

    Extension fields (FR-SC-04):
        correction_level: Correction level (L0-L3) for trace-related events

    System fields:
        checksum: SHA256 checksum for integrity verification
        created_at: Record creation timestamp
        archived: Whether the record has been archived to WORM
        archived_at: When the record was archived
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
        """Initialize an audit log entry.

        Args:
            log_id: UUID identifier for the audit log entry.
            timestamp: When the audited action occurred.
            actor: User ID or system component.
            action_type: Type of action performed.
            target_resource: Resource that was acted upon.
            old_value: State before the action.
            new_value: State after the action.
            correction_level: Correction level (L0-L3, optional).
            correlation_id: Optional correlation ID for tracing.
            checksum: SHA256 checksum (auto-computed if None).
            archived: Whether archived to WORM.
            archived_at: When archived.
            created_at: Record creation time.
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
        """Compute SHA256 checksum for integrity verification.

        Returns:
            str: SHA256 hex digest of the record's critical fields.
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
        """Verify the integrity of this audit log entry.

        Returns:
            bool: True if the checksum matches, False if tampered.
        """
        return self.checksum == self._compute_checksum()

    def to_dict(self) -> dict:
        """Convert to dictionary representation.

        Returns:
            dict: Dictionary with all audit log fields.
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
