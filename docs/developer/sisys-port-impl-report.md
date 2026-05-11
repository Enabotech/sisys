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
