"""基础设施层事件发件箱适配器模块

负责领域事件与发件箱实体之间的双向转换
事件类型注册统一使用 DomainEvent._registry（单一真实来源）

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from src.domain.events.base import DomainEvent
from src.infrastructure.messaging.outbox.outbox import OutboxEntity


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
        # 使用 DomainEvent._registry 验证 event_type（单一真实来源）
        if entity.event_type not in DomainEvent._registry:
            raise ValueError(f"Unknown event_type: {entity.event_type}")
        # 使用 DomainEvent.from_dict 正确处理 event_type
        return DomainEvent.from_dict(entity.payload)
