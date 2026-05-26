"""领域层 事件存储接口模块

定义于领域层，由基础设施层实现
为事件溯源提供持久化抽象
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from .base import DomainEvent


@runtime_checkable
class EventStore(Protocol):
    """事件溯源的抽象事件存储接口

    基础设施层的实现负责持久化和检索按聚合根组织的事件流
    """

    def save_events(self, events: list[DomainEvent]) -> None:
        """持久化领域事件列表

        Args:
            events: 要持久化的领域事件列表
        """

    def get_events(self, aggregate_id: UUID) -> list[DomainEvent]:
        """检索指定聚合的所有事件

        Args:
            aggregate_id: 聚合根ID

        Returns:
            该聚合的领域事件列表，按顺序排列
        """

    def get_events_by_version(
        self,
        aggregate_id: UUID,
        from_version: int,
        to_version: int,
    ) -> list[DomainEvent]:
        """检索指定聚合在版本范围内的事件

        Args:
            aggregate_id: 聚合根ID
            from_version: 起始版本号（包含）
            to_version: 结束版本号（包含）

        Returns:
            版本范围内的领域事件列表
        """
