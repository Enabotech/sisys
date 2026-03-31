"""
sisys - Event Bus Tests.

测试基础设施层事件总线。
"""

import pytest

from src.infrastructure.event_bus import EventBus


class TestEventBus:
    """测试事件总线"""

    @pytest.mark.asyncio
    async def test_publish_event(self):
        """Given 事件发布，When 调用 publish，Then 不抛出异常"""
        event_bus = EventBus()
        event_type = "plan.created"
        payload = {"plan_id": "test-123", "creator": "user-1"}

        # 调用不应抛出异常
        await event_bus.publish(event_type, payload)

    @pytest.mark.asyncio
    async def test_subscribe_event(self):
        """Given 事件订阅，When 调用 subscribe，Then 不抛出异常"""
        event_bus = EventBus()
        event_type = "plan.created"

        async def handler(payload: dict) -> None:
            pass

        # 调用不应抛出异常
        await event_bus.subscribe(event_type, handler)

    @pytest.mark.asyncio
    async def test_unsubscribe_event(self):
        """Given 事件取消订阅，When 调用 unsubscribe，Then 不抛出异常"""
        event_bus = EventBus()
        event_type = "plan.created"

        async def handler(payload: dict) -> None:
            pass

        # 调用不应抛出异常
        await event_bus.unsubscribe(event_type, handler)

    @pytest.mark.asyncio
    async def test_publish_with_empty_payload(self):
        """Given 空载荷事件，When 发布，Then 不抛出异常"""
        event_bus = EventBus()
        event_type = "plan.updated"

        await event_bus.publish(event_type, {})

    @pytest.mark.asyncio
    async def test_publish_with_complex_payload(self):
        """Given 复杂载荷事件，When 发布，Then 不抛出异常"""
        event_bus = EventBus()
        event_type = "plan.created"
        payload = {
            "plan_id": "test-123",
            "creator": "user-1",
            "metadata": {
                "nested": {"key": "value"},
                "list": [1, 2, 3],
            },
        }

        await event_bus.publish(event_type, payload)
