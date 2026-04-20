"""AuditService — Domain service interface for audit logging.

This module defines the audit service interface (Protocol)
following hexagonal architecture: domain layer defines interface,
infrastructure layer implements it.

Reference: architecture.md - ADR-003 Dual-channel event bus
Reference: FR-SC-02 Unified audit log requirements
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID

if TYPE_CHECKING:
    pass


class AuditService(Protocol):
    """Protocol defining audit service interface.

    The audit service is responsible for:
    - Recording audit log entries
    - Querying audit logs with multi-dimensional filters
    - Generating compliance reports
    - Ensuring audit log integrity

    This is a domain layer interface (Protocol) that must be implemented
    by the infrastructure layer (src/infrastructure/audit/audit_service.py).
    """

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

        Returns:
            UUID: The log_id of the created audit entry.

        Raises:
            AuditException: If logging fails.
        """
        ...

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
        ...

    async def get_by_id(self, log_id: UUID) -> dict[str, Any] | None:
        """Get a specific audit log entry by ID.

        Args:
            log_id: The unique identifier of the audit log entry.

        Returns:
            dict | None: The audit log entry, or None if not found.
        """
        ...

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
        ...

    async def verify_integrity(self, log_id: UUID) -> bool:
        """Verify the integrity of an audit log entry.

        Args:
            log_id: The unique identifier of the audit log entry.

        Returns:
            bool: True if the entry is intact, False if tampered.
        """
        ...

    async def archive(self, log_id: UUID, retention_days: int = 2555) -> bool:
        """Archive an audit log entry to immutable storage.

        Args:
            log_id: The unique identifier of the audit log entry.
            retention_days: Number of days to retain (default: 7 years = 2555 days).

        Returns:
            bool: True if archival succeeded.
        """
        ...
