"""Tests for EventBusFactory — dependency injection for event buses."""

from __future__ import annotations

from src.infrastructure.messaging.event_bus_factory import EventBusFactory


class TestEventBusFactoryInit:
    """Test EventBusFactory initialization."""

    def test_creates_shared_channel_router(self) -> None:
        """Factory should create a shared ChannelRouter."""
        factory = EventBusFactory()
        assert factory._router is not None


class TestEventBusFactoryCreateBuses:
    """Test factory bus creation methods."""

    def test_create_redis_bus_returns_redis_event_bus(self) -> None:
        """create_redis_bus should return RedisEventBus instance."""
        from src.infrastructure.messaging.redis_event_bus import RedisEventBus

        factory = EventBusFactory()
        bus = factory.create_redis_bus()
        assert isinstance(bus, RedisEventBus)

    def test_create_rabbitmq_bus_returns_rabbitmq_event_bus(self) -> None:
        """create_rabbitmq_bus should return RabbitMQEventBus instance."""
        from src.infrastructure.messaging.rabbitmq_event_bus import RabbitMQEventBus

        factory = EventBusFactory()
        bus = factory.create_rabbitmq_bus()
        assert isinstance(bus, RabbitMQEventBus)

    def test_create_dual_channel_bus_returns_tuple(self) -> None:
        """create_dual_channel_bus should return tuple of (DualChannelEventBus, AsyncOutboxPoller)."""
        from src.infrastructure.messaging.dual_channel_event_bus import DualChannelEventBus
        from src.infrastructure.messaging.outbox.outbox_processor import AsyncOutboxPoller

        factory = EventBusFactory()
        result = factory.create_dual_channel_bus()
        assert isinstance(result, tuple)
        assert len(result) == 2
        bus, poller = result
        assert isinstance(bus, DualChannelEventBus)
        assert isinstance(poller, AsyncOutboxPoller)


class TestEventBusFactoryReuse:
    """Test that factory reuses shared instances."""

    def test_multiple_redis_buses_share_same_publisher(self) -> None:
        """Multiple calls to create_redis_bus should reuse same publisher."""
        factory = EventBusFactory()
        bus1 = factory.create_redis_bus()
        bus2 = factory.create_redis_bus()
        assert bus1._publisher is bus2._publisher

    def test_multiple_rabbitmq_buses_share_same_publisher(self) -> None:
        """Multiple calls to create_rabbitmq_bus should reuse same RabbitMQ publisher."""
        factory = EventBusFactory()
        bus1 = factory.create_rabbitmq_bus()
        bus2 = factory.create_rabbitmq_bus()
        assert bus1._outbox_repo is bus2._outbox_repo
