# SISYS 端口实现机制全面调研报告

**调研时间:** 2026-05-11
**调研范围:** `src/domain/ports/`, `src/application/ports/`, 服务文件内部

---

## 一、端口定义分布

| 位置 | 文件数 | 导出机制 |
|------|--------|----------|
| `src/domain/ports/` | 36 | `__init__.py` (部分导出) |
| `src/application/ports/` | 8 | **无 `__init__.py`** |
| 服务文件内部 | 6处 | 本地定义 |

---

## 二、`__init__.py` 导出完整性

```python
# src/domain/ports/__init__.py
# 已导出: 17 个
# 未导出: ~24 个 (占比 60%)
```

**已导出 (17个):**
- GraphManager, GraphStorage, L1CachePort
- L2MetadataRepositoryPort, L2ChangeHistoryRepositoryPort, L2GroupMemberRepositoryPort
- L3VectorPort, L4ObjectPort, L5GraphPort
- SessionStorage, OutboxRepository, UnifiedStoragePort, UnitOfWork
- StorageLayer, StorageTier, DataAccessPattern

**未导出但已定义 (~24个):**
- Story 1.11 相关: `SensitiveDataDetectorPort`, `ComplianceGatewayPort`, `CrossBorderTransferServicePort`, `DataResidencyEnforcerPort`, `WhitelistServicePort`, `PIPLComplianceServicePort`
- 认证/授权: `PasswordValidationServicePort`, `TokenBlacklistPort`, `PermissionServicePort`, `AuthServicePort`
- 审计: `AuditServicePort`, `AuditRepositoryPort`
- 存储: `L0StoragePort`, `HealthCheckPort`, `IndexManagerPort`, `IntegrityPort`, `LoginAttemptRepositoryPort`
- 事件: `EventPublisher`, `InMemoryEventPublisher`
- 其他: `UserRepositoryPort`, `RoleRepositoryPort`, `UserRoleRepositoryPort`, `BaseRepository`, `CollectionManager`, `VectorStorage`, `ObjectStorageRepository`, `GraphNode`, `GraphRelationship`

---

## 三、服务内本地定义 Protocol (重复问题)

| 服务文件 | 本地定义 | 应该使用 |
|---------|---------|---------|
| `auto_route_service.py` | `EventPublisherProtocol` | `EventPublisher` |
| `auto_route_service.py` | `HashRouterProtocol` | 应统一到 `ports/` |
| `auto_route_service.py` | `SemanticRouterProtocol` | 应统一到 `ports/` |
| `auto_trigger_service.py` | `EventPublisherProtocol` | `EventPublisher` |
| `auto_execute_service.py` | `SandboxExecutorProtocol` | `SandboxExecutor` |
| `auto_execute_service.py` | `SnapshotRepositoryProtocol` | 应统一到 `ports/` |
| `auto_execute_completed_handler.py` | `EventPublisherProtocol` | `EventPublisher` |
| `auto_route_handler.py` | `EventPublisherProtocol` | `EventPublisher` |

### 问题详情

**`EventPublisherProtocol` 重复定义 (4处):**
```python
# 错误: 每个文件都本地定义
# src/domain/services/auto_route_service.py:15
class EventPublisherProtocol(Protocol):
    async def publish(self, event: DomainEvent, channel: str | None = None) -> None: ...

# src/domain/services/auto_trigger_service.py:15
class EventPublisherProtocol(Protocol):
    async def publish(self, event: DomainEvent, channel: str | None = None) -> None: ...

# src/application/event_handlers/auto_execute_completed_handler.py:18
class EventPublisherProtocol(Protocol):
    async def publish(self, event: DomainEvent, channel: str | None = None) -> None: ...

# src/application/event_handlers/auto_route_handler.py:27
class EventPublisherProtocol(Protocol):
    async def publish(self, event: DomainEvent, channel: str | None = None) -> None: ...
```

**正确做法:**
```python
# 应该从统一端口导入
from src.domain.ports.event_publisher import EventPublisher

class AutoRouteService:
    def __init__(self, publisher: EventPublisher | None = None):
        self._publisher = publisher
```

---

## 四、Protocol 命名不一致

| 正确命名 (已统一) | 错误命名 (仍在用) |
|------------------|------------------|
| `EventPublisher` | `EventPublisherProtocol` (4处) |
| `SandboxExecutor` | `SandboxExecutorProtocol` (1处) |

---

## 五、基础设施层实现情况

| Protocol | 实现类 | 位置 |
|----------|--------|------|
| `EventPublisher` | `DualChannelEventBus`, `RabbitMQEventBus`, `RedisEventBus` | `infrastructure/messaging/` |
| `InMemoryEventPublisher` | `InMemoryEventBus` | `infrastructure/messaging/` |
| `HashRouterProtocol` | `HashRouter` | `infrastructure/routing/` |
| `SemanticRouterProtocol` | (未找到实现) | - |

---

## 六、application/ports 问题

| 问题 | 说明 |
|------|------|
| 无 `__init__.py` | 无法统一导入 |
| 散乱导入 | 直接导入具体文件而非统一入口 |
| Protocol 定义在应用层 | 应统一在 `domain/ports/` |

**application/ports 定义列表:**
- `MetricsPort`
- `TextExtractorService`
- `EventSubscriber`
- `CompressorService`
- `ExceptionMetricsPort`
- `PublicBlackboard`
- `SandboxExecutor`
- `SemanticCache`

---

## 七、循环依赖风险分析

```
src/domain/events/base.py
         ↓ (DomainEvent)
src/domain/ports/event_publisher.py
         ↓ (导入 DomainEvent)
src/domain/services/auto_route_service.py
         ↓ (定义 EventPublisherProtocol)
src/infrastructure/messaging/redis_event_bus.py
         ↓ (实现 EventPublisher)
```

**存在潜在循环依赖:**
- `auto_route_service.py` 定义了 `EventPublisherProtocol(Protocol)`
- 但它同时导入了 `DomainEvent` (从 `domain.events.base`)
- 如果实现类 `RedisEventBus` 导入 `auto_route_service.py` 可能触发循环

---

## 八、完整 Protocol 清单

### domain/ports/ 定义 (41个)

| 文件 | Protocol | 状态 |
|------|----------|------|
| audit_repository.py | `AuditRepositoryPort` | 未导出 |
| audit_service.py | `AuditServicePort` | 未导出 |
| auth_service.py | `AuthServicePort` | 未导出 |
| base.py | `BaseRepository` | 未导出 |
| compliance_gateway.py | `ComplianceGatewayPort` | 未导出 |
| cross_border_transfer_service.py | `CrossBorderTransferServicePort` | 未导出 |
| data_residency_enforcer.py | `DataResidencyEnforcerPort` | 未导出 |
| event_publisher.py | `EventPublisher`, `InMemoryEventPublisher` | 未导出 |
| graph_storage.py | `GraphNode`, `GraphRelationship`, `GraphManager`, `GraphStorage` | GraphManager/GraphStorage 已导出 |
| health_check.py | `HealthCheckPort` | 未导出 |
| index_manager.py | `IndexManagerPort` | 未导出 |
| integrity.py | `IntegrityPort` | 未导出 |
| l0_storage.py | `L0StoragePort` | 未导出 |
| l1_cache.py | `L1CachePort` | 已导出 |
| l2_rdb.py | `L2MetadataRepositoryPort`, `L2ChangeHistoryRepositoryPort`, `L2GroupMemberRepositoryPort` | 全部已导出 |
| l3_vector.py | `L3VectorPort` | 已导出 |
| l4_object.py | `L4ObjectPort` | 已导出 |
| l5_graph.py | `L5GraphPort` | 已导出 |
| login_attempt_repository.py | `LoginAttemptRepositoryPort` | 未导出 |
| outbox.py | `OutboxRepository` | 已导出 |
| password_validation_service.py | `PasswordValidationServicePort` | 未导出 |
| permission_service.py | `PermissionServicePort` | 未导出 |
| pipl_compliance_service.py | `PIPLComplianceServicePort` | 未导出 |
| role_repository.py | `RoleRepositoryPort` | 未导出 |
| sensitive_data_detector.py | `SensitiveDataDetectorPort` | 未导出 |
| session_storage.py | `SessionStorage` | 已导出 |
| storage.py | `ObjectStorageRepository` | 未导出 |
| storage_enums.py | `StorageLayer`, `StorageTier`, `DataAccessPattern` | 全部已导出 |
| token_blacklist.py | `TokenBlacklistPort` | 未导出 |
| unified_storage.py | `UnifiedStoragePort` | 已导出 |
| unit_of_work.py | `UnitOfWork` | 已导出 |
| user_repository.py | `UserRepositoryPort` | 未导出 |
| user_role_repository.py | `UserRoleRepositoryPort` | 未导出 |
| vector_storage.py | `CollectionManager`, `VectorStorage` | 未导出 |
| whitelist_service.py | `WhitelistServicePort` | 未导出 |

### application/ports/ 定义 (8个)

| 文件 | Protocol | 状态 |
|------|----------|------|
| compressor_service.py | `CompressorService` | 无导出 |
| event_subscriber.py | `EventSubscriber` | 无导出 |
| exception_metrics_port.py | `ExceptionMetricsPort` | 无导出 |
| metrics_port.py | `MetricsPort` | 无导出 |
| public_blackboard.py | `PublicBlackboard` | 无导出 |
| sandbox_port.py | `SandboxExecutor` | 无导出 |
| semantic_cache.py | `SemanticCache` | 无导出 |
| text_extractor_service.py | `TextExtractorService` | 无导出 |

---

## 九、修复建议

### 1. 补全 `domain/ports/__init__.py`

导出所有 41 个 Protocol，保持一致性。

### 2. 创建 `application/ports/__init__.py`

统一导出 8 个 Protocol。

### 3. 删除服务内本地定义

| 文件 | 删除 | 替换为 |
|------|------|--------|
| `auto_route_service.py` | `EventPublisherProtocol` | `from event_publisher import EventPublisher` |
| `auto_route_service.py` | `HashRouterProtocol` | 移动到 `ports/routing.py` |
| `auto_route_service.py` | `SemanticRouterProtocol` | 移动到 `ports/routing.py` |
| `auto_trigger_service.py` | `EventPublisherProtocol` | `from event_publisher import EventPublisher` |
| `auto_execute_service.py` | `SandboxExecutorProtocol` | `from sandbox_port import SandboxExecutor` |
| `auto_execute_service.py` | `SnapshotRepositoryProtocol` | 移动到 `ports/snapshot.py` |
| `auto_execute_completed_handler.py` | `EventPublisherProtocol` | `from event_publisher import EventPublisher` |
| `auto_route_handler.py` | `EventPublisherProtocol` | `from event_publisher import EventPublisher` |

### 4. 统一命名规范

删除 `*Protocol` 后缀:
- `EventPublisherProtocol` → `EventPublisher`
- `SandboxExecutorProtocol` → `SandboxExecutor`

### 5. 移动路由相关 Protocol

创建 `src/domain/ports/routing.py`:
- `HashRouterProtocol`
- `SemanticRouterProtocol`
- `SnapshotRepositoryProtocol`

---

## 十、架构约束

根据六边形架构原则:

1. **端口定义位置**: 所有 Port 应定义在 `src/domain/ports/` 或 `src/application/ports/`
2. **服务内禁止定义**: 服务文件内部不应定义 Port
3. **统一导入**: 使用 `from src.domain.ports.xxx import XXX` 而非本地定义
4. **依赖方向**: 领域层定义接口，基础设施层实现，依赖从外向内

---

## 十一、第1轮审查P0问题与系统解决方案

### P0问题汇总

| P0-ID | 模块 | 问题描述 | 严重程度 |
|-------|------|----------|----------|
| P0-1 | 服务内Protocol | `auto_route_service.py` 本地定义 `EventPublisherProtocol`，与 `event_publisher.py` 重复 | 严重 |
| P0-2 | 服务内Protocol | `auto_trigger_service.py` 本地定义相同的 `EventPublisherProtocol` | 严重 |
| P0-3 | 服务内Protocol | `auto_route_service.py` 本地定义 `HashRouterProtocol`、`SemanticRouterProtocol` | 严重 |
| P0-4 | 服务内Protocol | `auto_execute_completed_handler.py` 和 `auto_route_handler.py` 各自本地定义 `EventPublisherProtocol` | 严重 |
| P0-5 | 接口不一致 | 本地 `EventPublisherProtocol` 返回 `None`，正式 `EventPublisher` 返回 `PublishResult` | 严重 |
| P0-6 | 事件发布 | `AutoRouteHandler.on_triggered()` 计算了 `routed` 但从未调用 `_publish(routed)` | 严重 |
| P0-7 | 导出完整性 | `__init__.py` 仅导出17个，遗漏超过24个重要端口（BaseRepository、ObjectStorageRepository等） | 严重 |
| P0-8 | 导出缺失 | `L0StoragePort`、`IntegrityPort`、`CollectionManager`、`VectorStorage` 等核心接口未导出 | 严重 |
| P0-9 | application/ports | 缺少 `__init__.py`，无法统一导入 | 严重 |
| P0-10 | 事件总线工厂 | `EventBusFactory.__init__` 初始化 `None`，运行时调用触发 `AttributeError` | 严重 |
| P0-11 | 事件总线工厂 | `_get_outbox_repository()` 返回 `None`，`RabbitMQEventBus.publish()` 触发 `AttributeError` | 严重 |
| P0-12 | 组件复用 | 工厂类声称"共享组件复用"但实际未实现，所有 publisher 始终为 `None` | 严重 |
| P0-13 | Protocol不兼容 | `InMemoryEventBus.publish()` 同步返回 `None`，与 `EventPublisher` 异步返回 `PublishResult` 不兼容 | 严重 |
| P0-14 | 接口冗余 | `VectorStorage` Protocol 与 `L3VectorPort` 语义重复 | 中等 |
| P0-15 | 接口冗余 | `GraphManager`/`GraphStorage` Protocol 与 `L5GraphPort` 语义重复 | 中等 |
| P0-16 | 存储层 | `CollectionManager` 无实现类，`QdrantCollectionManager` 未声明实现该接口 | 中等 |
| P0-17 | 存储层 | `SessionStorage` 与 `L1CachePort` 功能重叠但无关联 | 中等 |

### 系统解决方案

#### 方案1: 删除服务内本地Protocol定义

**问题根源**: 服务文件违反六边形架构"端口集中定义"原则

**执行步骤**:
1. 删除 `auto_route_service.py` 第15-18行 `EventPublisherProtocol`
2. 删除 `auto_trigger_service.py` 第15-18行 `EventPublisherProtocol`
3. 删除 `auto_execute_completed_handler.py` 第18-21行 `EventPublisherProtocol`
4. 删除 `auto_route_handler.py` 第27-30行 `EventPublisherProtocol`
5. 统一导入: `from src.domain.ports.event_publisher import EventPublisher`

**代码变更示例**:
```python
# auto_route_service.py 删除后
from src.domain.ports.event_publisher import EventPublisher

class AutoRouteService:
    def __init__(self, publisher: EventPublisher | None = None):
        self._publisher = publisher
```

#### 方案2: 创建路由协议端口文件

**问题根源**: `HashRouterProtocol`、`SemanticRouterProtocol` 应属于领域层端口

**执行步骤**:
1. 创建 `src/domain/ports/routing.py`
2. 从 `auto_route_service.py` 迁移 `HashRouterProtocol`、`SemanticRouterProtocol` 定义
3. 更新 `auto_route_service.py` 导入语句

**routing.py 内容**:
```python
"""路由协议端口 — 六边形架构路由接口"""
from __future__ import annotations
from typing import Protocol

class HashRouterProtocol(Protocol):
    """基于session_id哈希的路由协议"""
    def route(self, session_id: str) -> str: ...

class SemanticRouterProtocol(Protocol):
    """基于任务上下文语义相似度的路由协议"""
    async def route(self, task_context: dict) -> tuple[str, float]: ...
```

#### 方案3: 补全domain/ports/__init__.py导出

**问题根源**: `__all__` 仅17项，遗漏超过24个重要端口

**执行步骤**:
1. 在 `__init__.py` 添加缺失导出
2. 按分类组织: 核心存储、合规安全、事件认证、辅助接口

**导出补充**:
```python
# 核心存储接口
from src.domain.ports.base import BaseRepository
from src.domain.ports.storage import ObjectStorageRepository, ComplianceLockError
from src.domain.ports.vector_storage import CollectionManager, VectorStorage
from src.domain.ports.l0_storage import L0StoragePort
from src.domain.ports.integrity import IntegrityPort

# 合规安全接口
from src.domain.ports.compliance_gateway import ComplianceGatewayPort
from src.domain.ports.sensitive_data_detector import SensitiveDataDetectorPort
from src.domain.ports.data_residency_enforcer import DataResidencyEnforcerPort

# 事件认证接口
from src.domain.ports.event_publisher import EventPublisher, InMemoryEventPublisher
from src.domain.ports.auth_service import AuthServicePort
from src.domain.ports.audit_service import AuditServicePort
```

#### 方案4: 创建application/ports/__init__.py

**问题根源**: `application/ports/` 缺少 `__init__.py` 导致导出断裂

**执行步骤**:
1. 创建 `src/application/ports/__init__.py`
2. 统一导出8个Protocol

**__init__.py 内容**:
```python
"""Application ports package — 应用层端口定义"""
from src.application.ports.metrics_port import MetricsPort
from src.application.ports.text_extractor_service import TextExtractorService
from src.application.ports.event_subscriber import EventSubscriber
from src.application.ports.compressor_service import CompressorService
from src.application.ports.exception_metrics_port import ExceptionMetricsPort
from src.application.ports.public_blackboard import PublicBlackboard
from src.application.ports.sandbox_port import SandboxExecutor
from src.application.ports.semantic_cache import SemanticCache

__all__ = [
    "CompressorService",
    "EventSubscriber",
    "ExceptionMetricsPort",
    "MetricsPort",
    "PublicBlackboard",
    "SandboxExecutor",
    "SemanticCache",
    "TextExtractorService",
]
```

#### 方案5: 修复EventBusFactory初始化

**问题根源**: 工厂类初始化publisher/subscriber为None，运行时失败

**执行步骤**:
1. 修改 `EventBusFactory.__init__` 接受真实组件注入
2. 实现单例组件复用机制
3. 添加运行时检查防止None访问

**修复代码**:
```python
class EventBusFactory:
    def __init__(
        self,
        redis_client: RedisClient | None = None,
        rabbitmq_config: RabbitMQConfig | None = None,
    ):
        self._router = ChannelRouter()
        self._redis_publisher = RedisPublisher(redis_client) if redis_client else None
        self._redis_subscriber = RedisSubscriber(redis_client) if redis_client else None
        self._rabbitmq_publisher = RabbitMQPublisher(rabbitmq_config) if rabbitmq_config else None

    def create_redis_bus(self) -> RedisEventBus:
        if self._redis_publisher is None or self._redis_subscriber is None:
            raise RuntimeError("Redis client not configured")
        return RedisEventBus(
            publisher=self._redis_publisher,
            subscriber=self._redis_subscriber,
            router=self._router,
        )
```

#### 方案6: 统一EventPublisher Protocol

**问题根源**: `InMemoryEventPublisher` 与 `EventPublisher` 接口不一致

**执行步骤**:
1. 统一为单一 `EventPublisher` Protocol
2. `InMemoryEventBus` 实现异步 `publish()` 返回 `PublishResult`

**统一接口**:
```python
class EventPublisher(Protocol):
    """统一事件发布端口"""
    async def publish(self, event: DomainEvent) -> PublishResult: ...

# InMemoryEventBus 实现
class InMemoryEventBus:
    async def publish(self, event: DomainEvent) -> PublishResult:
        for handler in self._handlers:
            await handler(event)
        return PublishResult(success=True, event_id=str(event.event_id))
```

#### 方案7: 统一存储层端口

**问题根源**: 存储层级端口语义重叠（VectorStorage/L3VectorPort, GraphManager/L5GraphPort）

**执行步骤**:
1. L3层统一为 `L3VectorPort`，废弃 `VectorStorage`
2. L5层统一为 `L5GraphPort`，废弃 `GraphManager`/`GraphStorage`
3. `QdrantCollectionManager` 声明实现 `L3VectorPort`

**清理后的端口层次**:
| 层级 | 端口 | 状态 |
|------|------|------|
| L0 | `L0StoragePort` | 保留 |
| L1 | `L1CachePort` | 保留 |
| L2 | `L2MetadataRepositoryPort`, `L2ChangeHistoryRepositoryPort`, `L2GroupMemberRepositoryPort` | 保留 |
| L3 | `L3VectorPort` | 统一，废弃 `VectorStorage` |
| L4 | `L4ObjectPort` | 保留 |
| L5 | `L5GraphPort` | 统一，废弃 `GraphManager`/`GraphStorage` |

### 修复优先级

| 优先级 | P0-ID | 修复内容 |
|--------|-------|----------|
| P0 | P0-1, P0-2, P0-3, P0-4 | 删除服务内本地Protocol定义 |
| P0 | P0-10, P0-11, P0-12 | 修复EventBusFactory初始化 |
| P0 | P0-5, P0-6 | 修复接口不一致和事件发布缺失 |
| P0 | P0-7, P0-8, P0-9 | 补全导出完整性 |
| P1 | P0-13 | 统一EventPublisher Protocol |
| P2 | P0-14, P0-15, P0-16, P0-17 | 清理冗余接口 |

---

*第1轮审查完成，共发现17个P0问题，制定7套系统解决方案*
