"""领域层事件发布端口模块

应用层仅依赖此接口发布事件，不关心底层传输实现
对标 NServiceBus 的 IBus.Publish 接口
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.events.base import DomainEvent
from src.domain.events.publish_result import PublishResult


@runtime_checkable
class EventPublisher(Protocol):
    """事件发布抽象端口

    定义事件发布接口
    实现类负责：
    1. 通道选择（通过 ChannelRouter 推断）
    2. 序列化（DomainEvent → JSON）
    3. 错误处理（内部消化，返回 PublishResult）
    """

    async def publish(self, event: DomainEvent) -> PublishResult:
        """发布领域事件

        通道选择由实现类通过 ChannelRouter 推断

        Args:
            event: 领域事件实例

        Returns:
            PublishResult: 发布结果的不可变数据类
        """
