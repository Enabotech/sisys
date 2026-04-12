"""Tests for EventPublisher interface."""

import uuid

import pytest

from src.domain.events.base import DomainEvent
from src.domain.events.publisher import EventPublisher


class TestEventPublisher:
    """Test EventPublisher abstract interface."""

    def test_publish_raises_not_implemented(self):
        """Base EventPublisher.publish() raises NotImplementedError."""
        publisher = EventPublisher()
        event = DomainEvent(
            aggregate_id=uuid.uuid4(),
            event_type="TestEvent",
        )
        with pytest.raises(NotImplementedError, match="Subclasses must implement"):
            publisher.publish(event)

    def test_can_be_subclassed(self):
        """EventPublisher can be subclassed and overridden."""

        class MockPublisher(EventPublisher):
            def __init__(self):
                self.published = []

            def publish(self, event: DomainEvent) -> None:
                self.published.append(event)

        mock = MockPublisher()
        event = DomainEvent(
            aggregate_id=uuid.uuid4(),
            event_type="TestEvent",
        )
        mock.publish(event)
        assert len(mock.published) == 1
        assert mock.published[0] is event
