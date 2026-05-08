# Sisys 接口层事件监听器迁移重构计划

**状态**: 待执行
**日期**: 2026-05-04
**架构师**: 宗师级设计审查
**参考文档**: architecture.md §3 (六边形架构), Story 1.14a/1.14b/1.14c/1.15a

---

## 1. 问题诊断

### 1.1 当前架构问题

四个文件混合了**三层职责**，违反六边形架构约束：

| 文件 | 当前行数 | 混合的职责 |
|------|---------|-----------|
| `auto_trigger_listener.py` | 218行 | 线程/队列(infrastructure) + 业务编排(application) + 领域服务调用(domain) |
| `auto_route_listener.py` | 119行 | 事件转换(interfaces) + 业务编排(application) + 领域服务调用(domain) |
| `auto_execute_completed_listener.py` | 126行 | 业务编排(application) + 领域服务调用(domain) |
| `memory_changed_listener.py` | ~100行 | 业务编排(application) + 下游存储操作(infrastructure) |

### 1.2 违反的架构原则

1. **接口层不纯**: `auto_trigger_listener.py` 包含 `threading.Thread`、`queue.Queue` 等基础设施代码
2. **应用层缺失**: 业务编排逻辑散落在接口层
3. **领域层泄露**: 接口层直接调用 `AutoTriggerService`、`AutoRouteService` 等领域服务

### 1.3 六边形架构约束

```
接口层 (Interfaces) → 应用层 (Application) → 领域层 (Domain)
     ↓                    ↓                      ↑
 纸壳适配器              业务编排                核心逻辑
 (纯转换)              (调用领域)              (零依赖)
```

**领域层零依赖原则**
- 领域层（src/domain/）仅使用 Python 标准库
- 禁止导入：包括且不限于 langgraph, prefect, fastapi, pydantic, sqlalchemy, typer, redis, qdrant, minio, neo4j, aio_pika, litellm, instructor, requests, httpx, docker, psycopg2

**四层架构定义**
| 层次 | 目录 | 职责 |
|------|------|------|
| domain | src/domain/ | 核心业务逻辑，零外部依赖 |
| application | src/application/ | 用例编排 |
| interfaces | src/interfaces/ | 适配器 |
| infrastructure | src/infrastructure/ | 技术实现 |

**依赖方向规则**
- 领域层 → 应用/接口/基础设施层：✗ 禁止
- 应用层 → 接口层/基础设施层：✗ 禁止
- 接口层      → 应用层/领域层 ✓ 允许
- 应用层      → 领域层 ✓ 允许
- 基础设施层  → 应用层/领域层 ✓ 允许
- 领域层      → 仅标准库 ✓ 允许

---

## 2. 目标架构

### 2.1 三层分离设计

```
事件总线
    ↓
interfaces/event_listeners/      # 纸壳适配器 (<10行/文件)
    ├── auto_trigger_adapter.py      # 仅：反序列化 → 转换 → 调用 handler
    ├── auto_route_adapter.py
    ├── auto_execute_completed_adapter.py
    └── memory_changed_adapter.py
    ↓
application/event_handlers/       # 业务编排中枢 (新目录)
    ├── auto_trigger_handler.py     # 调用 AutoTriggerService，发布 Triggered 事件
    ├── auto_route_handler.py       # 调用 AutoRouteService，发布 Routed 事件
    ├── auto_execute_completed_handler.py  # 发布下游领域事件
    └── memory_changed_handler.py   # 处理 L1-L5 存储协调
    ↓
domain/services/                 # 核心业务逻辑 (现有)
    ├── auto_trigger_service.py
    ├── auto_route_service.py
    ├── auto_execute_service.py
    └── memory_service.py
```

### 2.2 职责边界

| 层级 | 职责 | 代码量限制 |
|------|------|-----------|
| `interfaces/` | 纸壳适配器，纯格式转换 | <20 行/文件 |
| `application/` | 业务编排，跨聚合协调 | 业务逻辑所在 |
| `domain/` | 核心领域逻辑 | 零外部依赖 |

---

## 3. 文件迁移映射

| 旧路径 | 新路径 (Adapter) | 新路径 (Handler) |
|-------|-----------------|------------------|
| `interfaces/event_listeners/listeners/auto_trigger_listener.py` | `interfaces/event_listeners/auto_trigger_adapter.py` | `application/event_handlers/auto_trigger_handler.py` |
| `interfaces/event_listeners/listeners/auto_route_listener.py` | `interfaces/event_listeners/auto_route_adapter.py` | `application/event_handlers/auto_route_handler.py` |
| `interfaces/event_listeners/listeners/auto_execute_completed_listener.py` | `interfaces/event_listeners/auto_execute_completed_adapter.py` | `application/event_handlers/auto_execute_completed_handler.py` |
| `interfaces/event_listeners/listeners/memory_changed_listener.py` | `interfaces/event_listeners/memory_changed_adapter.py` | `application/event_handlers/memory_changed_handler.py` |

---

## 4. 详细执行步骤

### Phase 1: 创建应用层事件处理目录

**Step 1.1: 创建目录结构**

```bash
mkdir -p src/application/event_handlers
```

**Step 1.2: 创建 `__init__.py`**

```python
# src/application/event_handlers/__init__.py
"""Event handlers - business orchestration layer.

This layer sits between interfaces (adapters) and domain (services).
Handlers receive domain events from adapters, orchestrate business logic
by calling domain services, and coordinate next actions.

Architecture:
    interfaces/ → adapters (thin, <20 lines)
    application/ → handlers (orchestration)
    domain/ → services (core logic)

Migration (2026-05):
    - Old listeners/ split into adapter + handler pairs
    - Adapters live in interfaces/ (thin)
    - Handlers live in application/ (orchestration)
"""

from .auto_trigger_handler import AutoTriggerHandler
from .auto_route_handler import AutoRouteHandler
from .auto_execute_completed_handler import AutoExecuteCompletedHandler
from .memory_changed_handler import MemoryChangedHandler

__all__ = [
    "AutoTriggerHandler",
    "AutoRouteHandler",
    "AutoExecuteCompletedHandler",
    "MemoryChangedHandler",
]
```

---

### Phase 2: 实现 AutoTriggerHandler

**Step 2.1: 创建 `auto_trigger_handler.py`**

```python
# src/application/event_handlers/auto_trigger_handler.py
"""AutoTriggerHandler — business orchestration for trigger mechanism.

Receives domain events from AutoTriggerAdapter, coordinates with
AutoTriggerService (domain), and publishes AutoTriggered events.

This handler implements the orchestration logic:
    1. Receive domain event from adapter
    2. Call domain service (AutoTriggerService)
    3. Publish output event via EventPublisher

Reference: Story 1.14a
"""

from __future__ import annotations

import logging
from typing import Protocol

from src.domain.events.auto_trigger_events import AutoTriggered
from src.domain.events.base import DomainEvent
from src.domain.events.heartbeat_events import HeartbeatTriggered
from src.domain.services.auto_trigger_service import AutoTriggerService

logger = logging.getLogger(__name__)


class EventPublisherProtocol(Protocol):
    """Protocol for event publishing (implemented by infrastructure)."""

    async def publish(self, event: DomainEvent, channel: str | None = None) -> None: ...


class AutoTriggerHandler:
    """Handler for trigger mechanism business orchestration.

    Responsible for:
    - Receiving domain events from AutoTriggerAdapter
    - Delegating to AutoTriggerService for context extraction
    - Publishing AutoTriggered events to downstream route stage

    This is application layer orchestration - NOT domain logic.
    Domain logic lives in AutoTriggerService.
    """

    def __init__(
        self,
        auto_trigger_service: AutoTriggerService,
        publisher: EventPublisherProtocol | None = None,
    ) -> None:
        """Initialize AutoTriggerHandler.

        Args:
            auto_trigger_service: Domain service for trigger processing.
            publisher: Event publisher port for downstream events.
        """
        self._auto_trigger_service = auto_trigger_service
        self._publisher = publisher

    async def handle(self, event: DomainEvent, event_type: str) -> AutoTriggered | None:
        """Handle domain event: extract context and publish AutoTriggered.

        Args:
            event: Domain event from event bus.
            event_type: Event type string for routing.

        Returns:
            AutoTriggered event if processing succeeded, None otherwise.
        """
        logger.info(
            "AutoTriggerHandler processing event: type=%s",
            event_type,
        )

        try:
            # Delegate to domain service for business logic
            if event_type == "HeartbeatTriggered":
                triggered = await self._auto_trigger_service.on_heartbeat_event(
                    HeartbeatTriggered.from_dict(event.to_dict())
                )
            else:
                triggered = await self._auto_trigger_service.on_domain_event(event)

            if triggered is not None:
                logger.info(
                    "Trigger processed: type=%s session_id=%s",
                    triggered.trigger_type,
                    triggered.session_id,
                )
                # Publish to downstream route stage
                await self._publish_triggered(triggered)
            else:
                logger.warning(
                    "AutoTriggerService returned None for event: %s",
                    event_type,
                )

            return triggered

        except Exception as e:
            logger.error("Failed to process event %s: %s", event_type, e)
            raise

    async def _publish_triggered(self, event: AutoTriggered) -> None:
        """Publish AutoTriggered event to downstream route stage."""
        if self._publisher is None:
            logger.warning("No publisher configured, AutoTriggered not published")
            return

        try:
            await self._publisher.publish(event, channel="rt:AutoTriggered")
            logger.debug("Published AutoTriggered: session_id=%s", event.session_id)
        except Exception as e:
            logger.error("Failed to publish AutoTriggered: %s", e)
            raise
```

---

### Phase 3: 实现 AutoTriggerAdapter (纸壳)

**Step 3.1: 创建 `auto_trigger_adapter.py`**

```python
# src/interfaces/event_listeners/auto_trigger_adapter.py
"""AutoTriggerAdapter — thin adapter for trigger mechanism.

This adapter is a "paper shell": it receives deserialized messages
from infrastructure consumers, converts to domain events, and immediately
delegates to AutoTriggerHandler.

Rules:
    - NO if/else business branches
    - NO domain service calls
    - NO port operations (beyond calling handler)
    - Max ~20 lines of actual code

Reference: Story 1.14a
Reference: architecture.md §3 - hexagonal architecture
"""

from __future__ import annotations

import logging

from src.application.event_handlers.auto_trigger_handler import AutoTriggerHandler

logger = logging.getLogger(__name__)


class AutoTriggerAdapter:
    """Thin adapter that bridges event bus to AutoTriggerHandler.

    Responsibility:
        1. Receive message from event bus (infrastructure)
        2. Convert to domain event object
        3. Call handler.handle(event) - delegate all logic

    This is NOT the place for business logic.
    All orchestration goes to AutoTriggerHandler (application layer).
    """

    def __init__(self, handler: AutoTriggerHandler) -> None:
        """Initialize AutoTriggerAdapter."""
        self._handler = handler

    async def on_event(self, event_type: str, event_data: dict) -> None:
        """Handle incoming event from event bus.

        Args:
            event_type: Type string from event bus.
            event_data: Deserialized event data dict.
        """
        # Convert dict to domain event - minimal transformation
        from src.domain.events.base import DomainEvent
        event = DomainEvent.from_dict(event_data)

        # Delegate all business logic to handler (application layer)
        await self._handler.handle(event, event_type)
```

---

### Phase 4: 实现 AutoRouteHandler

**Step 4.1: 创建 `auto_route_handler.py`**

```python
# src/application/event_handlers/auto_route_handler.py
"""AutoRouteHandler — business orchestration for route mechanism.

Receives AutoTriggered events from AutoTriggerAdapter, coordinates with
AutoRouteService (domain) to make routing decisions, and publishes
AutoRouted events to downstream execute stage.

Reference: Story 1.14b
"""

from __future__ import annotations

import logging
from typing import Protocol

from src.domain.events.auto_route_events import AutoRouted
from src.domain.events.auto_trigger_events import AutoTriggered
from src.domain.events.base import DomainEvent
from src.domain.services.auto_route_service import AutoRouteService

logger = logging.getLogger(__name__)


class EventPublisherProtocol(Protocol):
    """Protocol for event publishing."""

    async def publish(self, event: DomainEvent, channel: str | None = None) -> None: ...


class AutoRouteHandler:
    """Handler for route mechanism business orchestration.

    Responsible for:
    - Receiving AutoTriggered events
    - Invoking AutoRouteService for routing decisions
    - Publishing AutoRouted events to downstream execute stage

    This is application layer orchestration - NOT domain logic.
    """

    def __init__(
        self,
        auto_route_service: AutoRouteService,
        publisher: EventPublisherProtocol | None = None,
    ) -> None:
        self._auto_route_service = auto_route_service
        self._publisher = publisher

    async def handle(self, event: AutoTriggered) -> AutoRouted | None:
        """Handle AutoTriggered event: make routing decision and emit AutoRouted."""
        logger.info(
            "AutoRouteHandler processing AutoTriggered: session_id=%s trigger_type=%s",
            event.session_id,
            getattr(event, "trigger_type", "unknown"),
        )

        try:
            routed = await self._auto_route_service.on_triggered_event(event)

            if routed is not None:
                logger.info(
                    "Route completed: session_id=%s route_type=%s route_target=%s score=%.3f",
                    routed.session_id,
                    routed.route_type,
                    routed.route_target,
                    routed.route_score,
                )
                await self._publish_routed(routed)
            else:
                logger.warning("AutoRouteService returned None for AutoTriggered event")

            return routed

        except Exception as e:
            logger.error("Failed to process AutoTriggered event: %s", e)
            raise

    async def _publish_routed(self, event: AutoRouted) -> None:
        """Publish AutoRouted event to downstream execute stage."""
        if self._publisher is None:
            logger.warning("No publisher configured, AutoRouted event not published")
            return

        try:
            await self._publisher.publish(event, channel="rt:AutoRouted")
            logger.debug("Published AutoRouted: session_id=%s", event.session_id)
        except Exception as e:
            logger.error("Failed to publish AutoRouted: %s", e)
            raise
```

**Step 4.2: 创建 `auto_route_adapter.py`**

```python
# src/interfaces/event_listeners/auto_route_adapter.py
"""AutoRouteAdapter — thin adapter for route mechanism.

This adapter is a "paper shell": it receives deserialized messages,
converts to domain event, and immediately delegates to AutoRouteHandler.

Rules:
    - NO if/else business branches
    - NO domain service calls
    - Max ~20 lines of actual code

Reference: Story 1.14b
"""

from __future__ import annotations

import logging

from src.application.event_handlers.auto_route_handler import AutoRouteHandler
from src.domain.events.auto_trigger_events import AutoTriggered

logger = logging.getLogger(__name__)


class AutoRouteAdapter:
    """Thin adapter that bridges AutoTriggered events to AutoRouteHandler."""

    def __init__(self, handler: AutoRouteHandler) -> None:
        self._handler = handler

    async def on_triggered(self, event_data: dict) -> None:
        """Handle AutoTriggered event from event bus."""
        # Convert to domain event - minimal transformation
        event = AutoTriggered.from_dict(event_data)
        # Delegate all business logic to handler
        await self._handler.handle(event)
```

---

### Phase 5: 实现 AutoExecuteCompletedHandler

**Step 5.1: 创建 `auto_execute_completed_handler.py`**

```python
# src/application/event_handlers/auto_execute_completed_handler.py
"""AutoExecuteCompletedHandler — business orchestration for execute completion.

Receives AutoExecuted events from AutoExecuteAdapter, publishes
corresponding downstream domain events (DocumentProcessed/ToolExecuted/AgentDecided)
based on business_event_type.

Reference: Story 1.14c
"""

from __future__ import annotations

import logging
from typing import Protocol

from src.domain.events.agent_events import AgentDecided
from src.domain.events.auto_execute_events import AutoExecuted
from src.domain.events.base import DomainEvent
from src.domain.events.document_events import DocumentProcessed
from src.domain.events.tool_events import ToolExecuted

logger = logging.getLogger(__name__)


class EventPublisherProtocol(Protocol):
    """Protocol for event publishing."""

    async def publish(self, event: DomainEvent, channel: str | None = None) -> None: ...


class AutoExecuteCompletedHandler:
    """Handler for execute completion business orchestration.

    Responsible for:
    - Listening to AutoExecuted events from AutoExecuteService
    - Publishing corresponding domain events based on business_event_type:
      - "DocumentProcessed" → DocumentProcessed event
      - "ToolExecuted" → ToolExecuted event
      - "AgentDecided" → AgentDecided event
    """

    def __init__(self, publisher: EventPublisherProtocol | None = None) -> None:
        self._publisher = publisher

    async def handle(self, event: AutoExecuted) -> None:
        """Handle AutoExecuted event: publish downstream domain event."""
        business_event_type = event.business_event_type or "ToolExecuted"

        logger.info(
            "AutoExecuteCompletedHandler: session_id=%s business_event_type=%s",
            event.session_id,
            business_event_type,
        )

        if business_event_type == "DocumentProcessed":
            await self._publish_document_processed(event)
        elif business_event_type == "ToolExecuted":
            await self._publish_tool_executed(event)
        elif business_event_type == "AgentDecided":
            await self._publish_agent_decided(event)
        else:
            logger.warning("Unknown business_event_type: %s, defaulting to ToolExecuted", business_event_type)
            await self._publish_tool_executed(event)

    async def _publish_document_processed(self, event: AutoExecuted) -> None:
        domain_event = DocumentProcessed(
            document_id=event.task_context.get("document_id", ""),
            parse_result=event.execution_result,
        )
        await self._publish(domain_event, "domain:DocumentProcessed")
        logger.info("Published DocumentProcessed: document_id=%s", domain_event.document_id)

    async def _publish_tool_executed(self, event: AutoExecuted) -> None:
        domain_event = ToolExecuted(
            tool_id=event.task_context.get("tool_id", ""),
            execution_result=event.execution_result,
            cost_audit={"estimated": event.cost_estimate},
        )
        await self._publish(domain_event, "domain:ToolExecuted")
        logger.info("Published ToolExecuted: tool_id=%s", domain_event.tool_id)

    async def _publish_agent_decided(self, event: AutoExecuted) -> None:
        domain_event = AgentDecided(
            agent_id=event.task_context.get("agent_id", ""),
            decision_result=event.execution_result,
            confidence=event.route_score,
        )
        await self._publish(domain_event, "domain:AgentDecided")
        logger.info("Published AgentDecided: agent_id=%s", domain_event.agent_id)

    async def _publish(self, event: DomainEvent, channel: str) -> None:
        if self._publisher is None:
            logger.warning("No publisher configured, event not published: %s", event.event_type)
            return

        try:
            await self._publisher.publish(event, channel=channel)
            logger.debug("Published event: type=%s channel=%s", event.event_type, channel)
        except Exception as e:
            logger.error("Failed to publish %s event: %s", event.event_type, e)
            raise
```

**Step 5.2: 创建 `auto_execute_completed_adapter.py`**

```python
# src/interfaces/event_listeners/auto_execute_completed_adapter.py
"""AutoExecuteCompletedAdapter — thin adapter for execute completion.

This adapter is a "paper shell": it receives deserialized messages,
converts to AutoExecuted event, and immediately delegates to handler.

Rules:
    - NO if/else business branches
    - NO domain service calls
    - Max ~20 lines of actual code

Reference: Story 1.14c
"""

from __future__ import annotations

import logging

from src.application.event_handlers.auto_execute_completed_handler import (
    AutoExecuteCompletedHandler,
)
from src.domain.events.auto_execute_events import AutoExecuted

logger = logging.getLogger(__name__)


class AutoExecuteCompletedAdapter:
    """Thin adapter that bridges AutoExecuted events to handler."""

    def __init__(self, handler: AutoExecuteCompletedHandler) -> None:
        self._handler = handler

    async def on_executed(self, event_data: dict) -> None:
        """Handle AutoExecuted event from event bus."""
        # Convert to domain event - minimal transformation
        event = AutoExecuted.from_dict(event_data)
        # Delegate all business logic to handler
        await self._handler.handle(event)
```

---

### Phase 6: 实现 MemoryChangedHandler

**Step 6.1: 创建 `memory_changed_handler.py`**

```python
# src/application/event_handlers/memory_changed_handler.py
"""MemoryChangedHandler — business orchestration for memory change events.

Receives MemoryChanged events, coordinates L1-L5 storage operations,
and ensures "context ≠ cache" invariant via L1 cache invalidation.

L1 vs L3 Clarification:
    - L1 (this handler): User-triggered, lightweight (≤500字→~150字), no PersistentNote
    - L3 (Story 6.3): Checkpoint-triggered, heavyweight (~50K→~2K tokens), needs PersistentNote

Reference: Story 1.15a
Reference: architecture.md §11.2.6 - externalized memory trigger mechanism
"""

from __future__ import annotations

import logging
from typing import Protocol

from src.domain.events.memory_events import MemoryChanged

logger = logging.getLogger(__name__)


class StorageCoordinatorProtocol(Protocol):
    """Protocol for multi-layer storage coordination."""

    async def invalidate(self, layer: str, key: str) -> None: ...


class L2MetadataRepositoryProtocol(Protocol):
    """Protocol for L2 PostgreSQL memory metadata operations."""

    async def upsert(self, event: MemoryChanged) -> None: ...


class L2ChangeHistoryRepositoryProtocol(Protocol):
    """Protocol for L2 PostgreSQL memory change history."""

    async def append(self, event: MemoryChanged) -> None: ...


class VectorStoreProtocol(Protocol):
    """Protocol for L3 Qdrant vector storage."""

    async def embed(self, event: MemoryChanged) -> None: ...


class EntityExtractorProtocol(Protocol):
    """Protocol for L5 Neo4j entity extraction."""

    async def extract(self, event: MemoryChanged) -> None: ...


class MemoryChangedHandler:
    """Handler for memory change event business orchestration.

    Responsible for:
    - L1 Redis cache invalidation (synchronous, immediate)
    - L2 PostgreSQL write: metadata + history (append-only)
    - L3 Qdrant vector embedding (on-demand, content >500 tokens)
    - L5 Neo4j entity extraction (on-demand)

    L4 MinIO is NOT in this flow - triggered independently by Checkpoint (Story 6.3).

    This is application layer orchestration - NOT domain logic.
    """

    def __init__(
        self,
        storage_coordinator: StorageCoordinatorProtocol | None = None,
        metadata_repo: L2MetadataRepositoryProtocol | None = None,
        history_repo: L2ChangeHistoryRepositoryProtocol | None = None,
        vector_store: VectorStoreProtocol | None = None,
        entity_extractor: EntityExtractorProtocol | None = None,
    ) -> None:
        self._storage = storage_coordinator
        self._metadata_repo = metadata_repo
        self._history_repo = history_repo
        self._vector_store = vector_store
        self._entity_extractor = entity_extractor

    async def handle(self, event: MemoryChanged) -> None:
        """Handle MemoryChanged event: coordinate multi-layer storage."""
        logger.info(
            "MemoryChangedHandler: memory_id=%s change_type=%s is_automatic=%s",
            event.memory_id,
            event.change_type,
            event.is_automatic,
        )

        try:
            # Step 1: L1 Redis cache invalidation (synchronous, immediate)
            # Ensures "context ≠ cache" invariant from system axiom 2
            await self._invalidate_l1_cache(event)

            # Step 2: L2 PostgreSQL write (via repositories)
            await self._write_l2(event)

            # Step 3: L3 Qdrant vector embedding (on-demand, content >500 tokens)
            content_length = len(str(event.new_value or "")) if event.new_value else 0
            if content_length > 500:
                await self._embed_l3(event)

            # Step 4: L5 Neo4j entity extraction (on-demand)
            await self._extract_l5(event)

            logger.info("MemoryChanged handled successfully: memory_id=%s", event.memory_id)

        except Exception as e:
            logger.error("Failed to handle MemoryChanged event: %s", e)
            raise

    async def _invalidate_l1_cache(self, event: MemoryChanged) -> None:
        """Invalidate L1 Redis cache (synchronous, immediate)."""
        if self._storage is None:
            logger.debug("No storage coordinator, skipping L1 invalidation")
            return

        # Redis key format: memory:user:{user_id}:{memory_id}
        key = f"memory:user:{event.user_id}:{event.memory_id}"
        await self._storage.invalidate(layer="L1", key=key)
        logger.debug("L1 cache invalidated: key=%s", key)

    async def _write_l2(self, event: MemoryChanged) -> None:
        """Write to L2 PostgreSQL (metadata + history)."""
        if self._metadata_repo is not None:
            await self._metadata_repo.upsert(event)
            logger.debug("L2 metadata upserted: memory_id=%s", event.memory_id)

        if self._history_repo is not None:
            await self._history_repo.append(event)
            logger.debug("L2 history appended: memory_id=%s", event.memory_id)

    async def _embed_l3(self, event: MemoryChanged) -> None:
        """Embed to L3 Qdrant vector store (on-demand)."""
        if self._vector_store is None:
            logger.debug("No vector store, skipping L3 embedding")
            return

        await self._vector_store.embed(event)
        logger.debug("L3 vector embedded: memory_id=%s", event.memory_id)

    async def _extract_l5(self, event: MemoryChanged) -> None:
        """Extract to L5 Neo4j graph (on-demand)."""
        if self._entity_extractor is None:
            logger.debug("No entity extractor, skipping L5 extraction")
            return

        await self._entity_extractor.extract(event)
        logger.debug("L5 entity extracted: memory_id=%s", event.memory_id)
```

**Step 6.2: 创建 `memory_changed_adapter.py`**

```python
# src/interfaces/event_listeners/memory_changed_adapter.py
"""MemoryChangedAdapter — thin adapter for memory change events.

This adapter is a "paper shell": it receives deserialized messages,
converts to MemoryChanged event, and immediately delegates to handler.

Rules:
    - NO if/else business branches
    - NO domain service calls
    - Max ~20 lines of actual code

Reference: Story 1.15a
"""

from __future__ import annotations

import logging

from src.application.event_handlers.memory_changed_handler import MemoryChangedHandler
from src.domain.events.memory_events import MemoryChanged

logger = logging.getLogger(__name__)


class MemoryChangedAdapter:
    """Thin adapter that bridges MemoryChanged events to handler."""

    def __init__(self, handler: MemoryChangedHandler) -> None:
        self._handler = handler

    async def on_changed(self, event_data: dict) -> None:
        """Handle MemoryChanged event from event bus."""
        # Convert to domain event - minimal transformation
        event = MemoryChanged.from_dict(event_data)
        # Delegate all business logic to handler
        await self._handler.handle(event)
```

---

### Phase 7: 更新 interfaces/event_listeners/__init__.py

**Step 7.1: 重写 `__init__.py`**

```python
# src/interfaces/event_listeners/__init__.py
"""Event listeners package - adapter layer for hexagonal architecture.

This package contains thin adapters (not business logic).
Business orchestration lives in application/event_handlers/.

Migration (2026-05):
    - Old listeners/ auto_*_listener.py files → split into:
        - interfaces/event_listeners/auto_*_adapter.py (thin, <20 lines)
        - application/event_handlers/auto_*_handler.py (orchestration)
    - listeners/ directory removed

Architecture:
    interfaces/ → adapters (thin)
    application/ → handlers (orchestration)
    domain/ → services (core logic)
"""

from .auto_trigger_adapter import AutoTriggerAdapter
from .auto_route_adapter import AutoRouteAdapter
from .auto_execute_completed_adapter import AutoExecuteCompletedAdapter
from .memory_changed_adapter import MemoryChangedAdapter

__all__ = [
    "AutoTriggerAdapter",
    "AutoRouteAdapter",
    "AutoExecuteCompletedAdapter",
    "MemoryChangedAdapter",
]
```

---

### Phase 8: 删除旧文件

**Step 8.1: 删除旧的 listener 文件**

```bash
# 删除旧的事件监听器文件
rm -f src/application/event_handlers/auto_trigger_listener.py
rm -f src/application/event_handlers/auto_route_listener.py
rm -f src/application/event_handlers/auto_execute_completed_listener.py
rm -f src/application/event_handlers/memory_changed_listener.py

# 如果 listeners/ 目录为空，删除目录
rmdir src/interfaces/event_listeners/listeners 2>/dev/null || true
```

**Step 8.2: 验证文件删除**

```bash
# 确认旧文件已删除
ls -la src/application/event_handlers/ 2>/dev/null || echo "Directory removed or empty"
```

---

### Phase 9: 更新相关 Story 文档

**Step 9.1: 更新 Story 文件中的路径引用**

| Story | 旧路径 | 新路径 |
|-------|--------|--------|
| 1.14a | `src/application/event_handlers/auto_trigger_listener.py` | `src/interfaces/event_listeners/auto_trigger_adapter.py` + `src/application/event_handlers/auto_trigger_handler.py` |
| 1.14b | `src/application/event_handlers/auto_route_listener.py` | `src/interfaces/event_listeners/auto_route_adapter.py` + `src/application/event_handlers/auto_route_handler.py` |
| 1.14c | `src/application/event_handlers/auto_execute_completed_listener.py` | `src/interfaces/event_listeners/auto_execute_completed_adapter.py` + `src/application/event_handlers/auto_execute_completed_handler.py` |
| 1.15a | `src/application/event_handlers/memory_changed_listener.py` | `src/interfaces/event_listeners/memory_changed_adapter.py` + `src/application/event_handlers/memory_changed_handler.py` |

---

### Phase 10: 验证六边形架构合规

**Step 10.1: 运行架构验证测试**

```bash
# 验证无循环依赖
poetry run pytest tests/unit/architecture/ -v

# 验证领域层零依赖
poetry run mypy src/domain/ --strict

# 验证接口层不包含业务逻辑（行数检查）
find src/interfaces/event_listeners/ -name "*_adapter.py" -exec wc -l {} \;
# 预期：每个 adapter <30 行
```

**Step 10.2: 验证测试通过**

```bash
# 运行相关测试
poetry run pytest tests/unit/domain/services/test_auto_trigger_service.py -v
poetry run pytest tests/unit/domain/services/test_auto_route_service.py -v
poetry run pytest tests/unit/domain/services/test_auto_execute_service.py -v
poetry run pytest tests/unit/domain/services/test_memory_service.py -v

# 运行并行测试确保无回归
poetry run pytest tests/ -n 8 -v
```

---

## 5. 架构验证矩阵

### 5.1 依赖方向验证

| 层级 | 可导入 | 不可导入 |
|------|--------|----------|
| `interfaces/` | `application/`, `domain/` | 无 |
| `application/` | `domain/` | `interfaces/` |
| `domain/` | 仅 Python 标准库 | `application/`, `interfaces/`, 外部依赖 |

**依赖方向规则**
- 领域层 → 应用/接口/基础设施层：✗ 禁止
- 应用层 → 接口层/基础设施层：✗ 禁止
- 接口层      → 应用层/领域层 ✓ 允许
- 应用层      → 领域层 ✓ 允许
- 基础设施层  → 应用层/领域层 ✓ 允许
- 领域层      → 仅标准库 ✓ 允许

### 5.2 纸壳适配器规则验证

| 检查项 | 要求 | 验证方法 |
|--------|------|----------|
| 代码行数 | <30 行/文件 | `wc -l` |
| 无 if/else 业务分支 | 0 个 | 代码审查 |
| 无领域服务调用 | 0 个 | 代码审查 |
| 仅调用 handler.handle() | 必须 | 代码审查 |

### 5.3 应用层处理器规则验证

| 检查项 | 要求 | 验证方法 |
|--------|------|----------|
| 调用领域服务 | 必须 | 代码审查 |
| 发布事件 | 必须 | 代码审查 |
| 无基础设施实现 | 0 个 threading/queue | 代码审查 |
| 包含业务编排 | 必须 | 代码审查 |

---

## 6. 新项目结构

```
sisys/
├── src/
│   ├── domain/
│   │   ├── events/
│   │   │   ├── base.py
│   │   │   ├── auto_trigger_events.py
│   │   │   ├── auto_route_events.py
│   │   │   ├── auto_execute_events.py
│   │   │   └── memory_events.py
│   │   └── services/
│   │       ├── auto_trigger_service.py
│   │       ├── auto_route_service.py
│   │       ├── auto_execute_service.py
│   │       └── memory_service.py
│   ├── application/
│   │   └── event_handlers/              # NEW: 业务编排中枢
│   │       ├── __init__.py
│   │       ├── auto_trigger_handler.py
│   │       ├── auto_route_handler.py
│   │       ├── auto_execute_completed_handler.py
│   │       └── memory_changed_handler.py
│   └── interfaces/
│       └── event_listeners/
│           ├── __init__.py
│           ├── auto_trigger_adapter.py      # 纸壳适配器 (<20行)
│           ├── auto_route_adapter.py
│           ├── auto_execute_completed_adapter.py
│           └── memory_changed_adapter.py
```

---

## 7. 执行检查清单

- [ ] Phase 1: 创建 `src/application/event_handlers/` 目录
- [ ] Phase 2: 实现 `AutoTriggerHandler`
- [ ] Phase 3: 实现 `AutoTriggerAdapter` (纸壳)
- [ ] Phase 4: 实现 `AutoRouteHandler` 和 `AutoRouteAdapter`
- [ ] Phase 5: 实现 `AutoExecuteCompletedHandler` 和 `AutoExecuteCompletedAdapter`
- [ ] Phase 6: 实现 `MemoryChangedHandler` 和 `MemoryChangedAdapter`
- [ ] Phase 7: 更新 `interfaces/event_listeners/__init__.py`
- [ ] Phase 8: 删除旧文件 (`listeners/` 目录)
- [ ] Phase 9: 更新 Story 文档路径引用
- [ ] Phase 10: 运行架构验证测试

---

## 8. 回滚计划

如迁移过程中出现问题：

```bash
# 恢复旧文件（从 git）
git checkout HEAD -- src/application/event_handlers/

# 删除新创建的文件
rm -rf src/application/event_handlers/
rm -f src/interfaces/event_listeners/*_adapter.py
```

---

## 9. 附录

### A. 六边形架构原则

1. **领域层零依赖**: 仅使用 Python 标准库
2. **依赖倒置**: 领域层定义接口，基础设施层实现
3. **单向依赖**: 上层可以调用下层，下层不能调用上层
4. **事件驱动解耦**: 通过事件总线通信，不直接调用

### B. 相关文档

- [architecture.md](../../_bmad-output/planning-artifacts/architecture.md) - 架构设计文档
- [Story 1.14a](../../_bmad-output/implementation-artifacts/stories/1-14a-autonomous-invocation-trigger.md) - trigger 实现
- [Story 1.14b](../../_bmad-output/implementation-artifacts/stories/1-14b-autonomous-invocation-route.md) - route 实现
- [Story 1.14c](../../_bmad-output/implementation-artifacts/stories/1-14c-autonomous-invocation-execute.md) - execute 实现
- [Story 1.15a](../../_bmad-output/implementation-artifacts/stories/1-15a-externalized-memory-context-compression.md) - L1 显式确认压缩
