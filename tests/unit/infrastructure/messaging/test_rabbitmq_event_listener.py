"""Task 8 TDD Tests — RabbitMQEventListener (AC-8)."""

from __future__ import annotations

from unittest import mock
from uuid import uuid4

import pytest

from src.domain.events.base import DomainEvent


class TestRabbitMQEventListenerInterface:
    """RabbitMQEventListener interface tests."""

    def test_has_event_listener_async_methods(self):
        """RabbitMQEventListener should have EventListenerAsync methods."""
        from src.infrastructure.messaging.rabbitmq_listener import RabbitMQEventListener

        assert hasattr(RabbitMQEventListener, "async_handle")


class TestRabbitMQEventListenerIntegration:
    """RabbitMQEventListener integration tests with mocks."""

    @pytest.fixture
    def mock_dependencies(self):
        """Provide mock dependencies for RabbitMQEventListener."""
        mock_redis = mock.AsyncMock()
        # register_script 是同步方法，不应返回 coroutine
        mock_redis.register_script = mock.MagicMock(return_value=mock.MagicMock())
        mock_config = mock.MagicMock()
        mock_config.queue_name = "test_queue"
        mock_config.host = "localhost"
        mock_config.port = 5672
        mock_config.username = "guest"
        mock_config.password = "guest"  # pragma: allowlist secret
        mock_config.virtual_host = "/"
        mock_config.prefetch_count = 10
        return mock_redis, mock_config

    async def test_async_handle_calls_process_event(self, mock_dependencies):
        """async_handle should process the event and return None."""
        from src.infrastructure.messaging.rabbitmq_listener import RabbitMQEventListener

        mock_redis, mock_config = mock_dependencies

        listener = RabbitMQEventListener(
            config=mock_config,
            redis_client=mock_redis,
        )

        event = DomainEvent(event_type="TestEvent")

        # Should not raise
        await listener.async_handle(event)

    async def test_async_handle_with_document_processed(self, mock_dependencies):
        """async_handle should handle DocumentProcessed event."""
        from src.domain.events import DocumentProcessed
        from src.infrastructure.messaging.rabbitmq_listener import RabbitMQEventListener

        mock_redis, mock_config = mock_dependencies

        listener = RabbitMQEventListener(
            config=mock_config,
            redis_client=mock_redis,
        )

        event = DocumentProcessed(
            document_id=uuid4(),
            parse_result={"pages": 10},
            embedding=[0.1] * 1024,
        )

        await listener.async_handle(event)

    async def test_listener_uses_idempotency_checker(self, mock_dependencies):
        """Listener should use DualIdempotencyChecker for idempotency."""
        from src.infrastructure.messaging.rabbitmq_listener import RabbitMQEventListener

        mock_redis, mock_config = mock_dependencies

        listener = RabbitMQEventListener(
            config=mock_config,
            redis_client=mock_redis,
        )

        # Verify idempotency checker is initialized
        assert listener._idempotency is not None

    async def test_listener_uses_retry_queue(self, mock_dependencies):
        """Listener should use RedisRetryQueue for retries."""
        from src.infrastructure.messaging.rabbitmq_listener import RabbitMQEventListener

        mock_redis, mock_config = mock_dependencies

        listener = RabbitMQEventListener(
            config=mock_config,
            redis_client=mock_redis,
        )

        # Verify retry queue is initialized
        assert listener._retry_queue is not None

    async def test_listener_has_set_dead_letter_queue_method(self, mock_dependencies):
        """Listener should have set_dead_letter_queue method."""
        from src.infrastructure.messaging.rabbitmq_listener import RabbitMQEventListener

        mock_redis, mock_config = mock_dependencies

        listener = RabbitMQEventListener(
            config=mock_config,
            redis_client=mock_redis,
        )

        # Verify method exists
        assert hasattr(listener, "set_dead_letter_queue")
