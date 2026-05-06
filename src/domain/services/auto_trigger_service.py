"""AutoTriggerService — domain service that processes domain/heartbeat events and emits AutoTriggered events."""

from __future__ import annotations

import logging
from typing import Protocol

from src.domain.events.auto_trigger_events import AutoTriggered
from src.domain.events.base import DomainEvent
from src.domain.value_objects.auto_trigger_context import AutoTriggerContext

logger = logging.getLogger(__name__)


class EventPublisherProtocol(Protocol):
    """Protocol for event publishing (implemented by infrastructure)."""

    async def publish(self, event: DomainEvent, channel: str | None = None) -> None: ...


class AutoTriggerService:
    """Domain service that listens to domain and heartbeat events, extracts context, and emits AutoTriggered events.

    Responsibilities:
    - Listen to domain events (DocumentProcessed, ToolExecuted, AgentDecided, etc.)
    - Listen to HeartbeatTriggered events from AutoHeartbeatScheduler
    - Extract session_id and task context using AutoTriggerContext
    - Publish AutoTriggered events to downstream route stage (Story 1.14b)

    Architecture: Domain layer (no external dependencies), uses port/protocol for event publishing.
    """

    def __init__(self, publisher: EventPublisherProtocol | None = None):
        """Initialize AutoTriggerService.

        Args:
            publisher: Event publisher port (infrastructure implements). None for standalone testing.
        """
        self._publisher = publisher

    async def on_domain_event(self, event: DomainEvent) -> AutoTriggered | None:
        """Handle a domain event: extract context and emit AutoTriggered.

        Args:
            event: DomainEvent subclass (DocumentProcessed, ToolExecuted, etc.)

        Returns:
            AutoTriggered event if context was extracted and published, None otherwise
        """
        logger.debug("Processing domain event: %s", event.event_type)

        # Build payload from event
        payload = event.payload.copy() if event.payload else {}
        payload["event_type"] = event.event_type

        # Extract context using factory
        context = AutoTriggerContext.from_domain_event(
            event_type=event.event_type,
            payload=payload,
            event_id=str(event.event_id) if event.event_id else None,
        )

        triggered = AutoTriggered(
            trigger_type=context.trigger_type,
            session_id=context.session_id,
            agent_id=context.agent_id,
            task_context=context.task_context,
            source_event_type=context.source_event_type,
            source_event_id=context.source_event_id,
        )

        await self._publish(triggered)
        return triggered

    async def on_heartbeat_event(self, event: DomainEvent) -> AutoTriggered | None:
        """Handle HeartbeatTriggered event: extract context and emit AutoTriggered.

        Args:
            event: HeartbeatTriggered domain event

        Returns:
            AutoTriggered event if published, None otherwise
        """
        logger.debug("Processing heartbeat event: %s", event.event_type)

        # Extract fields from heartbeat event
        heartbeat_id = str(getattr(event, "heartbeat_id", "unknown"))
        wake_reason = getattr(event, "wake_reason", "")
        todo_items = getattr(event, "todo_items", ())
        cost_budget = getattr(event, "cost_budget", 0.0)

        context = AutoTriggerContext.from_heartbeat(
            heartbeat_id=heartbeat_id,
            wake_reason=wake_reason,
            todo_items=todo_items if todo_items else None,
            cost_budget=cost_budget,
        )

        triggered = AutoTriggered(
            trigger_type=context.trigger_type,
            session_id=context.session_id,
            agent_id=context.agent_id,
            task_context=context.task_context,
            source_event_type=context.source_event_type,
            source_event_id=context.source_event_id,
        )

        await self._publish(triggered)
        return triggered

    def extract_context(self, event: DomainEvent) -> AutoTriggerContext:
        """Extract AutoTriggerContext from any domain event without publishing.

        Args:
            event: DomainEvent instance

        Returns:
            AutoTriggerContext with extracted fields

        Raises:
            ValueError: If event_type is unknown
        """
        if event.event_type == "HeartbeatTriggered":
            heartbeat_id = str(getattr(event, "heartbeat_id", "unknown"))
            return AutoTriggerContext.from_heartbeat(
                heartbeat_id=heartbeat_id,
                wake_reason=getattr(event, "wake_reason", ""),
                todo_items=getattr(event, "todo_items", ()),
                cost_budget=getattr(event, "cost_budget", 0.0),
            )

        payload = event.payload.copy() if event.payload else {}
        payload["event_type"] = event.event_type
        return AutoTriggerContext.from_domain_event(
            event_type=event.event_type,
            payload=payload,
            event_id=str(event.event_id) if event.event_id else None,
        )

    async def _publish(self, event: AutoTriggered) -> None:
        """Publish AutoTriggered event via configured publisher.

        Args:
            event: AutoTriggered event to publish
        """
        if self._publisher is None:
            logger.warning("No publisher configured, AutoTriggered event not published: %s", event.event_id)
            return

        try:
            await self._publisher.publish(event, channel="rt:AutoTriggered")
            logger.info(
                "Published AutoTriggered event: session_id=%s trigger_type=%s",
                event.session_id,
                event.trigger_type,
            )
        except Exception as e:
            logger.error("Failed to publish AutoTriggered event: %s", e)
            raise
