"""AuditEvent — Domain events for audit logging.

AC-1 Standard fields (FR-SC-02):
    log_id: UUID identifier for the audit log entry
    timestamp: When the action occurred (UTC)
    actor: User ID or system component that performed the action
    action_type: Type of action performed
    target_resource: Resource that was acted upon
    old_value: State before the action (JSON)
    new_value: State after the action (JSON)

Extension fields (FR-SC-04 multi-dimensional search):
    correction_level: Correction level (L0-L3) for trace-related events

Reference: Story 1.10 SDD规范定义
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from src.domain.events.base import DomainEvent


class AuditActionType(str, Enum):
    """Audit action types for system operations."""

    # Authentication events
    AUTHENTICATION_LOGIN = "authentication:login"
    AUTHENTICATION_LOGOUT = "authentication:logout"
    AUTHENTICATION_FAILED = "authentication:failed"
    AUTHENTICATION_LOCKED = "authentication:locked"

    # Authorization events
    AUTHORIZATION_GRANT = "authorization:grant"
    AUTHORIZATION_REVOKE = "authorization:revoke"
    AUTHORIZATION_ACCESS = "authorization:access"

    # Document events
    DOCUMENT_UPLOAD = "document:upload"
    DOCUMENT_DOWNLOAD = "document:download"
    DOCUMENT_DELETE = "document:delete"
    DOCUMENT_PROCESS = "document:process"

    # Agent events
    AGENT_DECIDE = "agent:decide"
    AGENT_EXECUTE = "agent:execute"
    AGENT_ROUTE = "agent:route"

    # Checkpoint events
    CHECKPOINT_CREATE = "checkpoint:create"
    CHECKPOINT_RESTORE = "checkpoint:restore"
    CHECKPOINT_REPLAY = "checkpoint:replay"

    # Correction events
    CORRECTION_APPROVE = "correction:approve"
    CORRECTION_REJECT = "correction:reject"
    CORRECTION_APPLY = "correction:apply"

    # System events
    SYSTEM_CONFIG_CHANGE = "system:config_change"
    SYSTEM_INIT = "system:init"
    SYSTEM_SHUTDOWN = "system:shutdown"


@dataclass(frozen=True)
class AuditEvent(DomainEvent):
    """Domain event for audit log entries.

    Extends DomainEvent with audit-specific fields per FR-SC-02.

    Standard fields:
        event_id: Unique event identifier (from DomainEvent)
        event_type: "AuditEvent" (from DomainEvent)
        timestamp: When the audited action occurred (from DomainEvent)
        source: System component that produced this event
        aggregate_id: ID of the entity being audited
        aggregate_type: Type of entity being audited
        payload: Contains audit-specific fields

    Payload fields:
        log_id: UUID identifier for the audit log entry
        actor: User ID or system component
        action_type: Type of action performed
        target_resource: Resource that was acted upon
        old_value: State before the action (JSON)
        new_value: State after the action (JSON)
        correction_level: Correction level (L0-L3, optional)
    """

    event_type: str = "AuditEvent"
    source: str = "audit"
    log_id: UUID = field(default_factory=uuid4)
    actor: str = ""
    action_type: str = ""
    target_resource: str = ""
    old_value: dict[str, Any] = field(default_factory=dict)
    new_value: dict[str, Any] = field(default_factory=dict)
    correction_level: int | None = None

    def __post_init__(self) -> None:
        """Validate required fields after initialization."""
        if not self.actor:
            raise ValueError("actor is required for AuditEvent")
        if not self.action_type:
            raise ValueError("action_type is required for AuditEvent")
        if self.correction_level is not None and not (0 <= self.correction_level <= 3):
            raise ValueError("correction_level must be 0-3 or None")

    def to_audit_dict(self) -> dict[str, Any]:
        """Serialize to audit-specific dictionary format.

        Returns:
            Dictionary with FR-SC-02 fields: log_id, timestamp, actor,
            action_type, target_resource, old_value, new_value.
        """
        return {
            "log_id": str(self.log_id),
            "timestamp": self.timestamp.isoformat(),
            "actor": self.actor,
            "action_type": self.action_type,
            "target_resource": self.target_resource,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "correction_level": self.correction_level,
        }


# Register for polymorphic deserialization
DomainEvent.register("AuditEvent", AuditEvent)
