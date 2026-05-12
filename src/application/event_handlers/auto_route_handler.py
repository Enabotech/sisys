"""AutoRouteListener — event listener for auto-route mechanism.

Listens to AutoTriggered events from AutoTriggerService (Story 1.14a),
invokes AutoRouteService to make routing decisions, and publishes
AutoRouted events to downstream execute stage (Story 1.14c).

Note: This is distinct from UDMR's RoutingDecided event (Story 1.17):
    - AutoRouteListener emits: AutoRouted (auto_route_events.py) — selects Agent/tool
    - UDMR emits: RoutingDecided (routing_events.py) — selects local/cloud model

Reference: Story 1.14b SDD规范定义
Reference: or.md 系统公理一 (trigger→route→execute)
"""

from __future__ import annotations

import logging

from src.domain.events.auto_route_events import AutoRouted
from src.domain.events.base import DomainEvent
from src.domain.ports.event_publisher import EventPublisher
from src.domain.services.auto_route_service import AutoRouteService

logger = logging.getLogger(__name__)


class AutoRouteHandler:
    """Event listener that bridges AutoTriggered events to AutoRouteService.

    Responsible for:
    - Listening to AutoTriggered events from AutoTriggerService (Story 1.14a)
    - Invoking AutoRouteService to make routing decisions
    - Publishing AutoRouted events to downstream execute stage (Story 1.14c)

    Architecture: Interfaces layer, implements event listener pattern.
    Follows hexagonal architecture: domain logic (AutoRouteService) is isolated from
    infrastructure concerns (event bus, logging).
    """

    def __init__(
        self,
        auto_route_service: AutoRouteService,
        publisher: EventPublisher | None = None,
    ) -> None:
        """Initialize AutoRouteListener.

        Args:
            auto_route_service: Domain service for making routing decisions.
            publisher: Event publisher port. None for standalone testing.
        """
        self._auto_route_service = auto_route_service
        self._publisher = publisher

    async def on_triggered(self, event: DomainEvent) -> AutoRouted | None:
        """Handle AutoTriggered event: make routing decision and emit AutoRouted.

        Args:
            event: AutoTriggered event from AutoTriggerService (Story 1.14a)

        Returns:
            AutoRouted event if routing decision was made, None otherwise
        """
        from src.domain.events.auto_trigger_events import AutoTriggered

        if not isinstance(event, AutoTriggered):
            logger.warning("Received non-AutoTriggered event: %s", type(event).__name__)
            return None

        logger.info(
            "Processing AutoTriggered event: session_id=%s trigger_type=%s",
            event.session_id,
            getattr(event, "trigger_type", "unknown"),
        )

        try:
            routed = await self._auto_route_service.on_triggered_event(event)

            if routed is not None:
                logger.info(
                    "Route completed: session_id=%s route_type=%s route_target=%s score=%.3f",
                    routed.session_id,
                    routed.route_type,
                    routed.route_target,
                    routed.route_score,
                )
            else:
                logger.warning("AutoRouteService returned None for AutoTriggered event")

            return routed

        except Exception as e:
            logger.error("Failed to process AutoTriggered event: %s", e)
            raise

    async def _publish(self, event: AutoRouted, channel: str | None = None) -> None:
        """Publish AutoRouted event via configured publisher.

        Args:
            event: AutoRouted event to publish
            channel: Channel name (default: "rt:AutoRouted")
        """
        if self._publisher is None:
            logger.warning("No publisher configured, AutoRouted event not published")
            return

        try:
            await self._publisher.publish(event, channel=channel or "rt:AutoRouted")
            logger.debug("Published AutoRouted event: session_id=%s", event.session_id)
        except Exception as e:
            logger.error("Failed to publish AutoRouted event: %s", e)
            raise
