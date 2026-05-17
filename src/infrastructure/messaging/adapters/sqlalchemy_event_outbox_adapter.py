"""SQLAlchemyEventOutboxAdapter — DomainEvent ↔ OutboxModel 转换器

新建适配器，直接输出 OutboxModel（SQLAlchemy 模型），
避免在 OutboxEntity dataclass 和 OutboxModel 之间反复转换
"""

from __future__ import annotations

from src.domain.events.base import DomainEvent
from src.infrastructure.messaging.adapters.event_outbox_adapter import EventRegistry
from src.infrastructure.storage.postgresql.models import OutboxModel


class SQLAlchemyEventOutboxAdapter:
    """DomainEvent ↔ OutboxModel 双向转换器（基础设施层）"""

    @staticmethod
    def from_domain_event(event: DomainEvent) -> OutboxModel:
        """领域事件转 OutboxModel

        Args:
            event: 领域事件实例

        Returns:
            对应的 OutboxModel 实例
        """
        model = OutboxModel(
            event_id=event.event_id,
            event_type=event.event_type,
            payload=event.to_dict(),
            created_at=event.timestamp,
        )
        model.status = "pending"
        return model

    @staticmethod
    def to_domain_event(model: OutboxModel) -> DomainEvent:
        """OutboxModel 转领域事件

        使用 EventRegistry 按 event_type 路由到正确的领域事件子类

        Args:
            model: OutboxModel 实例

        Returns:
            对应的领域事件实例

        Raises:
            ValueError: 如果 event_type 未注册
        """
        # Validate event_type is known
        EventRegistry.get(model.event_type)
        # Use DomainEvent.from_dict which handles event_type correctly
        return DomainEvent.from_dict(model.payload)
