"""AutoTriggerListener — Event listener adapter for auto-trigger mechanism.

Listens to domain events from the event bus and passes them
to AutoTriggerService for processing.

Reference: Story 1.14a SDD规范定义
Reference: or.md 系统公理一 (trigger→route→execute)
"""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
from collections.abc import Callable

from src.domain.events.base import DomainEvent
from src.domain.events.listener import EventListener
from src.domain.services.auto_trigger_service import AutoTriggerService

logger = logging.getLogger(__name__)


class AutoTriggerListener:
    """Event listener that bridges event bus to AutoTriggerService.

    Registers handlers for domain events and delegates processing
    to the AutoTriggerService domain service.

    This is the infrastructure adapter layer - it adapts the event bus
    interface to the AutoTriggerService interface while maintaining
    hexagonal architecture compliance (domain layer remains isolated).

    Implementation uses a background thread with its own event loop
    to safely bridge synchronous event handlers to async AutoTriggerService.
    """

    def __init__(
        self,
        auto_trigger_service: AutoTriggerService,
        event_listener: EventListener,
    ) -> None:
        """Initialize AutoTriggerListener.

        Args:
            auto_trigger_service: The domain service for processing triggers.
            event_listener: The event listener for registering handlers.
        """
        self._auto_trigger_service = auto_trigger_service
        self._event_listener = event_listener
        self._registered_event_types = [
            "DocumentProcessed",
            "ToolExecuted",
            "AgentDecided",
            "CheckpointReached",
            "CheckpointRecovered",
            "CorrectionClassified",
            "CorrectionApproved",
            "RoutingDecided",
            "IsolationLevelSwitched",
            "HeartbeatTriggered",
            "StrategicDeviationWarning",
            "AuditEvent",
        ]
        # Background thread for async processing
        self._event_queue: queue.Queue[tuple[str, DomainEvent]] = queue.Queue()
        self._worker_thread: threading.Thread | None = None
        self._running = False

    def register_handlers(self) -> None:
        """Register handlers for all supported domain event types.

        Each handler delegates to the appropriate AutoTriggerService method
        based on event type.
        """
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

        for event_type in self._registered_event_types:
            handler = self._create_handler(event_type)
            self._event_listener.on_event(event_type, handler)
            logger.debug(f"Registered handler for event type: {event_type}")

    def _create_handler(self, event_type: str) -> Callable[[DomainEvent], None]:
        """Create a handler function for the given event type.

        Args:
            event_type: The type of event to handle.

        Returns:
            A handler function that processes events of the given type.
        """

        def handle_event(event: DomainEvent) -> None:
            """Handle a domain event and trigger processing.

            Args:
                event: The domain event to process.
            """
            try:
                # Queue the event for async processing in background thread
                self._event_queue.put((event_type, event))
            except Exception as e:
                logger.error(f"Failed to queue event {event_type}: {e}")

        return handle_event

    def _worker_loop(self) -> None:
        """Background worker loop that processes events asynchronously."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            while self._running:
                try:
                    event_type, event = self._event_queue.get(timeout=0.1)
                    asyncio.run(self._process_event(event_type, event))
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"Error in worker loop: {e}")
        finally:
            loop.close()

    def stop(self) -> None:
        """Stop the background worker thread."""
        self._running = False
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)

    async def _process_event(self, event_type: str, event: DomainEvent) -> None:
        """Process a domain event asynchronously.

        Args:
            event_type: The type of event being processed.
            event: The domain event to process.
        """
        try:
            if event_type == "HeartbeatTriggered":
                # HeartbeatTriggered requires special handling
                from src.domain.events.heartbeat_events import HeartbeatTriggered

                heartbeat_event = HeartbeatTriggered.from_dict(event.to_dict())
                triggered = await self._auto_trigger_service.on_heartbeat_event(heartbeat_event)
            else:
                # Standard domain event processing
                triggered = await self._auto_trigger_service.on_domain_event(event)

            if triggered is not None:
                logger.info(f"Trigger processed: type={triggered.trigger_type}, " f"session_id={triggered.session_id}")
            else:
                logger.warning(f"AutoTriggerService returned None for event: {event_type}")

        except Exception as e:
            logger.error(f"Failed to process event {event_type}: {e}")

    @property
    def registered_event_types(self) -> list[str]:
        """Return list of event types this listener handles.

        Returns:
            List of registered event type names.
        """
        return list(self._registered_event_types)
