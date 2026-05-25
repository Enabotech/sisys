"""RedisEventBus 单元测试

验证 RedisEventBus 的 publish/subscribe/start/close 方法
通过 mock publisher/subscriber/router 测试总线编排逻辑

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from src.domain.events.base import DomainEvent
from src.infrastructure.messaging.redis_event_bus import RedisEventBus


def _make_event(**kwargs: Any) -> DomainEvent:
    """创建测试用 DomainEvent."""
    event_id = kwargs.pop("event_id", uuid4())
    event_type = kwargs.pop("event_type", "TestEvent")
    source = kwargs.pop("source", "test")
    return DomainEvent(event_id=event_id, event_type=event_type, source=source, **kwargs)


def _make_bus(
    channel: str | None = "sisys:rt:testevent",
) -> RedisEventBus:
    """创建带 mock 的 RedisEventBus."""
    mock_publisher = AsyncMock()
    mock_subscriber = AsyncMock()
    mock_router = MagicMock()
    mock_router.get_redis_channel.return_value = channel
    return RedisEventBus(
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        router=mock_router,
    )


class TestRedisEventBusPublish:
    """RedisEventBus.publish 测试."""

    async def test_publish_returns_success(self) -> None:
        """正常发布应返回成功结果."""
        bus = _make_bus()
        event = _make_event()
        result = await bus.publish(event)
        assert result.is_success
        assert result.results[0].channel_name == "realtime"
        assert result.results[0].success is True

    async def test_publish_calls_publisher(self) -> None:
        """应调用底层 publisher.publish."""
        bus = _make_bus()
        event = _make_event()
        await bus.publish(event)
        bus._publisher.publish.assert_called_once_with(event, "sisys:rt:testevent")

    async def test_publish_unregistered_event_type_returns_failure(self) -> None:
        """未注册的事件类型（channel=None）应返回失败."""
        bus = _make_bus(channel=None)
        event = _make_event()
        result = await bus.publish(event)
        assert result.is_full_failure
        assert result.results[0].success is False

    async def test_publish_exception_returns_failure(self) -> None:
        """publisher 抛异常时应返回失败（不抛出异常）."""
        bus = _make_bus()
        bus._publisher.publish.side_effect = ConnectionError("redis down")
        event = _make_event()
        result = await bus.publish(event)
        assert result.is_full_failure
        error = result.results[0].error
        assert error is not None
        assert "redis down" in error


class TestRedisEventBusSubscribe:
    """RedisEventBus.subscribe/subscribe_async 测试."""

    async def test_subscribe_delegates_to_subscriber(self) -> None:
        """subscribe 应委托给底层 subscriber."""
        bus = _make_bus()
        handler = MagicMock()
        # Mock subscribe 为同步方法
        bus._subscriber.subscribe = MagicMock()
        await bus.subscribe("TestEvent", handler)
        bus._subscriber.subscribe.assert_called_once_with("sisys:rt:testevent", handler)

    async def test_subscribe_async_delegates_to_subscriber(self) -> None:
        """subscribe_async 应委托给底层 subscriber."""
        bus = _make_bus()
        handler = AsyncMock()
        # Mock subscribe_async 为同步方法
        bus._subscriber.subscribe_async = MagicMock()
        await bus.subscribe_async("TestEvent", handler)
        bus._subscriber.subscribe_async.assert_called_once_with("sisys:rt:testevent", handler)


class TestRedisEventBusLifecycle:
    """RedisEventBus.start/close 测试."""

    async def test_start_delegates_to_subscriber(self) -> None:
        """start 应调用 subscriber.start."""
        bus = _make_bus()
        await bus.start()
        bus._subscriber.start.assert_called_once()

    async def test_close_closes_publisher_and_subscriber(self) -> None:
        """close 应关闭 publisher 和 subscriber."""
        bus = _make_bus()
        await bus.close()
        bus._publisher.close.assert_called_once()
        bus._subscriber.close.assert_called_once()
