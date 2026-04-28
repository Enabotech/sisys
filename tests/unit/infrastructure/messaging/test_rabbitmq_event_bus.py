"""Task 2 TDD Tests — RabbitMQ async event channel."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# Ensure all event classes are imported so EventRegistry can discover them
from src.domain.events import DocumentProcessed
from src.domain.events.base import DomainEvent
from src.infrastructure.config.rabbitmq import RabbitMQConfig


def _make_event() -> DomainEvent:
    return DocumentProcessed(
        document_id=uuid4(),
        parse_result={"pages": 10},
        embedding=[0.1] * 1024,
    )


# ============================================================================
# TDD Cycle A: RabbitMQConfig
# ============================================================================


class TestRabbitMQConfig:
    """RabbitMQConfig configuration model tests."""

    def test_default_values(self):
        """RabbitMQConfig should have sensible defaults."""
        config = RabbitMQConfig()
        assert config.host == "localhost"
        assert config.port == 5672
        assert config.virtual_host == "/"
        assert config.username == "guest"  # pragma: allowlist secret
        assert config.password == "guest"  # pragma: allowlist secret
        assert config.exchange_name == "sisys.events.reliable"
        assert config.exchange_type == "topic"
        assert config.prefetch_count == 10
        assert config.heartbeat == 60

    def test_custom_values(self):
        """RabbitMQConfig should accept custom values."""
        config = RabbitMQConfig(
            host="rabbit.example.com",
            port=5673,
            virtual_host="/prod",
            username="user",
            password="pass",  # nosec B106         # pragma: allowlist secret
            exchange_name="my.exchange",
            prefetch_count=20,
            heartbeat=30,
        )
        assert config.host == "rabbit.example.com"
        assert config.port == 5673

    def test_from_env(self):
        """RabbitMQConfig.from_env should read environment variables."""
        import os

        env = os.environ.copy()
        try:
            os.environ["RABBITMQ_HOST"] = "my-rabbit"
            os.environ["RABBITMQ_PORT"] = "5673"
            os.environ["RABBITMQ_PREFETCH"] = "20"

            config = RabbitMQConfig.from_env()
            assert config.host == "my-rabbit"
            assert config.port == 5673
            assert config.prefetch_count == 20
        finally:
            os.environ.clear()
            os.environ.update(env)


# ============================================================================
# TDD Cycle B: RabbitMQPublisher
# ============================================================================


class TestAsyncRabbitMQPublisher:
    """RabbitMQPublisher tests using mocks."""

    @pytest.mark.asyncio
    async def test_connect_declares_exchange(self):
        """Connect should declare exchange on channel."""
        from src.infrastructure.messaging.rabbitmq_publisher import RabbitMQPublisher

        config = RabbitMQConfig()
        publisher = RabbitMQPublisher(config)

        mock_exchange = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.declare_exchange.return_value = mock_exchange
        mock_connection = AsyncMock()
        mock_connection.channel.return_value = mock_channel
        mock_connection.is_closed = False

        with patch("aio_pika.connect_robust", return_value=mock_connection):
            await publisher.connect()

        mock_channel.declare_exchange.assert_called_once_with(
            config.exchange_name,
            pytest.importorskip("aio_pika").ExchangeType.TOPIC,
            durable=True,
        )

    @pytest.mark.asyncio
    async def test_async_publish_sends_message(self):
        """async_publish should send message with correct routing key."""
        import aio_pika

        from src.infrastructure.messaging.rabbitmq_publisher import RabbitMQPublisher

        config = RabbitMQConfig()
        publisher = RabbitMQPublisher(config)

        mock_exchange = AsyncMock()
        publisher._exchange = mock_exchange
        publisher._connection = AsyncMock()
        publisher._connection.is_closed = False

        event = _make_event()
        await publisher.async_publish(event, routing_key="sisys.events.reliable.DocumentProcessed")

        mock_exchange.publish.assert_called_once()
        call_args = mock_exchange.publish.call_args
        message = call_args.kwargs.get("message") or call_args.args[0]
        routing_key = call_args.kwargs.get("routing_key") or call_args.args[1]

        assert routing_key == "sisys.events.reliable.DocumentProcessed"
        assert message.delivery_mode == aio_pika.DeliveryMode.PERSISTENT

    @pytest.mark.asyncio
    async def test_async_publish_sends_with_retry_count(self):
        """async_publish should include retry_count in message headers."""
        from src.infrastructure.messaging.rabbitmq_publisher import RabbitMQPublisher

        config = RabbitMQConfig()
        publisher = RabbitMQPublisher(config)

        mock_exchange = AsyncMock()
        publisher._exchange = mock_exchange

        event = _make_event()
        await publisher.async_publish(event, routing_key="test", retry_count=3)

        message = mock_exchange.publish.call_args.args[0]
        assert message.headers["x-retry-count"] == "3"

    @pytest.mark.asyncio
    async def test_async_publish_raises_if_not_connected(self):
        """async_publish should raise RuntimeError if not connected."""
        from src.infrastructure.messaging.rabbitmq_publisher import RabbitMQPublisher

        config = RabbitMQConfig()
        publisher = RabbitMQPublisher(config)

        event = _make_event()
        with pytest.raises(RuntimeError, match="Not connected"):
            await publisher.async_publish(event, routing_key="test")

    @pytest.mark.asyncio
    async def test_close_connection(self):
        """close should close connection."""
        from src.infrastructure.messaging.rabbitmq_publisher import RabbitMQPublisher

        config = RabbitMQConfig()
        publisher = RabbitMQPublisher(config)

        mock_connection = AsyncMock()
        mock_connection.is_closed = False
        publisher._connection = mock_connection

        await publisher.close()
        mock_connection.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_skips_if_already_closed(self):
        """close should not raise if connection already closed."""
        from src.infrastructure.messaging.rabbitmq_publisher import RabbitMQPublisher

        config = RabbitMQConfig()
        publisher = RabbitMQPublisher(config)
        publisher._connection = MagicMock()
        publisher._connection.is_closed = True

        await publisher.close()  # Should not raise

    @pytest.mark.asyncio
    async def test_close_skips_if_no_connection(self):
        """close should not raise if no connection set."""
        from src.infrastructure.messaging.rabbitmq_publisher import RabbitMQPublisher

        config = RabbitMQConfig()
        publisher = RabbitMQPublisher(config)
        await publisher.close()  # Should not raise


# ============================================================================
# TDD Cycle C: RabbitMQConsumer
# ============================================================================


class TestAsyncRabbitMQConsumer:
    """RabbitMQConsumer tests using mocks."""

    def test_consumer_instantiation(self):
        """Consumer should be instantiable with all dependencies."""
        from src.infrastructure.messaging.rabbitmq_consumer import RabbitMQConsumer

        config = RabbitMQConfig()
        consumer = RabbitMQConsumer(
            config,
            idempotency_checker=None,
            metrics_collector=None,
            dlq=None,
            retry_policy=None,
        )
        assert consumer._config == config
        assert consumer._handlers == {}

    def test_register_handler(self):
        """register_handler should add handler to dict."""
        from src.infrastructure.messaging.rabbitmq_consumer import RabbitMQConsumer

        config = RabbitMQConfig()
        consumer = RabbitMQConsumer(config)

        async def handler(evt):
            pass

        consumer.register_handler("test-queue", handler)
        assert "test-queue" in consumer._handlers
        assert len(consumer._handlers["test-queue"]) == 1

    def test_register_handler_multiple(self):
        """register_handler should support multiple handlers per queue."""
        from src.infrastructure.messaging.rabbitmq_consumer import RabbitMQConsumer

        config = RabbitMQConfig()
        consumer = RabbitMQConsumer(config)

        async def h1(evt):
            pass

        async def h2(evt):
            pass

        consumer.register_handler("q1", h1)
        consumer.register_handler("q1", h2)
        assert len(consumer._handlers["q1"]) == 2

    @pytest.mark.asyncio
    async def test_connect_sets_channel_and_qos(self):
        """connect should create channel and set QoS."""
        from src.infrastructure.messaging.rabbitmq_consumer import RabbitMQConsumer

        config = RabbitMQConfig()
        consumer = RabbitMQConsumer(config)

        mock_channel = AsyncMock()
        mock_connection = AsyncMock()
        mock_connection.channel.return_value = mock_channel
        mock_connection.is_closed = False

        with patch("aio_pika.connect_robust", return_value=mock_connection):
            await consumer.connect()

        mock_channel.set_qos.assert_called_once_with(prefetch_count=config.prefetch_count)
        assert consumer._channel is not None

    @pytest.mark.asyncio
    async def test_on_message_acks_on_success_with_handler(self):
        """_on_message should ack when handler succeeds."""
        from src.infrastructure.messaging.idempotency.checker import IdempotencyChecker
        from src.infrastructure.messaging.rabbitmq_consumer import RabbitMQConsumer

        config = RabbitMQConfig()
        mock_checker = MagicMock(spec=IdempotencyChecker)
        mock_checker.try_acquire.return_value = True

        consumer = RabbitMQConsumer(
            config,
            idempotency_checker=mock_checker,
            metrics_collector=None,
            dlq=None,
            retry_policy=None,
        )
        consumer._connection = AsyncMock()

        event = _make_event()
        message_body = json.dumps(event.to_dict()).encode()

        mock_message = AsyncMock()
        mock_message.body = message_body
        mock_message.headers = {}

        handler_called = []

        async def handler(evt):
            handler_called.append(evt)

        consumer._handlers = {"DocumentProcessed": [handler]}
        await consumer._on_message(mock_message)

        assert len(handler_called) == 1
        mock_message.ack.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_message_acks_duplicate_event(self):
        """_on_message should ack when try_acquire returns False (duplicate)."""
        from src.infrastructure.messaging.idempotency.checker import IdempotencyChecker
        from src.infrastructure.messaging.rabbitmq_consumer import RabbitMQConsumer

        config = RabbitMQConfig()
        mock_checker = MagicMock(spec=IdempotencyChecker)
        mock_checker.try_acquire.return_value = False

        consumer = RabbitMQConsumer(
            config,
            idempotency_checker=mock_checker,
            metrics_collector=None,
            dlq=None,
            retry_policy=None,
        )
        consumer._connection = AsyncMock()

        event = _make_event()
        mock_message = AsyncMock()
        mock_message.body = json.dumps(event.to_dict()).encode()
        mock_message.headers = {}

        async def noop_handler(evt):
            pass

        consumer._handlers = {"DocumentProcessed": [noop_handler]}
        await consumer._on_message(mock_message)

        mock_message.ack.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_message_nacks_on_handler_failure_with_retry(self):
        """_on_message should nack(requeue=True) when handler fails and retry available."""
        from src.infrastructure.messaging.idempotency.checker import IdempotencyChecker
        from src.infrastructure.messaging.idempotency.retry_policy import RetryPolicy
        from src.infrastructure.messaging.rabbitmq_consumer import RabbitMQConsumer

        config = RabbitMQConfig()
        mock_checker = MagicMock(spec=IdempotencyChecker)
        mock_checker.try_acquire.return_value = True

        mock_retry = MagicMock(spec=RetryPolicy)
        mock_retry.max_retries = 3
        mock_retry.should_retry.return_value = True

        consumer = RabbitMQConsumer(
            config,
            idempotency_checker=mock_checker,
            metrics_collector=None,
            dlq=None,
            retry_policy=mock_retry,
        )
        consumer._connection = AsyncMock()

        event = _make_event()
        mock_message = AsyncMock()
        mock_message.body = json.dumps(event.to_dict()).encode()
        mock_message.headers = {}

        async def failing_handler(evt):
            raise RuntimeError("handler error")

        consumer._handlers = {"DocumentProcessed": [failing_handler]}
        await consumer._on_message(mock_message)

        mock_message.nack.assert_called_once_with(requeue=True)

    @pytest.mark.asyncio
    async def test_on_message_nacks_to_dlq_when_max_retries_exceeded(self):
        """_on_message should nack(requeue=False) and enqueue to DLQ when retries exhausted."""
        from src.infrastructure.messaging.idempotency.checker import IdempotencyChecker
        from src.infrastructure.messaging.idempotency.retry_policy import RetryPolicy
        from src.infrastructure.messaging.rabbitmq_consumer import RabbitMQConsumer

        config = RabbitMQConfig()
        mock_checker = MagicMock(spec=IdempotencyChecker)
        mock_checker.try_acquire.return_value = True

        mock_retry = MagicMock(spec=RetryPolicy)
        mock_retry.max_retries = 3
        mock_retry.should_retry.return_value = False

        mock_dlq = MagicMock()

        consumer = RabbitMQConsumer(
            config,
            idempotency_checker=mock_checker,
            metrics_collector=None,
            dlq=mock_dlq,
            retry_policy=mock_retry,
        )
        consumer._connection = AsyncMock()

        event = _make_event()
        mock_message = AsyncMock()
        mock_message.body = json.dumps(event.to_dict()).encode()
        mock_message.headers = {}

        async def failing_handler(evt):
            raise RuntimeError("handler error")

        consumer._handlers = {"DocumentProcessed": [failing_handler]}
        await consumer._on_message(mock_message)

        mock_message.nack.assert_called_once_with(requeue=False)
        mock_dlq.enqueue.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_message_nacks_to_dlq_when_no_retry_policy(self):
        """_on_message should nack(requeue=False) and enqueue to DLQ when no retry policy configured."""
        from src.infrastructure.messaging.idempotency.checker import IdempotencyChecker
        from src.infrastructure.messaging.rabbitmq_consumer import RabbitMQConsumer

        config = RabbitMQConfig()
        mock_checker = MagicMock(spec=IdempotencyChecker)
        mock_checker.try_acquire.return_value = True
        mock_dlq = MagicMock()

        consumer = RabbitMQConsumer(
            config,
            idempotency_checker=mock_checker,
            metrics_collector=None,
            dlq=mock_dlq,
            retry_policy=None,
        )
        consumer._connection = AsyncMock()

        event = _make_event()
        mock_message = AsyncMock()
        mock_message.body = json.dumps(event.to_dict()).encode()
        mock_message.headers = {}

        async def failing_handler(evt):
            raise RuntimeError("handler error")

        consumer._handlers = {"DocumentProcessed": [failing_handler]}
        await consumer._on_message(mock_message)

        mock_message.nack.assert_called_once_with(requeue=False)
        mock_dlq.enqueue.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_message_nacks_unknown_event_type(self):
        """_on_message should nack(requeue=False) for unknown event_type."""
        from src.infrastructure.messaging.rabbitmq_consumer import RabbitMQConsumer

        config = RabbitMQConfig()
        consumer = RabbitMQConsumer(config)
        consumer._connection = AsyncMock()

        mock_message = AsyncMock()
        mock_message.body = json.dumps({"event_type": "UnknownEvent"}).encode()

        await consumer._on_message(mock_message)

        mock_message.nack.assert_called_once_with(requeue=False)

    @pytest.mark.asyncio
    async def test_on_message_nacks_invalid_json(self):
        """_on_message should nack(requeue=False) for invalid JSON."""
        from src.infrastructure.messaging.rabbitmq_consumer import RabbitMQConsumer

        config = RabbitMQConfig()
        consumer = RabbitMQConsumer(config)
        consumer._connection = AsyncMock()

        mock_message = AsyncMock()
        mock_message.body = b"{invalid json"

        await consumer._on_message(mock_message)

        mock_message.nack.assert_called_once_with(requeue=False)

    @pytest.mark.asyncio
    async def test_on_message_records_metrics_on_success(self):
        """_on_message should record metrics on successful processing."""
        from src.infrastructure.messaging.idempotency.checker import IdempotencyChecker
        from src.infrastructure.messaging.rabbitmq_consumer import RabbitMQConsumer
        from src.infrastructure.monitoring.event_metrics import EventMetricsCollector

        config = RabbitMQConfig()
        mock_checker = MagicMock(spec=IdempotencyChecker)
        mock_checker.try_acquire.return_value = True
        mock_collector = MagicMock(spec=EventMetricsCollector)

        consumer = RabbitMQConsumer(
            config,
            idempotency_checker=mock_checker,
            metrics_collector=mock_collector,
            dlq=None,
            retry_policy=None,
        )
        consumer._connection = AsyncMock()

        event = _make_event()
        mock_message = AsyncMock()
        mock_message.body = json.dumps(event.to_dict()).encode()
        mock_message.headers = {}

        async def handler(evt):
            pass

        consumer._handlers = {"DocumentProcessed": [handler]}
        await consumer._on_message(mock_message)

        mock_collector.record_processed.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_message_records_retry_metric(self):
        """_on_message should record retry metric when retrying."""
        from src.infrastructure.messaging.idempotency.checker import IdempotencyChecker
        from src.infrastructure.messaging.idempotency.retry_policy import RetryPolicy
        from src.infrastructure.messaging.rabbitmq_consumer import RabbitMQConsumer
        from src.infrastructure.monitoring.event_metrics import EventMetricsCollector

        config = RabbitMQConfig()
        mock_checker = MagicMock(spec=IdempotencyChecker)
        mock_checker.try_acquire.return_value = True

        mock_retry = MagicMock(spec=RetryPolicy)
        mock_retry.max_retries = 3
        mock_retry.should_retry.return_value = True

        mock_collector = MagicMock(spec=EventMetricsCollector)

        consumer = RabbitMQConsumer(
            config,
            idempotency_checker=mock_checker,
            metrics_collector=mock_collector,
            dlq=None,
            retry_policy=mock_retry,
        )
        consumer._connection = AsyncMock()

        event = _make_event()
        mock_message = AsyncMock()
        mock_message.body = json.dumps(event.to_dict()).encode()
        mock_message.headers = {}

        async def failing_handler(evt):
            raise RuntimeError("handler error")

        consumer._handlers = {"DocumentProcessed": [failing_handler]}
        await consumer._on_message(mock_message)

        mock_collector.record_retried.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_message_records_dlq_metric(self):
        """_on_message should record DLQ metric when event goes to DLQ."""
        from src.infrastructure.messaging.idempotency.checker import IdempotencyChecker
        from src.infrastructure.messaging.idempotency.retry_policy import RetryPolicy
        from src.infrastructure.messaging.rabbitmq_consumer import RabbitMQConsumer
        from src.infrastructure.monitoring.event_metrics import EventMetricsCollector

        config = RabbitMQConfig()
        mock_checker = MagicMock(spec=IdempotencyChecker)
        mock_checker.try_acquire.return_value = True

        mock_retry = MagicMock(spec=RetryPolicy)
        mock_retry.max_retries = 3
        mock_retry.should_retry.return_value = False

        mock_dlq = MagicMock()
        mock_collector = MagicMock(spec=EventMetricsCollector)

        consumer = RabbitMQConsumer(
            config,
            idempotency_checker=mock_checker,
            metrics_collector=mock_collector,
            dlq=mock_dlq,
            retry_policy=mock_retry,
        )
        consumer._connection = AsyncMock()

        event = _make_event()
        mock_message = AsyncMock()
        mock_message.body = json.dumps(event.to_dict()).encode()
        mock_message.headers = {}

        async def failing_handler(evt):
            raise RuntimeError("handler error")

        consumer._handlers = {"DocumentProcessed": [failing_handler]}
        await consumer._on_message(mock_message)

        mock_collector.record_dlq.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_message_no_handler_acks_message(self):
        """_on_message should ack when no handler is registered (event silently dropped)."""
        from src.infrastructure.messaging.idempotency.checker import IdempotencyChecker
        from src.infrastructure.messaging.rabbitmq_consumer import RabbitMQConsumer

        config = RabbitMQConfig()
        mock_checker = MagicMock(spec=IdempotencyChecker)
        mock_checker.try_acquire.return_value = True

        consumer = RabbitMQConsumer(
            config,
            idempotency_checker=mock_checker,
            metrics_collector=None,
            dlq=None,
            retry_policy=None,
        )
        consumer._connection = AsyncMock()

        event = _make_event()
        mock_message = AsyncMock()
        mock_message.body = json.dumps(event.to_dict()).encode()
        mock_message.headers = {}

        # No handlers registered
        await consumer._on_message(mock_message)

        mock_message.ack.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_message_handles_non_numeric_retry_header(self):
        """_on_message should handle non-numeric x-retry-count header gracefully."""
        from src.infrastructure.messaging.idempotency.checker import IdempotencyChecker
        from src.infrastructure.messaging.idempotency.retry_policy import RetryPolicy
        from src.infrastructure.messaging.rabbitmq_consumer import RabbitMQConsumer

        config = RabbitMQConfig()
        mock_checker = MagicMock(spec=IdempotencyChecker)
        mock_checker.try_acquire.return_value = True

        mock_retry = MagicMock(spec=RetryPolicy)
        mock_retry.max_retries = 3
        mock_retry.should_retry.return_value = True

        consumer = RabbitMQConsumer(
            config,
            idempotency_checker=mock_checker,
            metrics_collector=None,
            dlq=None,
            retry_policy=mock_retry,
        )
        consumer._connection = AsyncMock()

        event = _make_event()
        mock_message = AsyncMock()
        mock_message.body = json.dumps(event.to_dict()).encode()
        mock_message.headers = {"x-retry-count": "abc"}  # Non-numeric

        async def failing_handler(evt):
            raise RuntimeError("handler error")

        consumer._handlers = {"DocumentProcessed": [failing_handler]}
        await consumer._on_message(mock_message)

        # Should not crash, should retry with default 0
        mock_message.nack.assert_called_once_with(requeue=True)

    @pytest.mark.asyncio
    async def test_close_connection(self):
        """close should close connection."""
        from src.infrastructure.messaging.rabbitmq_consumer import RabbitMQConsumer

        config = RabbitMQConfig()
        consumer = RabbitMQConsumer(config)

        mock_connection = AsyncMock()
        mock_connection.is_closed = False
        consumer._connection = mock_connection

        await consumer.close()
        mock_connection.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_skips_if_already_closed(self):
        """close should not raise if connection already closed."""
        from src.infrastructure.messaging.rabbitmq_consumer import RabbitMQConsumer

        config = RabbitMQConfig()
        consumer = RabbitMQConsumer(config)

        mock_connection = AsyncMock()
        mock_connection.is_closed = True
        consumer._connection = mock_connection

        await consumer.close()  # Should not raise

    @pytest.mark.asyncio
    async def test_close_skips_if_no_connection(self):
        """close should not raise if no connection set."""
        from src.infrastructure.messaging.rabbitmq_consumer import RabbitMQConsumer

        config = RabbitMQConfig()
        consumer = RabbitMQConsumer(config)

        await consumer.close()  # Should not raise
