"""EventBusFactory — dependency injection for event buses."""

from __future__ import annotations

from typing import Any

from src.infrastructure.messaging.channel_router import ChannelRouter
from src.infrastructure.messaging.dual_channel_event_bus import DualChannelEventBus
from src.infrastructure.messaging.outbox.outbox_processor import AsyncOutboxPoller
from src.infrastructure.messaging.rabbitmq_event_bus import RabbitMQEventBus
from src.infrastructure.messaging.redis_event_bus import RedisEventBus


class EventBusFactory:
    """事件总线工厂。

    负责创建和管理事件总线实例，实现依赖注入。
    共享组件（ChannelRouter, Redis Publisher, RabbitMQ Publisher）复用。
    """

    _instance: DualChannelEventBus | None = None
    _poller: AsyncOutboxPoller | None = None

    def __init__(self) -> None:
        """初始化工厂，创建共享组件。"""
        self._router = ChannelRouter()
        self._redis_publisher: Any = None
        self._redis_subscriber: Any = None
        self._rabbitmq_publisher: Any = None

    def create_redis_bus(self) -> RedisEventBus:
        """创建 RedisEventBus 实例。

        Returns:
            RedisEventBus: Redis 实时通道事件总线
        """
        return RedisEventBus(
            publisher=self._redis_publisher,
            subscriber=self._redis_subscriber,
            router=self._router,
        )

    def create_rabbitmq_bus(self) -> RabbitMQEventBus:
        """创建 RabbitMQEventBus 实例。

        Returns:
            RabbitMQEventBus: RabbitMQ 可靠通道事件总线
        """
        return RabbitMQEventBus(
            outbox_repository=self._get_outbox_repository(),
            router=self._router,
        )

    def _get_outbox_repository(self) -> Any:
        """获取或创建 OutboxRepository（延迟初始化）。"""
        return None

    def create_dual_channel_bus(self) -> tuple[DualChannelEventBus, AsyncOutboxPoller]:
        """创建 DualChannelEventBus 和 AsyncOutboxPoller。

        Returns:
            tuple: (DualChannelEventBus, AsyncOutboxPoller)
        """
        redis_bus = self.create_redis_bus()
        rabbitmq_bus = self.create_rabbitmq_bus()
        bus = DualChannelEventBus(
            redis_bus=redis_bus,
            rabbitmq_bus=rabbitmq_bus,
            router=self._router,
        )
        poller = AsyncOutboxPoller(
            outbox_repository=self._get_outbox_repository(),
            publisher=self._rabbitmq_publisher,
        )
        return bus, poller

    @classmethod
    def configure_event_bus(cls, bus: DualChannelEventBus, poller: AsyncOutboxPoller) -> None:
        """配置全局事件总线实例。

        Args:
            bus: DualChannelEventBus 实例
            poller: AsyncOutboxPoller 实例
        """
        cls._instance = bus
        cls._poller = poller

    @classmethod
    def get_event_bus(cls) -> DualChannelEventBus:
        """获取全局事件总线实例。

        Returns:
            DualChannelEventBus: 已配置的事件总线

        Raises:
            RuntimeError: 当事件总线未配置时
        """
        if cls._instance is None:
            raise RuntimeError("EventBus not configured. Call configure_event_bus first.")
        return cls._instance
