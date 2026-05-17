"""SISYS 应用层事件订阅端口模块。

对标 NServiceBus 的 IBus.Subscribe 接口。

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from src.domain.events.base import DomainEvent


class EventSubscriber(Protocol):
    """事件订阅抽象端口。

    定义事件订阅接口。
    实现类负责：向消息系统注册订阅、反序列化消息、分发到注册的 handler。
    """

    async def subscribe(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], Any],
    ) -> None:
        """订阅领域事件（同步等待响应）。

        Args:
            event_type: 事件类型。
            handler: 事件处理器。
        """

    async def subscribe_async(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], Awaitable[Any]],
    ) -> None:
        """订阅领域事件（支持异步处理器）。

        Args:
            event_type: 事件类型。
            handler: 异步事件处理器。
        """

    async def start(self) -> None:
        """启动订阅者，开始监听消息。

        应在所有 subscribe() 调用完成后调用。
        """

    async def close(self) -> None:
        """关闭订阅者，释放资源。"""
