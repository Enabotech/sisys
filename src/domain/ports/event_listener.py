"""领域层事件监听器端口模块

定义同步和异步事件监听器 Protocol，由基础设施层实现

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from src.domain.events.base import DomainEvent


@runtime_checkable
class EventListener(Protocol):
    """抽象事件监听器接口

    订阅者为特定事件类型注册处理器，事件发布时接收通知
    """

    def on_event(self, event_type: str, handler: Callable[[DomainEvent], None]) -> None: ...

    def dispatch(self, event: DomainEvent) -> None: ...


@runtime_checkable
class EventListenerAsync(Protocol):
    """抽象异步事件监听器接口

    用于异步事件消费场景（RabbitMQEventListener 实现）
    与同步 EventListener 接口独立，不继承以避免强制实现同步方法
    """

    async def async_handle(self, event: DomainEvent) -> None: ...
