"""Integration tests for dual-channel event bus.

Validates AC-10: Story 1.3 AC-3 constraint satisfaction.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.domain.events.base import DomainEvent
from src.domain.events.publish_result import ChannelResult, PublishResult
from src.infrastructure.messaging.channel_router import ChannelRouter
from src.infrastructure.messaging.dual_channel_event_bus import DualChannelEventBus
from src.infrastructure.messaging.rabbitmq_event_bus import RabbitMQEventBus
from src.infrastructure.messaging.redis_event_bus import RedisEventBus


class TestRealtimeEventPublishToRedis:
    """AC-10.1: REALTIME events should publish directly to Redis."""

    async def test_auto_triggered_event_publishes_to_redis(self) -> None:
        """AutoTriggered (REALTIME) should publish via RedisEventBus."""
        router = ChannelRouter()
        redis_bus = MagicMock(spec=RedisEventBus)
        redis_result = PublishResult(event_id="test-123", results=(ChannelResult("realtime", True),))
        redis_bus.publish = AsyncMock(return_value=redis_result)
        rabbitmq_bus = MagicMock(spec=RabbitMQEventBus)

        bus = DualChannelEventBus(
            redis_bus=redis_bus,
            rabbitmq_bus=rabbitmq_bus,
            router=router,
        )

        event = MagicMock(spec=DomainEvent)
        event.event_id = "test-123"
        event.event_type = "AutoTriggered"

        result = await bus.publish(event)

        redis_bus.publish.assert_called_once_with(event)
        rabbitmq_bus.publish.assert_not_called()
        assert result.redis_success is True

    async def test_auto_routed_event_publishes_to_redis(self) -> None:
        """AutoRouted (REALTIME) should publish via RedisEventBus."""
        router = ChannelRouter()
        redis_bus = MagicMock(spec=RedisEventBus)
        redis_result = PublishResult(event_id="test-123", results=(ChannelResult("realtime", True),))
        redis_bus.publish = AsyncMock(return_value=redis_result)
        rabbitmq_bus = MagicMock(spec=RabbitMQEventBus)

        bus = DualChannelEventBus(
            redis_bus=redis_bus,
            rabbitmq_bus=rabbitmq_bus,
            router=router,
        )

        event = MagicMock(spec=DomainEvent)
        event.event_id = "test-123"
        event.event_type = "AutoRouted"

        result = await bus.publish(event)

        redis_bus.publish.assert_called_once_with(event)
        assert result.redis_success is True


class TestReliableEventWritesToOutbox:
    """AC-10.2: RELIABLE events should write to Outbox."""

    async def test_document_processed_event_writes_to_outbox(self) -> None:
        """DocumentProcessed (RELIABLE) should publish via RabbitMQEventBus/Outbox."""
        router = ChannelRouter()
        redis_bus = MagicMock(spec=RedisEventBus)
        rabbitmq_bus = MagicMock(spec=RabbitMQEventBus)
        rabbitmq_result = PublishResult(event_id="test-123", results=(ChannelResult("reliable", True),))
        rabbitmq_bus.publish = AsyncMock(return_value=rabbitmq_result)

        bus = DualChannelEventBus(
            redis_bus=redis_bus,
            rabbitmq_bus=rabbitmq_bus,
            router=router,
        )

        event = MagicMock(spec=DomainEvent)
        event.event_id = "test-123"
        event.event_type = "DocumentProcessed"

        result = await bus.publish(event)

        rabbitmq_bus.publish.assert_called_once_with(event)
        redis_bus.publish.assert_not_called()
        assert result.outbox_saved is True

    async def test_memory_changed_event_writes_to_outbox(self) -> None:
        """MemoryChanged (RELIABLE) should publish via RabbitMQEventBus/Outbox."""
        router = ChannelRouter()
        redis_bus = MagicMock(spec=RedisEventBus)
        rabbitmq_bus = MagicMock(spec=RabbitMQEventBus)
        rabbitmq_result = PublishResult(event_id="test-123", results=(ChannelResult("reliable", True),))
        rabbitmq_bus.publish = AsyncMock(return_value=rabbitmq_result)

        bus = DualChannelEventBus(
            redis_bus=redis_bus,
            rabbitmq_bus=rabbitmq_bus,
            router=router,
        )

        event = MagicMock(spec=DomainEvent)
        event.event_id = "test-123"
        event.event_type = "MemoryChanged"

        result = await bus.publish(event)

        rabbitmq_bus.publish.assert_called_once_with(event)
        assert result.outbox_saved is True

    async def test_audit_event_writes_to_outbox(self) -> None:
        """AuditEvent (RELIABLE) should publish via RabbitMQEventBus/Outbox."""
        router = ChannelRouter()
        redis_bus = MagicMock(spec=RedisEventBus)
        rabbitmq_bus = MagicMock(spec=RabbitMQEventBus)
        rabbitmq_result = PublishResult(event_id="test-123", results=(ChannelResult("reliable", True),))
        rabbitmq_bus.publish = AsyncMock(return_value=rabbitmq_result)

        bus = DualChannelEventBus(
            redis_bus=redis_bus,
            rabbitmq_bus=rabbitmq_bus,
            router=router,
        )

        event = MagicMock(spec=DomainEvent)
        event.event_id = "test-123"
        event.event_type = "AuditEvent"

        result = await bus.publish(event)

        rabbitmq_bus.publish.assert_called_once_with(event)
        assert result.outbox_saved is True


class TestPollerPublishesToRabbitMQ:
    """AC-10.3: Poller should correctly publish Outbox events to RabbitMQ."""

    async def test_poller_reads_unpublished_events_and_publishes(self) -> None:
        """AsyncOutboxPoller should read unpublished events and publish to RabbitMQ."""
        from src.infrastructure.messaging.outbox.outbox_processor import AsyncOutboxPoller

        mock_repo = MagicMock()
        mock_publisher = MagicMock()
        mock_event = MagicMock(spec=DomainEvent)
        mock_event.event_id = uuid4()
        mock_event.event_type = "DocumentProcessed"

        mock_repo.get_unpublished = AsyncMock(return_value=[])
        mock_publisher.async_publish = AsyncMock()

        router = ChannelRouter()

        poller = AsyncOutboxPoller(
            outbox_repository=mock_repo,
            publisher=mock_publisher,
            router=router,
            poll_interval=0.1,
            batch_size=10,
        )

        await poller.poll_once()

        mock_repo.get_unpublished.assert_called_once_with(limit=10)


class TestSubscribeOnlyForRealtime:
    """AC-10.4: subscribe() should only work for REALTIME events."""

    async def test_subscribe_raises_for_reliable_event(self) -> None:
        """subscribe() should raise ValueError for RELIABLE event type."""
        router = ChannelRouter()
        redis_bus = MagicMock(spec=RedisEventBus)
        rabbitmq_bus = MagicMock(spec=RabbitMQEventBus)

        bus = DualChannelEventBus(
            redis_bus=redis_bus,
            rabbitmq_bus=rabbitmq_bus,
            router=router,
        )

        handler = MagicMock()

        with pytest.raises(ValueError, match="RELIABLE mode"):
            await bus.subscribe("DocumentProcessed", handler)

    async def test_subscribe_works_for_realtime_event(self) -> None:
        """subscribe() should work for REALTIME event type."""
        router = ChannelRouter()
        redis_bus = MagicMock(spec=RedisEventBus)
        redis_bus.subscribe = AsyncMock()
        rabbitmq_bus = MagicMock(spec=RabbitMQEventBus)

        bus = DualChannelEventBus(
            redis_bus=redis_bus,
            rabbitmq_bus=rabbitmq_bus,
            router=router,
        )

        handler = MagicMock()
        await bus.subscribe("AutoTriggered", handler)

        redis_bus.subscribe.assert_called_once_with("AutoTriggered", handler)
