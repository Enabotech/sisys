"""Tests for DualChannelEventBus — unified event bus facade."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.events.base import DomainEvent
from src.domain.events.publish_result import PublishResult
from src.infrastructure.messaging.channel_router import ChannelRouter
from src.infrastructure.messaging.dual_channel_event_bus import DualChannelEventBus
from src.infrastructure.messaging.rabbitmq_event_bus import RabbitMQEventBus
from src.infrastructure.messaging.redis_event_bus import RedisEventBus


class TestDualChannelEventBusImplementsInterfaces:
    """Test that DualChannelEventBus implements EventPublisher."""

    def test_implements_event_publisher(self) -> None:
        """DualChannelEventBus should implement EventPublisher."""
        from src.domain.ports.event_publisher import EventPublisher

        assert issubclass(DualChannelEventBus, EventPublisher)


class TestDualChannelEventBusInit:
    """Test DualChannelEventBus constructor."""

    def test_constructor_accepts_redis_and_rabbitmq_buses(self) -> None:
        """Constructor should accept RedisEventBus and RabbitMQEventBus."""
        router = ChannelRouter()
        redis_bus = MagicMock(spec=RedisEventBus)
        rabbitmq_bus = MagicMock(spec=RabbitMQEventBus)
        bus = DualChannelEventBus(redis_bus=redis_bus, rabbitmq_bus=rabbitmq_bus, router=router)
        assert bus._redis_bus is redis_bus
        assert bus._rabbitmq_bus is rabbitmq_bus


class TestDualChannelEventBusPublish:
    """Test DualChannelEventBus.publish method."""

    @pytest.mark.asyncio
    async def test_publish_routes_realtime_to_redis(self) -> None:
        """REALTIME event should be published via RedisEventBus."""
        router = ChannelRouter()
        redis_bus = MagicMock(spec=RedisEventBus)
        redis_result = PublishResult(event_id="test-123", redis_success=True)
        redis_bus.publish = AsyncMock(return_value=redis_result)
        rabbitmq_bus = MagicMock(spec=RabbitMQEventBus)
        bus = DualChannelEventBus(redis_bus=redis_bus, rabbitmq_bus=rabbitmq_bus, router=router)

        event = MagicMock(spec=DomainEvent)
        event.event_id = "test-123"
        event.event_type = "AutoTriggered"

        result = await bus.publish(event)

        redis_bus.publish.assert_called_once_with(event)
        rabbitmq_bus.publish.assert_not_called()
        assert result.redis_success is True

    @pytest.mark.asyncio
    async def test_publish_routes_reliable_to_rabbitmq(self) -> None:
        """RELIABLE event should be published via RabbitMQEventBus (Outbox)."""
        router = ChannelRouter()
        redis_bus = MagicMock(spec=RedisEventBus)
        rabbitmq_bus = MagicMock(spec=RabbitMQEventBus)
        rabbitmq_result = PublishResult(event_id="test-123", outbox_saved=True)
        rabbitmq_bus.publish = AsyncMock(return_value=rabbitmq_result)
        bus = DualChannelEventBus(redis_bus=redis_bus, rabbitmq_bus=rabbitmq_bus, router=router)

        event = MagicMock(spec=DomainEvent)
        event.event_id = "test-123"
        event.event_type = "DocumentProcessed"

        result = await bus.publish(event)

        rabbitmq_bus.publish.assert_called_once_with(event)
        redis_bus.publish.assert_not_called()
        assert result.outbox_saved is True


class TestDualChannelEventBusSubscribe:
    """Test DualChannelEventBus.subscribe method."""

    @pytest.mark.asyncio
    async def test_subscribe_raises_for_reliable_mode(self) -> None:
        """subscribe should raise ValueError for RELIABLE event type."""
        router = ChannelRouter()
        redis_bus = MagicMock(spec=RedisEventBus)
        rabbitmq_bus = MagicMock(spec=RabbitMQEventBus)
        bus = DualChannelEventBus(redis_bus=redis_bus, rabbitmq_bus=rabbitmq_bus, router=router)

        handler = MagicMock()

        with pytest.raises(ValueError, match="RELIABLE mode.*subscribe"):
            await bus.subscribe("DocumentProcessed", handler)

    @pytest.mark.asyncio
    async def test_subscribe_delegates_to_redis_for_realtime(self) -> None:
        """subscribe should delegate to RedisEventBus for REALTIME event type."""
        router = ChannelRouter()
        redis_bus = MagicMock(spec=RedisEventBus)
        redis_bus.subscribe = AsyncMock()
        rabbitmq_bus = MagicMock(spec=RabbitMQEventBus)
        bus = DualChannelEventBus(redis_bus=redis_bus, rabbitmq_bus=rabbitmq_bus, router=router)

        handler = MagicMock()
        await bus.subscribe("AutoTriggered", handler)

        redis_bus.subscribe.assert_called_once_with("AutoTriggered", handler)


class TestDualChannelEventBusLifecycle:
    """Test DualChannelEventBus start and close methods."""

    @pytest.mark.asyncio
    async def test_start_calls_redis_start(self) -> None:
        """start should call redis_bus.start()."""
        router = ChannelRouter()
        redis_bus = MagicMock(spec=RedisEventBus)
        redis_bus.start = AsyncMock()
        rabbitmq_bus = MagicMock(spec=RabbitMQEventBus)
        bus = DualChannelEventBus(redis_bus=redis_bus, rabbitmq_bus=rabbitmq_bus, router=router)

        await bus.start()

        redis_bus.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_calls_both_buses_close(self) -> None:
        """close should call both redis_bus.close() and rabbitmq_bus.close()."""
        router = ChannelRouter()
        redis_bus = MagicMock(spec=RedisEventBus)
        redis_bus.close = AsyncMock()
        rabbitmq_bus = MagicMock(spec=RabbitMQEventBus)
        rabbitmq_bus.close = AsyncMock()
        bus = DualChannelEventBus(redis_bus=redis_bus, rabbitmq_bus=rabbitmq_bus, router=router)

        await bus.close()

        redis_bus.close.assert_called_once()
        rabbitmq_bus.close.assert_called_once()
