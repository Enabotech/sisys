"""领域层事务发件箱仓储端口模块

使用 DomainEvent 实例，不感知 OutboxEntity
基础设施层负责 DomainEvent 与 OutboxEntity 转换

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from src.domain.events.base import DomainEvent


@runtime_checkable
class OutboxRepository(Protocol):
    """事务发件箱仓储接口（领域层）

    所有方法使用 DomainEvent，基础设施层实现时在内部转换为 OutboxEntity
    保证领域层零 OutboxEntity 污染（方案 A 彻底隔离）
    """

    def save(self, event: DomainEvent) -> None:
        """保存事件至发件箱（与业务操作同事务）

        Args:
            event: 领域事件实例
        """

    def get_unpublished(self, limit: int) -> list[DomainEvent]:
        """获取未发布的事件列表

        Args:
            limit: 最大返回数量

        Returns:
            未发布的领域事件列表（FIFO 排序）
        """

    def mark_published(self, event_id: UUID) -> None:
        """标记事件已发布

        Args:
            event_id: 事件唯一标识
        """

    def mark_failed(self, event_id: UUID, error: str) -> None:
        """标记事件发布失败

        Args:
            event_id: 事件唯一标识
            error: 错误信息
        """
