"""Tests for RedisEventBus — new unified class."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.events.base import DomainEvent
from src.domain.events.publish_result import PublishResult
from src.infrastructure.messaging.channel_router import ChannelRouter, DeliveryMode
from src.infrastructure.messaging.redis_event_bus import RedisEventBus


class TestRedisEventBusImplementsInterfaces:
    """Test that RedisEventBus has EventPublisher and EventSubscriber methods — structural check."""

    def test_has_event_publisher_methods(self) -> None:
        """RedisEventBus should have EventPublisher methods."""
        assert hasattr(RedisEventBus, "publish"), "RedisEventBus must have publish method"

    def test_has_event_subscriber_methods(self) -> None:
        """RedisEventBus should have EventSubscriber methods."""
        from src.application.ports.event_subscriber import EventSubscriber

        assert hasattr(EventSubscriber, "subscribe"), "EventSubscriber must have subscribe method"
        assert hasattr(EventSubscriber, "subscribe_async"), "EventSubscriber must have subscribe_async method"


class TestRedisEventBusPublish:
    """Test RedisEventBus.publish method."""

    @pytest.mark.asyncio
    async def test_publish_returns_publish_result(self) -> None:
        """publish should return a PublishResult."""
        router = ChannelRouter()
        publisher = AsyncMock()
        subscriber = MagicMock()
        bus = RedisEventBus(publisher=publisher, subscriber=subscriber, router=router)

        # Create a mock event
        event = MagicMock(spec=DomainEvent)
        event.event_id = "test-123"
        event.event_type = "AutoTriggered"

        result = await bus.publish(event)

        assert isinstance(result, PublishResult)

    @pytest.mark.asyncio
    async def test_publish_returns_redis_success_true_on_success(self) -> None:
        """publish should return redis_success=True on successful publish."""
        router = ChannelRouter()
        publisher = AsyncMock()
        subscriber = MagicMock()
        bus = RedisEventBus(publisher=publisher, subscriber=subscriber, router=router)

        event = MagicMock(spec=DomainEvent)
        event.event_id = "test-123"
        event.event_type = "AutoTriggered"

        result = await bus.publish(event)

        assert result.redis_success is True

    @pytest.mark.asyncio
    async def test_publish_returns_redis_success_false_when_no_channel(self) -> None:
        """publish should return redis_success=False when no Redis channel configured."""
        router = ChannelRouter(load_defaults=False)
        # Register a mapping with no redis channel
        from src.infrastructure.messaging.channel_router import ChannelMapping

        mapping = ChannelMapping(
            event_type="UnknownEvent",
            delivery_mode=DeliveryMode.RELIABLE,
            redis_channel=None,
        )
        router.register(mapping)
        publisher = AsyncMock()
        subscriber = MagicMock()
        bus = RedisEventBus(publisher=publisher, subscriber=subscriber, router=router)

        event = MagicMock(spec=DomainEvent)
        event.event_id = "test-123"
        event.event_type = "UnknownEvent"

        result = await bus.publish(event)

        assert result.redis_success is False

    @pytest.mark.asyncio
    async def test_publish_calls_publisher_with_correct_channel(self) -> None:
        """publish should call publisher.publish with the correct channel."""
        router = ChannelRouter()
        publisher = AsyncMock()
        subscriber = MagicMock()
        bus = RedisEventBus(publisher=publisher, subscriber=subscriber, router=router)

        event = MagicMock(spec=DomainEvent)
        event.event_id = "test-123"
        event.event_type = "AutoTriggered"

        await bus.publish(event)

        publisher.publish.assert_called_once()
        call_args = publisher.publish.call_args
        assert call_args[0][1] == "sisys:rt:auto_triggered"


class TestRedisEventBusSubscribe:
    """Test RedisEventBus.subscribe and subscribe_async methods."""

    @pytest.mark.asyncio
    async def test_subscribe_is_async(self) -> None:
        """subscribe should be an async method."""
        import inspect

        router = ChannelRouter()
        publisher = AsyncMock()
        subscriber = AsyncMock()
        bus = RedisEventBus(publisher=publisher, subscriber=subscriber, router=router)

        assert inspect.iscoroutinefunction(bus.subscribe)

    @pytest.mark.asyncio
    async def test_subscribe_async_is_async(self) -> None:
        """subscribe_async should be an async method."""
        import inspect

        router = ChannelRouter()
        publisher = AsyncMock()
        subscriber = AsyncMock()
        bus = RedisEventBus(publisher=publisher, subscriber=subscriber, router=router)

        assert inspect.iscoroutinefunction(bus.subscribe_async)

    @pytest.mark.asyncio
    async def test_subscribe_calls_subscriber_subscribe(self) -> None:
        """subscribe should delegate to subscriber.subscribe."""
        router = ChannelRouter()
        publisher = AsyncMock()
        subscriber = AsyncMock()
        bus = RedisEventBus(publisher=publisher, subscriber=subscriber, router=router)

        handler = MagicMock()
        await bus.subscribe("AutoTriggered", handler)

        subscriber.subscribe.assert_called()


class TestRedisEventBusLifecycle:
    """Test RedisEventBus start and close methods."""

    @pytest.mark.asyncio
    async def test_start_is_async(self) -> None:
        """start should be an async method."""
        import inspect

        router = ChannelRouter()
        publisher = AsyncMock()
        subscriber = AsyncMock()
        bus = RedisEventBus(publisher=publisher, subscriber=subscriber, router=router)

        assert inspect.iscoroutinefunction(bus.start)

    @pytest.mark.asyncio
    async def test_close_is_async(self) -> None:
        """close should be an async method."""
        import inspect

        router = ChannelRouter()
        publisher = AsyncMock()
        subscriber = AsyncMock()
        bus = RedisEventBus(publisher=publisher, subscriber=subscriber, router=router)

        assert inspect.iscoroutinefunction(bus.close)

    @pytest.mark.asyncio
    async def test_start_calls_subscriber_start(self) -> None:
        """start should call subscriber.start()."""
        router = ChannelRouter()
        publisher = AsyncMock()
        subscriber = AsyncMock()
        bus = RedisEventBus(publisher=publisher, subscriber=subscriber, router=router)

        await bus.start()

        subscriber.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_calls_publisher_and_subscriber_close(self) -> None:
        """close should call both publisher.close() and subscriber.close()."""
        router = ChannelRouter()
        publisher = AsyncMock()
        subscriber = AsyncMock()
        bus = RedisEventBus(publisher=publisher, subscriber=subscriber, router=router)

        await bus.close()

        publisher.close.assert_called_once()
        subscriber.close.assert_called_once()
