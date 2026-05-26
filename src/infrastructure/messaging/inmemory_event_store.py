"""基础设施层内存事件存储模块

基于内存字典和列表实现事件溯源存储，适用于测试和 MVP 阶段，
生产环境应替换为 PostgreSQL 实现
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from uuid import UUID

from src.domain.events.base import DomainEvent
from src.domain.events.event_store import EventStore


class InMemoryEventStore(EventStore):
    """内存事件溯源存储实现

    使用内存字典和列表存储事件，按 aggregate_id 索引以支持高效查询

    Attributes:
        _events_by_aggregate: 聚合 ID 到事件列表的映射
    """

    def __init__(self) -> None:
        """初始化空的事件存储。"""
        self._events_by_aggregate: dict[UUID, list[DomainEvent]] = defaultdict(list)

    def save_events(self, events: Sequence[DomainEvent]) -> None:
        """持久化领域事件列表到内存

        事件按顺序追加到聚合的事件列表中

        Args:
            events: 要持久化的领域事件列表
        """
        for event in events:
            if event.aggregate_id is not None:
                self._events_by_aggregate[event.aggregate_id].append(event)

    def get_events(self, aggregate_id: UUID) -> list[DomainEvent]:
        """获取指定聚合的所有事件

        Args:
            aggregate_id: 聚合根 ID

        Returns:
            该聚合的领域事件列表（按顺序）
        """
        return list(self._events_by_aggregate.get(aggregate_id, []))

    def get_events_by_version(
        self,
        aggregate_id: UUID,
        from_version: int,
        to_version: int,
    ) -> list[DomainEvent]:
        """获取指定聚合在版本范围内的事件

        使用事件在列表中的位置作为版本号（1-based 索引）

        Args:
            aggregate_id: 聚合根 ID
            from_version: 起始版本（含，1-based）
            to_version: 结束版本（含，1-based）

        Returns:
            版本范围内的领域事件列表

        Raises:
            ValueError: 当 from_version > to_version 或版本号为负时
        """
        if from_version < 1 or to_version < 1:
            raise ValueError("Version numbers must be >= 1")
        if from_version > to_version:
            raise ValueError(f"from_version ({from_version}) must be <= to_version ({to_version})")
        all_events = self._events_by_aggregate.get(aggregate_id, [])
        # 将 1-based 版本号转换为 0-based 索引
        start_idx = max(0, from_version - 1)
        end_idx = min(len(all_events), to_version)
        return list(all_events[start_idx:end_idx])

    def clear(self) -> None:
        """清空所有已存储的事件（用于测试）。"""
        self._events_by_aggregate.clear()
