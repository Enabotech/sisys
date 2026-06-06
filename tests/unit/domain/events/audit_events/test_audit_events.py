"""Test AuditEvent - Domain Event.

Reference: Story 1.10 Task 0 - SDD Specification
Reference: FR-SC-02 Unified Audit Log
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from src.domain.exceptions import EntityValidationError


class TestAuditEventCreation:
    """Test AuditEvent creation."""

    def test_create_audit_event_with_required_fields(self):
        """Can create AuditEvent with required fields."""
        from src.domain.events.audit_events import AuditEvent

        log_id = uuid.uuid4()
        timestamp = datetime.now(UTC)
        event = AuditEvent(
            log_id=log_id,
            timestamp=timestamp,
            actor="user-123",
            action_type="document:upload",
            target_resource="document/doc-456",
        )

        assert event.log_id == log_id
        assert event.timestamp == timestamp
        assert event.actor == "user-123"
        assert event.action_type == "document:upload"
        assert event.target_resource == "document/doc-456"

    def test_create_audit_event_with_optional_fields(self):
        """Can create AuditEvent with optional fields."""
        from src.domain.events.audit_events import AuditEvent

        old_value = {"status": "draft"}
        new_value = {"status": "published"}

        event = AuditEvent(
            log_id=uuid.uuid4(),
            timestamp=datetime.now(UTC),
            actor="user-123",
            action_type="document:upload",
            target_resource="document/doc-456",
            old_value=old_value,
            new_value=new_value,
            correction_level=1,
        )

        assert event.old_value == old_value
        assert event.new_value == new_value
        assert event.correction_level == 1

    def test_audit_event_is_frozen(self):
        """AuditEvent is frozen (immutable)."""
        from src.domain.events.audit_events import AuditEvent

        event = AuditEvent(
            log_id=uuid.uuid4(),
            timestamp=datetime.now(UTC),
            actor="user-123",
            action_type="document:upload",
            target_resource="document/doc-456",
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            event.actor = "changed"

    def test_audit_event_requires_actor(self):
        """AuditEvent requires non-empty actor."""
        from src.domain.events.audit_events import AuditEvent

        with pytest.raises(EntityValidationError, match="actor is required"):
            AuditEvent(
                log_id=uuid.uuid4(),
                timestamp=datetime.now(UTC),
                actor="",
                action_type="document:upload",
                target_resource="document/doc-456",
            )

    def test_audit_event_requires_action_type(self):
        """AuditEvent requires non-empty action_type."""
        from src.domain.events.audit_events import AuditEvent

        with pytest.raises(EntityValidationError, match="action_type is required"):
            AuditEvent(
                log_id=uuid.uuid4(),
                timestamp=datetime.now(UTC),
                actor="user-123",
                action_type="",
                target_resource="document/doc-456",
            )


class TestAuditEventSerialization:
    """Test AuditEvent serialization."""

    def test_to_dict_includes_audit_fields_in_payload(self):
        """to_dict() includes audit-specific fields in payload."""
        from src.domain.events.audit_events import AuditEvent

        log_id = uuid.uuid4()
        timestamp = datetime.now(UTC)
        event = AuditEvent(
            log_id=log_id,
            timestamp=timestamp,
            actor="user-123",
            action_type="document:upload",
            target_resource="document/doc-456",
            old_value={"status": "draft"},
            new_value={"status": "published"},
            correction_level=0,
        )

        d = event.to_dict()

        # Audit fields are in payload (DomainEvent.to_dict() puts subclass fields there)
        assert d["payload"]["log_id"] == str(log_id)
        assert d["payload"]["actor"] == "user-123"
        assert d["payload"]["action_type"] == "document:upload"
        assert d["payload"]["target_resource"] == "document/doc-456"
        assert d["payload"]["old_value"] == {"status": "draft"}
        assert d["payload"]["new_value"] == {"status": "published"}
        assert d["payload"]["correction_level"] == 0

    def test_to_audit_dict_returns_fr_sc02_fields(self):
        """to_audit_dict() returns FR-SC-02 fields."""
        from src.domain.events.audit_events import AuditEvent

        log_id = uuid.uuid4()
        timestamp = datetime.now(UTC)
        event = AuditEvent(
            log_id=log_id,
            timestamp=timestamp,
            actor="user-123",
            action_type="document:upload",
            target_resource="document/doc-456",
            old_value={"status": "draft"},
            new_value={"status": "published"},
            correction_level=2,
        )

        audit_dict = event.to_audit_dict()

        assert audit_dict["log_id"] == str(log_id)
        assert audit_dict["timestamp"] == timestamp.isoformat()
        assert audit_dict["actor"] == "user-123"
        assert audit_dict["action_type"] == "document:upload"
        assert audit_dict["target_resource"] == "document/doc-456"
        assert audit_dict["correction_level"] == 2


class TestAuditActionType:
    """Test AuditActionType enum."""

    def test_authentication_action_types(self):
        """Has authentication action types."""
        from src.domain.events.audit_events import AuditActionType

        assert AuditActionType.AUTHENTICATION_LOGIN.value == "authentication:login"
        assert AuditActionType.AUTHENTICATION_LOGOUT.value == "authentication:logout"
        assert AuditActionType.AUTHENTICATION_FAILED.value == "authentication:failed"

    def test_document_action_types(self):
        """Has document action types."""
        from src.domain.events.audit_events import AuditActionType

        assert AuditActionType.DOCUMENT_UPLOAD.value == "document:upload"
        assert AuditActionType.DOCUMENT_DOWNLOAD.value == "document:download"
        assert AuditActionType.DOCUMENT_DELETE.value == "document:delete"
        assert AuditActionType.DOCUMENT_PROCESS.value == "document:process"

    def test_agent_action_types(self):
        """Has agent action types."""
        from src.domain.events.audit_events import AuditActionType

        assert AuditActionType.AGENT_DECIDE.value == "agent:decide"
        assert AuditActionType.AGENT_EXECUTE.value == "agent:execute"
        assert AuditActionType.AGENT_ROUTE.value == "agent:route"

    def test_correction_action_types(self):
        """Has correction action types."""
        from src.domain.events.audit_events import AuditActionType

        assert AuditActionType.CORRECTION_APPROVE.value == "correction:approve"
        assert AuditActionType.CORRECTION_REJECT.value == "correction:reject"
        assert AuditActionType.CORRECTION_APPLY.value == "correction:apply"
