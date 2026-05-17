"""EventBusFactory — dependency injection for event buses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.infrastructure.config.rabbitmq import RabbitMQConfig
from src.infrastructure.config.redis import RedisConfig
from src.infrastructure.messaging.channel_router import ChannelRouter
from src.infrastructure.messaging.dual_channel_event_bus import DualChannelEventBus
from src.infrastructure.messaging.outbox.outbox_processor import AsyncOutboxPoller
from src.infrastructure.messaging.rabbitmq_event_bus import RabbitMQEventBus
from src.infrastructure.messaging.redis_event_bus import RedisEventBus


@dataclass
class EventBusConfig:
    """Configuration for event bus components."""

    redis_url: str | None = None
    rabbitmq_url: str | None = None
    outbox_repository: Any = None
    poll_interval: float = 1.0
    batch_size: int = 10
    _redis_config: RedisConfig | None = field(default=None, repr=False)
    _rabbitmq_config: RabbitMQConfig | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Create RedisConfig and RabbitMQConfig from URLs."""
        if self._redis_config is None and self.redis_url:
            object.__setattr__(self, "_redis_config", RedisConfig(host=self.redis_url))
        if self._rabbitmq_config is None and self.rabbitmq_url:
            object.__setattr__(self, "_rabbitmq_config", RabbitMQConfig(host=self.rabbitmq_url))


class EventBusFactory:
    """事件总线工厂

    负责创建和管理事件总线实例，实现依赖注入
    共享组件（ChannelRouter, Redis Publisher, RabbitMQ Publisher）复用

    使用方式:
        1. 创建工厂实例（可注入配置）
        2. 调用 create_dual_channel_bus() 获取已配置的实例
        3. 或使用 configure_event_bus() 设置全局单例
    """

    _instance: DualChannelEventBus | None = None
    _poller: AsyncOutboxPoller | None = None

    def __init__(self, config: EventBusConfig | None = None) -> None:
        """初始化工厂，创建共享组件

        Args:
            config: 事件总线配置，如果为 None 则使用默认配置
        """
        self._config = config or EventBusConfig()
        self._router = ChannelRouter()
        self._redis_publisher: Any = None
        self._redis_subscriber: Any = None
        self._rabbitmq_publisher: Any = None
        self._initialized = False

    def _initialize_components(self) -> None:
        """延迟初始化消息组件

        只有当配置提供了必要的连接信息时才初始化
        """
        if self._initialized:
            return

        # Initialize Redis publisher/subscriber if config provided
        if self._config.redis_url:
            self._redis_publisher = self._create_redis_publisher()
            self._redis_subscriber = self._create_redis_subscriber()

        # Initialize RabbitMQ publisher if config provided
        if self._config.rabbitmq_url:
            self._rabbitmq_publisher = self._create_rabbitmq_publisher()

        self._initialized = True

    def _create_redis_publisher(self) -> Any:
        """Create Redis publisher instance."""
        from src.infrastructure.messaging.redis_publisher import RedisEventPublisher

        if self._config._redis_config is None:
            return None
        return RedisEventPublisher(config=self._config._redis_config)

    def _create_redis_subscriber(self) -> Any:
        """Create Redis subscriber instance."""
        from src.infrastructure.messaging.redis_subscriber import RedisEventSubscriber

        if self._config._redis_config is None:
            return None
        return RedisEventSubscriber(config=self._config._redis_config)

    def _create_rabbitmq_publisher(self) -> Any:
        """Create RabbitMQ publisher instance."""
        from src.infrastructure.messaging.rabbitmq_publisher import RabbitMQPublisher

        if self._config._rabbitmq_config is None:
            return None
        return RabbitMQPublisher(config=self._config._rabbitmq_config)

    def create_redis_bus(self) -> RedisEventBus:
        """创建 RedisEventBus 实例

        Returns:
            RedisEventBus: Redis 实时通道事件总线
        """
        self._initialize_components()
        return RedisEventBus(
            publisher=self._redis_publisher,
            subscriber=self._redis_subscriber,
            router=self._router,
        )

    def create_rabbitmq_bus(self) -> RabbitMQEventBus:
        """创建 RabbitMQEventBus 实例

        Returns:
            RabbitMQEventBus: RabbitMQ 可靠通道事件总线
        """
        self._initialize_components()
        return RabbitMQEventBus(
            outbox_repository=self._config.outbox_repository,
            router=self._router,
        )

    def create_dual_channel_bus(self) -> tuple[DualChannelEventBus, AsyncOutboxPoller]:
        """创建 DualChannelEventBus 和 AsyncOutboxPoller.

        Returns:
            tuple: (DualChannelEventBus, AsyncOutboxPoller)
        """
        self._initialize_components()

        redis_bus = self.create_redis_bus()
        rabbitmq_bus = RabbitMQEventBus(
            outbox_repository=self._config.outbox_repository,
            router=self._router,
        )
        bus = DualChannelEventBus(
            redis_bus=redis_bus,
            rabbitmq_bus=rabbitmq_bus,
            router=self._router,
        )

        # Create poller with proper validation
        poller = AsyncOutboxPoller(
            outbox_repository=self._config.outbox_repository,
            publisher=self._rabbitmq_publisher,
            poll_interval=self._config.poll_interval,
            batch_size=self._config.batch_size,
        )

        return bus, poller

    @classmethod
    def configure_event_bus(cls, bus: DualChannelEventBus, poller: AsyncOutboxPoller) -> None:
        """配置全局事件总线实例

        Args:
            bus: DualChannelEventBus 实例
            poller: AsyncOutboxPoller 实例
        """
        cls._instance = bus
        cls._poller = poller

    @classmethod
    def get_event_bus(cls) -> DualChannelEventBus:
        """获取全局事件总线实例

        Returns:
            DualChannelEventBus: 已配置的事件总线

        Raises:
            RuntimeError: 当事件总线未配置时
        """
        if cls._instance is None:
            raise RuntimeError("EventBus not configured. Call configure_event_bus first.")
        return cls._instance

    @classmethod
    def get_poller(cls) -> AsyncOutboxPoller | None:
        """获取全局事件轮询器实例

        Returns:
            AsyncOutboxPoller: 已配置的轮询器，如果未配置则返回 None
        """
        return cls._poller

    @property
    def redis_publisher(self) -> Any:
        """获取 Redis 发布器（延迟初始化后）。"""
        self._initialize_components()
        return self._redis_publisher

    @property
    def redis_subscriber(self) -> Any:
        """获取 Redis 订阅器（延迟初始化后）。"""
        self._initialize_components()
        return self._redis_subscriber

    @property
    def rabbitmq_publisher(self) -> Any:
        """获取 RabbitMQ 发布器（延迟初始化后）。"""
        self._initialize_components()
        return self._rabbitmq_publisher
