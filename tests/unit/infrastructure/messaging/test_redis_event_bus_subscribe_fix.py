"""Tests for RedisEventBus.subscribe() BUG fixes (P0-29/30/31).

验证 3 个 BUG 修复：
1. P0-29: subscribe() 传递 event_type 而非 Redis channel 名（频道名不匹配）
2. P0-30: subscribe_async() 调用不存在的方法（AttributeError）
3. P0-31: handler 收到 dict 而非 DomainEvent（缺少 from_dict 反序列化）

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.events.base import DomainEvent
from src.infrastructure.messaging.channel_router import ChannelRouter
from src.infrastructure.messaging.redis_event_bus import RedisEventBus
from src.infrastructure.messaging.redis_subscriber import RedisEventSubscriber

# ===================================================================
# 测试事件类
# ===================================================================


class SampleEvent(DomainEvent):
    """测试用事件类."""

    event_type: str = "SampleEvent"


DomainEvent.register("SampleEvent", SampleEvent)


def _make_event_dict() -> dict[str, str | int]:
    """构造测试事件 dict."""
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "SampleEvent",
        "timestamp": datetime.now().isoformat(),
        "source": "test",
    }


# ===================================================================
# P0-29: 频道名转换测试
# ===================================================================


class TestSubscribeChannelNameResolution:
    """验证 subscribe() 使用 ChannelRouter 解析频道名."""

    @pytest.mark.asyncio
    async def test_subscribe_resolves_channel_name(self) -> None:
        """subscribe("AutoTriggered") 应订阅 Redis channel "sisys:rt:auto_triggered"."""
        router = ChannelRouter()
        mock_publisher = AsyncMock()
        mock_subscriber = MagicMock()

        bus = RedisEventBus(
            publisher=mock_publisher,
            subscriber=mock_subscriber,
            router=router,
        )

        handler = MagicMock()
        await bus.subscribe("AutoTriggered", handler)

        # 验证：subscriber.subscribe 收到正确的 Redis channel 名
        # 不是 event_type "AutoTriggered"，而是 "sisys:rt:auto_triggered"
        mock_subscriber.subscribe.assert_called_once()
        call_args = mock_subscriber.subscribe.call_args
        assert call_args[0][0] == "sisys:rt:auto_triggered", (
            f"Expected channel 'sisys:rt:auto_triggered', got {call_args[0][0]}"
        )

    @pytest.mark.asyncio
    async def test_subscribe_routing_decided_channel(self) -> None:
        """subscribe("RoutingDecided") 应订阅 Redis channel "sisys:rt:routing_decided"."""
        router = ChannelRouter()
        mock_publisher = AsyncMock()
        mock_subscriber = MagicMock()

        bus = RedisEventBus(
            publisher=mock_publisher,
            subscriber=mock_subscriber,
            router=router,
        )

        handler = MagicMock()
        await bus.subscribe("RoutingDecided", handler)

        mock_subscriber.subscribe.assert_called_once()
        call_args = mock_subscriber.subscribe.call_args
        assert call_args[0][0] == "sisys:rt:routing_decided"

    @pytest.mark.asyncio
    async def test_subscribe_unknown_event_type_passes_none(self) -> None:
        """未知 event_type 时 get_redis_channel 返回 None，应传递 None 给 subscriber."""
        router = ChannelRouter()
        mock_publisher = AsyncMock()
        mock_subscriber = MagicMock()

        bus = RedisEventBus(
            publisher=mock_publisher,
            subscriber=mock_subscriber,
            router=router,
        )

        handler = MagicMock()
        await bus.subscribe("UnknownEventType", handler)

        mock_subscriber.subscribe.assert_called_once()
        call_args = mock_subscriber.subscribe.call_args
        assert call_args[0][0] is None


# ===================================================================
# P0-30: subscribe_async 方法存在性测试
# ===================================================================


class TestSubscribeAsyncMethodExists:
    """验证 RedisEventSubscriber.subscribe_async() 方法存在且可调用."""

    def test_subscriber_has_subscribe_async_method(self) -> None:
        """RedisEventSubscriber 应有 subscribe_async() 方法."""
        from src.infrastructure.config.redis import RedisConfig

        config = RedisConfig()
        subscriber = RedisEventSubscriber(config)
        assert hasattr(subscriber, "subscribe_async"), "RedisEventSubscriber missing subscribe_async() method"
        assert callable(subscriber.subscribe_async)

    @pytest.mark.asyncio
    async def test_bus_subscribe_async_delegates_correctly(self) -> None:
        """RedisEventBus.subscribe_async() 应正确委托给 subscriber.subscribe_async()."""
        router = ChannelRouter()
        mock_publisher = AsyncMock()
        mock_subscriber = MagicMock()

        # subscribe_async 是同步方法，用 MagicMock 避免 RuntimeWarning
        mock_subscriber.subscribe_async = MagicMock()

        bus = RedisEventBus(
            publisher=mock_publisher,
            subscriber=mock_subscriber,
            router=router,
        )

        handler = MagicMock()
        await bus.subscribe_async("AutoTriggered", handler)

        mock_subscriber.subscribe_async.assert_called_once()
        call_args = mock_subscriber.subscribe_async.call_args
        # 验证频道名解析
        assert call_args[0][0] == "sisys:rt:auto_triggered"


# ===================================================================
# P0-31: DomainEvent 反序列化测试
# ===================================================================


class TestHandlerReceivesDomainEvent:
    """验证 handler 收到 DomainEvent 对象而非 dict."""

    def test_dispatch_message_deserializes_to_domain_event(self) -> None:
        """_dispatch_message 应调用 DomainEvent.from_dict 反序列化."""
        from src.infrastructure.config.redis import RedisConfig

        config = RedisConfig()
        subscriber = RedisEventSubscriber(config)

        received: list[object] = []

        def handler(event: object) -> None:
            received.append(event)

        subscriber.subscribe("sisys:rt:test", handler)

        # 模拟 Redis 消息（使用合法 UUID）
        test_event_id = str(uuid.uuid4())
        subscriber._dispatch_message(
            "sisys:rt:test",
            f'{{"event_id": "{test_event_id}", "event_type": "SampleEvent",'
            f' "timestamp": "2026-01-01T00:00:00", "source": "test"}}',
        )

        assert len(received) == 1
        assert isinstance(received[0], DomainEvent), f"Handler received {type(received[0])}, expected DomainEvent"

    def test_dispatch_message_with_real_event_dict(self) -> None:
        """使用完整事件 dict 测试反序列化."""
        import json

        from src.infrastructure.config.redis import RedisConfig

        config = RedisConfig()
        subscriber = RedisEventSubscriber(config)

        received: list[object] = []

        def handler(event: object) -> None:
            received.append(event)

        subscriber.subscribe("sisys:rt:test", handler)

        event_dict = _make_event_dict()
        json_str = json.dumps(event_dict)
        subscriber._dispatch_message("sisys:rt:test", json_str)

        assert len(received) == 1
        assert isinstance(received[0], DomainEvent)
        assert received[0].event_type == "SampleEvent"


# ===================================================================
# 集成测试：完整订阅流程
# ===================================================================


class TestSubscribeIntegration:
    """端到端验证订阅流程."""

    @pytest.mark.asyncio
    async def test_full_subscribe_flow_with_channel_resolution(self) -> None:
        """完整订阅流程：event_type → channel → handler 注册."""
        router = ChannelRouter()
        mock_publisher = AsyncMock()

        # 使用真实 RedisEventSubscriber（mock Redis 连接）
        from src.infrastructure.config.redis import RedisConfig

        config = RedisConfig()
        real_subscriber = RedisEventSubscriber(config)

        # Mock _get_pool 避免真实 Redis 连接
        with patch.object(
            real_subscriber,
            "_get_pool",
            new_callable=AsyncMock,
        ) as mock_pool:
            mock_pool.return_value = MagicMock()

            bus = RedisEventBus(
                publisher=mock_publisher,
                subscriber=real_subscriber,
                router=router,
            )

            handler = MagicMock()
            await bus.subscribe("AutoTriggered", handler)

            # 验证内部 handler 注册使用正确的 channel 名
            assert "sisys:rt:auto_triggered" in real_subscriber._handlers
