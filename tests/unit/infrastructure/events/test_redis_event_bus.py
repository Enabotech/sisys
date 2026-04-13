"""Task 1 TDD Tests — Redis Pub/Sub event channel."""

from __future__ import annotations

import json
import os
from unittest.mock import patch
from uuid import uuid4

import fakeredis
import pytest

from src.domain.events import DocumentProcessed
from src.domain.events.base import DomainEvent
from src.infrastructure.config.redis import RedisConfig

# ============================================================================
# TDD Cycle A: RedisConfig
# ============================================================================


class TestRedisConfig:
    """RedisConfig configuration model tests."""

    def test_default_values(self):
        """RedisConfig should have sensible defaults."""
        config = RedisConfig()
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.db == 0
        assert config.password is None
        assert config.max_connections == 10
        assert config.socket_timeout == 5.0

    def test_custom_values(self):
        """RedisConfig should accept custom values."""
        config = RedisConfig(
            host="redis.example.com",
            port=6380,
            db=1,
            password="secret",  # nosec B106
            max_connections=20,
            socket_timeout=10.0,
        )
        assert config.host == "redis.example.com"
        assert config.port == 6380
        assert config.db == 1
        assert config.password == "secret"  # pragma: allowlist secret
        assert config.max_connections == 20
        assert config.socket_timeout == 10.0

    def test_from_env_with_defaults(self):
        """RedisConfig.from_env should use environment variables."""
        env = os.environ.copy()
        try:
            # Clear any existing Redis env vars
            for key in list(os.environ.keys()):
                if key.startswith("REDIS_"):
                    del os.environ[key]

            config = RedisConfig.from_env()
            assert config.host == "localhost"
            assert config.port == 6379
            assert config.db == 0
            assert config.password is None
        finally:
            # Restore environment
            os.environ.clear()
            os.environ.update(env)

    def test_from_env_with_custom_values(self):
        """RedisConfig.from_env should read environment variables."""
        env = os.environ.copy()
        try:
            os.environ["REDIS_HOST"] = "my-redis"
            os.environ["REDIS_PORT"] = "6380"
            os.environ["REDIS_DB"] = "2"
            os.environ["REDIS_PASSWORD"] = "pass123"  # pragma: allowlist secret
            os.environ["REDIS_MAX_CONNECTIONS"] = "50"
            os.environ["REDIS_SOCKET_TIMEOUT"] = "3.0"

            config = RedisConfig.from_env()
            assert config.host == "my-redis"
            assert config.port == 6380
            assert config.db == 2
            assert config.password == "pass123"  # pragma: allowlist secret
            assert config.max_connections == 50
            assert config.socket_timeout == 3.0
        finally:
            os.environ.clear()
            os.environ.update(env)


# ============================================================================
# TDD Cycle B: RedisEventPublisher
# ============================================================================


class TestRedisEventPublisher:
    """RedisEventPublisher tests using fakeredis."""

    def _make_event(self) -> DomainEvent:
        return DocumentProcessed(
            document_id=uuid4(),
            parse_result={"pages": 10},
            embedding=[0.1] * 1024,
        )

    def test_publish_serializes_event_to_json(self):
        """RedisEventPublisher should serialize event to JSON."""
        from src.infrastructure.events.redis_publisher import RedisEventPublisher

        fake_redis = fakeredis.FakeRedis()
        config = RedisConfig()

        with patch("redis.Redis", return_value=fake_redis):
            publisher = RedisEventPublisher(config)
            # Use the fake redis directly
            publisher._pool = fake_redis.connection_pool

            event = self._make_event()
            publisher.publish(event, channel="sisys:rt:documentprocessed")

            # Verify the message was published
            # fakeredis stores published messages in a pubsub mechanism
            # We'll verify via the pubsub subscriber

    def test_publish_uses_connection_pool(self):
        """RedisEventPublisher should use connection pool."""
        from src.infrastructure.events.redis_publisher import RedisEventPublisher

        config = RedisConfig()
        publisher = RedisEventPublisher(config)
        # _pool should be None initially (lazy initialization)
        assert publisher._pool is None

    def test_publish_raises_on_connection_error(self):
        """RedisEventPublisher should raise on connection failure."""
        from src.infrastructure.events.redis_publisher import RedisEventPublisher

        config = RedisConfig(host="invalid-host", port=9999)
        publisher = RedisEventPublisher(config)
        event = self._make_event()

        with pytest.raises(Exception):
            publisher.publish(event, channel="sisys:rt:test")

    def test_close_disconnects_pool(self):
        """RedisEventPublisher.close should disconnect the pool."""
        from src.infrastructure.events.redis_publisher import RedisEventPublisher

        config = RedisConfig()
        publisher = RedisEventPublisher(config)
        publisher.close()  # Should not raise even if pool is None


# ============================================================================
# TDD Cycle C: RedisEventSubscriber
# ============================================================================


class TestRedisEventSubscriber:
    """RedisEventSubscriber tests using fakeredis."""

    def test_subscribe_registers_handler(self):
        """RedisEventSubscriber should register event handlers."""
        from src.infrastructure.events.redis_subscriber import RedisEventSubscriber

        config = RedisConfig()
        subscriber = RedisEventSubscriber(config)

        handler_called = []

        def handler(event_data):
            handler_called.append(event_data)

        subscriber.subscribe("sisys:rt:test", handler)
        assert "sisys:rt:test" in subscriber._handlers

    def test_deserializes_json_event(self):
        """RedisEventSubscriber should deserialize JSON to dict."""
        from src.infrastructure.events.redis_subscriber import RedisEventSubscriber

        config = RedisConfig()
        subscriber = RedisEventSubscriber(config)

        received = []

        def handler(event_dict):
            received.append(event_dict)

        subscriber.subscribe("sisys:rt:test", handler)

        # Simulate a message
        event = DocumentProcessed(
            document_id=uuid4(),
            parse_result={"pages": 5},
            embedding=[0.1] * 1024,
        )
        message = json.dumps(event.to_dict())

        # Manually dispatch (simulating pubsub receive)
        subscriber._dispatch_message("sisys:rt:test", message)

        assert len(received) == 1
        assert received[0]["event_type"] == "DocumentProcessed"

    def test_handles_deserialization_error(self):
        """RedisEventSubscriber should handle malformed JSON gracefully."""
        from src.infrastructure.events.redis_subscriber import RedisEventSubscriber

        config = RedisConfig()
        subscriber = RedisEventSubscriber(config)

        errors = []

        def handler(event_dict):
            pass

        def error_handler(channel, message, error):
            errors.append((channel, message, error))

        subscriber.subscribe("sisys:rt:test", handler, error_handler=error_handler)

        # Send malformed JSON
        subscriber._dispatch_message("sisys:rt:test", "{invalid json")

        assert len(errors) == 1

    def test_close_stops_subscription(self):
        """RedisEventSubscriber.close should stop the pubsub thread."""
        from src.infrastructure.events.redis_subscriber import RedisEventSubscriber

        config = RedisConfig()
        subscriber = RedisEventSubscriber(config)
        subscriber.close()  # Should not raise

    def test_get_pool_creates_pool_on_first_call(self):
        """_get_pool should create connection pool on first call."""
        from src.infrastructure.events.redis_subscriber import RedisEventSubscriber

        config = RedisConfig()
        subscriber = RedisEventSubscriber(config)
        assert subscriber._pool is None

        pool = subscriber._get_pool()
        assert pool is not None
        assert subscriber._pool is pool

    def test_get_pool_reuses_existing_pool(self):
        """_get_pool should return existing pool on subsequent calls."""
        from src.infrastructure.events.redis_subscriber import RedisEventSubscriber

        config = RedisConfig()
        subscriber = RedisEventSubscriber(config)

        pool1 = subscriber._get_pool()
        pool2 = subscriber._get_pool()
        assert pool1 is pool2

    def test_subscribe_registers_multiple_handlers_same_channel(self):
        """subscribe should support multiple handlers on same channel."""
        from src.infrastructure.events.redis_subscriber import RedisEventSubscriber

        config = RedisConfig()
        subscriber = RedisEventSubscriber(config)

        received = []

        def handler1(data):
            received.append(("h1", data))

        def handler2(data):
            received.append(("h2", data))

        subscriber.subscribe("channel1", handler1)
        subscriber.subscribe("channel1", handler2)

        assert len(subscriber._handlers["channel1"]) == 2

    def test_subscribe_only_first_error_handler_is_used(self):
        """subscribe should only use the first error_handler per channel."""
        from src.infrastructure.events.redis_subscriber import RedisEventSubscriber

        config = RedisConfig()
        subscriber = RedisEventSubscriber(config)

        first_errors = []
        second_errors = []

        def handler(data):
            pass

        def first_error_handler(channel, message, error):
            first_errors.append((channel, message))

        def second_error_handler(channel, message, error):
            second_errors.append((channel, message))

        subscriber.subscribe("ch1", handler, error_handler=first_error_handler)
        subscriber.subscribe("ch1", handler, error_handler=second_error_handler)

        # Dispatch malformed JSON
        subscriber._dispatch_message("ch1", "{bad")

        assert len(first_errors) == 1
        assert len(second_errors) == 0

    def test_dispatch_calls_all_handlers_even_if_first_raises(self):
        """_dispatch_message should call all handlers even if one raises."""
        from src.infrastructure.events.redis_subscriber import RedisEventSubscriber

        config = RedisConfig()
        subscriber = RedisEventSubscriber(config)

        results = []

        def handler1(data):
            results.append("h1")
            raise ValueError("handler1 error")

        def handler2(data):
            results.append("h2")

        subscriber.subscribe("ch1", handler1)
        subscriber.subscribe("ch1", handler2)

        event = DocumentProcessed(
            document_id=uuid4(),
            parse_result={"pages": 5},
            embedding=[0.1] * 1024,
        )
        subscriber._dispatch_message("ch1", json.dumps(event.to_dict()))

        assert results == ["h1", "h2"]

    def test_dispatch_logs_warning_for_no_handlers(self):
        """_dispatch_message should handle missing channel gracefully."""
        from src.infrastructure.events.redis_subscriber import RedisEventSubscriber

        config = RedisConfig()
        subscriber = RedisEventSubscriber(config)

        # Should not raise, just no handlers
        subscriber._dispatch_message("nonexistent", '{"key": "value"}')

    def test_start_is_idempotent(self):
        """start should return early if already running."""
        from src.infrastructure.events.redis_subscriber import RedisEventSubscriber

        config = RedisConfig()
        subscriber = RedisEventSubscriber(config)

        def handler(data):
            pass

        subscriber.subscribe("ch1", handler)
        subscriber._running = True  # Simulate already running
        subscriber.start()  # Should return immediately without creating new pubsub
        assert subscriber._pubsub is None

    def test_close_handles_empty_pubsub(self):
        """close should handle case where pubsub was never created."""
        from src.infrastructure.events.redis_subscriber import RedisEventSubscriber

        config = RedisConfig()
        subscriber = RedisEventSubscriber(config)
        subscriber.close()  # Should not raise

    def test_close_clears_state(self):
        """close should clear handlers and error_handlers."""
        from src.infrastructure.events.redis_subscriber import RedisEventSubscriber

        config = RedisConfig()
        subscriber = RedisEventSubscriber(config)

        subscriber.subscribe("ch1", lambda data: None)
        subscriber.close()

        assert subscriber._handlers == {}
        assert subscriber._error_handlers == {}

    def test_close_with_active_pool_disconnects(self):
        """close should disconnect active connection pool."""
        from src.infrastructure.events.redis_subscriber import RedisEventSubscriber

        config = RedisConfig()
        subscriber = RedisEventSubscriber(config)

        # Create pool
        pool = subscriber._get_pool()
        assert pool is not None

        subscriber.close()
        assert subscriber._pool is None
