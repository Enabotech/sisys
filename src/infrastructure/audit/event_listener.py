"""AuditEventListener — Event listener for audit integration.

Listens to domain events and automatically converts them
to audit log entries.

Reference: Story 1.10 SDD规范定义
Reference: AC-5 Event-driven integration requirements
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from src.domain.events.base import DomainEvent
from src.domain.services.audit_service import AuditService

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class AuditEventListener:
    """Listens to domain events and records audit logs.

    Maps domain events to audit events based on configured rules.
    Supports event filtering and aggregation to reduce log volume.
    """

    def __init__(
        self,
        audit_service: AuditService,
    ) -> None:
        """Initialize AuditEventListener.

        Args:
            audit_service: The audit service for recording logs.
        """
        self._audit_service = audit_service
        self._event_type_map: dict[str, str] = {
            # Authentication events
            "AuthenticationEvent": "authentication:login",
            "LogoutEvent": "authentication:logout",
            "LoginFailedEvent": "authentication:failed",
            "AccountLockedEvent": "authentication:locked",
            # Authorization events
            "AuthorizationGrantedEvent": "authorization:grant",
            "AuthorizationRevokedEvent": "authorization:revoke",
            "AuthorizationDeniedEvent": "authorization:access",
            # Document events
            "DocumentProcessed": "document:process",
            "DocumentUploaded": "document:upload",
            "DocumentDownloaded": "document:download",
            "DocumentDeleted": "document:delete",
            # Agent events
            "AgentDecided": "agent:decide",
            "AgentExecuted": "agent:execute",
            "RoutingDecided": "agent:route",
            # Checkpoint events
            "CheckpointReached": "checkpoint:create",
            "CheckpointRecovered": "checkpoint:restore",
            "CheckpointReplay": "checkpoint:replay",
            # Correction events
            "CorrectionApproved": "correction:approve",
            "CorrectionRejected": "correction:reject",
            "CorrectionApplied": "correction:apply",
            # System events
            "SystemInitialized": "system:init",
            "SystemShutdown": "system:shutdown",
            "ConfigChanged": "system:config_change",
        }

    def handle_event(self, event: DomainEvent) -> None:
        """Handle a domain event and record an audit log.

        WARNING: This method MUST NOT be called from within an async context.
        Use handle_event_async() in async contexts instead.

        Args:
            event: The domain event to process.

        Raises:
            RuntimeError: If called from within an existing event loop.
        """
        import asyncio

        try:
            # Check if we're already in an async context
            asyncio.get_running_loop()
            raise RuntimeError("handle_event() called from async context. " "Use handle_event_async() instead.")
        except RuntimeError as e:
            # "no running event loop" means we're in sync context - this is OK
            if "no running event loop" not in str(e).lower():
                raise

        try:
            audit_data = self._event_to_audit(event)
            if audit_data is None:
                logger.debug(f"Event {event.event_type} filtered, not recording audit")
                return

            # Record the audit log synchronously via asyncio.run
            asyncio.run(
                self._audit_service.log(
                    actor=audit_data["actor"],
                    action_type=audit_data["action_type"],
                    target_resource=audit_data["target_resource"],
                    old_value=audit_data.get("old_value"),
                    new_value=audit_data.get("new_value"),
                    correlation_id=audit_data.get("correlation_id"),
                    correction_level=audit_data.get("correction_level"),
                )
            )

            logger.debug(f"Recorded audit for event: {event.event_type}")

        except Exception as e:
            logger.error(f"Failed to record audit for event {event.event_type}: {e}")

    async def handle_event_async(self, event: DomainEvent) -> None:
        """Handle a domain event asynchronously and record an audit log.

        Args:
            event: The domain event to process.
        """
        try:
            audit_data = self._event_to_audit(event)
            if audit_data is None:
                logger.debug(f"Event {event.event_type} filtered, not recording audit")
                return

            await self._audit_service.log(
                actor=audit_data["actor"],
                action_type=audit_data["action_type"],
                target_resource=audit_data["target_resource"],
                old_value=audit_data.get("old_value"),
                new_value=audit_data.get("new_value"),
                correlation_id=audit_data.get("correlation_id"),
                correction_level=audit_data.get("correction_level"),
            )

            logger.debug(f"Recorded audit for event: {event.event_type}")

        except Exception as e:
            logger.error(f"Failed to record audit for event {event.event_type}: {e}")

    def _event_to_audit(self, event: DomainEvent) -> dict[str, Any] | None:
        """Convert a domain event to audit log data.

        Args:
            event: The domain event to convert.

        Returns:
            dict | None: Audit log data, or None if event should be filtered.
        """
        # Map event type to action type
        action_type = self._event_type_map.get(event.event_type)
        if action_type is None:
            # Unknown event type, use generic mapping
            action_type = f"event:{event.event_type.lower()}"

        # Extract actor from event source or payload
        actor = self._extract_actor(event)

        # Extract target resource
        target_resource = self._extract_target_resource(event)

        # Extract old/new values for state change events
        old_value, new_value = self._extract_state_changes(event)

        # Extract correlation ID if present
        correlation_id = event.payload.get("correlation_id")

        # Extract correction level if applicable
        correction_level = event.payload.get("correction_level")

        return {
            "actor": actor,
            "action_type": action_type,
            "target_resource": target_resource,
            "old_value": old_value,
            "new_value": new_value,
            "correlation_id": correlation_id,
            "correction_level": correction_level,
        }

    def _extract_actor(self, event: DomainEvent) -> str:
        """Extract the actor (user/system) from an event.

        Args:
            event: The domain event.

        Returns:
            str: The actor identifier.
        """
        # Try to get actor from payload
        if "actor" in event.payload:
            return str(event.payload["actor"])

        # Try to get user_id from payload
        if "user_id" in event.payload:
            return str(event.payload["user_id"])

        # Fall back to source
        return event.source or "system"

    def _extract_target_resource(self, event: DomainEvent) -> str:
        """Extract the target resource from an event.

        Args:
            event: The domain event.

        Returns:
            str: The target resource identifier.
        """
        # Try to get resource from payload
        if "resource" in event.payload:
            return str(event.payload["resource"])

        if "target" in event.payload:
            return str(event.payload["target"])

        if "document_id" in event.payload:
            return f"document:{event.payload['document_id']}"

        if "entity_type" in event.payload and "entity_id" in event.payload:
            return f"{event.payload['entity_type']}:{event.payload['entity_id']}"

        # Fall back to aggregate type and ID
        if event.aggregate_type and event.aggregate_id:
            return f"{event.aggregate_type}:{event.aggregate_id}"

        return f"event:{event.event_type}"

    def _extract_state_changes(self, event: DomainEvent) -> tuple[dict[str, Any], dict[str, Any]]:
        """Extract old and new values from an event.

        Args:
            event: The domain event.

        Returns:
            tuple: (old_value, new_value) dictionaries.
        """
        old_value = event.payload.get("old_value", {})
        new_value = event.payload.get("new_value", {})

        # Handle events with explicit before/after state
        if "before" in event.payload:
            old_value = event.payload["before"]
        if "after" in event.payload:
            new_value = event.payload["after"]

        return old_value, new_value

    def register_event_type(self, event_type: str, action_type: str) -> None:
        """Register a custom event type to action type mapping.

        Args:
            event_type: The domain event type name.
            action_type: The corresponding audit action type.
        """
        self._event_type_map[event_type] = action_type
