# SISYS Domain 层目录结构重构方案 (DDR-EVD-DIR-REFACTOR)

## 文档信息

| 字段 | 值 |
|------|-----|
| 文档编号 | DDR-EVD-DIR-REFACTOR |
| 版本 | v1.0 |
| 日期 | 2026-05-02 |
| 状态 | 待评审 |
| 关联 Story | Epic 20 架构重构 |

---

## 1. 背景与目的

### 1.1 当前问题

`src/domain/` 目录存在以下架构问题：

1. **目录命名不准确** — `repositories/` 目录实际存放的是 **Port（端口接口）**，而非仓储实现
2. **事件基础设施混入领域** — `publisher.py`、`listener.py`、`store.py` 是发布-订阅机制基础设施，不属于领域定义
3. **Protocol 定义错位** — 纯接口定义（`AuditService`、`CompressorService` 等）混入 `domain/services/`，应属于应用层
4. **序列化职责混乱** — `DomainEvent.to_dict()/from_dict()` 将序列化逻辑置于领域层，应属于适配器
5. **异常定义分散** — `MemoryNotFoundError` 定义在 `memory_service.py` 中，应独立为领域异常模块

### 1.2 重构目标

- 使目录结构准确反映六边形架构的**端口与适配器**模式
- 明确分离**领域概念**与**基础设施实现**
- 提升代码可维护性和可发现性
- 消除"一个目录混合多种职责"的问题

---

## 2. 当前结构分析

### 2.1 当前目录概览

```
src/domain/
├── __init__.py
├── entities/              # 9 files — ✅ 正确
├── events/                # 20+ files — ⚠️ 混合基础设施
├── exceptions/            # 1 file (empty) — ⚠️ 未使用
├── repositories/         # 14 files — ⚠️ 实际是 Port 接口
├── services/             # 14 files — ⚠️ 混合 Protocol
└── value_objects/        # 2 files — ✅ 正确
```

### 2.2 当前文件分类

| 类别 | 文件 | 问题 |
|------|------|------|
| **Entities** (✅) | `agent.py`, `checkpoint.py`, `document.py`, `memory_metadata.py`, `memory_change_history.py`, `routing_decision_log.py`, `strategic_plan.py`, `tool.py`, `checkpoint_snapshot.py` | 无 |
| **Domain Events** (✅) | `agent_events.py`, `audit_events.py`, `auto_execute_events.py`, `auto_route_events.py`, `auto_trigger_events.py`, `checkpoint_events.py`, `compliance_events.py`, `correction_events.py`, `document_events.py`, `heartbeat_events.py`, `isolation_events.py`, `memory_events.py`, `planning_events.py`, `routing_events.py`, `tool_events.py` | 无 |
| **Event Infrastructure** (❌) | `base.py`, `enums.py`, `publisher.py`, `listener.py`, `store.py`, `publish_result.py` | 应移至 `infrastructure/` |
| **Ports** (应重命名) | `base.py`, `graph_storage.py`, `health_check.py`, `index_manager.py`, `integrity.py`, `l0_storage.py`, `memory_repository.py`, `outbox.py`, `session_storage.py`, `storage.py`, `unit_of_work.py`, `vector_storage.py` | 应重命名 `repositories/` → `ports/` |
| **Service Protocols** (❌) | `audit_service.py`, `auth_service.py`, `permission_service.py`, `public_blackboard.py`, `semantic_cache.py`, `compressor_service.py`, `text_extractor_service.py`, `auto_execute_service.py`, `auto_route_service.py` | 应移至 `application/ports/` |
| **Domain Services** (✅) | `memory_service.py`, `auto_trigger_service.py`, `udmr_router.py` | 保留在 `domain/services/` |
| **Value Objects** (✅) | `auto_trigger_context.py`, `routing_decision.py` | 无 |
| **Exceptions** (❌) | `exceptions/__init__.py` (empty) | 应创建异常定义文件 |

---

## 3. 目标结构

### 3.1 重构后目录结构

```
src/domain/
├── __init__.py
├── entities/                      # ✅ 领域实体（不变）
│   ├── __init__.py
│   ├── agent.py
│   ├── checkpoint.py
│   ├── document.py
│   ├── memory_change_history.py
│   ├── memory_metadata.py
│   ├── routing_decision_log.py
│   ├── strategic_plan.py
│   ├── tool.py
│   └── checkpoint_snapshot.py
│
├── events/                        # ✅ 纯领域事件（移除基础设施）
│   ├── __init__.py
│   ├── base.py                    # DomainEvent 基类（移除序列化）
│   ├── enums.py                   # 领域枚举（保留）
│   ├── agent_events.py
│   ├── audit_events.py
│   ├── auto_execute_events.py
│   ├── auto_route_events.py
│   ├── auto_trigger_events.py
│   ├── checkpoint_events.py
│   ├── compliance_events.py
│   ├── correction_events.py
│   ├── document_events.py
│   ├── heartbeat_events.py
│   ├── isolation_events.py
│   ├── memory_events.py
│   ├── planning_events.py
│   ├── routing_events.py
│   └── tool_events.py
│
├── ports/                          # 🆕 端口接口（从 repositories/ 重命名）
│   ├── __init__.py
│   ├── base.py                    # BaseRepository Generic ABC
│   ├── memory_repository.py       # MemoryMetadataRepositoryProtocol
│   ├── l0_storage.py               # L0StoragePort
│   ├── health_check.py             # HealthCheckPort
│   ├── integrity.py                # IntegrityPort
│   ├── index_manager.py            # IndexManagerPort
│   ├── vector_storage.py           # VectorStorage Protocol
│   ├── graph_storage.py            # GraphManager / GraphStorage ABC
│   ├── session_storage.py          # SessionStorage Protocol
│   ├── outbox.py                   # OutboxRepository ABC
│   └── unit_of_work.py             # UnitOfWork ABC
│
├── services/                       # ✅ 具体业务逻辑（移除 Protocol）
│   ├── __init__.py
│   ├── memory_service.py           # 含 MemoryNotFoundError 等异常
│   ├── auto_trigger_service.py
│   └── udmr_router.py
│
├── value_objects/                 # ✅ 值对象（不变）
│   ├── __init__.py
│   ├── auto_trigger_context.py
│   └── routing_decision.py
│
└── exceptions/                     # 🆕 领域异常（从 services/ 移出）
    ├── __init__.py
    └── memory_exceptions.py        # MemoryNotFoundError, MemoryVersionConflictError
```

### 3.2 移除的文件（移至 infrastructure/）

| 原路径 | 目标路径 | 理由 |
|--------|----------|------|
| `domain/events/publisher.py` | `infrastructure/messaging/event_publisher.py` | 发布-订阅是基础设施模式 |
| `domain/events/listener.py` | `infrastructure/messaging/event_listener.py` | 发布-订阅是基础设施模式 |
| `domain/events/store.py` | `infrastructure/events/event_store.py` | 事件溯源存储是基础设施 |
| `domain/events/publish_result.py` | `infrastructure/messaging/publish_result.py` | 基础设施数据结构 |
| `domain/services/audit_service.py` | `application/ports/audit_port.py` | 纯 Protocol 接口 |
| `domain/services/auth_service.py` | `application/ports/auth_port.py` | 纯 Protocol 接口 |
| `domain/services/permission_service.py` | `application/ports/permission_port.py` | 纯 Protocol 接口 |
| `domain/services/public_blackboard.py` | `application/ports/public_blackboard_port.py` | 纯 Protocol 接口 |
| `domain/services/semantic_cache.py` | `application/ports/semantic_cache_port.py` | 纯 Protocol 接口 |
| `domain/services/compressor_service.py` | `application/ports/compressor_port.py` | 纯 Protocol 接口 |
| `domain/services/text_extractor_service.py` | `application/ports/text_extractor_port.py` | 纯 Protocol 接口 |
| `domain/services/auto_execute_service.py` | `application/ports/auto_execute_port.py` | 纯 Protocol 接口 |
| `domain/services/auto_route_service.py` | `application/ports/auto_route_port.py` | 纯 Protocol 接口 |

---

## 4. 详细迁移方案

### 4.1 Step 1: 创建目标目录结构

```bash
# 1. 创建新 ports 目录（repositories/ 重命名）
mv src/domain/repositories/ src/domain/ports/

# 2. 创建 exceptions 目录
mkdir -p src/domain/exceptions/
```

### 4.2 Step 2: 迁移 Event Infrastructure 文件

```bash
# 创建基础设施目录
mkdir -p src/infrastructure/messaging/
mkdir -p src/infrastructure/events/

# 迁移文件
mv src/domain/events/publisher.py src/infrastructure/messaging/event_publisher.py
mv src/domain/events/listener.py src/infrastructure/messaging/event_listener.py
mv src/domain/events/store.py src/infrastructure/events/event_store.py
mv src/domain/events/publish_result.py src/infrastructure/messaging/publish_result.py
```

### 4.3 Step 3: 迁移 Service Protocol 文件

```bash
# 创建应用层端口目录
mkdir -p src/application/ports/

# 迁移 Protocol 文件
mv src/domain/services/audit_service.py src/application/ports/audit_port.py
mv src/domain/services/auth_service.py src/application/ports/auth_port.py
mv src/domain/services/permission_service.py src/application/ports/permission_port.py
mv src/domain/services/public_blackboard.py src/application/ports/public_blackboard_port.py
mv src/domain/services/semantic_cache.py src/application/ports/semantic_cache_port.py
mv src/domain/services/compressor_service.py src/application/ports/compressor_port.py
mv src/domain/services/text_extractor_service.py src/application/ports/text_extractor_port.py
mv src/domain/services/auto_execute_service.py src/application/ports/auto_execute_port.py
mv src/domain/services/auto_route_service.py src/application/ports/auto_route_port.py
```

### 4.4 Step 4: 创建领域异常模块

创建 `src/domain/exceptions/memory_exceptions.py`：

```python
"""Domain exceptions for memory operations."""

class MemoryNotFoundError(Exception):
    """Raised when a memory entity is not found."""
    pass

class MemoryVersionConflictError(Exception):
    """Raised when memory version conflict occurs during update."""
    pass
```

从 `memory_service.py` 删除异常定义，改为导入：

```python
from src.domain.exceptions.memory_exceptions import (
    MemoryNotFoundError,
    MemoryVersionConflictError,
)
```

### 4.5 Step 5: 清理 DomainEvent.base.py

移除 `to_dict()` / `from_dict()` 序列化方法，保留纯业务属性：

```python
# 修改前
class DomainEvent:
    def to_dict(self) -> dict: ...
    def from_dict(cls, data: dict) -> DomainEvent: ...

# 修改后 — 序列化由适配器负责
class DomainEvent:
    """Base class for all domain events.

    Serialization is handled by infrastructure adapters (JSON, MessagePack, etc.)
    """
    pass  # 仅保留 AC-1 标准属性定义
```

### 4.6 Step 6: 更新所有导入路径

```python
# 需要更新的导入（示例）
# 旧
from src.domain.services.audit_service import AuditService
from src.domain.repositories.health_check import HealthCheckPort

# 新
from src.application.ports.audit_port import AuditService
from src.domain.ports.health_check import HealthCheckPort
```

### 4.7 Step 7: 更新 __init__.py 导出

更新相关 `__init__.py` 文件的导出语句。

---

## 5. 迁移文件清单

### 5.1 重命名的文件

| 操作 | 原路径 | 新路径 |
|------|--------|--------|
| 重命名 | `domain/repositories/` | `domain/ports/` |

### 5.2 移动的文件

| 操作 | 原路径 | 新路径 |
|------|--------|--------|
| 移动 | `domain/events/publisher.py` | `infrastructure/messaging/event_publisher.py` |
| 移动 | `domain/events/listener.py` | `infrastructure/messaging/event_listener.py` |
| 移动 | `domain/events/store.py` | `infrastructure/events/event_store.py` |
| 移动 | `domain/events/publish_result.py` | `infrastructure/messaging/publish_result.py` |
| 移动 | `domain/services/audit_service.py` | `application/ports/audit_port.py` |
| 移动 | `domain/services/auth_service.py` | `application/ports/auth_port.py` |
| 移动 | `domain/services/permission_service.py` | `application/ports/permission_port.py` |
| 移动 | `domain/services/public_blackboard.py` | `application/ports/public_blackboard_port.py` |
| 移动 | `domain/services/semantic_cache.py` | `application/ports/semantic_cache_port.py` |
| 移动 | `domain/services/compressor_service.py` | `application/ports/compressor_port.py` |
| 移动 | `domain/services/text_extractor_service.py` | `application/ports/text_extractor_port.py` |
| 移动 | `domain/services/auto_execute_service.py` | `application/ports/auto_execute_port.py` |
| 移动 | `domain/services/auto_route_service.py` | `application/ports/auto_route_port.py` |

### 5.3 新建的文件

| 操作 | 路径 | 内容 |
|------|------|------|
| 新建 | `domain/exceptions/__init__.py` | 导出异常 |
| 新建 | `domain/exceptions/memory_exceptions.py` | MemoryNotFoundError, MemoryVersionConflictError |

### 5.4 删除的文件

| 操作 | 路径 | 理由 |
|------|------|------|
| 删除 | `domain/exceptions/__init__.py` (旧) | 重写内容 |

### 5.5 修改的文件

| 操作 | 路径 | 修改内容 |
|------|------|----------|
| 修改 | `domain/events/base.py` | 移除序列化方法 |
| 修改 | `domain/services/memory_service.py` | 从 exceptions 导入异常 |
| 修改 | `domain/__init__.py` | 更新导出 |
| 修改 | `domain/entities/__init__.py` | 无变化 |
| 修改 | `domain/events/__init__.py` | 移除基础设施导出 |
| 修改 | `domain/ports/__init__.py` | 重命名后更新导出 |
| 修改 | `domain/services/__init__.py` | 移除 Protocol 导出 |
| 修改 | `domain/value_objects/__init__.py` | 无变化 |

---

## 6. 一致性规则

### 6.1 目录职责定义

| 目录 | 职责 | 包含内容 |
|------|------|----------|
| `domain/entities/` | 领域实体 | 业务对象（含状态、验证、业务规则） |
| `domain/events/` | 领域事件 | 领域内发生的业务事实（无序列化） |
| `domain/ports/` | 端口接口 | 依赖注入的抽象接口（ABC/Protocol） |
| `domain/services/` | 领域服务 | 具体业务逻辑实现（非接口） |
| `domain/value_objects/` | 值对象 | 不可变数据结构 |
| `domain/exceptions/` | 领域异常 | 领域级异常定义 |
| `application/ports/` | 应用层端口 | 应用层接口定义（调用 domain ports） |
| `infrastructure/messaging/` | 消息基础设施 | 发布-订阅、事件分发 |
| `infrastructure/events/` | 事件存储基础设施 | 事件溯源存储 |

### 6.2 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| Port 接口 | `XxxPort` 或 `XxxProtocol` | `HealthCheckPort`, `IntegrityPort` |
| Repository 接口 | `XxxRepositoryProtocol` | `MemoryMetadataRepositoryProtocol` |
| 领域服务 | `XxxService` | `MemoryService`, `AutoRouteService` |
| 领域异常 | `XxxError` | `MemoryNotFoundError` |
| 值对象 | `XxxContext` / `XxxDecision` | `AutoTriggerContext`, `RoutingDecision` |

---

## 7. 影响范围

### 7.1 需要更新的导入文件数

| 层级 | 文件数（估计） |
|------|----------------|
| `src/domain/` 内部 | ~30 files |
| `src/application/` | ~15 files |
| `src/infrastructure/` | ~40 files |
| `src/interfaces/` | ~20 files |
| `tests/` | ~50 files |
| **总计** | **~155 files** |

### 7.2 测试影响

- 所有使用移动后文件的测试需要更新导入路径
- 建议在迁移完成后运行完整测试套件验证

---

## 8. 执行计划

### 8.1 阶段划分

| 阶段 | 任务 | 风险 |
|------|------|------|
| Phase 1 | 创建目录结构 | 低 |
| Phase 2 | 迁移 event infrastructure | 中 |
| Phase 3 | 迁移 service protocol | 中 |
| Phase 4 | 创建异常模块 | 低 |
| Phase 5 | 清理 DomainEvent | 高 |
| Phase 6 | 更新所有导入 | 高 |
| Phase 7 | 验证测试通过 | 低 |

### 8.2 建议

- **每阶段完成后运行测试**，确保功能完整
- **使用 Git 分支**进行重构，便于回滚
- **批量更新导入**使用 IDE 重构功能或 sed/grep 批量替换

---

## 9. 验收标准

- [ ] `domain/repositories/` 目录重命名为 `domain/ports/`
- [ ] 所有 Protocol 文件从 `domain/services/` 移至 `application/ports/`
- [ ] 所有事件基础设施从 `domain/events/` 移至 `infrastructure/`
- [ ] `DomainEvent` 类不包含序列化方法
- [ ] `MemoryNotFoundError` 等异常定义在 `domain/exceptions/`
- [ ] 所有 3572 个测试通过
- [ ] `mypy .` 和 `ruff check .` 无错误

---

## 10. 附录

### A. 六边形架构参考

```
                    ┌─────────────────────────────────────┐
                    │           Application               │
                    │  ┌─────────────────────────────┐     │
                    │  │      Use Cases / Services   │     │
                    │  └─────────────────────────────┘     │
                    │           │                         │
                    │  ┌─────────▼─────────┐              │
                    │  │  Driver Ports      │              │
                    │  │  (interfaces/)     │              │
                    │  └─────────┬─────────┘              │
                    └────────────┼────────────────────────┘
                                 │
                    ┌────────────┼────────────────────────┐
                    │            │      Domain            │
                    │  ┌─────────▼─────────┐              │
                    │  │    Entities      │              │
                    │  │    Events        │              │
                    │  │    Value Objects │              │
                    │  │    (Pure Logic)  │              │
                    │  └─────────┬─────────┘              │
                    │  ┌─────────▼─────────┐              │
                    │  │  Driven Ports     │              │
                    │  │  (repositories/)  │              │
                    │  └─────────┬─────────┘              │
                    └────────────┼────────────────────────┘
                                 │
                    ┌────────────┼────────────────────────┐
                    │            │   Infrastructure       │
                    │  ┌─────────▼─────────┐              │
                    │  │    Adapters      │              │
                    │  │  (implement      │              │
                    │  │   Driven Ports)   │              │
                    │  └───────────────────┘              │
                    └────────────────────────────────────┘
```

### B. 关键原则

1. **领域层零外部依赖** — domain 只用 Python 标准库
2. **接口定义在 domain，实现在 infrastructure** — 遵循依赖倒置
3. **协议分离** — Driver Ports（应用调用）与 Driven Ports（基础设施实现）
4. **序列化是适配器责任** — 领域只关心业务属性
