"""
sisys - Infrastructure Event Bus.

事件总线实现。
"""


class EventBus:
    """简单事件总线占位符。"""

    async def publish(self, event_type: str, payload: dict) -> None:
        """发布事件。"""
        pass

    async def subscribe(self, event_type: str, handler) -> None:
        """订阅事件。"""
        pass

    async def unsubscribe(self, event_type: str, handler) -> None:
        """取消订阅。"""
        pass
