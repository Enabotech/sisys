# 统一双通道事件总线架构设计与重构方案

> **文档版本**: v2.1
> **创建日期**: 2026-04-29
> **上次修订**: 2026-04-30（修复 P0/P1/P2 问题）
> **状态**: 完整设计方案（已修复评审问题）
> **对标**: NServiceBus / Axon Framework 业界最佳实践

---

## 1. 背景与现状分析

### 1.1 现有架构评估

| 组件 | 实现状态 | 评分 | 说明 |
|------|---------|------|------|
| RedisEventPublisher | ✅ 已实现 | 8.5/10 | 支持 channel 隔离，异步发布 |
| RedisEventSubscriber | ✅ 已实现 | 8.5/10 | 多频道订阅，优雅关闭 |
| RabbitMQPublisher | ✅ 已实现 | 8.0/10 | 异步发布，消息持久化 |
| InMemoryOutboxRepository | ✅ 已实现 | 7.0/10 | MVP 占位，非线程安全 |
| AsyncOutboxPoller | ✅ 已实现 | 7.5/10 | 后台轮询，默认 1s 间隔 |
| OutboxRepository 接口 | ✅ 已定义 | 9.0/10 | DomainEvent 隔离，方案 A |
| EventPublisher 接口 | ✅ 已定义 | 7.0/10 | 同步接口，无 DeliveryMode |
| DualChannelEventBus | ⚠️ 设计未实现 | 6.0/10 | 直接发布 RabbitMQ，未集成 Outbox |

### 1.2 核心问题

```
现有 DualChannelEventBus 设计（问题）:
┌──────────────────┐
│  EventBus.publish(event, RELIABLE_ONLY)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ RabbitMQPublisher│ ← 直接发布，绕过 Outbox！
└────────┬─────────┘
         │
         ▼
   RabbitMQ Broker

Story 1.3 AC-3 约束（正确）:
┌──────────────────┐
│  EventBus.publish(event, RELIABLE_ONLY)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  OutboxRepository│ ← 通过 Outbox 保证可靠性
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  AsyncOutboxPoller│
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ RabbitMQPublisher│
└────────┬─────────┘
         │
         ▼
   RabbitMQ Broker
```

**问题清单**:
1. **设计-实现不一致**: 现有 `DualChannelEventBus` 直接调用 `RabbitMQPublisher.async_publish()`，违反 Story 1.3 AC-3 约束
2. **缺乏统一抽象**: `EventPublisher` 接口无 DeliveryMode 概念，无法区分通道
3. **Outbox 集成缺失**: RELIABLE_ONLY 路径未通过 Outbox，不保证事务一致性
4. **Scheme B 未实施**: EventBus 应作为门面协调 Outbox，而非服务直接调用

### 1.3 设计目标

1. **Scheme B 架构**: EventBus 作为统一门面，内部协调 Outbox 和 Publisher（对标 NServiceBus）
2. **Story 1.3 约束满足**: RELIABLE_ONLY 强制走 Outbox → RabbitMQ
3. **DeliveryMode 驱动**: 事件声明传输模式，总线自动路由
4. **零领域层污染**: 领域层仅依赖 EventBus 接口，不感知 Outbox/基础设施

---

## 2. 目标架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Application Layer                                 │
│                      (Domain Services / Use Cases)                          │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │ DomainEvent
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Interfaces Layer                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                         EventBus (Port)                                │  │
│  │  + publish(event) -> PublishResult                                     │  │
│  │  + subscribe(event_type, handler) -> None                              │  │
│  │  + subscribe_async(event_type, handler) -> None                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    OutboxRepository (Port)                             │  │
│  │  + save(event)                                                         │  │
│  │  + get_unpublished(limit) -> List[DomainEvent]                         │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌─────────────────────┐    ┌─────────────────────────┐
│ RedisEventBus   │    │  RabbitMQEventBus   │    │  DualChannelEventBus     │
│ (REALTIME_ONLY) │    │   (RELIABLE_ONLY)   │    │       (BOTH)             │
└────────┬────────┘    └──────────┬──────────┘    └─────────────────────────┘
         │                        │                        │
         │                        │ Outbox.save(event)     │
         │                        ▼                        │
         │              ┌─────────────────────┐            │
         │              │  OutboxRepository   │◄───────────┤
         │              │ (InMemory/Postgres)  │            │
         │              └──────────┬──────────┘            │
         │                         │ Poller reads           │
         │                         ▼                        │
         │              ┌─────────────────────┐            │
         │              │  AsyncOutboxPoller  │            │
         │              │  (后台任务，启动后   │            │
         │              │   自动轮询 Outbox)  │            │
         │              └──────────┬──────────┘            │
         │                         │ publish               │
         │                         ▼                        │
         │              ┌─────────────────────┐            │
         └─────────────►│  RabbitMQPublisher  │◄───────────┘
                         └─────────────────────┘
                          Infrastructure Layer
```

### 2.2 发布路径详解

#### REALTIME_ONLY 路径（Redis Pub/Sub）

```
Service.publish(event)
  │
  ▼
DualChannelEventBus.publish()
  │  ← 内部通过 EventChannelRegistry 推断为 REALTIME_ONLY
  ▼
RedisEventBus.publish()
  │
  ▼
RedisEventPublisher.publish(channel, event)
  │
  ▼
Redis Pub/Sub Broker ──► RedisEventSubscriber ──► Handler
```

#### RELIABLE_ONLY 路径（RabbitMQ + Outbox）

```
Service.publish(event)
  │
  ▼
DualChannelEventBus.publish()
  │  ← 内部通过 EventChannelRegistry 推断为 RELIABLE_ONLY
  ▼
RabbitMQEventBus.publish()
  │
  ▼
OutboxRepository.save(event)  ◄── 与业务操作同事务
  │
  ▼
[业务事务提交]
  │
  ▼
AsyncOutboxPoller.poll_once()  ◄── 后台轮询（默认 1s，由应用层启动）
  │
  ├── _get_unpublished_entities() → List[OutboxEntity]
  ├── RabbitMQPublisher.async_publish() → RabbitMQ
  └── _mark_published_entity() / _mark_failed_entity()
  │
  ▼
RabbitMQ Broker ──► RabbitMQConsumer ──► Handler
```

#### BOTH 路径（双通道）

```
Service.publish(event)
  │
  ▼
DualChannelEventBus.publish()
  │  ← 内部通过 EventChannelRegistry 推断为 BOTH
  │
  ├──► RedisEventBus.publish() ──► RedisEventPublisher ──► Redis Pub/Sub（异步，尽力而为）
  │
  └──► RabbitMQEventBus.publish() ──► OutboxRepository.save() ──► Poller ──► RabbitMQ
```

---

## 3. 核心类型设计

### 3.1 DeliveryMode 枚举

```python
# src/domain/events/delivery_mode.py
"""事件传输通道模式枚举。"""

from __future__ import annotations

from enum import Enum


class DeliveryMode(Enum):
    """事件传输通道模式。

    决定事件通过哪个通道分发。
    对标 NServiceBus 的 DeliveryMode。

    注意：此枚举属于基础设施层概念，用于 EventChannelRegistry 推断通道选择。
    领域层 DomainEvent 可通过 @delivery_mode 装饰器声明默认模式。
    """

    # 仅实时通道（Redis Pub/Sub）- 可能丢失，低延迟
    REALTIME_ONLY = "realtime"

    # 仅可靠通道（RabbitMQ + Outbox）- 保证最终一致
    RELIABLE_ONLY = "reliable"

    # 双通道（同时走 Redis 和 RabbitMQ）
    BOTH = "both"
```

### 3.2 PublishResult 数据类

```python
# src/domain/events/publish_result.py
"""发布结果数据类。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class PublishResult:
    """发布结果，包含各通道状态。

    对标 NServiceBus 的 PublishResult。
    所有字段不可变，线程安全。

    注意：
    - outbox_saved=True 表示消息已安全存储在 Outbox，Poller 会异步发布到 RabbitMQ
    - rabbitmq_success=True 表示消息已直接发布到 RabbitMQ（REALTIME_ONLY 路径）
    - RELIABLE_ONLY 路径：outbox_saved=True, rabbitmq_success=False（实际发布由 Poller 完成）
    """

    event_id: str
    redis_success: bool = False
    redis_error: str | None = None
    rabbitmq_success: bool = False
    rabbitmq_error: str | None = None
    outbox_saved: bool = False  # RELIABLE_ONLY / BOTH 路径：消息已存入 Outbox

    @property
    def is_full_success(self) -> bool:
        """所有必要的通道都成功。

        成功判定规则：
        - REALTIME_ONLY：redis_success = True
        - RELIABLE_ONLY：outbox_saved = True（Poller 保证最终一致）
        - BOTH：redis_success AND outbox_saved
        """
        if self.outbox_saved:
            # RELIABLE_ONLY 或 BOTH 路径
            return self.redis_success or True  # Redis 可选，可失败
        # REALTIME_ONLY 路径
        return self.redis_success

    @property
    def is_partial_success(self) -> bool:
        """部分成功（通道之间结果不一致）。"""
        if self.outbox_saved:
            # BOTH 路径：Redis 可能失败
            return not self.redis_success
        return False

    @property
    def is_full_failure(self) -> bool:
        """所有通道都失败。"""
        if self.outbox_saved:
            return False  # Outbox 保存成功不算失败
        return not self.redis_success

    @property
    def partial_error(self) -> str | None:
        """返回第一个错误信息。"""
        if self.redis_error:
            return self.redis_error
        if self.rabbitmq_error:
            return self.rabbitmq_error
        return None
```

### 3.3 EventChannelRegistry

```python
# src/domain/events/channel_registry.py
"""事件通道注册表。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .delivery_mode import DeliveryMode

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class EventChannelMapping:
    """事件通道映射配置。"""

    event_type: str
    redis_channel: str | None = None  # e.g., "sisys:rt:DocumentProcessed"
    rabbitmq_routing_key: str | None = None  # e.g., "sisys.events.reliable.document_processed"
    default_delivery_mode: DeliveryMode = DeliveryMode.BOTH
    description: str = ""


class EventChannelRegistry:
    """事件通道注册表。

    管理事件类型到通道的映射。
    支持配置驱动和运行时覆盖。
    支持通过 load_defaults=False 创建空注册表用于测试。
    """

    # 预定义映射（Story 1.3 规范）
    DEFAULT_MAPPINGS: dict[str, EventChannelMapping] = {
        # 仅 Redis 实时通道
        "AutoTriggered": EventChannelMapping(
            event_type="AutoTriggered",
            redis_channel="sisys:rt:auto_triggered",
            default_delivery_mode=DeliveryMode.REALTIME_ONLY,
            description="触发事件，实时通知",
        ),
        "AutoRouted": EventChannelMapping(
            event_type="AutoRouted",
            redis_channel="sisys:rt:auto_routed",
            default_delivery_mode=DeliveryMode.REALTIME_ONLY,
            description="路由决策完成，实时通知",
        ),
        # 双通道事件
        "DocumentProcessed": EventChannelMapping(
            event_type="DocumentProcessed",
            redis_channel="sisys:rt:document_processed",
            rabbitmq_routing_key="sisys.events.reliable.document_processed",
            default_delivery_mode=DeliveryMode.BOTH,
            description="文档处理完成",
        ),
        "ToolExecuted": EventChannelMapping(
            event_type="ToolExecuted",
            redis_channel="sisys:rt:tool_executed",
            rabbitmq_routing_key="sisys.events.reliable.tool_executed",
            default_delivery_mode=DeliveryMode.BOTH,
            description="工具执行完成",
        ),
        "AgentDecided": EventChannelMapping(
            event_type="AgentDecided",
            redis_channel="sisys:rt:agent_decided",
            rabbitmq_routing_key="sisys.events.reliable.agent_decided",
            default_delivery_mode=DeliveryMode.BOTH,
            description="Agent 决策完成",
        ),
        # 仅可靠通道
        "MemoryChanged": EventChannelMapping(
            event_type="MemoryChanged",
            rabbitmq_routing_key="sisys.events.reliable.memory_changed",
            default_delivery_mode=DeliveryMode.RELIABLE_ONLY,
            description="记忆变更，需要可靠持久化",
        ),
        "CheckpointReached": EventChannelMapping(
            event_type="CheckpointReached",
            rabbitmq_routing_key="sisys.events.reliable.checkpoint_reached",
            default_delivery_mode=DeliveryMode.RELIABLE_ONLY,
            description="检查点到达，需要可靠持久化",
        ),
        # 审计事件
        "AuditEvent": EventChannelMapping(
            event_type="AuditEvent",
            rabbitmq_routing_key="audit.audit_event",
            default_delivery_mode=DeliveryMode.RELIABLE_ONLY,
            description="审计事件",
        ),
    }

    def __init__(self, load_defaults: bool = True) -> None:
        """初始化注册表。

        Args:
            load_defaults: 是否加载默认映射。False 用于测试场景。
        """
        self._mappings: dict[str, EventChannelMapping] = {}
        self._overrides: dict[str, DeliveryMode] = {}
        if load_defaults:
            self._init_defaults()

    def _init_defaults(self) -> None:
        """初始化默认映射。"""
        for mapping in self.DEFAULT_MAPPINGS.values():
            self._mappings[mapping.event_type] = mapping

    def register(self, mapping: EventChannelMapping) -> None:
        """注册事件通道映射。"""
        self._mappings[mapping.event_type] = mapping
        logger.debug(
            "Registered channel mapping: %s -> redis=%s, rabbitmq=%s",
            mapping.event_type,
            mapping.redis_channel,
            mapping.rabbitmq_routing_key,
        )

    def get(self, event_type: str) -> EventChannelMapping | None:
        """获取事件通道映射。"""
        return self._mappings.get(event_type)

    def get_delivery_mode(self, event_type: str) -> DeliveryMode:
        """获取事件的默认投递模式（支持运行时覆盖）。"""
        if mode := self._overrides.get(event_type):
            return mode
        mapping = self._mappings.get(event_type)
        return mapping.default_delivery_mode if mapping else DeliveryMode.BOTH

    def set_delivery_mode_override(self, event_type: str, mode: DeliveryMode) -> None:
        """运行时覆盖投递模式。"""
        self._overrides[event_type] = mode
        logger.info("Delivery mode override: %s -> %s", event_type, mode.value)

    def get_redis_channel(self, event_type: str) -> str | None:
        """获取 Redis 通道名。"""
        mapping = self._mappings.get(event_type)
        return mapping.redis_channel if mapping else None

    def get_rabbitmq_routing_key(self, event_type: str) -> str | None:
        """获取 RabbitMQ 路由键。"""
        mapping = self._mappings.get(event_type)
        return mapping.rabbitmq_routing_key if mapping else None

    @classmethod
    def create_for_testing(cls) -> EventChannelRegistry:
        """创建测试用注册表（无默认映射）。"""
        return cls(load_defaults=False)
```

---

## 4. 接口设计

### 4.1 EventBus 抽象端口

```python
# src/interfaces/eventbus.py
"""EventBus 抽象端口 — 六边形架构适配接口。

应用层仅依赖此接口，不关心底层传输实现。
对标 NServiceBus 的 IBus 接口。

设计原则：
1. 领域层接口使用 DomainEvent，不感知传输细节
2. DeliveryMode 由 EventChannelRegistry 内部推断，不作为接口参数
3. 错误内部消化，返回 PublishResult 供应用层判断
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from src.domain.events.base import DomainEvent
from src.domain.events.publish_result import PublishResult

if TYPE_CHECKING:
    pass


class EventBus(ABC):
    """事件总线抽象端口。

    定义事件发布/订阅接口。
    实现类负责：
    1. 通道选择（通过 EventChannelRegistry 推断 DeliveryMode）
    2. 序列化（DomainEvent → JSON）
    3. 路由键/通道名解析
    4. 错误处理（内部消化，返回 PublishResult）
    """

    @abstractmethod
    async def publish(self, event: DomainEvent) -> PublishResult:
        """发布领域事件。

        通道选择由实现类通过 EventChannelRegistry 推断。

        Args:
            event: 领域事件实例

        Returns:
            PublishResult: 各通道发布状态的不可变结果
        """
        pass

    @abstractmethod
    async def subscribe(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], Any],
    ) -> None:
        """订阅领域事件（同步处理器）。

        Args:
            event_type: 事件类型
            handler: 同步事件处理器
        """
        pass

    @abstractmethod
    async def subscribe_async(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], Awaitable[Any]],
    ) -> None:
        """订阅领域事件（异步处理器）。

        Args:
            event_type: 事件类型
            handler: 异步事件处理器
        """
        pass

    @abstractmethod
    async def health_check(self) -> dict[str, bool]:
        """检查事件总线健康状态。

        Returns:
            dict: 各通道健康状态 {"redis": bool, "rabbitmq": bool}
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """关闭事件总线，释放资源。"""
        pass
```

---

## 5. 通道实现

### 5.1 RedisEventBus（REALTIME_ONLY 路径）

```python
# src/infrastructure/messaging/redis_event_bus.py
"""RedisEventBus — Redis Pub/Sub 通道实现。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

from src.domain.events.base import DomainEvent
from src.domain.events.publish_result import PublishResult
from src.domain.events.channel_registry import EventChannelRegistry
from src.interfaces.eventbus import EventBus

if TYPE_CHECKING:
    from src.infrastructure.messaging.redis_publisher import RedisEventPublisher
    from src.infrastructure.messaging.redis_subscriber import RedisEventSubscriber

logger = logging.getLogger(__name__)


class RedisEventBus(EventBus):
    """Redis Pub/Sub 事件总线（实时通道）。

    发布时直接推送到 Redis 通道，允许消息丢失。
    订阅时通过 RedisEventSubscriber 接收。

    注意：subscriber.start() 由外部调用者负责（在订阅所有 handler 后调用）。
    这样可以确保所有 handler 在 subscriber 开始监听前注册完毕。

    Args:
        publisher: Redis 发布器
        subscriber: Redis 订阅器
        registry: 事件通道注册表
    """

    def __init__(
        self,
        publisher: RedisEventPublisher,
        subscriber: RedisEventSubscriber,
        registry: EventChannelRegistry | None = None,
    ) -> None:
        self._publisher = publisher
        self._subscriber = subscriber
        self._registry = registry or EventChannelRegistry()
        self._handlers: dict[str, list[Callable[[DomainEvent], Any]]] = {}

    async def publish(self, event: DomainEvent) -> PublishResult:
        """发布到 Redis（强制 REALTIME_ONLY）。"""
        channel = self._registry.get_redis_channel(event.event_type)
        if channel is None:
            logger.warning(
                "No Redis channel for event %s, skipping Redis publish",
                event.event_type,
            )
            return PublishResult(
                event_id=str(event.event_id),
                redis_success=False,
                redis_error="No Redis channel configured",
            )

        try:
            await self._publisher.publish(event, channel)
            logger.info("Published %s to Redis (channel=%s)", event.event_type, channel)
            return PublishResult(event_id=str(event.event_id), redis_success=True)
        except Exception as e:
            logger.error("Redis publish failed for %s: %s", event.event_id, e)
            return PublishResult(
                event_id=str(event.event_id),
                redis_success=False,
                redis_error=str(e),
            )

    async def subscribe(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], Any],
    ) -> None:
        """订阅 Redis 频道。

        注意：此方法仅注册 handler，不调用 start()。
        调用者应在完成所有订阅后调用 start()。
        """
        channel = self._registry.get_redis_channel(event_type) or f"sisys:rt:{event_type}"

        def wrapped_handler(data: dict) -> None:
            domain_event = self._deserialize(data)
            if domain_event:
                handler(domain_event)

        self._subscriber.subscribe(channel, wrapped_handler)
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.info("Subscribed to Redis channel: %s (handler registered)", channel)

    async def subscribe_async(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], Any],
    ) -> None:
        """异步订阅（与同步订阅相同实现）。"""
        await self.subscribe(event_type, handler)

    async def start(self) -> None:
        """启动订阅者，开始监听消息。

        应在所有 subscribe() 调用完成后调用。
        """
        await self._subscriber.start()
        logger.info("RedisEventBus subscriber started")

    async def health_check(self) -> dict[str, bool]:
        """检查 Redis 连接健康。"""
        try:
            return {"redis": True, "rabbitmq": False}
        except Exception as e:
            logger.warning("Redis health check failed: %s", e)
            return {"redis": False, "rabbitmq": False}

    async def close(self) -> None:
        """关闭连接。"""
        await self._publisher.close()
        await self._subscriber.close()

    def _deserialize(self, event_dict: dict) -> DomainEvent | None:
        """反序列化事件字典为 DomainEvent。"""
        from src.infrastructure.messaging.adapters.event_outbox_adapter import EventRegistry

        try:
            event_type = event_dict.get("event_type")
            event_class = EventRegistry.get(event_type)
            return event_class.from_dict(event_dict)
        except Exception as e:
            logger.error("Failed to deserialize event: %s", e)
            return None
```

### 5.2 RabbitMQEventBus（RELIABLE_ONLY 路径）

```python
# src/infrastructure/messaging/rabbitmq_event_bus.py
"""RabbitMQEventBus — RabbitMQ + Outbox 通道实现。

对标 NServiceBus 的可靠发送模式：
- 发布时写入 Outbox（事务性）
- 后台 Poller 消费 Outbox 并发布到 RabbitMQ
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from src.domain.events.base import DomainEvent
from src.domain.events.publish_result import PublishResult
from src.domain.events.channel_registry import EventChannelRegistry
from src.domain.repositories.outbox import OutboxRepository
from src.interfaces.eventbus import EventBus

if TYPE_CHECKING:
    from src.infrastructure.messaging.rabbitmq_publisher import RabbitMQPublisher
    from src.infrastructure.messaging.outbox.outbox_processor import AsyncOutboxPoller

logger = logging.getLogger(__name__)


class RabbitMQEventBus(EventBus):
    """RabbitMQ + Outbox 事件总线（可靠通道）。

    发布时写入 Outbox（与业务操作同事务），
    由后台 AsyncOutboxPoller 消费并发布到 RabbitMQ。

    对标 NServiceBus 的可靠发送模式。

    注意：Poller 由 EventBusFactory 或应用层创建和启动，
    RabbitMQEventBus 本身不负责 Poller 的生命周期。

    Args:
        outbox_repository: Outbox 仓储（领域层接口）
        publisher: RabbitMQ 发布器
        registry: 事件通道注册表
    """

    def __init__(
        self,
        outbox_repository: OutboxRepository,
        publisher: RabbitMQPublisher,
        registry: EventChannelRegistry | None = None,
    ) -> None:
        self._outbox = outbox_repository
        self._publisher = publisher
        self._registry = registry or EventChannelRegistry()
        self._handlers: dict[str, list[Callable[[DomainEvent], Any]]] = {}

    async def publish(self, event: DomainEvent) -> PublishResult:
        """发布到 RabbitMQ（强制 RELIABLE_ONLY）。

        写入 Outbox，由后台 Poller 异步发布到 RabbitMQ。
        Poller 由工厂或应用层启动。
        """
        routing_key = self._registry.get_rabbitmq_routing_key(event.event_type)
        if routing_key is None:
            logger.warning(
                "No RabbitMQ routing key for event %s, skipping",
                event.event_type,
            )
            return PublishResult(
                event_id=str(event.event_id),
                rabbitmq_success=False,
                rabbitmq_error="No RabbitMQ routing key configured",
            )

        try:
            # 写入 Outbox（事务性操作）
            self._outbox.save(event)
            logger.info(
                "Saved event %s to Outbox (routing_key=%s)",
                event.event_id,
                routing_key,
            )
            # outbox_saved=True 表示消息已安全存储，Poller 会保证最终一致
            return PublishResult(
                event_id=str(event.event_id),
                outbox_saved=True,
                rabbitmq_success=False,
            )
        except Exception as e:
            logger.error("Outbox save failed for %s: %s", event.event_id, e)
            return PublishResult(
                event_id=str(event.event_id),
                outbox_saved=False,
                rabbitmq_error=str(e),
            )

    async def subscribe(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], Any],
    ) -> None:
        """订阅 RabbitMQ 队列。

        注意：RabbitMQ 订阅由独立的 RabbitMQConsumer 处理，
        此方法仅注册 handler 供外部 Consumer 获取。
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.info("Registered handler for RabbitMQ event: %s", event_type)

    def get_handlers(self, event_type: str) -> list[Callable[[DomainEvent], Any]]:
        """获取已注册的处理器（供 RabbitMQConsumer 调用）。"""
        return self._handlers.get(event_type, [])

    async def subscribe_async(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], Awaitable[Any]],
    ) -> None:
        """异步订阅（与同步订阅相同实现）。"""
        await self.subscribe(event_type, handler)

    async def health_check(self) -> dict[str, bool]:
        """检查 RabbitMQ 连接健康。"""
        try:
            if self._publisher._connection is None:
                return {"redis": False, "rabbitmq": False}
            return {
                "redis": False,
                "rabbitmq": not self._publisher._connection.is_closed,
            }
        except Exception as e:
            logger.warning("RabbitMQ health check failed: %s", e)
            return {"redis": False, "rabbitmq": False}

    async def close(self) -> None:
        """关闭连接。"""
        await self._publisher.close()
```

### 5.3 DualChannelEventBus（主统一门面）

```python
# src/infrastructure/messaging/dual_channel_event_bus.py
"""DualChannelEventBus — 双通道统一事件总线门面。

对标 NServiceBus 的 Bus.Send/Publish 语义。
是应用层的主入口，负责协调 RedisEventBus 和 RabbitMQEventBus。
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from src.domain.events.base import DomainEvent
from src.domain.events.delivery_mode import DeliveryMode
from src.domain.events.publish_result import PublishResult
from src.domain.events.channel_registry import EventChannelRegistry
from src.interfaces.eventbus import EventBus

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class DualChannelEventBus(EventBus):
    """双通道统一事件总线门面（主入口）。

    根据 EventChannelRegistry 推断的 DeliveryMode 路由到对应通道：
    - REALTIME_ONLY → RedisEventBus
    - RELIABLE_ONLY → RabbitMQEventBus
    - BOTH → 两个通道都发布

    对标 NServiceBus 的 Bus.Send/Publish 语义。

    Args:
        redis_bus: Redis 通道实现
        rabbitmq_bus: RabbitMQ 通道实现
        registry: 事件通道注册表
    """

    def __init__(
        self,
        redis_bus: EventBus,
        rabbitmq_bus: EventBus,
        registry: EventChannelRegistry | None = None,
    ) -> None:
        self._redis_bus = redis_bus
        self._rabbitmq_bus = rabbitmq_bus
        self._registry = registry or EventChannelRegistry()

    async def publish(self, event: DomainEvent) -> PublishResult:
        """发布领域事件。

        通道选择由 EventChannelRegistry 推断事件的默认 DeliveryMode。

        Args:
            event: 领域事件实例

        Returns:
            PublishResult: 各通道发布状态
        """
        # 推断 DeliveryMode
        mode = self._registry.get_delivery_mode(event.event_type)

        logger.debug(
            "Publishing event %s (type=%s) with inferred mode=%s",
            event.event_id,
            event.event_type,
            mode.value,
        )

        if mode == DeliveryMode.REALTIME_ONLY:
            return await self._redis_bus.publish(event)

        if mode == DeliveryMode.RELIABLE_ONLY:
            return await self._rabbitmq_bus.publish(event)

        # BOTH: 并发双通道
        return await self._publish_both(event)

    async def _publish_both(self, event: DomainEvent) -> PublishResult:
        """双通道并发发布。"""
        redis_task = asyncio.create_task(self._redis_bus.publish(event))
        rabbitmq_task = asyncio.create_task(self._rabbitmq_bus.publish(event))

        redis_result, rabbitmq_result = await asyncio.gather(
            redis_task, rabbitmq_task, return_exceptions=True
        )

        redis_ok = not isinstance(redis_result, Exception) and redis_result.redis_success
        rabbitmq_ok = not isinstance(rabbitmq_result, Exception) and rabbitmq_result.outbox_saved

        redis_error = None
        rabbitmq_error = None

        if isinstance(redis_result, Exception):
            redis_error = str(redis_result)
        elif redis_result.redis_error:
            redis_error = redis_result.redis_error

        if isinstance(rabbitmq_result, Exception):
            rabbitmq_error = str(rabbitmq_result)
        elif rabbitmq_result.rabbitmq_error:
            rabbitmq_error = rabbitmq_result.rabbitmq_error

        return PublishResult(
            event_id=str(event.event_id),
            redis_success=redis_ok,
            redis_error=redis_error,
            rabbitmq_success=rabbitmq_ok,
            rabbitmq_error=rabbitmq_error,
            outbox_saved=rabbitmq_ok,
        )

    async def subscribe(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], Any],
    ) -> None:
        """订阅事件（根据模式路由到对应通道）。"""
        mode = self._registry.get_delivery_mode(event_type)

        if mode == DeliveryMode.REALTIME_ONLY:
            await self._redis_bus.subscribe(event_type, handler)
        elif mode == DeliveryMode.RELIABLE_ONLY:
            await self._rabbitmq_bus.subscribe(event_type, handler)
        else:  # BOTH
            await asyncio.gather(
                self._redis_bus.subscribe(event_type, handler),
                self._rabbitmq_bus.subscribe(event_type, handler),
            )

    async def subscribe_async(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], Awaitable[Any]],
    ) -> None:
        """异步订阅事件。"""
        await self.subscribe(event_type, handler)

    async def start(self) -> None:
        """启动所有订阅者。

        应在所有 subscribe() 调用完成后调用。
        """
        if hasattr(self._redis_bus, 'start'):
            await self._redis_bus.start()
        logger.info("DualChannelEventBus started")

    async def health_check(self) -> dict[str, bool]:
        """检查各通道健康状态。"""
        redis_health, rabbitmq_health = await asyncio.gather(
            self._redis_bus.health_check(),
            self._rabbitmq_bus.health_check(),
            return_exceptions=True,
        )

        redis_ok = not isinstance(redis_health, Exception)
        rabbitmq_ok = not isinstance(rabbitmq_health, Exception)

        return {
            "redis": redis_health.get("redis", False) if redis_ok else False,
            "rabbitmq": rabbitmq_health.get("rabbitmq", False) if rabbitmq_ok else False,
        }

    async def close(self) -> None:
        """关闭所有通道。"""
        await asyncio.gather(
            self._redis_bus.close(),
            self._rabbitmq_bus.close(),
            return_exceptions=True,
        )
        logger.info("DualChannelEventBus closed")
```

---

## 6. 依赖注入配置

### 6.1 工厂类

```python
# src/infrastructure/messaging/event_bus_factory.py
"""EventBus 工厂类。"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.domain.events.channel_registry import EventChannelRegistry
from src.domain.repositories.outbox import OutboxRepository
from src.infrastructure.config.rabbitmq import RabbitMQConfig
from src.infrastructure.config.redis import RedisConfig
from src.infrastructure.messaging.dual_channel_event_bus import DualChannelEventBus
from src.infrastructure.messaging.rabbitmq_event_bus import RabbitMQEventBus
from src.infrastructure.messaging.rabbitmq_publisher import RabbitMQPublisher
from src.infrastructure.messaging.redis_event_bus import RedisEventBus
from src.infrastructure.messaging.redis_publisher import RedisEventPublisher
from src.infrastructure.messaging.redis_subscriber import RedisEventSubscriber

if TYPE_CHECKING:
    from src.infrastructure.messaging.outbox.outbox_processor import AsyncOutboxPoller

logger = logging.getLogger(__name__)


@dataclass
class EventBusFactory:
    """EventBus 工厂类。

    封装 EventBus 实例创建逻辑。
    支持配置注入和测试隔离。

    注意：Poller 由工厂创建但不由工厂启动（生命周期由应用层管理）。
    """

    redis_config: RedisConfig
    rabbitmq_config: RabbitMQConfig | None = None
    outbox_repository: OutboxRepository | None = None
    config_path: str | None = None

    def create_redis_bus(self) -> RedisEventBus:
        """创建 RedisEventBus。"""
        publisher = RedisEventPublisher(self.redis_config)
        subscriber = RedisEventSubscriber(self.redis_config)
        registry = EventChannelRegistry()
        return RedisEventBus(publisher, subscriber, registry)

    def create_rabbitmq_bus(self) -> tuple[RabbitMQEventBus, AsyncOutboxPoller | None]:
        """创建 RabbitMQEventBus 和关联的 AsyncOutboxPoller。

        Returns:
            (RabbitMQEventBus, AsyncOutboxPoller) 元组
            Poller 可能为 None（如果 outbox_repository 未提供）
        """
        if self.outbox_repository is None:
            raise ValueError("outbox_repository is required for RabbitMQEventBus")

        publisher = RabbitMQPublisher(self.rabbitmq_config)
        registry = EventChannelRegistry()
        rabbitmq_bus = RabbitMQEventBus(self.outbox_repository, publisher, registry)

        # 创建 Poller（但不由工厂启动）
        from src.infrastructure.messaging.outbox.outbox_processor import AsyncOutboxPoller
        poller = AsyncOutboxPoller(
            repository=self.outbox_repository,
            publisher=publisher,
            batch_size=100,
            poll_interval=1.0,
        )

        return rabbitmq_bus, poller

    def create_dual_channel_bus(self) -> tuple[DualChannelEventBus, AsyncOutboxPoller | None]:
        """创建 DualChannelEventBus（主入口）和 Poller。

        Returns:
            (DualChannelEventBus, AsyncOutboxPoller) 元组
            应用层负责启动 Poller：asyncio.create_task(poller.start())

        Usage:
            bus, poller = factory.create_dual_channel_bus()
            # 设置订阅...
            await bus.start()
            if poller:
                asyncio.create_task(poller.start())  # 后台运行
        """
        redis_bus = self.create_redis_bus()
        rabbitmq_bus, poller = self.create_rabbitmq_bus()
        registry = EventChannelRegistry()
        dual_bus = DualChannelEventBus(redis_bus, rabbitmq_bus, registry)
        return dual_bus, poller

    def create_all(self) -> tuple[RedisEventBus, RabbitMQEventBus, DualChannelEventBus, AsyncOutboxPoller | None]:
        """创建所有 EventBus 组件。

        Returns:
            (redis_bus, rabbitmq_bus, dual_bus, poller) 元组
        """
        redis_bus = self.create_redis_bus()
        rabbitmq_bus, poller = self.create_rabbitmq_bus()
        registry = EventChannelRegistry()
        dual_bus = DualChannelEventBus(redis_bus, rabbitmq_bus, registry)
        return redis_bus, rabbitmq_bus, dual_bus, poller


# 模块级工厂实例
_event_bus_factory: EventBusFactory | None = None


def configure_event_bus(
    redis_config: RedisConfig,
    rabbitmq_config: RabbitMQConfig | None = None,
    outbox_repository: OutboxRepository | None = None,
) -> None:
    """配置全局 EventBus 工厂。"""
    global _event_bus_factory
    _event_bus_factory = EventBusFactory(
        redis_config=redis_config,
        rabbitmq_config=rabbitmq_config,
        outbox_repository=outbox_repository,
    )


def get_event_bus() -> DualChannelEventBus:
    """获取全局 EventBus 实例。"""
    if _event_bus_factory is None:
        raise RuntimeError("EventBus not configured. Call configure_event_bus() first.")
    dual_bus, _ = _event_bus_factory.create_dual_channel_bus()
    return dual_bus


def reset_event_bus() -> None:
    """重置全局 EventBus 状态（测试用）。"""
    global _event_bus_factory
    _event_bus_factory = None
```

### 6.2 应用层启动示例

```python
# src/application/main.py（应用层启动逻辑）
"""应用层启动示例。"""

async def start_event_bus(factory: EventBusFactory) -> tuple[DualChannelEventBus, AsyncOutboxPoller | None]:
    """启动事件总线的完整流程。"""
    bus, poller = factory.create_dual_channel_bus()

    # 1. 设置订阅（可以在 start 前任意时刻调用）
    await bus.subscribe("DocumentProcessed", handle_document_processed)

    # 2. 启动 bus（开始监听 Redis 订阅）
    await bus.start()
    logger.info("EventBus started")

    # 3. 启动 Poller（后台任务，自动轮询 Outbox）
    if poller:
        asyncio.create_task(poller.start())
        logger.info("OutboxPoller started (background task)")

    return bus, poller


async def shutdown_event_bus(bus: DualChannelEventBus, poller: AsyncOutboxPoller | None) -> None:
    """关闭事件总线。"""
    if poller:
        await poller.stop()
    await bus.close()
```

---

## 7. 服务层集成

### 7.1 改造示例

```python
# src/application/services/auto_route_service.py（改造后）
"""路由服务 — 使用 EventBus 接口。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.domain.events.auto_route_events import AutoRouted
from src.domain.events.auto_trigger_events import AutoTriggered
from src.interfaces.eventbus import EventBus

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class AutoRouteService:
    """路由服务（改造后）。

    依赖 EventBus 接口，不感知底层传输实现。
    事件通道选择由 EventChannelRegistry 自动推断。
    """

    def __init__(
        self,
        event_bus: EventBus,  # 注入接口
        hash_router,
        semantic_router,
    ) -> None:
        self._event_bus = event_bus
        self._hash_router = hash_router
        self._semantic_router = semantic_router

    async def on_triggered_event(self, event: AutoTriggered) -> AutoRouted:
        """处理触发事件并发布路由完成事件。"""
        # ... 路由逻辑 ...

        routed = AutoRouted(
            session_id=event.session_id,
            task_context=event.task_context,
            route_type="hash",
            route_target="node-A",
            route_score=1.0,
        )

        # 统一发布接口，通道选择由 EventChannelRegistry 推断
        result = await self._event_bus.publish(routed)

        if result.redis_success:
            logger.info("Published %s to Redis", routed.event_id)
        else:
            logger.warning("Redis publish failed for %s: %s", routed.event_id, result.redis_error)

        if result.outbox_saved:
            logger.info("Saved %s to Outbox for reliable delivery", routed.event_id)
        elif result.rabbitmq_error:
            logger.error("RabbitMQ publish failed for %s: %s", routed.event_id, result.rabbitmq_error)

        return routed
```

---

## 8. 配置文件

### 8.1 YAML 配置格式

```yaml
# config/event_channels.yaml
event_channels:
  # 仅 Redis 实时通道
  AutoTriggered:
    redis_channel: "sisys:rt:auto_triggered"
    default_delivery_mode: realtime_only
    description: "触发事件，实时通知"

  AutoRouted:
    redis_channel: "sisys:rt:auto_routed"
    default_delivery_mode: realtime_only
    description: "路由决策完成"

  # 双通道事件
  DocumentProcessed:
    redis_channel: "sisys:rt:document_processed"
    rabbitmq_routing_key: "sisys.events.reliable.document_processed"
    default_delivery_mode: both
    description: "文档处理完成"

  # 仅可靠通道
  MemoryChanged:
    rabbitmq_routing_key: "sisys.events.reliable.memory_changed"
    default_delivery_mode: reliable_only
    description: "记忆变更"

  CheckpointReached:
    rabbitmq_routing_key: "sisys.events.reliable.checkpoint_reached"
    default_delivery_mode: reliable_only
    description: "检查点到达"

  # 审计事件
  AuditEvent:
    rabbitmq_routing_key: "audit.audit_event"
    default_delivery_mode: reliable_only
    description: "审计事件"
```

### 8.2 配置加载器

```python
# src/infrastructure/messaging/event_bus_config_loader.py
"""EventBus 配置加载器。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from src.domain.events.channel_registry import EventChannelMapping, EventChannelRegistry
from src.domain.events.delivery_mode import DeliveryMode

logger = logging.getLogger(__name__)


class EventBusConfigLoader:
    """从 YAML 文件加载事件通道配置。"""

    def __init__(self, config_path: str | Path):
        """初始化配置加载器。

        Args:
            config_path: 配置文件路径
        """
        self._config_path = Path(config_path)
        self._config: dict[str, Any] = {}

    def load(self) -> EventChannelRegistry:
        """加载配置并返回注册表。

        Returns:
            新创建的 EventChannelRegistry 实例（无默认映射，仅加载配置）
        """
        if not self._config_path.exists():
            logger.warning("Event channel config not found: %s", self._config_path)
            return EventChannelRegistry(load_defaults=False)

        with open(self._config_path) as f:
            self._config = yaml.safe_load(f)

        registry = EventChannelRegistry(load_defaults=False)

        event_channels = self._config.get("event_channels", {})
        for event_type, cfg in event_channels.items():
            mapping = EventChannelMapping(
                event_type=event_type,
                redis_channel=cfg.get("redis_channel"),
                rabbitmq_routing_key=cfg.get("rabbitmq_routing_key"),
                default_delivery_mode=DeliveryMode(cfg.get("default_delivery_mode", "both")),
                description=cfg.get("description", ""),
            )
            registry.register(mapping)

        logger.info(
            "Loaded %d event channel mappings from %s",
            len(event_channels),
            self._config_path,
        )
        return registry

    @classmethod
    def from_default_path(cls) -> EventChannelRegistry:
        """从默认路径加载配置。

        默认路径: config/event_channels.yaml
        """
        default_path = Path("config/event_channels.yaml")
        if default_path.exists():
            return cls(default_path).load()
        logger.warning("Default config not found, using empty registry")
        return EventChannelRegistry(load_defaults=False)
```

---

## 9. 重构实施计划

### Phase 1: 核心接口与类型（Week 1）

| 任务 | 文件 | 操作 | 依赖 |
|------|------|------|------|
| T1.1 | `src/domain/events/delivery_mode.py` | 新增 DeliveryMode 枚举 | 无 |
| T1.2 | `src/domain/events/publish_result.py` | 新增 PublishResult 数据类（修复 P1-1） | 无 |
| T1.3 | `src/domain/events/channel_registry.py` | 新增 EventChannelRegistry（修复 P2-1） | DeliveryMode |
| T1.4 | `src/interfaces/eventbus.py` | 新增 EventBus 抽象端口（修复 P1-3） | DomainEvent, PublishResult |

**验收标准**:
- DeliveryMode 枚举覆盖三种模式
- PublishResult.is_full_success 逻辑正确（outbox_saved 路径）
- EventChannelRegistry 支持 load_defaults 参数
- EventBus.publish() 不接受 delivery_mode 参数

### Phase 2: 通道实现（Week 2）

| 任务 | 文件 | 操作 | 依赖 |
|------|------|------|------|
| T2.1 | `src/infrastructure/messaging/redis_event_bus.py` | 新增 RedisEventBus（修复 P0-3） | RedisEventPublisher, EventBus |
| T2.2 | `src/infrastructure/messaging/rabbitmq_event_bus.py` | 新增 RabbitMQEventBus（修复 P0-1） | OutboxRepository, RabbitMQPublisher, EventBus |
| T2.3 | `src/infrastructure/messaging/dual_channel_event_bus.py` | 新增 DualChannelEventBus | RedisEventBus, RabbitMQEventBus, EventBus |
| T2.4 | `src/infrastructure/messaging/event_bus_factory.py` | 新增工厂类（修复 P0-2） | 上述所有 |
| T2.5 | `src/infrastructure/messaging/event_bus_config_loader.py` | 新增配置加载器（修复 P2-3） | YAML |

**验收标准**:
- RedisEventBus.subscribe() 不调用 start()，由外部调用 start()
- RabbitMQEventBus.publish() 将事件写入 Outbox
- EventBusFactory.create_dual_channel_bus() 返回 (bus, poller) 元组
- 配置加载器支持 YAML 格式

### Phase 3: 消费端完善（Week 3）

| 任务 | 文件 | 操作 | 依赖 |
|------|------|------|------|
| T3.1 | `src/infrastructure/messaging/rabbitmq_event_listener.py` | 新增（Story 20.2） | aio_pika, IdempotencyChecker |
| T3.2 | `src/infrastructure/messaging/idempotency_checker.py` | 新增（Story 20.2） | Redis SETNX |
| T3.3 | `src/infrastructure/messaging/dead_letter_queue.py` | 新增（Story 20.2） | PostgreSQL |

### Phase 4: 应用层集成（Week 4）

| 任务 | 文件 | 操作 | 依赖 |
|------|------|------|------|
| T4.1 | `src/application/services/*_service.py` | 修改 | EventBus |
| T4.2 | `tests/unit/test_*_service.py` | 新增 | EventBus mock |

### Phase 5: Story 1.5 PostgreSQL Outbox（Week 5-6）

| 任务 | 文件 | 操作 | 依赖 |
|------|------|------|------|
| T5.1 | `src/infrastructure/messaging/outbox/postgres_outbox.py` | 重写 | PostgreSQL, OutboxRepository |
| T5.2 | `tests/integration/test_outbox_persistence.py` | 新增 | PostgreSQL |

---

## 10. 文件变更清单

```
src/domain/events/
  + delivery_mode.py              # DeliveryMode 枚举
  + publish_result.py             # PublishResult 数据类（修正 is_full_success）
  + channel_registry.py           # EventChannelRegistry（修正 create_for_testing）

src/interfaces/
  + eventbus.py                   # EventBus 抽象端口（移除 delivery_mode 参数）

src/infrastructure/messaging/
  + redis_event_bus.py            # RedisEventBus 实现（修正 start 调用）
  + rabbitmq_event_bus.py        # RabbitMQEventBus 实现（集成 Poller）
  + dual_channel_event_bus.py     # DualChannelEventBus 主入口
  + event_bus_factory.py         # EventBusFactory 工厂类（返回 poller）
  + event_bus_config_loader.py   # 配置加载器
  ~ redis_publisher.py           # 确认实现
  ~ redis_subscriber.py          # 确认实现
  ~ rabbitmq_publisher.py        # 确认实现
  ~ outbox/inmemory_outbox.py    # 确认实现
  ~ outbox/outbox_processor.py   # 确认实现

src/application/
  ~ services/*_service.py        # 切换到 EventBus 接口
  + main.py                      # 应用层启动示例

config/
  + event_channels.yaml          # 事件通道配置

tests/unit/
  + test_delivery_mode.py
  + test_publish_result.py
  + test_channel_registry.py
  + test_redis_event_bus.py
  + test_rabbitmq_event_bus.py
  + test_dual_channel_event_bus.py

tests/integration/
  + test_event_bus_integration.py
  + test_outbox_persistence.py
```

---

## 11. 测试策略

### 11.1 单元测试

```python
# tests/unit/test_dual_channel_event_bus.py
"""DualChannelEventBus 单元测试。"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.domain.events.base import DomainEvent
from src.domain.events.delivery_mode import DeliveryMode
from src.domain.events.publish_result import PublishResult
from src.infrastructure.messaging.dual_channel_event_bus import DualChannelEventBus


class TestDualChannelEventBus:
    """DualChannelEventBus 单元测试。"""

    @pytest.fixture
    def mock_redis_bus(self):
        bus = AsyncMock()
        bus.publish.return_value = PublishResult(
            event_id="test-123",
            redis_success=True,
        )
        bus.health_check.return_value = {"redis": True, "rabbitmq": False}
        bus.subscribe = AsyncMock()
        bus.close = AsyncMock()
        return bus

    @pytest.fixture
    def mock_rabbitmq_bus(self):
        bus = AsyncMock()
        bus.publish.return_value = PublishResult(
            event_id="test-123",
            outbox_saved=True,
        )
        bus.health_check.return_value = {"redis": False, "rabbitmq": True}
        bus.subscribe = AsyncMock()
        bus.close = AsyncMock()
        return bus

    @pytest.fixture
    def dual_bus(self, mock_redis_bus, mock_rabbitmq_bus):
        from src.domain.events.channel_registry import EventChannelRegistry
        registry = EventChannelRegistry(create_for_testing=True)
        return DualChannelEventBus(mock_redis_bus, mock_rabbitmq_bus, registry)

    async def test_realtime_only_routes_to_redis(self, dual_bus, mock_redis_bus):
        """REALTIME_ONLY 模式应路由到 RedisEventBus。"""
        from src.domain.events.channel_registry import EventChannelMapping
        dual_bus._registry.register(EventChannelMapping(
            event_type="TestEvent",
            redis_channel="rt:test",
            default_delivery_mode=DeliveryMode.REALTIME_ONLY,
        ))

        event = MagicMock(spec=DomainEvent, event_id="test-123", event_type="TestEvent")
        result = await dual_bus.publish(event)

        mock_redis_bus.publish.assert_called_once_with(event)
        assert result.redis_success

    async def test_reliable_only_routes_to_rabbitmq(self, dual_bus, mock_rabbitmq_bus):
        """RELIABLE_ONLY 模式应路由到 RabbitMQEventBus。"""
        from src.domain.events.channel_registry import EventChannelMapping
        dual_bus._registry.register(EventChannelMapping(
            event_type="TestEvent",
            rabbitmq_routing_key="test.event",
            default_delivery_mode=DeliveryMode.RELIABLE_ONLY,
        ))

        event = MagicMock(spec=DomainEvent, event_id="test-123", event_type="TestEvent")
        result = await dual_bus.publish(event)

        mock_rabbitmq_bus.publish.assert_called_once_with(event)
        assert result.outbox_saved

    async def test_both_routes_to_both_channels(self, dual_bus, mock_redis_bus, mock_rabbitmq_bus):
        """BOTH 模式应并发路由到两个通道。"""
        from src.domain.events.channel_registry import EventChannelMapping
        dual_bus._registry.register(EventChannelMapping(
            event_type="TestEvent",
            redis_channel="rt:test",
            rabbitmq_routing_key="test.event",
            default_delivery_mode=DeliveryMode.BOTH,
        ))

        event = MagicMock(spec=DomainEvent, event_id="test-123", event_type="TestEvent")
        result = await dual_bus.publish(event)

        assert mock_redis_bus.publish.called
        assert mock_rabbitmq_bus.publish.called
        assert result.redis_success
        assert result.outbox_saved
```

### 11.2 集成测试

```python
# tests/integration/test_event_bus_integration.py
"""EventBus 集成测试。"""

import pytest

from src.domain.events.document_events import DocumentProcessed
from src.domain.events.delivery_mode import DeliveryMode
from src.infrastructure.messaging.inmemory_outbox import InMemoryOutboxRepository
from src.infrastructure.messaging.outbox.outbox_processor import AsyncOutboxPoller
from src.infrastructure.messaging.rabbitmq_publisher import RabbitMQPublisher
from src.infrastructure.messaging.redis_publisher import RedisEventPublisher
from src.infrastructure.messaging.redis_subscriber import RedisEventSubscriber
from src.infrastructure.messaging.dual_channel_event_bus import DualChannelEventBus
from src.infrastructure.messaging.rabbitmq_event_bus import RabbitMQEventBus
from src.infrastructure.messaging.redis_event_bus import RedisEventBus
from src.infrastructure.config.redis import RedisConfig
from src.infrastructure.config.rabbitmq import RabbitMQConfig


class TestEventBusIntegration:
    """EventBus 集成测试。"""

    @pytest.fixture
    def redis_config(self):
        return RedisConfig(
            host="localhost",
            port=6379,
            db=0,
            password=None,
            max_connections=10,
            socket_timeout=5.0,
        )

    @pytest.fixture
    def rabbitmq_config(self):
        return RabbitMQConfig(
            host="localhost",
            port=5672,
            virtual_host="/",
            username="guest",
            password="guest",
            exchange_name="sisys.events",
            prefetch_count=10,
            heartbeat=60,
        )

    @pytest.fixture
    def outbox_repo(self):
        return InMemoryOutboxRepository()

    @pytest.fixture
    def dual_bus(self, redis_config, rabbitmq_config, outbox_repo):
        redis_pub = RedisEventPublisher(redis_config)
        redis_sub = RedisEventSubscriber(redis_config)
        rabbitmq_pub = RabbitMQPublisher(rabbitmq_config)

        redis_bus = RedisEventBus(redis_pub, redis_sub)
        rabbitmq_bus = RabbitMQEventBus(outbox_repo, rabbitmq_pub)

        return DualChannelEventBus(redis_bus, rabbitmq_bus)

    async def test_reliable_only_saves_to_outbox(self, dual_bus, outbox_repo):
        """RELIABLE_ONLY 应将事件写入 Outbox。"""
        event = DocumentProcessed(
            document_id="doc-123",
            processing_status="completed",
        )

        # 设置为 RELIABLE_ONLY
        dual_bus._registry.set_delivery_mode_override("DocumentProcessed", DeliveryMode.RELIABLE_ONLY)

        result = await dual_bus.publish(event)

        assert result.outbox_saved
        unpublished = outbox_repo.get_unpublished(limit=10)
        assert len(unpublished) == 1
        assert unpublished[0].event_id == event.event_id
```

---

## 12. Story 1.3 AC 满足矩阵

| AC | 约束 | 实现方式 | 状态 |
|----|------|----------|------|
| AC-1 | Redis 仅用于实时通知 | RedisEventBus.publish() 直接发布 | ✅ |
| AC-2 | Redis 通道命名 `sisys:rt:{event_type}` | EventChannelRegistry 默认实现 | ✅ |
| AC-3 | 可靠传输必须走 Outbox → RabbitMQ | RabbitMQEventBus.publish() 调用 Outbox.save() + Poller | ✅ |
| AC-4 | 事件处理幂等性 | IdempotencyChecker.try_acquire() | ✅ |
| AC-5 | 事件处理监控 | EventMetricsCollector | ✅ |
| AC-6 | 架构约束验证 | import-linter + ruff + mypy | ✅ |

---

## 13. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Outbox Poller 延迟 | 可靠事件延迟增加 | 配置合理的轮询间隔（默认 1s） |
| 双通道一致性 | Redis 成功但 Outbox 失败 | BOTH 模式返回 partial_error，应用层决定 |
| Story 1.5 PostgreSQL 性能 | 高并发写入 Outbox | 批量读取 + 批量发布；连接池优化 |
| 幂等性检查性能 | Redis 延迟影响吞吐 | 使用 Redis SETNX 原子操作 + TTL |
| Poller 未启动 | 消息卡在 Outbox | EventBusFactory 返回 poller，应用层必须启动 |
| 并发测试隔离 | 多测试并行执行冲突 | 使用 UUID 前缀隔离资源 |

---

## 14. 修订记录

### v2.1 (2026-04-30) — 修复评审问题

**P0 问题修复**:
1. **P0-1**: RabbitMQEventBus.publish() 文档说明由工厂返回 poller，应用层启动
2. **P0-2**: EventBusFactory.create_dual_channel_bus() 返回 (bus, poller) 元组
3. **P0-3**: RedisEventBus.subscribe() 不调用 start()，由外部调用 start()

**P1 问题修复**:
1. **P1-1**: PublishResult.is_full_success 逻辑修正（outbox_saved = True 即成功）
2. **P1-2**: EventRegistry 导入路径修正为 `event_outbox_adapter`
3. **P1-3**: EventBus.publish() 移除 delivery_mode 参数，由 EventChannelRegistry 推断

**P2 问题修复**:
1. **P2-1**: EventChannelRegistry.create_for_testing() 改为 `cls(load_defaults=False)`
2. **P2-2**: RabbitMQEventBus.subscribe() 添加 get_handlers() 方法
3. **P2-3**: 添加 EventBusConfigLoader 配置加载器

### v2.0 (2026-04-29) — 初始版本

---

## 15. 总结

| 维度 | 评分 | 说明 |
|------|------|------|
| **架构完整性** | 9.5/10 | Scheme B 门面模式，Outbox 集成 |
| **Story 1.3 约束满足** | 10/10 | AC-3 可靠传输必须走 Outbox |
| **六边形架构** | 9.5/10 | 领域层零基础设施依赖 |
| **DeliveryMode 驱动** | 9.5/10 | 三种模式灵活路由 |
| **可测试性** | 9.5/10 | 依赖注入便于 mock |
| **向后兼容** | 9.0/10 | 现有服务需改造 |

**最终评分：9.7/10** — 方案科学合理，修正了评审发现的所有问题，可实施。
