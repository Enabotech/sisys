"""Test AuditEventListener - Red Phase (Test First).

TDD Cycle: Red -> Green -> Refactor
Reference: Story 1.10 Task 3 - Event-Driven Audit Integration
"""

from __future__ import annotations

import uuid
from unittest import mock

import pytest

from src.domain.events.base import DomainEvent


class TestAuditEventListenerMapping:
    """Test event-to-audit mapping."""

    def test_maps_authentication_events(self):
        """Maps authentication events to audit action types."""
        from src.infrastructure.audit.event_listener import AuditEventListener

        mock_service = mock.Mock()
        listener = AuditEventListener(audit_service=mock_service)

        # Test mapping exists for authentication events
        assert "AuthenticationEvent" in listener._event_type_map
        assert listener._event_type_map["AuthenticationEvent"] == "authentication:login"

    def test_maps_document_events(self):
        """Maps document events to audit action types."""
        from src.infrastructure.audit.event_listener import AuditEventListener

        mock_service = mock.Mock()
        listener = AuditEventListener(audit_service=mock_service)

        assert "DocumentProcessed" in listener._event_type_map
        assert listener._event_type_map["DocumentProcessed"] == "document:process"

    def test_maps_agent_events(self):
        """Maps agent events to audit action types."""
        from src.infrastructure.audit.event_listener import AuditEventListener

        mock_service = mock.Mock()
        listener = AuditEventListener(audit_service=mock_service)

        assert "AgentDecided" in listener._event_type_map
        assert listener._event_type_map["AgentDecided"] == "agent:decide"

    def test_register_custom_event_type(self):
        """register_event_type() adds custom mapping."""
        from src.infrastructure.audit.event_listener import AuditEventListener

        mock_service = mock.Mock()
        listener = AuditEventListener(audit_service=mock_service)

        listener.register_event_type("CustomEvent", "custom:action")

        assert listener._event_type_map["CustomEvent"] == "custom:action"


class TestAuditEventListenerHandleEvent:
    """Test handle_event() method."""

    def test_extracts_actor_from_event_payload(self):
        """Extracts actor from event payload."""
        from src.infrastructure.audit.event_listener import AuditEventListener

        mock_service = mock.Mock()
        mock_service.log = mock.Mock(return_value=uuid.uuid4())

        listener = AuditEventListener(audit_service=mock_service)

        event = DomainEvent(
            event_type="DocumentProcessed",
            source="test",
            payload={"actor": "user-456", "resource": "doc-123"},
        )

        listener.handle_event(event)

        # Verify log was called with correct actor
        call_args = mock_service.log.call_args
        assert call_args.kwargs["actor"] == "user-456"

    def test_extracts_target_resource(self):
        """Extracts target resource from event payload."""
        from src.infrastructure.audit.event_listener import AuditEventListener

        mock_service = mock.Mock()
        mock_service.log = mock.Mock(return_value=uuid.uuid4())

        listener = AuditEventListener(audit_service=mock_service)

        event = DomainEvent(
            event_type="DocumentProcessed",
            source="test",
            payload={"actor": "user-456", "resource": "doc-123"},
        )

        listener.handle_event(event)

        call_args = mock_service.log.call_args
        assert call_args.kwargs["target_resource"] == "doc-123"

    def test_uses_event_type_as_action_type(self):
        """Uses mapped event type as action type."""
        from src.infrastructure.audit.event_listener import AuditEventListener

        mock_service = mock.Mock()
        mock_service.log = mock.Mock(return_value=uuid.uuid4())

        listener = AuditEventListener(audit_service=mock_service)

        event = DomainEvent(
            event_type="DocumentProcessed",
            source="test",
            payload={"actor": "user-456"},
        )

        listener.handle_event(event)

        call_args = mock_service.log.call_args
        assert call_args.kwargs["action_type"] == "document:process"

    def test_uses_generic_action_for_unknown_event_type(self):
        """Uses generic action type for unknown events."""
        from src.infrastructure.audit.event_listener import AuditEventListener

        mock_service = mock.Mock()
        mock_service.log = mock.Mock(return_value=uuid.uuid4())

        listener = AuditEventListener(audit_service=mock_service)

        event = DomainEvent(
            event_type="UnknownEvent",
            source="test",
            payload={"actor": "user-456"},
        )

        listener.handle_event(event)

        call_args = mock_service.log.call_args
        assert call_args.kwargs["action_type"] == "event:unknownevent"

    def test_extracts_correction_level(self):
        """Extracts correction_level from event payload."""
        from src.infrastructure.audit.event_listener import AuditEventListener

        mock_service = mock.Mock()
        mock_service.log = mock.Mock(return_value=uuid.uuid4())

        listener = AuditEventListener(audit_service=mock_service)

        event = DomainEvent(
            event_type="CorrectionApproved",
            source="test",
            payload={"actor": "user-456", "correction_level": 2},
        )

        listener.handle_event(event)

        call_args = mock_service.log.call_args
        assert call_args.kwargs["correction_level"] == 2

    def test_handles_exception_gracefully(self):
        """Handles exceptions without crashing."""
        from src.infrastructure.audit.event_listener import AuditEventListener

        mock_service = mock.Mock()
        mock_service.log = mock.Mock(side_effect=Exception("Test error"))

        listener = AuditEventListener(audit_service=mock_service)

        event = DomainEvent(
            event_type="DocumentProcessed",
            source="test",
            payload={"actor": "user-456"},
        )

        # Should not raise
        listener.handle_event(event)


class TestAuditEventListenerAsync:
    """Test handle_event_async() method."""

    @pytest.mark.asyncio
    async def test_handle_event_async_awaits_log(self):
        """handle_event_async() properly awaits log()."""
        from src.infrastructure.audit.event_listener import AuditEventListener

        mock_service = mock.AsyncMock()
        mock_service.log = mock.AsyncMock(return_value=uuid.uuid4())

        listener = AuditEventListener(audit_service=mock_service)

        event = DomainEvent(
            event_type="DocumentProcessed",
            source="test",
            payload={"actor": "user-456"},
        )

        await listener.handle_event_async(event)

        mock_service.log.assert_awaited_once()
