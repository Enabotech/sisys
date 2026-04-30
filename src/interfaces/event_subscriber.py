"""EventSubscriber abstract port — hexagonal architecture subscribe interface.

对标 NServiceBus 的 IBus.Subscribe 接口。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from src.domain.events.base import DomainEvent

if TYPE_CHECKING:
    pass


class EventSubscriber(ABC):
    """事件订阅抽象端口。

    定义事件订阅接口。
    实现类负责：
    1. 向消息系统注册订阅
    2. 反序列化消息
    3. 分发到注册的 handler
    """

    @abstractmethod
    async def subscribe(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], Any],
    ) -> None:
        """订阅领域事件（同步等待响应）。

        Args:
            event_type: 事件类型
            handler: 事件处理器
        """
        pass

    @abstractmethod
    async def subscribe_async(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], Awaitable[Any]],
    ) -> None:
        """订阅领域事件（支持异步处理器）。

        Args:
            event_type: 事件类型
            handler: 异步事件处理器
        """
        pass

    @abstractmethod
    async def start(self) -> None:
        """启动订阅者，开始监听消息。

        应在所有 subscribe() 调用完成后调用。
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """关闭订阅者，释放资源。"""
        pass
