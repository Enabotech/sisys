"""Tests for RabbitMQEventBus — reliable event bus via Outbox."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.domain.events.base import DomainEvent
from src.domain.events.publish_result import PublishResult
from src.infrastructure.messaging.channel_router import ChannelMapping, ChannelRouter, DeliveryMode
from src.infrastructure.messaging.rabbitmq_event_bus import RabbitMQEventBus


class TestRabbitMQEventBusImplementsInterfaces:
    """Test that RabbitMQEventBus has EventPublisher methods — structural check."""

    def test_has_event_publisher_methods(self) -> None:
        """RabbitMQEventBus should have EventPublisher methods."""
        assert hasattr(RabbitMQEventBus, "publish"), "RabbitMQEventBus must have publish method"


class TestRabbitMQEventBusPublish:
    """Test RabbitMQEventBus.publish method."""

    @pytest.mark.asyncio
    async def test_publish_returns_publish_result(self) -> None:
        """publish should return a PublishResult."""
        router = ChannelRouter()
        outbox_repo = MagicMock()
        bus = RabbitMQEventBus(outbox_repository=outbox_repo, router=router)

        event = MagicMock(spec=DomainEvent)
        event.event_id = "test-123"
        event.event_type = "DocumentProcessed"

        result = await bus.publish(event)

        assert isinstance(result, PublishResult)

    @pytest.mark.asyncio
    async def test_publish_returns_outbox_saved_true_on_success(self) -> None:
        """publish should return outbox_saved=True on successful save."""
        router = ChannelRouter()
        outbox_repo = MagicMock()
        outbox_repo.save.return_value = None
        bus = RabbitMQEventBus(outbox_repository=outbox_repo, router=router)

        event = MagicMock(spec=DomainEvent)
        event.event_id = "test-123"
        event.event_type = "DocumentProcessed"

        result = await bus.publish(event)

        assert result.outbox_saved is True
        assert result.redis_success is False

    @pytest.mark.asyncio
    async def test_publish_calls_outbox_save(self) -> None:
        """publish should call outbox_repository.save with the event."""
        router = ChannelRouter()
        outbox_repo = MagicMock()
        outbox_repo.save = MagicMock(return_value=True)
        bus = RabbitMQEventBus(outbox_repository=outbox_repo, router=router)

        event = MagicMock(spec=DomainEvent)
        event.event_id = "test-123"
        event.event_type = "DocumentProcessed"

        await bus.publish(event)

        outbox_repo.save.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_publish_returns_outbox_saved_false_when_no_routing_key(self) -> None:
        """publish should return outbox_saved=False when no RabbitMQ routing key."""
        router = ChannelRouter(load_defaults=False)
        mapping = ChannelMapping(
            event_type="UnknownEvent",
            delivery_mode=DeliveryMode.RELIABLE,
            redis_channel="test:channel",
            rabbitmq_routing_key=None,
        )
        router.register(mapping)
        outbox_repo = MagicMock()
        outbox_repo.save = MagicMock(return_value=True)
        bus = RabbitMQEventBus(outbox_repository=outbox_repo, router=router)

        event = MagicMock(spec=DomainEvent)
        event.event_id = "test-123"
        event.event_type = "UnknownEvent"

        result = await bus.publish(event)

        assert result.outbox_saved is False
        outbox_repo.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_returns_error_on_outbox_failure(self) -> None:
        """publish should return outbox_error when save fails."""
        router = ChannelRouter()
        outbox_repo = MagicMock()
        outbox_repo.save.side_effect = Exception("DB connection failed")
        bus = RabbitMQEventBus(outbox_repository=outbox_repo, router=router)

        event = MagicMock(spec=DomainEvent)
        event.event_id = "test-123"
        event.event_type = "DocumentProcessed"

        result = await bus.publish(event)

        assert result.outbox_saved is False
        assert result.outbox_error == "DB connection failed"


class TestRabbitMQEventBusClose:
    """Test RabbitMQEventBus.close method."""

    @pytest.mark.asyncio
    async def test_close_is_async(self) -> None:
        """close should be an async method."""
        import inspect

        router = ChannelRouter()
        outbox_repo = MagicMock()
        bus = RabbitMQEventBus(outbox_repository=outbox_repo, router=router)

        assert inspect.iscoroutinefunction(bus.close)

    @pytest.mark.asyncio
    async def test_close_does_not_raise(self) -> None:
        """close should not raise (no resources to clean up)."""
        router = ChannelRouter()
        outbox_repo = MagicMock()
        bus = RabbitMQEventBus(outbox_repository=outbox_repo, router=router)

        await bus.close()
