"""基础设施层事件发件箱适配器模块。

负责领域事件与发件箱实体之间的双向转换，使用显式导入和惰性构建模式
确保事件类型注册表可靠

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

# 显式导入所有事件类，确保 __subclasses__() 能发现它们
from src.domain.events import (  # noqa: F401
    AgentDecided,
    CheckpointReached,
    CheckpointRecovered,
    CorrectionApproved,
    DocumentProcessed,
    HeartbeatTriggered,
    IsolationLevelSwitched,
    RoutingDecided,
    StrategicDeviationWarning,
    ToolExecuted,
)
from src.domain.events.base import DomainEvent
from src.infrastructure.messaging.outbox.outbox import OutboxEntity


class EventRegistry:
    """事件类型注册表 — 显式导入 + 惰性构建

    P0-4 修复要点:
    1. 模块顶层显式导入所有事件类 → 确保 __subclasses__() 能发现它们
    2. 惰性构建: 首次 get() 时扫描，避免导入时序问题
    3. 支持手动注册: 测试 Mock 或自定义事件
    """

    _registry: dict[str, type[DomainEvent]] = {}
    _built: bool = False

    @classmethod
    def register(cls, event_type: str, event_class: type[DomainEvent]) -> None:
        """手动注册事件类型（用于测试 Mock 或自定义事件）。

        Args:
            event_type: 事件类型名称。
            event_class: 事件类。
        """
        if not cls._built:
            cls._build_registry()
        cls._registry[event_type] = event_class

    @classmethod
    def _build_registry(cls) -> None:
        """扫描所有 DomainEvent 子类并构建注册表。"""
        cls._registry = {}
        for subclass in DomainEvent.__subclasses__():
            cls._registry[subclass.__name__] = subclass
            cls._recurse_subclasses(subclass)
        cls._built = True

    @classmethod
    def _recurse_subclasses(cls, parent: type) -> None:
        """递归收集所有子类。

        Args:
            parent: 父类。
        """
        for subclass in parent.__subclasses__():
            cls._registry[subclass.__name__] = subclass
            cls._recurse_subclasses(subclass)

    @classmethod
    def get(cls, event_type: str) -> type[DomainEvent]:
        """根据 event_type 获取事件类。

        Args:
            event_type: 事件类型名称。

        Returns:
            对应的事件类。

        Raises:
            ValueError: 当 event_type 未注册时。
        """
        if not cls._built:
            cls._build_registry()
        event_class = cls._registry.get(event_type)
        if not event_class:
            raise ValueError(f"Unknown event_type: {event_type}")
        return event_class

    @classmethod
    def reset(cls) -> None:
        """重置注册表（仅用于测试隔离）。"""
        cls._registry = {}
        cls._built = False


class EventOutboxAdapter:
    """DomainEvent ↔ OutboxEntity 双向转换器（基础设施层）"""

    @staticmethod
    def from_domain_event(event: DomainEvent) -> OutboxEntity:
        """领域事件转 OutboxEntity

        Args:
            event: 领域事件实例

        Returns:
            对应的 OutboxEntity 实例
        """
        entity = OutboxEntity()
        entity.event_id = event.event_id
        entity.event_type = event.event_type
        entity.payload = event.to_dict()
        entity.status = "pending"
        entity.created_at = event.timestamp
        return entity

    @staticmethod
    def to_domain_event(entity: OutboxEntity) -> DomainEvent:
        """OutboxEntity 转领域事件

        使用 DomainEvent.from_dict() 而非具体子类.from_dict()，
        因为 from_dict 内部使用 target_class(event_type=...) 构造，
        而具体子类的 event_type 是 init=False 字段

        Args:
            entity: OutboxEntity 实例

        Returns:
            对应的领域事件实例

        Raises:
            ValueError: 如果 event_type 未注册
        """
        # 验证 event_type 已注册
        EventRegistry.get(entity.event_type)
        # 使用 DomainEvent.from_dict 正确处理 event_type
        return DomainEvent.from_dict(entity.payload)
