"""ChannelRouter — 通道路由器，决定事件走哪个通道。

这是基础设施层组件，负责将事件类型映射到传输通道。
领域层通过 EventPublisher 接口发布事件，不感知路由细节。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class DeliveryMode(Enum):
    """事件传输通道模式（基础设施层概念）。

    注意：此枚举位于基础设施层，不属于领域层。
    领域层通过事件类型的通道映射推断传输模式。
    """

    # 仅实时通道（Redis Pub/Sub）- 可能丢失，低延迟
    REALTIME = "realtime"

    # 仅可靠通道（RabbitMQ + Outbox）- 保证最终一致
    RELIABLE = "reliable"


@dataclass
class ChannelMapping:
    """事件通道映射配置。"""

    event_type: str
    redis_channel: str | None = None
    rabbitmq_routing_key: str | None = None
    delivery_mode: DeliveryMode = DeliveryMode.RELIABLE
    description: str = ""


class ChannelRouter:
    """通道路由器。

    管理事件类型到通道的映射。
    支持配置驱动和运行时覆盖。
    """

    # 预定义映射（Story 1.3 规范）
    DEFAULT_MAPPINGS: dict[str, ChannelMapping] = {
        "AutoTriggered": ChannelMapping(
            event_type="AutoTriggered",
            redis_channel="sisys:rt:auto_triggered",
            delivery_mode=DeliveryMode.REALTIME,
            description="触发事件，实时通知",
        ),
        "AutoRouted": ChannelMapping(
            event_type="AutoRouted",
            redis_channel="sisys:rt:auto_routed",
            delivery_mode=DeliveryMode.REALTIME,
            description="路由决策完成",
        ),
        "DocumentProcessed": ChannelMapping(
            event_type="DocumentProcessed",
            redis_channel="sisys:rt:document_processed",
            rabbitmq_routing_key="sisys.events.reliable.document_processed",
            delivery_mode=DeliveryMode.RELIABLE,
            description="文档处理完成",
        ),
        "MemoryChanged": ChannelMapping(
            event_type="MemoryChanged",
            rabbitmq_routing_key="sisys.events.reliable.memory_changed",
            delivery_mode=DeliveryMode.RELIABLE,
            description="记忆变更",
        ),
        "CheckpointReached": ChannelMapping(
            event_type="CheckpointReached",
            rabbitmq_routing_key="sisys.events.reliable.checkpoint_reached",
            delivery_mode=DeliveryMode.RELIABLE,
            description="检查点到达",
        ),
        "AuditEvent": ChannelMapping(
            event_type="AuditEvent",
            rabbitmq_routing_key="audit.audit_event",
            delivery_mode=DeliveryMode.RELIABLE,
            description="审计事件",
        ),
    }

    def __init__(self, load_defaults: bool = True) -> None:
        """初始化路由器。

        Args:
            load_defaults: 是否加载默认映射。False 用于测试场景。
        """
        self._mappings: dict[str, ChannelMapping] = {}
        self._overrides: dict[str, DeliveryMode] = {}
        if load_defaults:
            self._init_defaults()

    def _init_defaults(self) -> None:
        """初始化默认映射。"""
        for mapping in self.DEFAULT_MAPPINGS.values():
            self._mappings[mapping.event_type] = mapping

    def get_mapping(self, event_type: str) -> ChannelMapping | None:
        """获取事件通道映射。"""
        return self._mappings.get(event_type)

    def get_delivery_mode(self, event_type: str) -> DeliveryMode:
        """获取事件的传输模式（支持运行时覆盖）。"""
        if mode := self._overrides.get(event_type):
            return mode
        mapping = self._mappings.get(event_type)
        return mapping.delivery_mode if mapping else DeliveryMode.RELIABLE

    def set_override(self, event_type: str, mode: DeliveryMode) -> None:
        """运行时覆盖传输模式。"""
        self._overrides[event_type] = mode
        logger.info("Delivery mode override: %s -> %s", event_type, mode.value)

    def register(self, mapping: ChannelMapping) -> None:
        """注册事件通道映射（运行时配置）。

        Args:
            mapping: 事件通道映射配置
        """
        self._mappings[mapping.event_type] = mapping
        logger.info("Registered channel mapping for: %s", mapping.event_type)

    def get_redis_channel(self, event_type: str) -> str | None:
        """获取 Redis 通道名。"""
        mapping = self._mappings.get(event_type)
        return mapping.redis_channel if mapping else None

    def get_rabbitmq_routing_key(self, event_type: str) -> str | None:
        """获取 RabbitMQ 路由键。"""
        mapping = self._mappings.get(event_type)
        return mapping.rabbitmq_routing_key if mapping else None

    @classmethod
    def create_for_testing(cls) -> ChannelRouter:
        """创建测试用路由器（无默认映射）。"""
        return cls(load_defaults=False)
