"""SISYS 领域层事件发布端口模块。

应用层仅依赖此接口发布事件，不关心底层传输实现。
对标 NServiceBus 的 IBus.Publish 接口。

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.events.base import DomainEvent
from src.domain.events.publish_result import PublishResult


@runtime_checkable
class EventPublisher(Protocol):
    """事件发布抽象端口。

    定义事件发布接口。
    实现类负责：
    1. 通道选择（通过 ChannelRouter 推断）
    2. 序列化（DomainEvent → JSON）
    3. 错误处理（内部消化，返回 PublishResult）
    """

    async def publish(self, event: DomainEvent, channel: str | None = None) -> PublishResult:
        """发布领域事件。

        通道选择由实现类通过 ChannelRouter 推断。

        Args:
            event: 领域事件实例
            channel: 事件发布通道（可选）

        Returns:
            PublishResult: 发布结果的不可变数据类
        """


@runtime_checkable
class InMemoryEventPublisher(Protocol):
    """内存事件发布器协议（P1-07 修复：Protocol 防止直接实例化）。

    基础设施层实现将事件发布到消息总线（RabbitMQ、Redis pub/sub 等）。
    """

    def publish(self, event: DomainEvent) -> None:
        """发布领域事件。

        Args:
            event: 待发布的领域事件

        Raises:
            NotImplementedError: 抽象接口始终抛出
        """
