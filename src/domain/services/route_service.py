"""RouteService — domain service that processes Triggered events and emits Routed events."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol

from src.domain.events.base import DomainEvent
from src.domain.events.route_events import Routed

if TYPE_CHECKING:
    from src.domain.events.trigger_events import Triggered


logger = logging.getLogger(__name__)


class EventPublisherProtocol(Protocol):
    """Protocol for event publishing (implemented by infrastructure)."""

    async def publish(self, event: DomainEvent, channel: str | None = None) -> None:
        ...


class HashRouterProtocol(Protocol):
    """Protocol for hash-based routing (implemented in infrastructure)."""

    def route(self, session_id: str) -> str:
        """Route based on session_id hash.

        Args:
            session_id: Session identifier

        Returns:
            Target node/agent ID
        """
        ...


class SemanticRouterProtocol(Protocol):
    """Protocol for semantic routing (implemented in infrastructure)."""

    async def route(self, task_context: dict) -> tuple[str, float]:
        """Route based on task context semantic similarity.

        Args:
            task_context: Task context dictionary

        Returns:
            Tuple of (target_id, similarity_score)
        """
        ...


class RouteService:
    """Domain service that listens to Triggered events, makes routing decisions, and emits Routed events.

    Responsibilities:
    - Listen to Triggered events from TriggerService (Story 1.14a)
    - Make routing decisions using hash routing (session consistency) and/or semantic routing (target matching)
    - Publish Routed events to downstream execute stage (Story 1.14c)
    - Log routing decisions to RoutingDecisionLog

    Architecture: Domain layer (no external dependencies), uses port/protocol for routing and publishing.
    """

    def __init__(
        self,
        publisher: EventPublisherProtocol | None = None,
        hash_router: HashRouterProtocol | None = None,
        semantic_router: SemanticRouterProtocol | None = None,
    ):
        """Initialize RouteService.

        Args:
            publisher: Event publisher port (infrastructure implements). None for standalone testing.
            hash_router: Hash router port (infrastructure implements). None to disable hash routing.
            semantic_router: Semantic router port (infrastructure implements). None to disable semantic routing.
        """
        self._publisher = publisher
        self._hash_router = hash_router
        self._semantic_router = semantic_router

    async def on_triggered_event(self, event: Triggered) -> Routed | None:
        """Handle a Triggered event: make routing decision and emit Routed.

        Args:
            event: Triggered event from trigger stage (Story 1.14a)

        Returns:
            Routed event if routing decision was made and published, None otherwise
        """
        logger.debug("Processing Triggered event: session_id=%s", event.session_id)

        # Determine route type and target based on available routers
        route_type, route_target, route_score = await self._make_routing_decision(event)

        routed = Routed(
            route_type=route_type,
            session_id=event.session_id,
            task_context=event.task_context,
            route_target=route_target,
            route_score=route_score,
            trigger_event_type=event.event_type,
            trigger_event_id=str(event.event_id) if event.event_id else None,
        )

        await self._publish(routed)
        return routed

    async def _make_routing_decision(self, event: Triggered) -> tuple[str, str, float]:
        """Make routing decision based on available routers.

        Args:
            event: Triggered event

        Returns:
            Tuple of (route_type, route_target, route_score)
        """
        hash_target = ""
        hash_score = 0.0
        semantic_target = ""
        semantic_score = 0.0

        # Hash routing (session consistency)
        if self._hash_router is not None:
            hash_target = self._hash_router.route(event.session_id)
            hash_score = 1.0  # Hash routing is deterministic, 100% confidence

        # Semantic routing (target matching)
        if self._semantic_router is not None:
            semantic_target, semantic_score = await self._semantic_router.route(event.task_context)

        # Determine final route type and target
        if hash_target and semantic_target:
            # In mixed mode, prefer semantic routing (more intelligent matching)
            # when it returns a valid target with meaningful score
            if semantic_score > 0:
                route_type = "mixed"
                route_target = semantic_target
                route_score = semantic_score
            else:
                route_type = "hash"
                route_target = hash_target
                route_score = hash_score
        elif semantic_target:
            route_type = "semantic"
            route_target = semantic_target
            route_score = semantic_score
        elif hash_target:
            route_type = "hash"
            route_target = hash_target
            route_score = hash_score
        else:
            # No router available, use defaults
            route_type = "hash"
            route_target = "default"
            route_score = 0.0

        return route_type, route_target, route_score

    async def _publish(self, event: Routed) -> None:
        """Publish Routed event via configured publisher.

        Args:
            event: Routed event to publish
        """
        if self._publisher is None:
            logger.warning("No publisher configured, Routed event not published: %s", event.event_id)
            return

        try:
            await self._publisher.publish(event, channel="rt:Routed")
            logger.info(
                "Published Routed event: session_id=%s route_type=%s route_target=%s score=%.3f",
                event.session_id,
                event.route_type,
                event.route_target,
                event.route_score,
            )
        except Exception as e:
            logger.error("Failed to publish Routed event: %s", e)
            raise
