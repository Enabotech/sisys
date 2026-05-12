"""AutoExecuteCompletedListener — event listener that publishes downstream domain events.

Listens for AutoExecuted events and publishes corresponding domain events
(DocumentProcessed/ToolExecuted/AgentDecided) based on business_event_type.
"""

from __future__ import annotations

import logging

from src.domain.events.auto_execute_events import AutoExecuted
from src.domain.events.base import DomainEvent
from src.domain.ports.event_publisher import EventPublisher

logger = logging.getLogger(__name__)


class AutoExecuteCompletedHandler:
    """Event listener that handles AutoExecuted events.

    Responsible for:
    - Listening to AutoExecuted events from AutoExecuteService
    - Publishing corresponding domain events based on business_event_type:
      - "DocumentProcessed" -> DocumentProcessed event
      - "ToolExecuted" -> ToolExecuted event
      - "AgentDecided" -> AgentDecided event

    Architecture: Interfaces layer, implements event listener pattern.
    """

    def __init__(self, publisher: EventPublisher | None = None):
        """Initialize AutoExecuteCompletedListener.

        Args:
            publisher: Event publisher port. None for standalone testing.
        """
        self._publisher = publisher

    async def on_executed(self, event: AutoExecuted) -> None:
        """Handle AutoExecuted event: publish downstream domain event.

        Args:
            event: AutoExecuted event from ExecuteService
        """
        business_event_type = event.business_event_type or "ToolExecuted"

        logger.info(
            "Processing AutoExecuted event: session_id=%s business_event_type=%s",
            event.session_id,
            business_event_type,
        )

        # Build domain event based on business_event_type
        if business_event_type == "DocumentProcessed":
            await self._publish_document_processed(event)
        elif business_event_type == "ToolExecuted":
            await self._publish_tool_executed(event)
        elif business_event_type == "AgentDecided":
            await self._publish_agent_decided(event)
        else:
            logger.warning("Unknown business_event_type: %s, defaulting to ToolExecuted", business_event_type)
            await self._publish_tool_executed(event)

    async def _publish_document_processed(self, event: AutoExecuted) -> None:
        """Publish DocumentProcessed domain event."""
        from src.domain.events.document_events import DocumentProcessed

        domain_event = DocumentProcessed(
            document_id=event.task_context.get("document_id", ""),
            parse_result=event.execution_result,
        )

        await self._publish(domain_event, "domain:DocumentProcessed")
        logger.info("Published DocumentProcessed: document_id=%s", domain_event.document_id)

    async def _publish_tool_executed(self, event: AutoExecuted) -> None:
        """Publish ToolExecuted domain event."""
        from src.domain.events.tool_events import ToolExecuted

        domain_event = ToolExecuted(
            tool_id=event.task_context.get("tool_id", ""),
            execution_result=event.execution_result,
            cost_audit={"estimated": event.cost_estimate},
        )

        await self._publish(domain_event, "domain:ToolExecuted")
        logger.info("Published ToolExecuted: tool_id=%s", domain_event.tool_id)

    async def _publish_agent_decided(self, event: AutoExecuted) -> None:
        """Publish AgentDecided domain event."""
        from src.domain.events.agent_events import AgentDecided

        domain_event = AgentDecided(
            agent_id=event.task_context.get("agent_id", ""),
            decision_result=event.execution_result,
            confidence=event.route_score,
        )

        await self._publish(domain_event, "domain:AgentDecided")
        logger.info("Published AgentDecided: agent_id=%s", domain_event.agent_id)

    async def _publish(self, event: DomainEvent, channel: str) -> None:
        """Publish domain event via configured publisher.

        Args:
            event: Domain event to publish
            channel: Channel name
        """
        if self._publisher is None:
            logger.warning("No publisher configured, event not published: %s", event.event_type)
            return

        try:
            await self._publisher.publish(event, channel=channel)
            logger.debug("Published event: type=%s channel=%s", event.event_type, channel)
        except Exception as e:
            logger.error("Failed to publish %s event: %s", event.event_type, e)
            raise
