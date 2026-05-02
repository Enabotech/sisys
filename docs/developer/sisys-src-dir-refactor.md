# SISYS 全局目录结构重构方案 (SISYS-GLOBAL-DIR-REFACTOR)

## 文档信息

| 字段 | 值 |
|------|-----|
| 文档编号 | SISYS-GLOBAL-DIR-REFACTOR |
| 版本 | v2.0 |
| 日期 | 2026-05-02 |
| 状态 | 待评审 |
| 关联 Story | Epic 20 架构重构 |

---

## 1. 背景与约束

### 1.1 架构约束 (DDD + EVD + Hexagonal)

| 约束 | 说明 |
|------|------|
| **领域层零外部依赖** | `src/domain/` 仅使用 Python 标准库 (uuid, dataclasses, datetime, enum, abc, typing, logging, json) |
| **六边形架构** | Domain 层定义 Port 接口，Infrastructure 层实现 |
| **EVD (Event-Driven)** | 领域事件与事件基础设施分离 |
| **四层架构** | Domain → Application → Infrastructure → Interfaces |
| **依赖倒置** | Domain/Application 定义接口，Infrastructure 实现接口 |

### 1.2 当前结构问题

| 问题 | 描述 |
|------|------|
| **目录命名不准确** | `domain/repositories/` 实际是 Port 接口，应为 `domain/ports/` |
| **事件基础设施混入领域** | `publisher.py`, `listener.py`, `store.py` 是技术实现，不是领域概念 |
| **Protocol 定义错位** | 纯接口（`AuditService`, `CompressorService` 等）混入 `domain/services/`，应属应用层 |
| **序列化职责混乱** | `DomainEvent.to_dict()/from_dict()` 在领域层，应属适配器 |
| **异常定义分散** | `MemoryNotFoundError` 定义在 `memory_service.py` 中 |
| **应用层混乱** | `application/events/adapters.py` 使用 pydantic，需审查 |

---

## 2. 当前结构全景

### 2.1 文件统计

```
src/
├── domain/          # 60+ files: entities, events, repositories, services, value_objects, exceptions
├── application/    # 5 files: events, services, use_cases
├── infrastructure/ # 100+ files: audit, config, external_services, messaging, monitoring, routing, scheduler, security, storage, utils, workflow
└── interfaces/     # 16 files: api, cli, event_listeners
```

### 2.2 Domain 层详细分类

#### 2.2.1 entities/ — ✅ 正确（9 files）

| 文件 | 定义 | 架构 |
|------|------|------|
| agent.py | Agent 实体, AgentRole/AgentStatus 枚举 | ✅ |
| checkpoint.py | Checkpoint 实体, CorrectionRecord, CheckpointStatus/RecoveryMode 枚举 | ✅ |
| checkpoint_snapshot.py | CheckpointSnapshot frozen dataclass | ✅ |
| document.py | Document 实体, DocumentType/ParseStatus 枚举, DocumentVersion | ✅ |
| memory_change_history.py | MemoryChangeHistory 实体 | ✅ |
| memory_metadata.py | MemoryMetadata 实体 | ✅ |
| routing_decision_log.py | RoutingDecisionLog 实体 | ✅ |
| strategic_plan.py | StrategicPlan 实体, BLMPhase/PlanStatus 枚举 | ✅ |
| tool.py | Tool 实体, ToolStatus/ToolCategory 枚举 | ✅ |

#### 2.2.2 events/ — ⚠️ 混合基础设施（20 files）

| 文件 | 定义 | 应在 |
|------|------|------|
| agent_events.py | AgentDecided | domain/events/ ✅ |
| audit_events.py | AuditEvent, AuditActionType | domain/events/ ✅ |
| auto_execute_events.py | AutoExecuted | domain/events/ ✅ |
| auto_route_events.py | AutoRouted | domain/events/ ✅ |
| auto_trigger_events.py | AutoTriggered | domain/events/ ✅ |
| base.py | DomainEvent 基类（带序列化） | domain/events/（移除序列化）|
| checkpoint_events.py | CheckpointReached, CheckpointRecovered | domain/events/ ✅ |
| compliance_events.py | MFAChallengeIssuedEvent 等 | domain/events/ ✅ |
| correction_events.py | CorrectionApproved | domain/events/ ✅ |
| document_events.py | DocumentProcessed | domain/events/ ✅ |
| enums.py | DeviationType/DeviationLevel/CorrectionType/IsolationLevel/RecoveryMode | domain/events/ ✅ |
| heartbeat_events.py | HeartbeatTriggered | domain/events/ ✅ |
| isolation_events.py | IsolationLevelSwitched | domain/events/ ✅ |
| memory_events.py | MemoryChanged | domain/events/ ✅ |
| planning_events.py | StrategicDeviationWarning | domain/events/ ✅ |
| routing_events.py | RoutingDecided | domain/events/ ✅ |
| tool_events.py | ToolExecuted | domain/events/ ✅ |
| publisher.py | EventPublisher ABC | infrastructure/messaging/ ❌ |
| listener.py | EventListener, InMemoryEventListener, EventListenerAsync | infrastructure/messaging/ ❌ |
| store.py | EventStore ABC | infrastructure/events/ ❌ |
| publish_result.py | PublishResult dataclass | infrastructure/messaging/ ❌ |

#### 2.2.3 repositories/ → ports/ — 重命名（12 files）

| 文件 | 定义 | 类型 |
|------|------|------|
| base.py | BaseRepository Generic ABC | Port ✅ |
| graph_storage.py | GraphManager, GraphStorage ABC | Port ✅ |
| health_check.py | HealthCheckPort ABC | Port ✅ |
| index_manager.py | IndexManagerPort ABC | Port ✅ |
| integrity.py | IntegrityPort ABC | Port ✅ |
| l0_storage.py | L0StoragePort ABC | Port ✅ |
| memory_repository.py | MemoryMetadataRepositoryProtocol, MemoryChangeHistoryRepositoryProtocol | Port ✅ |
| outbox.py | OutboxRepository ABC | Port ✅ |
| session_storage.py | SessionStorage Protocol | Port ✅ |
| storage.py | ObjectStorageRepository ABC | Port ✅ |
| unit_of_work.py | UnitOfWork ABC | Port ✅ |
| vector_storage.py | CollectionManager, VectorStorage Protocol | Port ✅ |

#### 2.2.4 services/ — 混合 Protocol 与具体服务（14 files）

| 文件 | 定义 | 类型 | 目标位置 |
|------|------|------|----------|
| audit_service.py | AuditService Protocol | Protocol ❌ | application/ports/ |
| auth_service.py | AuthService Protocol | Protocol ❌ | application/ports/ |
| auto_execute_service.py | AutoExecuteService (concrete) + SandboxExecutorProtocol/SnapshotRepositoryProtocol (nested) | **具体服务** ✅ | domain/services/ |
| auto_route_service.py | AutoRouteService (concrete) + EventPublisherProtocol/HashRouterProtocol/SemanticRouterProtocol (nested) | **具体服务** ✅ | domain/services/ |
| auto_trigger_service.py | AutoTriggerService | **具体服务** ✅ | domain/services/ |
| compressor_service.py | CompressorService ABC, CompressionResult | Protocol ❌ | application/ports/ |
| memory_service.py | MemoryService, Memory, MemoryVersionConflictError, MemoryNotFoundError, Request dataclasses | **具体服务** ✅ | domain/services/ |
| permission_service.py | PermissionService Protocol | Protocol ❌ | application/ports/ |
| public_blackboard.py | PublicBlackboard Protocol | Protocol ❌ | application/ports/ |
| semantic_cache.py | SemanticCache Protocol | Protocol ❌ | application/ports/ |
| text_extractor_service.py | TextExtractorService ABC, ExtractionResult | Protocol ❌ | application/ports/ |
| udmr_router.py | UDMRouter (concrete) + HealthChecker/RouterConfig Protocols (nested) | **具体服务** ✅ | domain/services/ |

#### 2.2.5 value_objects/ — ✅ 正确（2 files）

| 文件 | 定义 |
|------|------|
| auto_trigger_context.py | AutoTriggerContext frozen dataclass |
| routing_decision.py | RoutingDecision dataclass |

#### 2.2.6 exceptions/ — ⚠️ 空目录

| 文件 | 定义 |
|------|------|
| __init__.py | 空文件 |

---

## 3. 目标结构

### 3.1 最终目录树

```
src/
├── domain/                         # ✅ 领域层（零外部依赖）
│   ├── entities/                   # 9 files — 领域实体
│   ├── events/                     # 14 files — 领域事件（无基础设施）
│   ├── ports/                      # 12 files — 端口接口（repositories/ 重命名）
│   ├── services/                   # 5 files — 具体业务逻辑
│   ├── value_objects/              # 2 files — 值对象
│   └── exceptions/                 # 2 files — 领域异常
│
├── application/                     # ✅ 应用层（用例编排）
│   ├── ports/                      # 7 files — 应用层 Protocol（移动自 domain/services/）
│   ├── services/                   # 1 file — SixLayerStorageCoordinator
│   ├── events/                     # 1 file — adapters.py（需审查 pydantic）
│   └── use_cases/                  # 3 files — 用例
│
├── infrastructure/                  # ✅ 基础设施层
│   ├── audit/                      # 审计服务
│   ├── config/                     # 配置（需审查 sovereignty.py 跨模块导入）
│   ├── external_services/          # 外部服务适配器
│   ├── messaging/                 # 消息基础设施（含 event_store 实现）
│   ├── monitoring/                # 监控
│   ├── routing/                   # 路由实现（需审查 local_model_health.py）
│   ├── scheduler/                  # 调度器
│   ├── security/                   # 安全服务
│   ├── storage/                   # 存储适配器（L0-L5）
│   ├── utils/                     # 工具
│   └── workflow/                   # 工作流
│
└── interfaces/                      # ✅ 接口层
    ├── api/                        # FastAPI 端点
    ├── cli/                        # Typer 命令
    └── event_listeners/           # 事件监听器实现
```

---

## 4. 详细迁移方案

### 4.1 Domain 层迁移

#### 4.1.1 重命名 repositories/ → ports/

```bash
mv src/domain/repositories/ src/domain/ports/
```

#### 4.1.2 创建 domain/exceptions/

```bash
# 创建 memory_exceptions.py
cat > src/domain/exceptions/memory_exceptions.py << 'EOF'
"""Memory domain exceptions."""

class MemoryNotFoundError(Exception):
    """Raised when a memory entity is not found."""
    pass

class MemoryVersionConflictError(Exception):
    """Raised when memory version conflict occurs during update."""
    pass
EOF

# 重写 __init__.py
cat > src/domain/exceptions/__init__.py << 'EOF'
"""Domain exceptions."""

from src.domain.exceptions.memory_exceptions import (
    MemoryNotFoundError,
    MemoryVersionConflictError,
)

__all__ = [
    "MemoryNotFoundError",
    "MemoryVersionConflictError",
]
EOF
```

#### 4.1.3 修改 domain/events/base.py

移除 `to_dict()` / `from_dict()` 序列化方法，保留纯业务属性。

#### 4.1.4 移动事件基础设施

```bash
mkdir -p src/infrastructure/messaging/

# 注意：infrastructure/messaging/event_store.py 已存在（237行实现）
# 移动 domain/events/store.py（66行 ABC接口）到 infrastructure/messaging/event_store_domain.py
# 并更新 infrastructure/messaging/event_store.py 的导入

mv src/domain/events/publisher.py src/infrastructure/messaging/event_publisher.py
mv src/domain/events/listener.py src/infrastructure/messaging/event_listener.py
mv src/domain/events/store.py src/infrastructure/messaging/event_store_domain.py
mv src/domain/events/publish_result.py src/infrastructure/messaging/publish_result.py
```

#### 4.1.5 移动 Protocol 文件到 application/ports/

```bash
mkdir -p src/application/ports/

mv src/domain/services/audit_service.py src/application/ports/audit_port.py
mv src/domain/services/auth_service.py src/application/ports/auth_port.py
mv src/domain/services/permission_service.py src/application/ports/permission_port.py
mv src/domain/services/public_blackboard.py src/application/ports/public_blackboard_port.py
mv src/domain/services/semantic_cache.py src/application/ports/semantic_cache_port.py
mv src/domain/services/compressor_service.py src/application/ports/compressor_port.py
mv src/domain/services/text_extractor_service.py src/application/ports/text_extractor_port.py
```

---

### 4.2 Domain 层最终状态

#### 4.2.1 domain/entities/ — 无变化（9 files）

```
agent.py
checkpoint.py
checkpoint_snapshot.py
document.py
memory_change_history.py
memory_metadata.py
routing_decision_log.py
strategic_plan.py
tool.py
```

#### 4.2.2 domain/events/ — 移除基础设施（14 files）

| 文件 | 说明 |
|------|------|
| base.py | DomainEvent（移除序列化） |
| enums.py | 领域枚举 |
| agent_events.py | AgentDecided |
| audit_events.py | AuditEvent |
| auto_execute_events.py | AutoExecuted |
| auto_route_events.py | AutoRouted |
| auto_trigger_events.py | AutoTriggered |
| checkpoint_events.py | CheckpointReached, CheckpointRecovered |
| compliance_events.py | MFAChallengeIssuedEvent 等 |
| correction_events.py | CorrectionApproved |
| document_events.py | DocumentProcessed |
| heartbeat_events.py | HeartbeatTriggered |
| isolation_events.py | IsolationLevelSwitched |
| memory_events.py | MemoryChanged |
| planning_events.py | StrategicDeviationWarning |
| routing_events.py | RoutingDecided |
| tool_events.py | ToolExecuted |

#### 4.2.3 domain/ports/ — 重命名自 repositories/（12 files）

| 文件 | 定义 |
|------|------|
| base.py | BaseRepository |
| graph_storage.py | GraphManager, GraphStorage |
| health_check.py | HealthCheckPort |
| index_manager.py | IndexManagerPort |
| integrity.py | IntegrityPort |
| l0_storage.py | L0StoragePort |
| memory_repository.py | MemoryMetadataRepositoryProtocol, MemoryChangeHistoryRepositoryProtocol |
| outbox.py | OutboxRepository |
| session_storage.py | SessionStorage |
| storage.py | ObjectStorageRepository |
| unit_of_work.py | UnitOfWork |
| vector_storage.py | CollectionManager, VectorStorage |

#### 4.2.4 domain/services/ — 仅保留具体服务（5 files）

| 文件 | 定义 |
|------|------|
| memory_service.py | MemoryService, Memory, Request/Response dataclasses |
| auto_trigger_service.py | AutoTriggerService |
| auto_execute_service.py | AutoExecuteService, SandboxExecutorProtocol, SnapshotRepositoryProtocol |
| auto_route_service.py | AutoRouteService, EventPublisherProtocol, HashRouterProtocol, SemanticRouterProtocol |
| udmr_router.py | UDMRouter, HealthChecker, RouterConfig |

#### 4.2.5 domain/value_objects/ — 无变化（2 files）

| 文件 | 定义 |
|------|------|
| auto_trigger_context.py | AutoTriggerContext |
| routing_decision.py | RoutingDecision |

#### 4.2.6 domain/exceptions/ — 新建（2 files）

| 文件 | 定义 |
|------|------|
| __init__.py | 导出 MemoryNotFoundError, MemoryVersionConflictError |
| memory_exceptions.py | 异常定义 |

---

### 4.3 Application 层最终状态

#### 4.3.1 application/ports/ — 移动自 domain/services/（7 files）

| 文件 | 原位置 | 定义 |
|------|--------|------|
| audit_port.py | domain/services/audit_service.py | AuditService Protocol |
| auth_port.py | domain/services/auth_service.py | AuthService Protocol |
| permission_port.py | domain/services/permission_service.py | PermissionService Protocol |
| public_blackboard_port.py | domain/services/public_blackboard.py | PublicBlackboard Protocol |
| semantic_cache_port.py | domain/services/semantic_cache.py | SemanticCache Protocol |
| compressor_port.py | domain/services/compressor_service.py | CompressorService ABC |
| text_extractor_port.py | domain/services/text_extractor_service.py | TextExtractorService ABC |

#### 4.3.2 application/services/ — 无变化（1 file）

| 文件 | 定义 |
|------|------|
| six_layer_storage_coordinator.py | SixLayerStorageCoordinator |

#### 4.3.3 application/events/ — adapters.py 处理方案

| 文件 | 问题 | 处理方案 |
|------|------|----------|
| adapters.py | 使用 pydantic (TypeAdapter) | **审查后保留** — pydantic 用于应用层 DTO 转换，在边界处使用可接受 |

**审查标准**:
- 验证 pydantic 仅用于外部 API 边界
- 确认不属于领域层逻辑
- 如果内部只用 domain entities/values，应移除 pydantic

**验收条件**:
- [ ] adapters.py 不导入 domain 实体以外的外部依赖
- [ ] pydantic 使用仅限于 DTO 转换

#### 4.3.4 application/use_cases/ — 无变化（3 files）

| 文件 | 定义 |
|------|------|
| document_processing.py | DocumentProcessingUseCase |
| text_processing/l1_compressor.py | L1Compressor |
| text_processing/l1_text_extractor.py | L1TextExtractor |

---

### 4.4 Infrastructure 层最终状态

#### 4.4.1 infrastructure/messaging/ — 包含移动的事件基础设施

```
__init__.py
adapters/
  __init__.py
  event_outbox_adapter.py
  sqlalchemy_event_outbox_adapter.py
channel_router.py
dual_channel_event_bus.py
event_bus.py
event_bus_config_loader.py
event_bus_factory.py
event_store.py              # 已存在（实现）
event_store_domain.py       # 从 domain/events/store.py 移动（ABC接口）
event_listener.py           # 从 domain/events/listener.py 移动
event_publisher.py          # 从 domain/events/publisher.py 移动
message_serializer.py
outbox/
  __init__.py
  dead_letter_queue.py
  inmemory_outbox.py
  outbox.py
  outbox_processor.py
  outbox_repository.py
  postgres_dead_letter_queue.py
publish_result.py           # 从 domain/events/publish_result.py 移动
rabbitmq_consumer.py
rabbitmq_event_bus.py
rabbitmq_listener.py
rabbitmq_publisher.py
redis_event_bus.py
redis_publisher.py
redis_subscriber.py
retry/
  __init__.py
  checker.py
  dual_idempotency_checker.py
  redis_retry_queue.py
  retry_policy.py
unit_of_work/
  postgresql_unit_of_work.py
```

#### 4.4.2 infrastructure/events/ — 新目录

```
event_store.py  # 从 domain/events/store.py 移动
```
**注意**: `event_store.py` (237行) 是已存在的实现，`event_store_domain.py` (66行) 是 ABC 接口，应合并或重命名。

#### 4.4.3 其他 infrastructure/ 子目录 — 无变化

| 目录 | 文件数 | 说明 |
|------|--------|------|
| audit/ | 4 | 审计服务 |
| config/ | 14 | 配置（需审查 sovereignty.py 跨模块导入） |
| external_services/ | 2 | 外部服务 |
| monitoring/ | 4 | 监控 |

#### 4.4.4 infrastructure/routing/ 审查方案

| 文件 | 问题 | 处理方案 |
|------|------|----------|
| local_model_health.py | **已废弃** — 仅做向后兼容导入 | **保留但标记废弃** — 不再新增使用 |

**审查标准**:
- `local_model_health.py` 是兼容性别名模块，实际实现为 `OllamaHealthAdapter`
- 已有 `HealthCheckPort` 定义在 `domain/ports/health_check.py`
- 所有新代码应直接使用 `HealthCheckPort` 接口

**验收条件**:
- [ ] 新代码不导入 `local_model_health.LocalModelHealth`
- [ ] 使用 `domain.ports.health_check.HealthCheckPort` 替代
- [ ] 后续 Story 可完全移除 local_model_health.py

#### 4.4.5 infrastructure/config/ 审查方案

| 文件 | 问题 | 处理方案 |
|------|------|----------|
| sovereignty.py | 导入 `infrastructure.security.models` | **审查** — 配置层不应依赖安全服务层 |

**审查标准**:
- `infrastructure/config/sovereignty.py` 导入 `infrastructure/security/models.py`
- 这是 infrastructure 内部跨层导入，应重构为配置内聚

**验收条件**:
- [ ] `infrastructure/config/` 不导入 `infrastructure/security/`
- [ ] 配置类自包含，不依赖其他 infrastructure 子目录
| routing/ | 5 | 路由（需审查 local_model_health.py 已废弃） |
| scheduler/ | 1 | 调度器 |
| security/ | 21 | 安全服务 |
| storage/ | 30+ | 存储适配器 |
| utils/ | 1 | 工具 |
| workflow/ | 1 | 工作流 |

---

#### 4.5 Interfaces 层

| 目录 | 文件数 | 说明 |
|------|--------|------|
| api/ | 6 | FastAPI 端点 |
| cli/ | 3 | Typer 命令 |
| event_listeners/ | 4 | 事件监听器实现 |
| event_publisher.py | 1 | 接口层事件发布器 |
| event_subscriber.py | 1 | 接口层事件订阅器 |

**注意**: `interfaces/event_publisher.py` 和 `interfaces/event_subscriber.py` 是接口层实现，应保留在 interfaces/ 层。

---

## 5. 影响范围

### 5.1 文件操作统计

| 操作 | 数量 |
|------|------|
| 重命名目录 | 1 (`repositories/` → `ports/`) |
| 移动文件 | 15 |
| 新建文件 | 2 |
| 修改文件 | 1 (`base.py` 移除序列化) |

### 5.2 需更新的导入路径

| 层级 | 影响文件数（估计） |
|------|-------------------|
| domain/ | ~25 |
| application/ | ~15 |
| infrastructure/ | ~40 |
| interfaces/ | ~20 |
| tests/ | ~50 |
| **总计** | **~150 files** |

---

## 6. 验收标准

- [ ] `domain/repositories/` 目录重命名为 `domain/ports/`
- [ ] 7 个 Protocol 文件从 `domain/services/` 移至 `application/ports/`
- [ ] 4 个事件基础设施文件从 `domain/events/` 移至 `infrastructure/`
- [ ] `DomainEvent` 类不包含 `to_dict()` / `from_dict()` 方法
- [ ] `domain/exceptions/` 包含 `MemoryNotFoundError` 和 `MemoryVersionConflictError`
- [ ] 所有测试通过
- [ ] `mypy .` 无错误
- [ ] `ruff check .` 无错误

---

## 7. 六边形架构图

```
                        ┌─────────────────────────────────────────────────────────┐
                        │                    interfaces/                       │
                        │   FastAPI API    CLI Commands    Event Listeners      │
                        └────────────────────────┬────────────────────────────────┘
                                                 │
                        ┌────────────────────────▼────────────────────────────────┐
                        │                   application/                          │
                        │  ┌─────────────────────────────────────────────────┐    │
                        │  │           Use Cases / Services                  │    │
                        │  │   SixLayerStorageCoordinator                   │    │
                        │  └─────────────────────────────────────────────────┘    │
                        │  ┌─────────────────────────────────────────────────┐    │
                        │  │      Application Ports (Protocols)             │    │
                        │  │  AuditService  AuthService  CompressorService   │    │
                        │  └─────────────────────────────────────────────────┘    │
                        └────────────────────────┬────────────────────────────────┘
                                                 │
┌────────────────────────────────────────────────┼────────────────────────────────────────────────┐
│                    domain/                      │                                                     │
│  ┌─────────────────────────────────────────────▼─────────────────────────────────────────────┐       │
│  │                              Ports (interfaces)                                             │       │
│  │  HealthCheckPort  IntegrityPort  L0StoragePort  VectorStorage  GraphStorage  ...          │       │
│  └─────────────────────────────────────────────┬─────────────────────────────────────────────┘       │
│                                                │                                                         │
│  ┌─────────────────────────────────────────────▼─────────────────────────────────────────────┐       │
│  │                          Entities / Events / Value Objects                                   │       │
│  │   Agent  Checkpoint  Document  MemoryMetadata  StrategicPlan  (Domain Events)  (VO)         │       │
│  └─────────────────────────────────────────────┬─────────────────────────────────────────────┘       │
│                                                │                                                         │
│  ┌─────────────────────────────────────────────▼─────────────────────────────────────────────┐       │
│  │                          Domain Services                                                   │       │
│  │              MemoryService  AutoTriggerService  UDMRouter                                  │       │
│  └─────────────────────────────────────────────┬─────────────────────────────────────────────┘       │
└────────────────────────────────────────────────┼────────────────────────────────────────────────────┘
                                                 │
┌────────────────────────────────────────────────┼────────────────────────────────────────────────────┐
│               infrastructure/                  │                                                     │
│  ┌────────────────▼────────────────────────────▼─────────────────────────────────────────────┐       │
│  │                              Adapters (implement Ports)                                   │       │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │       │
│  │  │PostgreSQL│  │  Redis  │  │  MinIO  │  │ Qdrant  │  │  Neo4j  │  │  File   │            │       │
│  │  │   Repo  │  │  Cache  │  │ Object  │  │ Vector  │  │  Graph  │  │  L0     │            │       │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘            │       │
│  └────────────────────────────┬───────────────────────────────────────────────────────────────┘       │
│                               │                                                               │
│  ┌────────────────────────────▼───────────────────────────────────────────────────────────────┐       │
│  │                     Infrastructure Services                                                │       │
│  │  Routing  Security  Audit  Monitoring  Scheduler  Messaging  Config                        │       │
│  └────────────────────────────────────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. 关键原则总结

| 原则 | 说明 |
|------|------|
| **领域层零外部依赖** | domain/ 仅用 Python 标准库 |
| **Port 接口在 domain** | 接口定义与实现分离，依赖倒置 |
| **事件基础设施在 infrastructure** | 发布-订阅是技术机制，不是领域概念 |
| **Protocol 定义分离** | 纯接口移到 application/ports/ |
| **序列化是适配器责任** | DomainEvent 不含 to_dict/from_dict |
| **异常集中定义** | domain/exceptions/ 统一管理领域异常 |
| **目录命名准确** | repositories/ → ports/（反映本质） |

---

## 9. 附录

### A. 移动文件清单

| 原路径 | 目标路径 | 说明 |
|--------|----------|------|
| domain/repositories/ | domain/ports/ | 目录重命名 |
| domain/events/publisher.py | infrastructure/messaging/event_publisher.py | 事件基础设施 |
| domain/events/listener.py | infrastructure/messaging/event_listener.py | 事件基础设施 |
| domain/events/store.py | infrastructure/messaging/event_store_domain.py | 事件基础设施（ABC接口） |
| domain/events/publish_result.py | infrastructure/messaging/publish_result.py | 事件基础设施 |
| domain/services/audit_service.py | application/ports/audit_port.py | Protocol |
| domain/services/auth_service.py | application/ports/auth_port.py | Protocol |
| domain/services/permission_service.py | application/ports/permission_port.py | Protocol |
| domain/services/public_blackboard.py | application/ports/public_blackboard_port.py | Protocol |
| domain/services/semantic_cache.py | application/ports/semantic_cache_port.py | Protocol |
| domain/services/compressor_service.py | application/ports/compressor_port.py | Protocol |
| domain/services/text_extractor_service.py | application/ports/text_extractor_port.py | Protocol |

**注意**: `infrastructure/messaging/event_store.py` (237行) 已存在，是实现文件。移动的是 ABC 接口 `store.py` (66行)，重命名为 `event_store_domain.py`。

### B. 新建文件清单

| 路径 | 内容 |
|------|------|
| domain/exceptions/__init__.py | 导出异常 |
| domain/exceptions/memory_exceptions.py | MemoryNotFoundError, MemoryVersionConflictError |

### C. 修改文件清单

| 路径 | 修改内容 |
|------|----------|
| domain/events/base.py | 移除 to_dict()/from_dict() 序列化方法 |
| domain/services/memory_service.py | 从 domain/exceptions/ 导入异常 |

### D. 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| Port 接口 | `XxxPort` 或 `XxxProtocol` | `HealthCheckPort`, `IntegrityPort` |
| Repository 接口 | `XxxRepositoryProtocol` | `MemoryMetadataRepositoryProtocol` |
| 领域服务 | `XxxService` | `MemoryService`, `AutoRouteService` |
| 领域异常 | `XxxError` | `MemoryNotFoundError` |
| 值对象 | `XxxContext` / `XxxDecision` | `AutoTriggerContext`, `RoutingDecision` |
| 事件基础设施 | `XxxPublisher` / `XxxListener` | `EventPublisher`, `EventListener` |
