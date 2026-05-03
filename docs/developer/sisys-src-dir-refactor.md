# SISYS 全局目录结构重构方案 (SISYS-GLOBAL-DIR-REFACTOR)

## 文档信息

| 字段 | 值 |
|------|-----|
| 文档编号 | SISYS-GLOBAL-DIR-REFACTOR |
| 版本 | v2.18 |
| 日期 | 2026-05-03 |
| 状态 | 评审通过 |
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
| **事件基础设施混入领域** | `publisher.py`, `listener.py`, `event_store.py` 是技术实现，不是领域概念 |
| **Protocol 定义错位** | 纯接口（`AuditService`, `CompressorService` 等）混入 `domain/services/`，应属应用层 |
| **序列化职责混乱** | `DomainEvent`、`CheckpointSnapshot` 等直接在领域层实现序列化，缺乏统一抽象 |
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

#### 2.2.2 events/ — ⚠️ 混合基础设施（21 files → 18 files 改造后）

| 文件 | 定义 | 应在 |
|------|------|------|
| agent_events.py | AgentDecided | domain/events/ ✅ |
| audit_events.py | AuditEvent, AuditActionType | domain/events/ ✅ |
| auto_execute_events.py | AutoExecuted | domain/events/ ✅ |
| auto_route_events.py | AutoRouted | domain/events/ ✅ |
| auto_trigger_events.py | AutoTriggered | domain/events/ ✅ |
| base.py | DomainEvent 基类（带序列化） | domain/events/（移除序列化） ✅ |
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
| event_store.py | EventStore ABC | domain/events/ ✅（Port 接口，保留在 domain） |
| publish_result.py | PublishResult dataclass | infrastructure/messaging/ ❌（虽为纯数据类，但因与 EventPublisher 强耦合而移动） |

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

#### 2.2.4 services/ — 混合 Protocol 与具体服务（12 files）

| 文件 | 定义 | 类型 | 目标位置 |
|------|------|------|----------|
| audit_service.py | AuditService Protocol | Protocol ❌ | application/ports/ |
| auth_service.py | AuthService Protocol | Protocol ❌ | application/ports/ |
| auto_execute_service.py | AutoExecuteService + SandboxExecutorProtocol/SnapshotRepositoryProtocol (nested, stay) | **具体服务** ✅ | domain/services/ |
| auto_route_service.py | AutoRouteService + EventPublisherProtocol/HashRouterProtocol/SemanticRouterProtocol (nested, stay) | **具体服务** ✅ | domain/services/ |
| auto_trigger_service.py | AutoTriggerService | **具体服务** ✅ | domain/services/ |
| compressor_service.py | CompressorService ABC | Protocol ❌ | application/ports/ |
| memory_service.py | MemoryService, Memory, MemoryVersionConflictError, MemoryNotFoundError | **具体服务** ✅ | domain/services/ |
| permission_service.py | PermissionService Protocol | Protocol ❌ | application/ports/ |
| public_blackboard.py | PublicBlackboard Protocol | Protocol ❌ | application/ports/ |
| semantic_cache.py | SemanticCache Protocol | Protocol ❌ | application/ports/ |
| text_extractor_service.py | TextExtractorService ABC | Protocol ❌ | application/ports/ |
| udmr_router.py | UDMRouter + HealthChecker/RouterConfig (nested, stay) | **具体服务** ✅ | domain/services/ |

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
│   ├── events/                     # 18 files — 领域事件（移除基础设施前：21 files）
│   ├── ports/                      # 12 files — 端口接口（repositories/ 重命名）
│   ├── services/                   # 5 files — 具体业务逻辑
│   ├── value_objects/              # 2 files — 值对象（sensitive_data.py 待新建）
│   └── exceptions/                 # 2 files — 领域异常
│
├── application/                     # ✅ 应用层（用例编排）
│   ├── ports/                      # 10 files — 应用层 Protocol（7个移动 + 3个序列化框架）
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

#### 4.1.3 序列化框架重构：移除领域层序列化方法

**问题**：
- `domain/events/base.py` 的 `to_dict()/from_dict()` 违反六边形架构（领域层不应包含序列化实现）
- `domain/entities/checkpoint_snapshot.py` 的 `to_redis_hash()/from_redis_hash()` 领域层感知基础设施细节
- 各基础设施层实体重复实现相似的 `to_dict()/from_dict()` 模式

**解决方案**：采用 **Serializable Protocol** 方案

| 层级 | 职责 | 位置 |
|------|------|------|
| **Domain** | 实现 `Serializable` Protocol，提供字段元数据 | `domain/ports/serialization.py` |
| **Application** | 定义 `SerializationPort` 抽象接口 | `application/ports/serialization.py` |
| **Infrastructure** | 实现具体序列化器 | `infrastructure/serialization/*.py` |

**重构步骤**：

1. **创建 `domain/ports/serialization.py`**：定义 `Serializable` Protocol 和 `SerializationField`
2. **创建 `application/ports/serialization.py`**：定义 `SerializationPort` 抽象接口
3. **改造领域实体**：移除序列化方法，实现 `Serializable` Protocol
4. **基础设施层实现序列化器**：见 5.4 节

#### 4.1.4 移动事件基础设施

**说明**：`EventStore` ABC 是领域层定义的 Port 接口，应保留在 `domain/events/` 目录，不应移动到 infrastructure。

```bash
mkdir -p src/infrastructure/messaging/

# 注意：infrastructure/messaging/event_store.py 已存在（PostgreSQLEventStore 实现）
# 这是 PostgreSQLEventStore 实现，不是 ABC 接口

# 以下文件移动到 infrastructure/messaging/
mv src/domain/events/publisher.py src/infrastructure/messaging/event_publisher.py
mv src/domain/events/listener.py src/infrastructure/messaging/event_listener.py
mv src/domain/events/publish_result.py src/infrastructure/messaging/publish_result.py

# EventStore ABC 保留在 domain/events/event_store.py（是领域层 Port 定义）
# 不要移动 event_store.py 到 infrastructure/
```

**EventStore 接口的正确位置**：

| 文件 | 位置 | 原因 |
|------|------|------|
| `EventStore` ABC | `domain/events/event_store.py` | Port 接口定义，与 DomainEvent 紧密相关，保持内聚 |
| `InMemoryEventStore` | `tests/` | 测试实现 |
| `PostgreSQLEventStore` | `infrastructure/messaging/event_store.py` | 基础设施实现 |

**说明**：EventStore 放在 `domain/events/` 而非 `domain/ports/`，是因为它与 DomainEvent 紧密耦合（事件溯源核心概念），保持内聚性。

**关键约束**：
- Port 接口（ABC）在 domain 层
- 具体实现在 infrastructure 层
- `PostgreSQLEventStore` 实现中调用 `DomainEvent.from_dict()` 的问题需通过序列化器解决（见 5.8 节）

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

#### 4.2.2 domain/events/ — 移除基础设施（18 files）

| 文件 | 说明 |
|------|------|
| base.py | DomainEvent（移除序列化，实现 Serializable Protocol） |
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
| event_store.py | EventStore ABC（Port 接口，保留在 domain） |

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

#### 4.3.3 application/events/ — adapters.py 审查结论

| 文件 | 结论 |
|------|------|
| adapters.py | **保留** — pydantic TypeAdapter 用于 JSON 边界转换，在应用层使用可接受 |

**审查结论**:
- pydantic 仅用于 `dict ↔ JSON` 转换（应用层边界）
- 不在领域层使用，符合架构约束
- 符合"序列化是适配器责任"原则

**验收条件**:
- [ ] adapters.py 不导入 domain 实体以外的外部依赖 ✅
- [ ] pydantic 使用仅限于 dict/JSON 转换 ✅

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
event_store.py              # PostgreSQLEventStore 实现
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

---

#### 4.4.2 其他 infrastructure/ 子目录 — 无变化

| 目录 | 文件数 | 说明 |
|------|--------|------|
| audit/ | 4 | 审计服务 |
| config/ | 17 | 配置（需审查 sovereignty.py 跨模块导入） |
| external_services/ | 2 | 外部服务 |
| monitoring/ | 4 | 监控 |
| routing/ | 5 | 路由（需审查 local_model_health.py 已废弃） |
| scheduler/ | 1 | 调度器 |
| security/ | 20 | 安全服务 |
| storage/ | 51 | 存储适配器 |
| utils/ | 1 | 工具 |
| workflow/ | 1 | 工作流 |

#### 4.4.3 infrastructure/routing/ 审查方案

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

#### 4.4.4 infrastructure/config/ 审查方案

| 文件 | 问题 | 处理方案 |
|------|------|----------|
| sovereignty.py | 导入 `infrastructure.security.models` | **修复** — 配置层不应依赖安全服务层 |

**修正方案**（见第5章）:
- 新建 `domain/value_objects/sensitive_data.py`
- 重命名 `security/models.py` → `security/value_objects.py`
- 更新 `sovereignty.py` 导入路径

#### 4.4.5 infrastructure/security/ 命名修正

| 文件 | 问题 | 处理方案 |
|------|------|----------|
| models.py | 文件名暗示 SQLAlchemy 模型，实际是纯值对象 | **重命名** → `value_objects.py` |

---

### 4.5 Interfaces 层审查

| 目录 | 文件数 | 说明 |
|------|--------|------|
| api/ | 6 | FastAPI 端点 |
| cli/ | 3 | Typer 命令 |
| event_listeners/ | 4 | 事件监听器实现 |
| event_publisher.py | 1 | 接口层事件发布器（依赖 domain.events） |
| event_subscriber.py | 1 | 接口层事件订阅器（依赖 domain.events） |

**说明**:
- `interfaces/event_publisher.py` 依赖 `DomainEvent` 和 `PublishResult`，这是允许的（interfaces → domain 方向正确）
- `PublishResult` 移动到 `infrastructure/messaging/` 后，interfaces 层仍可正常导入
- `event_publisher.py` 和 `event_subscriber.py` 是接口层抽象，不属于领域定义

---

## 5. 通用序列化框架设计（Serializable Protocol 方案）

### 5.1 架构概述

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              domain/                                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  ports/serialization.py                                        │   │
│  │  • Serializable Protocol (领域层定义)                           │   │
│  │  • SerializationField (字段元数据)                              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  领域实体实现 Serializable Protocol                              │   │
│  │  • get_serialization_type() → 类型标识符                         │   │
│  │  • get_fields() → 字段元数据列表                                 │   │
│  │  无任何序列化方法，仅持有纯业务数据                                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │ 依赖倒置
                                    │
┌─────────────────────────────────────────────────────────────────────────┐
│                           application/                                  │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  ports/serialization.py                                         │   │
│  │  • SerializationPort (抽象接口)                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  ports/serialization_rules.py                                    │   │
│  │  • StandardSerializeRules (标准类型转换规则)                    │   │
│  │  • UUID ↔ str, datetime ↔ ISO 8601, Enum ↔ value               │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  ports/type_registry.py                                          │   │
│  │  • TypeRegistry (类型注册表)                                     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │ 实现
                                    │
┌─────────────────────────────────────────────────────────────────────────┐
│                          infrastructure/                                 │
│  ┌───────────────────────┐  ┌───────────────────────┐                   │
│  │   JsonSerializer     │  │  RedisHashSerializer  │                   │
│  │   → JSON string     │  │  → dict[str, str]     │                   │
│  └───────────────────────┘  └───────────────────────┘                   │
│  ┌───────────────────────┐  ┌───────────────────────┐                   │
│  │   JsonbSerializer    │  │   DictSerializer     │                   │
│  │   → PostgreSQL JSONB │  │   → Python dict      │                   │
│  └───────────────────────┘  └───────────────────────┘                   │
└─────────────────────────────────────────────────────────────────────────┘
```

**架构要点**：
- `Serializable Protocol` 定义在 `domain/ports/`，由领域实体实现
- `SerializationPort` 定义在 `application/ports/`，由基础设施实现
- `StandardSerializeRules` 和 `TypeRegistry` 在 `application/ports/`，为序列化器提供通用规则
- 依赖方向：`domain` ← `application` ← `infrastructure`（符合六边形架构）

### 5.2 Serializable Protocol 定义（domain 层）

```python
# domain/ports/serialization.py

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SerializationField:
    """字段序列化元数据（领域层定义）"""
    name: str
    type: type
    default: Any = None
    is_enum: bool = False
    is_uuid: bool = False
    is_datetime: bool = False
    is_nested_dataclass: bool = False
    is_union: bool = False  # 支持 UnionType（如 UUID | None）


class Serializable:
    """可序列化类型协议（由领域实体实现）"""

    @classmethod
    def get_serialization_type(cls) -> str:
        """返回类型标识符，用于反序列化时路由"""
        ...

    @classmethod
    def get_fields(cls) -> list[SerializationField]:
        """返回所有需要序列化的字段元数据"""
        ...
```

### 5.2.1 SerializationPort 定义（application 层）

```python
# application/ports/serialization.py

from abc import ABC, abstractmethod
from typing import Any, TypeVar, Generic

T = TypeVar("T")


class SerializationPort(ABC, Generic[T]):
    """序列化抽象端口（应用层定义，基础设施实现）"""

    @abstractmethod
    def serialize(self, obj: T) -> Any:
        """将对象序列化为目标格式"""
        ...

    @abstractmethod
    def deserialize(self, data: Any, target_type: type[T] | str) -> T:
        """从目标格式反序列化为对象"""
        ...

    @abstractmethod
    def can_handle(self, obj_or_type: Any) -> bool:
        """判断是否能处理该类型"""
        ...
```

### 5.3 领域实体改造示例

#### 5.3.1 CheckpointSnapshot 改造

**改造前**（违反架构）：
```python
# domain/entities/checkpoint_snapshot.py（改造前）
def to_redis_hash(self) -> dict[str, str]:
    return {"snapshot_id": str(self.snapshot_id), "state_data": json.dumps(self.state_data)}

def from_redis_hash(cls, data): ...
```

**改造后**（正确架构）：
```python
# domain/entities/checkpoint_snapshot.py（改造后）

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from src.domain.ports.serialization import Serializable, SerializationField


@dataclass(frozen=True)
class CheckpointSnapshot:
    """领域实体：会话快照（无序列化逻辑）"""

    snapshot_id: UUID
    session_id: str
    stage_id: str
    state_version: int
    state_data: dict[str, Any]
    timestamp: datetime
    ttl_seconds: int = 86400

    @classmethod
    def get_serialization_type(cls) -> str:
        return "CheckpointSnapshot"

    @classmethod
    def get_fields(cls) -> list[SerializationField]:
        return [
            SerializationField("snapshot_id", UUID, is_uuid=True),
            SerializationField("session_id", str),
            SerializationField("stage_id", str),
            SerializationField("state_version", int),
            SerializationField("state_data", dict),
            SerializationField("timestamp", datetime, is_datetime=True),
            SerializationField("ttl_seconds", int, default=86400),
        ]

    def with_updated_state(self, state_data: dict[str, Any], new_version: int | None = None) -> CheckpointSnapshot:
        """创建新快照（领域逻辑，不涉及序列化）"""
        return CheckpointSnapshot(
            snapshot_id=uuid.uuid4(),
            session_id=self.session_id,
            stage_id=self.stage_id,
            state_version=new_version if new_version is not None else self.state_version + 1,
            state_data={**self.state_data, **state_data},
            timestamp=datetime.now(UTC),
            ttl_seconds=self.ttl_seconds,
        )
```

**关键变更**：
- `to_redis_hash()` / `from_redis_hash()` 方法被移除
- 改为实现 `Serializable` Protocol，提供字段元数据
- 序列化逻辑由 `RedisHashSerializer` 接管（见 5.4.2 节）

#### 5.3.2 DomainEvent 改造

**改造前**（存在问题）：
```python
# domain/events/base.py（改造前）
def to_dict(self) -> dict[str, Any]: ...
def from_dict(cls, data): ...
```

**改造后**（正确架构）：
```python
# domain/events/base.py（改造后）

import uuid
from dataclasses import MISSING, dataclass, field, fields, is_dataclass
from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import UUID

from src.domain.ports.serialization import Serializable, SerializationField


@dataclass(frozen=True)
class DomainEvent:
    """领域事件基类（无序列化逻辑）"""

    event_id: UUID = field(default_factory=uuid.uuid4)
    event_type: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    source: str = ""
    schema_version: str = "1.0.0"
    aggregate_id: UUID | None = None
    aggregate_type: str = ""
    version: int = 0
    payload: dict[str, Any] = field(default_factory=dict)
    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    _registry: ClassVar[dict[str, type["DomainEvent"]]] = {}

    @classmethod
    def get_serialization_type(cls) -> str:
        """返回 event_type 字段值作为类型标识符"""
        return cls.event_type if cls.event_type else "DomainEvent"

    @classmethod
    def get_fields(cls) -> list[SerializationField]:
        return [
            SerializationField("event_id", UUID, is_uuid=True),
            SerializationField("event_type", str),
            SerializationField("timestamp", datetime, is_datetime=True),
            SerializationField("source", str),
            SerializationField("schema_version", str),
            SerializationField("aggregate_id", UUID | None, is_uuid=True, is_union=True),
            SerializationField("aggregate_type", str),
            SerializationField("version", int),
            SerializationField("payload", dict),
            SerializationField("correlation_id", UUID | None, is_uuid=True, is_union=True),
            SerializationField("causation_id", UUID | None, is_uuid=True, is_union=True),
            SerializationField("metadata", dict),
        ]

    @classmethod
    def register(cls, event_type: str, event_class: type["DomainEvent"]) -> None:
        """注册子类用于多态反序列化"""
        cls._registry[event_type] = event_class

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """自动注册子类（向 DomainEvent._registry 和 TypeRegistry）"""
        super().__init_subclass__(**kwargs)
        if is_dataclass(cls):
            for f in fields(cls):
                if f.name == "event_type" and not f.init:
                    if f.default is not MISSING:
                        DomainEvent._registry[f.default] = cls
                        # 向 TypeRegistry 注册（使用 event_type 值作为类型标识符）
                        from src.application.ports.type_registry import TypeRegistry
                        TypeRegistry.register(f.default, cls)
                    break
```

**关键变更**：
- `to_dict()` / `from_dict()` 方法被移除
- 改为实现 `Serializable` Protocol，提供字段元数据
- 序列化逻辑由 `JsonSerializer` 接管（见 5.4.1 节）

### 5.4 序列化规则与类型注册表

#### 5.4.1 StandardSerializeRules 实现

```python
# application/ports/serialization_rules.py

from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID


class StandardSerializeRules:
    """标准类型转换规则（应用层定义）"""

    @staticmethod
    def serialize_dataclass(obj: Any) -> dict[str, Any]:
        """将 dataclass 实例序列化为字典"""
        if not is_dataclass(obj):
            raise TypeError(f"Expected dataclass, got {type(obj)}")

        result = {}
        for f in fields(obj):
            value = getattr(obj, f.name)
            result[f.name] = StandardSerializeRules._serialize_value(value)
        return result

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        """递归序列化单个值"""
        if value is None:
            return None
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, (list, tuple)):
            return [StandardSerializeRules._serialize_value(item) for item in value]
        if isinstance(value, dict):
            return {k: StandardSerializeRules._serialize_value(v) for k, v in value.items()}
        return value
```

#### 5.4.2 TypeRegistry 实现

```python
# application/ports/type_registry.py


class TypeRegistry:
    """类型注册表，用于反序列化时路由到具体类型"""

    _registry: dict[str, type] = {}

    @classmethod
    def register(cls, type_id: str, typ: type) -> None:
        """注册类型映射"""
        cls._registry[type_id] = typ

    @classmethod
    def resolve(cls, type_id: str) -> type | None:
        """根据类型标识符解析类型"""
        return cls._registry.get(type_id)

    @classmethod
    def register_from_class(cls, typ: type) -> None:
        """从类自动注册（类需实现 Serializable）"""
        if hasattr(typ, "get_serialization_type"):
            cls.register(typ.get_serialization_type(), typ)

    @classmethod
    def auto_register_domain_events(cls) -> None:
        """自动注册所有 DomainEvent 子类"""
        from src.domain.events.base import DomainEvent
        for event_type, event_class in DomainEvent._registry.items():
            cls.register(event_type, event_class)
```

### 5.5 序列化器实现（基础设施层）

#### 5.5.1 JSON 序列化器

```python
# infrastructure/serialization/json_serializer.py

import json
from dataclasses import is_dataclass
from datetime import datetime
from typing import Any, TypeVar
from uuid import UUID

from src.application.ports.serialization import SerializationPort
from src.application.ports.serialization_rules import StandardSerializeRules
from src.domain.ports.serialization import SerializationField


T = TypeVar("T")


class JsonSerializer(SerializationPort[T]):
    """JSON 字符串序列化器"""

    def __init__(self, *, indent: int | None = None, ensure_ascii: bool = False):
        self._indent = indent
        self._ensure_ascii = ensure_ascii

    def serialize(self, obj: T) -> str:
        """对象 → JSON 字符串"""
        data = StandardSerializeRules.serialize_dataclass(obj)
        return json.dumps(data, indent=self._indent, ensure_ascii=self._ensure_ascii)

    def deserialize(self, data: str | bytes, target_type: type[T] | str) -> T:
        """JSON 字符串 → 对象"""
        parsed = json.loads(data) if isinstance(data, (str, bytes)) else data
        if isinstance(target_type, str):
            target_type = self._resolve_type(target_type)
        return self._dict_to_dataclass(parsed, target_type)

    def can_handle(self, obj_or_type: Any) -> bool:
        return is_dataclass(obj_or_type) if isinstance(obj_or_type, type) else is_dataclass(obj_or_type)

    def _dict_to_dataclass(self, data: dict[str, Any], target_type: type[T]) -> T:
        kwargs = {}
        for f_meta in target_type.get_fields():
            if f_meta.name in data:
                kwargs[f_meta.name] = self._deserialize_value(data[f_meta.name], f_meta)
        return target_type(**kwargs)

    def _deserialize_value(self, value: Any, field_meta: SerializationField) -> Any:
        if value is None:
            return field_meta.default
        if field_meta.is_union:
            return self._deserialize_union(value, field_meta.type)
        if field_meta.is_uuid:
            return UUID(value) if isinstance(value, str) else value
        if field_meta.is_datetime:
            return datetime.fromisoformat(value) if isinstance(value, str) else value
        if field_meta.is_enum:
            return field_meta.type(value)
        if field_meta.is_nested_dataclass:
            return self._dict_to_dataclass(value, field_meta.type)
        return value

    def _deserialize_union(self, value: Any, union_type: Any) -> Any:
        """处理 Union 类型（如 UUID | None）"""
        if value is None:
            return None  # 显式处理 None，避免静默丢失
        for arg in union_type.__args__ if hasattr(union_type, '__args__') else []:
            if arg is type(None):
                continue
            if arg is UUID and isinstance(value, str):
                return UUID(value)
            if arg is datetime and isinstance(value, str):
                return datetime.fromisoformat(value)
        raise ValueError(f"Cannot deserialize {value!r} to {union_type}")  # 明确报错

    def _resolve_type(self, type_id: str) -> type:
        """从类型注册表解析类型标识符"""
        from src.application.ports.type_registry import TypeRegistry
        resolved = TypeRegistry.resolve(type_id)
        if resolved is None:
            raise ValueError(f"Unknown type id: {type_id}")
        return resolved
```

#### 5.5.2 Redis Hash 序列化器

```python
# infrastructure/serialization/redis_hash_serializer.py

import json
from dataclasses import is_dataclass
from datetime import datetime
from typing import Any, TypeVar
from uuid import UUID

from src.application.ports.serialization import SerializationPort
from src.application.ports.serialization_rules import StandardSerializeRules
from src.domain.ports.serialization import SerializationField


T = TypeVar("T")


class RedisHashSerializer(SerializationPort[T]):
    """Redis Hash 序列化器（所有值为 string）"""

    def serialize(self, obj: T) -> dict[str, str]:
        """对象 → Redis Hash"""
        data = StandardSerializeRules.serialize_dataclass(obj)
        return self._to_redis_hash(data)

    def _to_redis_hash(self, data: dict[str, Any]) -> dict[str, str]:
        result = {}
        for key, value in data.items():
            if value is None:
                result[key] = ""
            elif isinstance(value, bool):
                result[key] = str(value)
            elif isinstance(value, (int, float)):
                result[key] = str(value)
            elif isinstance(value, str):
                result[key] = value
            else:
                result[key] = json.dumps(value)
        return result

    def deserialize(self, data: dict[str, str], target_type: type[T] | str) -> T:
        """Redis Hash → 对象"""
        if isinstance(target_type, str):
            target_type = self._resolve_type(target_type)
        dict_data = self._from_redis_hash(data)
        return self._dict_to_dataclass(dict_data, target_type)

    def _from_redis_hash(self, data: dict[str, str]) -> dict[str, Any]:
        result = {}
        for key, value in data.items():
            if not value:
                result[key] = None
                continue
            try:
                result[key] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                if value.lower() in ("true", "false"):
                    result[key] = value.lower() == "true"
                elif value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
                    result[key] = int(value)
                else:
                    result[key] = value
        return result

    def can_handle(self, obj_or_type: Any) -> bool:
        return is_dataclass(obj_or_type) if isinstance(obj_or_type, type) else is_dataclass(obj_or_type)

    def _dict_to_dataclass(self, data: dict[str, Any], target_type: type[T]) -> T:
        kwargs = {}
        for f_meta in target_type.get_fields():
            if f_meta.name in data:
                kwargs[f_meta.name] = self._deserialize_value(data[f_meta.name], f_meta)
        return target_type(**kwargs)

    def _deserialize_value(self, value: Any, field_meta: SerializationField) -> Any:
        if value is None:
            return field_meta.default
        if field_meta.is_union:
            return self._deserialize_union(value, field_meta.type)
        if field_meta.is_uuid:
            return UUID(value) if isinstance(value, str) else value
        if field_meta.is_datetime:
            return datetime.fromisoformat(value) if isinstance(value, str) else value
        if field_meta.is_enum:
            return field_meta.type(value)
        if field_meta.is_nested_dataclass:
            return self._dict_to_dataclass(value, field_meta.type)
        return value

    def _deserialize_union(self, value: Any, union_type: Any) -> Any:
        """处理 Union 类型（如 UUID | None）"""
        if value is None:
            return None  # 显式处理 None，避免静默丢失
        for arg in union_type.__args__ if hasattr(union_type, '__args__') else []:
            if arg is type(None):
                continue
            if arg is UUID and isinstance(value, str):
                return UUID(value)
            if arg is datetime and isinstance(value, str):
                return datetime.fromisoformat(value)
        raise ValueError(f"Cannot deserialize {value!r} to {union_type}")  # 明确报错

    def _resolve_type(self, type_id: str) -> type:
        """从类型注册表解析类型标识符"""
        from src.application.ports.type_registry import TypeRegistry
        resolved = TypeRegistry.resolve(type_id)
        if resolved is None:
            raise ValueError(f"Unknown type id: {type_id}")
        return resolved
```

### 5.6 DomainEvent 多态反序列化衔接

**问题**：现有 `DomainEvent` 通过 `__init_subclass__` + `_registry` 实现子类自动注册，新方案使用 `TypeRegistry`，两者需正确衔接。

**解决方案**：采用**延迟注册模式**，避免领域层直接导入 application 层模块。

> ⚠️ **关键约束**：领域层只能使用 Python 标准库。`DomainEvent.__init_subclass__` 中不能直接导入 `TypeRegistry`，否则违反"领域层零外部依赖"原则。

**设计方案**：

```python
# domain/events/base.py（改造后）

def __init_subclass__(cls, **kwargs: Any) -> None:
    """自动注册子类（仅向 DomainEvent._registry）"""
    super().__init_subclass__(**kwargs)
    if is_dataclass(cls):
        for f in fields(cls):
            if f.name == "event_type" and not f.init:
                if f.default is not MISSING:
                    # 只向 DomainEvent._registry 注册（领域层内部）
                    DomainEvent._registry[f.default] = cls
                break
```

**说明**：
- `DomainEvent._registry` 保留在领域层，用于从 dict 反序列化（向后兼容）
- `TypeRegistry` 注册由应用启动时统一完成（见下节）
- 两者通过相同的 `event_type` 值关联

**event_type 值与类映射**：

| 子类 | event_type 默认值 |
|------|-------------------|
| `DomainEvent` | `""`（基类不注册） |
| `DocumentProcessed` | `"DocumentProcessed"` |
| `StrategicDeviationWarning` | `"StrategicDeviationWarning"` |
| ... | ... |

**应用启动时初始化（延迟注册）**：
```python
# application/ports/type_registry.py

def auto_register_domain_events() -> None:
    """应用启动时调用，将 DomainEvent._registry 同步到 TypeRegistry。

    必须在所有 DomainEvent 子类加载完成后调用。
    """
    from src.domain.events.base import DomainEvent
    for event_type, event_class in DomainEvent._registry.items():
        if event_type:  # 跳过空字符串（基类）
            TypeRegistry.register(event_type, event_class)
```

**调用时机**：
- 在应用启动时（如 `main.py` 或 lifespan 事件中）调用
- 或在序列化器首次使用前调用
- 确保所有 DomainEvent 子类已被加载到 `DomainEvent._registry`
```

### 5.7 序列化格式与存储介质映射

| 存储介质 | 序列化器 | 值类型处理 |
|----------|----------|------------|
| Redis Hash | `RedisHashSerializer` | 所有值为 string |
| Redis String | `JsonSerializer` | JSON 字符串 |
| PostgreSQL JSONB | `JsonSerializer` | JSON 对象 |
| RabbitMQ Message | `JsonSerializer` | JSON 字符串 |
| Memory (测试) | `DictSerializer` | Python dict |

### 5.8 目录结构更新

```
src/
├── domain/                         # ✅ 领域层（零外部依赖）
│   ├── entities/
│   │   ├── checkpoint_snapshot.py  # ✅ 实现 Serializable Protocol
│   │   └── ...
│   ├── events/
│   │   ├── base.py                # ✅ 实现 Serializable Protocol
│   │   └── ...
│   ├── ports/
│   │   └── serialization.py        # ✅ Serializable Protocol, SerializationField
│   └── ...
│
├── application/                     # ✅ 应用层
│   ├── ports/
│   │   ├── __init__.py
│   │   ├── serialization.py       # ✅ SerializationPort (抽象接口)
│   │   ├── serialization_rules.py  # ✅ StandardSerializeRules
│   │   └── type_registry.py        # ✅ TypeRegistry
│   └── ...
│
├── infrastructure/                  # ✅ 基础设施层
│   └── serialization/               # ✅ 序列化器实现
│       ├── __init__.py
│       ├── json_serializer.py       # JsonSerializer
│       ├── redis_hash_serializer.py # RedisHashSerializer
│       ├── dict_serializer.py       # DictSerializer (测试用)
│       └── jsonb_serializer.py     # JsonbSerializer
│   └── ...
```

### 5.9 向后兼容性与调用方改造

**问题**：改造 `CheckpointSnapshot` 后，现有调用方 `RedisSnapshotStore` 直接调用 `to_redis_hash()` 方法。

**现有调用方**（`redis_snapshot_store.py`）：
```python
# 改造前
hash_data = snapshot.to_redis_hash()
snapshot = CheckpointSnapshot.from_redis_hash(hash_data)
```

**改造后方案**：
序列化器接管后，调用方应改为使用序列化器：

```python
# 改造后
from src.infrastructure.serialization.redis_hash_serializer import RedisHashSerializer

serializer = RedisHashSerializer()

# 保存时
hash_data = serializer.serialize(snapshot)

# 加载时
snapshot = serializer.deserialize(hash_data, CheckpointSnapshot)
```

**PostgreSQLEventStore 改造说明**：

当前 `infrastructure/messaging/event_store.py` 中 `PostgreSQLEventStore.get_events()` 直接调用 `DomainEvent.from_dict()`：

```python
# 当前实现（存在问题）
events.append(DomainEvent.from_dict(event_data))
```

改造后，`DomainEvent.from_dict()` 将被移除，改为使用序列化器：

```python
# 改造后
from src.infrastructure.serialization.json_serializer import JsonSerializer
from src.application.ports.type_registry import TypeRegistry

serializer = JsonSerializer()
events.append(serializer.deserialize(event_data, DomainEvent))
```

**验收条件**：
- [ ] `PostgreSQLEventStore` 使用 `JsonSerializer` 而非直接调用 `DomainEvent.from_dict()`
- [ ] `RedisSnapshotStore` 使用 `RedisHashSerializer` 而非直接调用实体方法
- [ ] `DomainEvent.from_dict()` 方法被移除
- [ ] `CheckpointSnapshot` 移除 `to_redis_hash()` / `from_redis_hash()` 方法
- [ ] 序列化器正确处理 `state_data: dict[str, Any]` 字段（嵌套字典的 JSON 序列化）

### 5.10 新建文件清单（序列化框架）

| 路径 | 说明 |
|------|------|
| `domain/ports/serialization.py` | Serializable Protocol, SerializationField |
| `application/ports/serialization.py` | SerializationPort 抽象接口 |
| `application/ports/serialization_rules.py` | StandardSerializeRules |
| `application/ports/type_registry.py` | TypeRegistry |
| `infrastructure/serialization/__init__.py` | 模块导出 |
| `infrastructure/serialization/json_serializer.py` | JsonSerializer |
| `infrastructure/serialization/redis_hash_serializer.py` | RedisHashSerializer |
| `infrastructure/serialization/dict_serializer.py` | DictSerializer（测试用） |
| `infrastructure/serialization/jsonb_serializer.py` | JsonbSerializer |

---

## 6. sovereignty.py 跨层导入修复方案

**问题**：`infrastructure/config/sovereignty.py` 导入 `infrastructure/security/models.py`，违反 infrastructure 内部分层原则。

**根本原因**：`security/models.py` 包含 `SensitiveDataType`、`DataResidency` 等值对象，这些本应属于领域层或独立值对象。

**修复方案**：

| 操作 | 路径 | 说明 |
|------|------|------|
| 新建 | `src/domain/value_objects/sensitive_data.py` | 迁移 SensitiveDataType, DataResidency, WhitelistStatus, ApprovalStatus |
| 重命名 | `infrastructure/security/models.py` → `infrastructure/security/value_objects.py` | 避免与 ORM models 混淆 |
| 修改 | `infrastructure/config/sovereignty.py` | 改为从 `domain.value_objects.sensitive_data` 导入 |
| 修改 | `infrastructure/security/` 下所有文件 | 改为从 `security.value_objects` 导入 |

**验收条件**：
- [ ] `infrastructure/config/` 不导入 `infrastructure/security/`
- [ ] `security/value_objects.py` 不导入其他 infrastructure 子目录
- [ ] 领域层值对象位于 `domain/value_objects/`

---

## 7. 影响范围

### 7.1 文件操作统计

| 操作 | 数量 |
|------|------|
| 重命名目录 | 1 (`repositories/` → `ports/`) |
| 移动文件 | 14（事件基础设施3个 + Protocol 7个 + security 重命名1个 + 新建 domain/ports/serialization.py 1个 + 新建 application/ports/ 3个） |
| 新建文件 | 9（序列化框架：domain/ports/serialization.py, application/ports/serialization.py, application/ports/serialization_rules.py, application/ports/type_registry.py, infrastructure/serialization/*.py） |
| 修改文件 | 2（`base.py` 改造为 Serializable Protocol, `checkpoint_snapshot.py` 移除序列化） |

### 7.2 需更新的导入路径

| 层级 | 影响文件数（估计） |
|------|-------------------|
| domain/ | ~25 |
| application/ | ~15 |
| infrastructure/ | ~45 |
| interfaces/ | ~20 |
| tests/ | ~50 |
| **总计** | **~155 files** |

---

## 8. 验收标准

- [ ] `domain/repositories/` 目录重命名为 `domain/ports/`
- [ ] 7 个 Protocol 文件从 `domain/services/` 移至 `application/ports/`
- [ ] 3 个事件基础设施文件从 `domain/events/` 移至 `infrastructure/`（publisher.py, listener.py, publish_result.py）
- [ ] `EventStore` ABC 保留在 `domain/events/event_store.py`（是领域层 Port 接口）
- [ ] `DomainEvent` 类实现 `Serializable` Protocol，无 `to_dict()` / `from_dict()` 方法
- [ ] `CheckpointSnapshot` 类实现 `Serializable` Protocol，无 `to_redis_hash()` / `from_redis_hash()` 方法
- [ ] `domain/ports/serialization.py` 定义 `Serializable` Protocol 和 `SerializationField`
- [ ] `application/ports/serialization.py` 定义 `SerializationPort` 抽象接口
- [ ] `application/ports/serialization_rules.py` 定义 `StandardSerializeRules`
- [ ] `application/ports/type_registry.py` 定义 `TypeRegistry`
- [ ] `JsonSerializer._resolve_type()` 完整实现（调用 TypeRegistry.resolve）
- [ ] `RedisHashSerializer._resolve_type()` 完整实现（调用 TypeRegistry.resolve）
- [ ] 序列化器处理 `UUID | None` 等 Union Types（`is_union=True` 字段）
- [ ] `DomainEvent.__init_subclass__` 自动向 `TypeRegistry` 注册子类
- [ ] `infrastructure/serialization/` 包含 JSON 和 Redis Hash 序列化器实现
- [ ] `domain/exceptions/` 包含 `MemoryNotFoundError` 和 `MemoryVersionConflictError`
- [ ] `domain/value_objects/sensitive_data.py` 包含敏感数据类型定义
- [ ] `infrastructure/security/models.py` 重命名为 `value_objects.py`
- [ ] `infrastructure/config/sovereignty.py` 从 `domain.value_objects` 导入
- [ ] `RedisSnapshotStore` 使用 `RedisHashSerializer` 而非直接调用实体方法
- [ ] `PostgreSQLEventStore` 使用 `JsonSerializer` 而非直接调用 `DomainEvent.from_dict()`
- [ ] 所有测试通过
- [ ] `mypy .` 无错误
- [ ] `ruff check .` 无错误

---

## 9. 六边形架构图

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
                        │  │  SerializationPort                              │    │
                        │  └─────────────────────────────────────────────────┘    │
                        └────────────────────────┬────────────────────────────────┘
                                                 │
┌────────────────────────────────────────────────┼────────────────────────────────────────────────┐
│                    domain/                      │                                                     │
│  ┌─────────────────────────────────────────────▼─────────────────────────────────────────────┐       │
│  │                              Ports (interfaces)                                             │       │
│  │  HealthCheckPort  IntegrityPort  L0StoragePort  VectorStorage  GraphStorage  ...          │       │
│  │  [Serializable Protocol ← 领域实体实现]                                                   │       │
│  └─────────────────────────────────────────────┬─────────────────────────────────────────────┘       │
│                                                │                                                         │
│  ┌─────────────────────────────────────────────▼─────────────────────────────────────────────┐       │
│  │                          Entities / Events / Value Objects                                   │       │
│  │   Agent  Checkpoint  Document  MemoryMetadata  StrategicPlan  (Domain Events)  (VO)         │       │
│  │   [实现 Serializable Protocol]                                                              │       │
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
│  │  ┌─────────────────────────────────────────────────────────────────────────────────┐      │       │
│  │  │  Serializers: JsonSerializer  RedisHashSerializer  JsonbSerializer          │      │       │
│  │  └─────────────────────────────────────────────────────────────────────────────────┘      │       │
│  └────────────────────────────┬───────────────────────────────────────────────────────────────┘       │
│                               │                                                               │
│  ┌────────────────────────────▼───────────────────────────────────────────────────────────────┐       │
│  │                     Infrastructure Services                                                │       │
│  │  Routing  Security  Audit  Monitoring  Scheduler  Messaging  Config                        │       │
│  └────────────────────────────────────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 10. 关键原则总结

| 原则 | 说明 |
|------|------|
| **领域层零外部依赖** | domain/ 仅用 Python 标准库 |
| **Port 接口在 domain** | 接口定义与实现分离，依赖倒置 |
| **事件基础设施在 infrastructure** | 发布-订阅是技术机制，不是领域概念 |
| **Protocol 定义分离** | 纯接口移到 application/ports/ |
| **序列化是适配器责任** | 领域实体实现 Serializable Protocol，序列化器在 infrastructure 层 |
| **通用序列化框架** | 通过 SerializationPort 支持多种序列化格式（JSON/Redis Hash/JSONB） |
| **异常集中定义** | domain/exceptions/ 统一管理领域异常 |
| **目录命名准确** | repositories/ → ports/（反映本质） |
| **值对象命名清晰** | security/models.py → security/value_objects.py |

---

## 11. 附录

### A. 移动文件清单

| 原路径 | 目标路径 | 说明 |
|--------|----------|------|
| domain/repositories/ | domain/ports/ | 目录重命名 |
| domain/events/publisher.py | infrastructure/messaging/event_publisher.py | 事件基础设施 |
| domain/events/listener.py | infrastructure/messaging/event_listener.py | 事件基础设施 |
| domain/events/publish_result.py | infrastructure/messaging/publish_result.py | 事件基础设施 |
| domain/services/audit_service.py | application/ports/audit_port.py | Protocol |
| domain/services/auth_service.py | application/ports/auth_port.py | Protocol |
| domain/services/permission_service.py | application/ports/permission_port.py | Protocol |
| domain/services/public_blackboard.py | application/ports/public_blackboard_port.py | Protocol |
| domain/services/semantic_cache.py | application/ports/semantic_cache_port.py | Protocol |
| domain/services/compressor_service.py | application/ports/compressor_port.py | Protocol |
| domain/services/text_extractor_service.py | application/ports/text_extractor_port.py | Protocol |
| infrastructure/security/models.py | infrastructure/security/value_objects.py | 重命名 |

**注意**：
- `EventStore` ABC 保留在 `domain/events/event_store.py`（是领域层 Port 接口）
- `infrastructure/messaging/event_store.py` 是 `PostgreSQLEventStore` 实现，无需移动

### B. 新建文件清单

| 路径 | 内容 |
|------|------|
| domain/exceptions/__init__.py | 导出异常 |
| domain/exceptions/memory_exceptions.py | MemoryNotFoundError, MemoryVersionConflictError |
| domain/value_objects/sensitive_data.py | SensitiveDataType, DataResidency, WhitelistStatus, ApprovalStatus 等值对象 |
| domain/ports/serialization.py | Serializable Protocol, SerializationField |
| application/ports/serialization.py | SerializationPort 抽象接口 |
| application/ports/serialization_rules.py | StandardSerializeRules 标准类型转换规则 |
| application/ports/type_registry.py | TypeRegistry 类型注册表 |
| infrastructure/serialization/__init__.py | 序列化模块导出 |
| infrastructure/serialization/json_serializer.py | JsonSerializer 实现 |
| infrastructure/serialization/redis_hash_serializer.py | RedisHashSerializer 实现 |

### C. 修改文件清单

| 路径 | 修改内容 |
|------|----------|
| domain/events/base.py | 改造为实现 Serializable Protocol（移除 to_dict/from_dict） |
| domain/entities/checkpoint_snapshot.py | 改造为实现 Serializable Protocol（移除 to_redis_hash/from_redis_hash） |
| domain/services/memory_service.py | 从 domain/exceptions/ 导入异常 |
| infrastructure/config/sovereignty.py | 改为从 domain.value_objects.sensitive_data 导入 |
| infrastructure/security/value_objects.py | 重命名自 models.py | |

### D. 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| Port 接口 | `XxxPort` 或 `XxxProtocol` | `HealthCheckPort`, `IntegrityPort` |
| Repository 接口 | `XxxRepositoryProtocol` | `MemoryMetadataRepositoryProtocol` |
| 领域服务 | `XxxService` | `MemoryService`, `AutoRouteService` |
| 领域异常 | `XxxError` | `MemoryNotFoundError` |
| 值对象 | `XxxContext` / `XxxDecision` / `XxxType` | `AutoTriggerContext`, `RoutingDecision`, `SensitiveDataType` |
| 事件基础设施 | `XxxPublisher` / `XxxListener` | `EventPublisher`, `EventListener` |
| 安全值对象 | `xxx_objects.py` | `value_objects.py`（非 models.py） |
| 序列化器 | `XxxSerializer` | `JsonSerializer`, `RedisHashSerializer` |
| 序列化端口 | `SerializationPort` | `SerializationPort[T]` |
| 可序列化类型 | 实现 `Serializable` Protocol | `DomainEvent`, `CheckpointSnapshot` |
