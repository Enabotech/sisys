"""AuditServiceImpl — Audit service implementation.

Implements the AuditService protocol for unified audit logging.
Uses PostgreSQL for audit storage with transactional outbox pattern.

Reference: Story 1.10 SDD规范定义
Reference: architecture.md - ADR-003 Transactional Outbox Pattern
Reference: FR-SC-02 Unified audit log
"""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.ports.audit_service import AuditService
from src.domain.events.audit_events import AuditEvent
from src.infrastructure.config.audit import AuditConfig, get_audit_config
from src.infrastructure.storage.postgresql.models.audit import AuditLogModel
from src.infrastructure.storage.postgresql.models.audit_outbox import AuditOutboxModel

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class AuditError(Exception):
    """Base exception for audit service errors."""

    pass


class AuditIntegrityError(AuditError):
    """Raised when audit log integrity check fails."""

    pass


class AuditNotFoundError(AuditError):
    """Raised when audit log entry is not found."""

    pass


class AuditServiceImpl:
    """Audit service implementation.

    Implements the AuditService protocol for unified audit logging
    using PostgreSQL storage with transactional outbox pattern.
    """

    def __init__(
        self,
        session: AsyncSession,
        config: AuditConfig | None = None,
    ) -> None:
        """Initialize AuditService.

        Args:
            session: SQLAlchemy async session for database operations.
            config: Audit configuration. If None, loads from environment.
        """
        self._session = session
        self._config = config or get_audit_config()

    async def log(
        self,
        actor: str,
        action_type: str,
        target_resource: str,
        old_value: dict[str, Any] | None = None,
        new_value: dict[str, Any] | None = None,
        correlation_id: str | None = None,
        correction_level: int | None = None,
    ) -> UUID:
        """Record an audit log entry.

        Args:
            actor: User ID or system component performing the action.
            action_type: Type of action (e.g., "document:upload").
            target_resource: Resource being acted upon.
            old_value: State before the action (optional).
            new_value: State after the action (optional).
            correlation_id: Optional correlation ID for tracing.
            correction_level: Correction level (L0-L3, optional).

        Returns:
            UUID: The log_id of the created audit entry.

        Raises:
            AuditException: If logging fails.
        """
        log_id = uuid4()
        timestamp = datetime.now(UTC)

        # Create audit event for outbox
        event = AuditEvent(
            log_id=log_id,
            timestamp=timestamp,
            source="audit",
            actor=actor,
            action_type=action_type,
            target_resource=target_resource,
            old_value=old_value or {},
            new_value=new_value or {},
            correction_level=correction_level,
        )

        # Write to audit outbox (transactional outbox pattern)
        outbox_entry = AuditOutboxModel(
            event_id=event.event_id,
            event_type="AuditEvent",
            payload=event.to_dict(),
        )
        self._session.add(outbox_entry)

        # Also write directly to audit_log for synchronous reads
        audit_log = AuditLogModel(
            log_id=log_id,
            timestamp=timestamp,
            actor=actor,
            action_type=action_type,
            target_resource=target_resource,
            old_value=old_value or {},
            new_value=new_value or {},
            correction_level=correction_level,
            correlation_id=correlation_id,
        )
        self._session.add(audit_log)

        await self._session.flush()
        return log_id

    async def query(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        actor: str | None = None,
        action_type: str | None = None,
        target_resource: str | None = None,
        correction_level: int | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """Query audit logs with multi-dimensional filters.

        Args:
            start_time: Filter by start time (inclusive).
            end_time: Filter by end time (inclusive).
            actor: Filter by actor (exact match).
            action_type: Filter by action type (exact match).
            target_resource: Filter by target resource (prefix match).
            correction_level: Filter by correction level (L0-L3).
            page: Page number (1-indexed).
            page_size: Number of results per page.

        Returns:
            dict: Paginated results containing:
                - items: List of audit log entries
                - total: Total count of matching entries
                - page: Current page number
                - page_size: Results per page
                - total_pages: Total number of pages
        """
        # Build query
        query = select(AuditLogModel)
        count_query = select(func.count(AuditLogModel.id))

        # Apply filters
        if start_time is not None:
            query = query.where(AuditLogModel.timestamp >= start_time)
            count_query = count_query.where(AuditLogModel.timestamp >= start_time)
        if end_time is not None:
            query = query.where(AuditLogModel.timestamp <= end_time)
            count_query = count_query.where(AuditLogModel.timestamp <= end_time)
        if actor:
            query = query.where(AuditLogModel.actor == actor)
            count_query = count_query.where(AuditLogModel.actor == actor)
        if action_type:
            query = query.where(AuditLogModel.action_type == action_type)
            count_query = count_query.where(AuditLogModel.action_type == action_type)
        if target_resource:
            query = query.where(AuditLogModel.target_resource.like(f"{target_resource}%"))
            count_query = count_query.where(AuditLogModel.target_resource.like(f"{target_resource}%"))
        if correction_level is not None:
            query = query.where(AuditLogModel.correction_level == correction_level)
            count_query = count_query.where(AuditLogModel.correction_level == correction_level)

        # Apply pagination with validation
        if page_size <= 0:
            page_size = self._config.page_size_default
        if page_size > self._config.page_size_max:
            page_size = self._config.page_size_max
        if page < 1:
            page = 1

        # Get total count
        total_result = await self._session.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        query = query.order_by(AuditLogModel.timestamp.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        # Execute query
        result = await self._session.execute(query)
        records = result.scalars().all()

        # Convert to dicts
        items = [record.to_dict() for record in records]

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if page_size > 0 else 0,
        }

    async def get_by_id(self, log_id: UUID) -> dict[str, Any] | None:
        """Get a specific audit log entry by ID.

        Args:
            log_id: The unique identifier of the audit log entry.

        Returns:
            dict | None: The audit log entry, or None if not found.
        """
        query = select(AuditLogModel).where(AuditLogModel.log_id == log_id)
        result = await self._session.execute(query)
        record = result.scalar_one_or_none()

        if record is None:
            return None

        return record.to_dict()

    async def get_stats(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Get audit statistics for compliance reporting.

        Args:
            start_time: Start of time range.
            end_time: End of time range.

        Returns:
            dict: Statistics containing:
                - total_entries: Total number of audit entries
                - by_action_type: Counts grouped by action type
                - by_actor: Counts grouped by actor
                - time_range: Start and end timestamps
        """
        # Base filter
        base_filter = []
        if start_time is not None:
            base_filter.append(AuditLogModel.timestamp >= start_time)
        if end_time is not None:
            base_filter.append(AuditLogModel.timestamp <= end_time)

        # Total count
        total_query = select(func.count(AuditLogModel.id))
        if base_filter:
            total_query = total_query.where(*base_filter)
        total_result = await self._session.execute(total_query)
        total = total_result.scalar() or 0

        # By action type
        action_type_query = select(AuditLogModel.action_type, func.count(AuditLogModel.id)).group_by(AuditLogModel.action_type)
        if base_filter:
            action_type_query = action_type_query.where(*base_filter)
        action_type_result = await self._session.execute(action_type_query)
        by_action_type = {row[0]: row[1] for row in action_type_result.all()}

        # By actor
        actor_query = select(AuditLogModel.actor, func.count(AuditLogModel.id)).group_by(AuditLogModel.actor)
        if base_filter:
            actor_query = actor_query.where(*base_filter)
        actor_result = await self._session.execute(actor_query)
        by_actor = {row[0]: row[1] for row in actor_result.all()}

        return {
            "total_entries": total,
            "by_action_type": by_action_type,
            "by_actor": by_actor,
            "time_range": {
                "start": start_time.isoformat() if start_time else None,
                "end": end_time.isoformat() if end_time else None,
            },
        }

    async def verify_integrity(self, log_id: UUID) -> bool:
        """Verify the integrity of an audit log entry.

        Args:
            log_id: The unique identifier of the audit log entry.

        Returns:
            bool: True if the entry is intact, False if tampered.

        Raises:
            AuditNotFoundError: If the audit log entry is not found.
        """
        query = select(AuditLogModel).where(AuditLogModel.log_id == log_id)
        result = await self._session.execute(query)
        record = result.scalar_one_or_none()

        if record is None:
            raise AuditNotFoundError(f"Audit log entry not found: {log_id}")

        return record.verify_checksum()

    async def archive(self, log_id: UUID, retention_days: int = 2555) -> bool:
        """Archive an audit log entry to immutable storage.

        Note: Due to RLS policies on audit_log (deny UPDATE), this method
        cannot modify the archived flag in PostgreSQL. Instead, it prepares
        the audit record for V2 MinIO WORM archival.

        Args:
            log_id: The unique identifier of the audit log entry.
            retention_days: Number of days to retain (default: 7 years = 2555 days).

        Returns:
            bool: True if archival preparation succeeded.

        Raises:
            AuditNotFoundError: If the audit log entry is not found.
        """
        query = select(AuditLogModel).where(AuditLogModel.log_id == log_id)
        result = await self._session.execute(query)
        record = result.scalar_one_or_none()

        if record is None:
            raise AuditNotFoundError(f"Audit log entry not found: {log_id}")

        # Note: RLS on audit_log denies UPDATE operations.
        # The archived flag is informational for V2 MinIO WORM archival.
        # For MVP, we skip the PostgreSQL UPDATE since it would fail.

        if self._config.archive_enabled:
            # Future: Write to MinIO audit-archives bucket with Object Lock
            # This requires the MinIO client to be configured and bucket to exist
            logger.info(
                f"Archive prepared for log_id={log_id}, retention_days={retention_days}. "
                "V2: Will write to MinIO WORM storage."
            )

        return True


# Global instance (lazy loading)
_audit_service: AuditService | None = None


def get_audit_service(session: AsyncSession) -> AuditService:
    """Get an AuditService instance.

    Args:
        session: SQLAlchemy async session.

    Returns:
        AuditService: An audit service instance.
    """
    return AuditServiceImpl(session)
