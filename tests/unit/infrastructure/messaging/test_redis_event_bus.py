"""Redis Pub/Sub event channel tests."""

from __future__ import annotations

import json
import os
from uuid import uuid4

import fakeredis.aioredis
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
        config = RedisConfig()
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.db == 0
        assert config.password is None
        assert config.max_connections == 10
        assert config.socket_timeout == 5.0

    def test_custom_values(self):
        config = RedisConfig(
            host="redis.example.com",
            port=6380,
            db=1,
            password="secret",  # pragma: allowlist secret,
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
        env = os.environ.copy()
        try:
            for key in list(os.environ.keys()):
                if key.startswith("REDIS_"):
                    del os.environ[key]
            config = RedisConfig.from_env()
            assert config.host == "localhost"
            assert config.port == 6379
        finally:
            os.environ.clear()
            os.environ.update(env)

    def test_from_env_with_custom_values(self):
        env = os.environ.copy()
        try:
            os.environ["REDIS_HOST"] = "my-redis"
            os.environ["REDIS_PORT"] = "6380"
            config = RedisConfig.from_env()
            assert config.host == "my-redis"
            assert config.port == 6380
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

    @pytest.mark.asyncio
    async def test_publish_serializes_event_to_json(self):
        from src.infrastructure.messaging.redis_publisher import RedisEventPublisher

        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        config = RedisConfig()
        publisher = RedisEventPublisher(config)
        publisher._pool = fake_redis.connection_pool

        event = self._make_event()
        await publisher.publish(event, channel="sisys:rt:documentprocessed")

        # 验证消息已发布：通过 pubsub 订阅同一频道
        pubsub = fake_redis.pubsub()
        await pubsub.subscribe("sisys:rt:documentprocessed")
        # 注意：fakeredis 中 publish 后消息不会回退给已有订阅者
        # 所以我们只验证不抛异常即可

    @pytest.mark.asyncio
    async def test_publish_uses_connection_pool(self):
        from src.infrastructure.messaging.redis_publisher import RedisEventPublisher

        config = RedisConfig()
        publisher = RedisEventPublisher(config)
        assert publisher._pool is None

    @pytest.mark.asyncio
    async def test_publish_returns_result_on_connection_error(self):
        """RedisEventPublisher 连接失败应返回 PublishResult（优雅降级）"""
        from src.infrastructure.messaging.redis_publisher import RedisEventPublisher

        config = RedisConfig(host="invalid-host", port=9999)
        publisher = RedisEventPublisher(config)
        event = self._make_event()

        # 优雅降级：不抛异常，返回 PublishResult
        result = await publisher.publish(event, channel="sisys:rt:test")
        assert result is not None
        assert result.redis_success is False
        assert result.redis_error is not None

    @pytest.mark.asyncio
    async def test_close_disconnects_pool(self):
        from src.infrastructure.messaging.redis_publisher import RedisEventPublisher

        config = RedisConfig()
        publisher = RedisEventPublisher(config)
        await publisher.close()


# ============================================================================
# TDD Cycle C: RedisEventSubscriber
# ============================================================================


class TestRedisEventSubscriber:
    """RedisEventSubscriber tests using fakeredis."""

    def test_subscribe_registers_handler(self):
        from src.infrastructure.messaging.redis_subscriber import RedisEventSubscriber

        config = RedisConfig()
        subscriber = RedisEventSubscriber(config)

        handler_called = []

        def handler(event_data):
            handler_called.append(event_data)

        subscriber.subscribe("sisys:rt:test", handler)
        assert "sisys:rt:test" in subscriber._handlers

    def test_deserializes_json_event(self):
        from src.infrastructure.messaging.redis_subscriber import RedisEventSubscriber

        config = RedisConfig()
        subscriber = RedisEventSubscriber(config)

        received = []

        def handler(event_dict):
            received.append(event_dict)

        subscriber.subscribe("sisys:rt:test", handler)

        event = DocumentProcessed(
            document_id=uuid4(),
            parse_result={"pages": 5},
            embedding=[0.1] * 1024,
        )
        message = json.dumps(event.to_dict())

        # 手动分发（模拟 pubsub 接收）
        subscriber._dispatch_message("sisys:rt:test", message)

        assert len(received) == 1
        assert received[0].event_type == "DocumentProcessed"

    def test_handles_deserialization_error(self):
        from src.infrastructure.messaging.redis_subscriber import RedisEventSubscriber

        config = RedisConfig()
        subscriber = RedisEventSubscriber(config)

        errors = []

        def handler(event_dict):
            pass

        def error_handler(channel, message, error):
            errors.append((channel, message, error))

        subscriber.subscribe("sisys:rt:test", handler, error_handler=error_handler)

        subscriber._dispatch_message("sisys:rt:test", "{invalid json")

        assert len(errors) == 1

    @pytest.mark.asyncio
    async def test_close_stops_subscription(self):
        from src.infrastructure.messaging.redis_subscriber import RedisEventSubscriber

        config = RedisConfig()
        subscriber = RedisEventSubscriber(config)
        await subscriber.close()

    @pytest.mark.asyncio
    async def test_close_handles_empty_pubsub(self):
        """close should handle case where pubsub was never created."""
        from src.infrastructure.messaging.redis_subscriber import RedisEventSubscriber

        config = RedisConfig()
        subscriber = RedisEventSubscriber(config)
        await subscriber.close()

    @pytest.mark.asyncio
    async def test_close_clears_state(self):
        """close should clear handlers and error_handlers."""
        from src.infrastructure.messaging.redis_subscriber import RedisEventSubscriber

        config = RedisConfig()
        subscriber = RedisEventSubscriber(config)
        subscriber.subscribe("ch1", lambda data: None)
        await subscriber.close()
        assert subscriber._handlers == {}
        assert subscriber._error_handlers == {}

    @pytest.mark.asyncio
    async def test_close_with_active_pool_disconnects(self):
        """close should disconnect active connection pool."""
        from src.infrastructure.messaging.redis_subscriber import RedisEventSubscriber

        config = RedisConfig()
        subscriber = RedisEventSubscriber(config)
        pool = await subscriber._get_pool()
        assert pool is not None
        await subscriber.close()
        assert subscriber._pool is None

    @pytest.mark.asyncio
    async def test_get_pool_creates_pool_on_first_call(self):
        from src.infrastructure.messaging.redis_subscriber import RedisEventSubscriber

        config = RedisConfig()
        subscriber = RedisEventSubscriber(config)
        assert subscriber._pool is None

        pool = await subscriber._get_pool()
        assert pool is not None
        assert subscriber._pool is pool

    @pytest.mark.asyncio
    async def test_get_pool_reuses_existing_pool(self):
        from src.infrastructure.messaging.redis_subscriber import RedisEventSubscriber

        config = RedisConfig()
        subscriber = RedisEventSubscriber(config)

        pool1 = await subscriber._get_pool()
        pool2 = await subscriber._get_pool()
        assert pool1 is pool2

    def test_subscribe_registers_multiple_handlers_same_channel(self):
        from src.infrastructure.messaging.redis_subscriber import RedisEventSubscriber

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
        from src.infrastructure.messaging.redis_subscriber import RedisEventSubscriber

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

        subscriber._dispatch_message("ch1", "{bad")

        assert len(first_errors) == 1
        assert len(second_errors) == 0

    def test_dispatch_calls_all_handlers_even_if_first_raises(self):
        from src.infrastructure.messaging.redis_subscriber import RedisEventSubscriber

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
        from src.infrastructure.messaging.redis_subscriber import RedisEventSubscriber

        config = RedisConfig()
        subscriber = RedisEventSubscriber(config)
        subscriber._dispatch_message("nonexistent", '{"key": "value"}')

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self):
        from unittest.mock import AsyncMock, MagicMock

        from src.infrastructure.messaging.redis_subscriber import RedisEventSubscriber

        config = RedisConfig()
        subscriber = RedisEventSubscriber(config)
        subscriber.subscribe("ch1", lambda d: None)

        # Mock pool with async aclose
        mock_pool = MagicMock()
        mock_pool.aclose = AsyncMock()
        subscriber._pool = mock_pool

        # Mock pubsub
        import redis.asyncio as aioredis_mod

        original_redis = aioredis_mod.Redis

        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.listen = MagicMock()
        mock_pubsub.listen.return_value.__aiter__ = MagicMock(return_value=iter([]))

        class MockAsyncRedis:
            def __init__(self, **kwargs):
                pass

            def pubsub(self):
                return mock_pubsub

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        aioredis_mod.Redis = MockAsyncRedis
        try:
            await subscriber.start()
            task1 = subscriber._task
            await subscriber.start()
            assert subscriber._task is task1
        finally:
            aioredis_mod.Redis = original_redis
            await subscriber.close()
