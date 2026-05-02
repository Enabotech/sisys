# SISYS 全局目录结构重构方案 (SISYS-GLOBAL-DIR-REFACTOR)

## 文档信息

| 字段 | 值 |
|------|-----|
| 文档编号 | SISYS-GLOBAL-DIR-REFACTOR |
| 版本 | v1.0 |
| 日期 | 2026-05-02 |
| 状态 | 待评审 |
| 关联 Story | Epic 20 架构重构 |

---

## 1. 背景与约束

### 1.1 约束条件 (DDD + EVD + Hexagonal)

1. **领域层零外部依赖** — `src/domain/` 仅使用 Python 标准库
2. **六边形架构** — Driver Ports (接口层调用) / Driven Ports (基础设施实现)
3. **EVD (Event-Driven Architecture)** — 事件驱动，领域事件与基础设施事件分离
4. **DDD 分层** — Entity / Value Object / Service / Repository / Event / Exception

### 1.2 当前问题

1. `domain/repositories/` 实际是 Port 接口，应重命名为 `ports/`
2. `domain/events/` 混合了**领域事件定义**与**事件基础设施**（publisher/listener/store）
3. `domain/services/` 混合了**具体业务逻辑**与**纯 Protocol 接口**
4. `application/events/adapters.py` 使用 `pydantic` 需要审查
5. `infrastructure/` 内部存在跨模块导入（config → security/models）

---

## 2. 当前结构全景

### 2.1 目录树

```
src/
├── domain/                    # 领域层（零外部依赖）
│   ├── entities/              # 9 files
│   ├── events/                # 22 files（含基础设施）
│   ├── repositories/          # 14 files（实为 Port）
│   ├── services/              # 14 files（混合 Protocol）
│   ├── value_objects/         # 2 files
│   └── exceptions/            # 1 file (empty)
│
├── application/               # 应用层（用例编排）
│   ├── events/               # 1 file (adapters.py)
│   ├── services/             # 1 file (six_layer_storage_coordinator.py)
│   └── use_cases/            # 3 files
│
├── infrastructure/           # 基础设施层（外部依赖）
│   ├── audit/                # 审计服务
│   ├── config/               # 配置（14 files）
│   ├── messaging/            # (待创建)
│   ├── routing/              # 5 files
│   ├── scheduler/            # 调度器
│   ├── security/             # 21 files
│   └── storage/              # 多存储适配器
│
└── interfaces/               # 接口层（API/CLI/Event Listeners）
    ├── api/                  # 6 files
    ├── cli/                  # CLI 命令
    └── event_listeners/       # 事件监听器
```

### 2.2 文件分类总览

| 层级 | 目录 | 文件数 | 架构正确性 |
|------|------|--------|-----------|
| Domain | entities/ | 9 | ✅ 正确 |
| Domain | events/ | 22 | ⚠️ 混合基础设施 |
| Domain | repositories/ | 14 | ⚠️ 实为 Port 接口 |
| Domain | services/ | 14 | ⚠️ 混合 Protocol |
| Domain | value_objects/ | 2 | ✅ 正确 |
| Domain | exceptions/ | 1 | ⚠️ 空目录 |
| Application | events/ | 1 | ⚠️ 使用 pydantic |
| Application | services/ | 1 | ⚠️ 需审查 |
| Application | use_cases/ | 3 | ✅ 正确 |
| Infrastructure | config/ | 14 | ⚠️ 内部跨模块导入 |
| Infrastructure | routing/ | 5 | ⚠️ local_model_health.py 已废弃 |
| Infrastructure | security/ | 21 | ⚠️ 需审查 |
| Infrastructure | storage/ | 20+ | ⚠️ 需审查 |
| Interfaces | api/ | 6 | ✅ 预期依赖 FastAPI |
| Interfaces | cli/ | ? | ✅ 预期依赖 Typer |
| Interfaces | event_listeners/ | 4 | ⚠️ 需审查 |

---

## 3. 目标结构

```
src/
├── domain/                        # ✅ 领域层（零外部依赖）
│   ├── entities/                  # 领域实体
│   ├── events/                    # 领域事件（仅业务事件）
│   ├── ports/                     # 端口接口（从 repositories/ 重命名）
│   ├── services/                  # 具体业务逻辑（移除 Protocol）
│   ├── value_objects/             # 值对象
│   └── exceptions/                 # 领域异常
│
├── application/                   # ✅ 应用层（用例编排）
│   ├── ports/                     # 应用层端口（Protocol 定义）
│   ├── use_cases/                 # 用例
│   └── services/                  # 应用服务（如 SixLayerStorageCoordinator）
│
├── infrastructure/                # ✅ 基础设施层
│   ├── config/                    # 配置
│   ├── messaging/                 # 消息基础设施（publisher/listener）
│   ├── routing/                   # 路由实现
│   ├── security/                  # 安全服务
│   ├── storage/                   # 存储适配器
│   ├── scheduler/                 # 调度器
│   └── events/                    # 事件存储（EventStore 实现）
│
└── interfaces/                    # ✅ 接口层
    ├── api/                       # FastAPI 端点
    ├── cli/                       # Typer 命令
    └── event_listeners/           # 事件监听器实现
```

---

## 4. 详细方案

### 4.1 Domain 层文件位置方案

#### 4.1.1 entities/ — 位置正确，无需移动

| 文件 | 当前位置 | 目标位置 | 操作 |
|------|----------|----------|------|
| agent.py | domain/entities/ | domain/entities/ | 保留 |
| checkpoint.py | domain/entities/ | domain/entities/ | 保留 |
| checkpoint_snapshot.py | domain/entities/ | domain/entities/ | 保留 |
| document.py | domain/entities/ | domain/entities/ | 保留 |
| memory_change_history.py | domain/entities/ | domain/entities/ | 保留 |
| memory_metadata.py | domain/entities/ | domain/entities/ | 保留 |
| routing_decision_log.py | domain/entities/ | domain/entities/ | 保留 |
| strategic_plan.py | domain/entities/ | domain/entities/ | 保留 |
| tool.py | domain/entities/ | domain/entities/ | 保留 |

#### 4.1.2 events/ — 需要分离

| 文件 | 当前位置 | 目标位置 | 操作 |
|------|----------|----------|------|
| agent_events.py | domain/events/ | domain/events/ | 保留（领域事件） |
| audit_events.py | domain/events/ | domain/events/ | 保留（领域事件） |
| auto_execute_events.py | domain/events/ | domain/events/ | 保留（领域事件） |
| auto_route_events.py | domain/events/ | domain/events/ | 保留（领域事件） |
| auto_trigger_events.py | domain/events/ | domain/events/ | 保留（领域事件） |
| base.py | domain/events/ | domain/events/ | **修改**：移除序列化方法 |
| checkpoint_events.py | domain/events/ | domain/events/ | 保留（领域事件） |
| compliance_events.py | domain/events/ | domain/events/ | 保留（领域事件） |
| correction_events.py | domain/events/ | domain/events/ | 保留（领域事件） |
| document_events.py | domain/events/ | domain/events/ | 保留（领域事件） |
| enums.py | domain/events/ | domain/events/ | 保留（领域枚举） |
| heartbeat_events.py | domain/events/ | domain/events/ | 保留（领域事件） |
| isolation_events.py | domain/events/ | domain/events/ | 保留（领域事件） |
| memory_events.py | domain/events/ | domain/events/ | 保留（领域事件） |
| planning_events.py | domain/events/ | domain/events/ | 保留（领域事件） |
| routing_events.py | domain/events/ | domain/events/ | 保留（领域事件） |
| tool_events.py | domain/events/ | domain/events/ | 保留（领域事件） |
| **publisher.py** | domain/events/ | **infrastructure/messaging/** | 移动 |
| **listener.py** | domain/events/ | **infrastructure/messaging/** | 移动 |
| **store.py** | domain/events/ | **infrastructure/events/** | 移动 |
| **publish_result.py** | domain/events/ | **infrastructure/messaging/** | 移动 |

#### 4.1.3 repositories/ → ports/ — 重命名目录

| 文件 | 当前位置 | 目标位置 | 操作 |
|------|----------|----------|------|
| base.py | domain/repositories/ | domain/ports/ | 重命名 |
| graph_storage.py | domain/repositories/ | domain/ports/ | 重命名 |
| health_check.py | domain/repositories/ | domain/ports/ | 重命名 |
| index_manager.py | domain/repositories/ | domain/ports/ | 重命名 |
| integrity.py | domain/repositories/ | domain/ports/ | 重命名 |
| l0_storage.py | domain/repositories/ | domain/ports/ | 重命名 |
| memory_repository.py | domain/repositories/ | domain/ports/ | 重命名 |
| outbox.py | domain/repositories/ | domain/ports/ | 重命名 |
| session_storage.py | domain/repositories/ | domain/ports/ | 重命名 |
| storage.py | domain/repositories/ | domain/ports/ | 重命名 |
| unit_of_work.py | domain/repositories/ | domain/ports/ | 重命名 |
| vector_storage.py | domain/repositories/ | domain/ports/ | 重命名 |

#### 4.1.4 services/ — 分离 Protocol 与具体服务

| 文件 | 当前位置 | 目标位置 | 操作 |
|------|----------|----------|------|
| **audit_service.py** | domain/services/ | **application/ports/** | 移动（Protocol） |
| **auth_service.py** | domain/services/ | **application/ports/** | 移动（Protocol） |
| **permission_service.py** | domain/services/ | **application/ports/** | 移动（Protocol） |
| **public_blackboard.py** | domain/services/ | **application/ports/** | 移动（Protocol） |
| **semantic_cache.py** | domain/services/ | **application/ports/** | 移动（Protocol） |
| **compressor_service.py** | domain/services/ | **application/ports/** | 移动（Protocol） |
| **text_extractor_service.py** | domain/services/ | **application/ports/** | 移动（Protocol） |
| **auto_execute_service.py** | domain/services/ | **application/ports/** | 移动（Protocol） |
| **auto_route_service.py** | domain/services/ | **application/ports/** | 移动（Protocol） |
| memory_service.py | domain/services/ | domain/services/ | 保留（具体服务） |
| auto_trigger_service.py | domain/services/ | domain/services/ | 保留（具体服务） |
| udmr_router.py | domain/services/ | domain/services/ | 保留（具体服务） |

#### 4.1.5 value_objects/ — 位置正确

| 文件 | 当前位置 | 目标位置 | 操作 |
|------|----------|----------|------|
| auto_trigger_context.py | domain/value_objects/ | domain/value_objects/ | 保留 |
| routing_decision.py | domain/value_objects/ | domain/value_objects/ | 保留 |

#### 4.1.6 exceptions/ — 需要创建内容

| 文件 | 当前位置 | 目标位置 | 操作 |
|------|----------|----------|------|
| exceptions/__init__.py | domain/exceptions/ | domain/exceptions/ | 重写（导出异常） |
| memory_exceptions.py | (不存在) | domain/exceptions/ | 新建 |

---

### 4.2 Application 层文件位置方案

| 文件 | 当前位置 | 目标位置 | 操作 | 理由 |
|------|----------|----------|------|------|
| events/adapters.py | application/events/ | application/events/ | **审查** | 使用 pydantic，需验证必要性 |
| services/six_layer_storage_coordinator.py | application/services/ | application/services/ | 保留 | 具体应用服务 |
| use_cases/document_processing.py | application/use_cases/ | application/use_cases/ | 保留 | 用例 |
| use_cases/text_processing/l1_compressor.py | application/use_cases/ | application/use_cases/ | 保留 | 用例 |
| use_cases/text_processing/l1_text_extractor.py | application/use_cases/ | application/use_cases/ | 保留 | 用例 |
| ports/ | (不存在) | application/ports/ | 新建 | 接收移动的 Protocol |

---

### 4.3 Infrastructure 层文件位置方案

#### 4.3.1 config/ — 需审查跨模块导入

| 文件 | 当前位置 | 目标位置 | 操作 | 理由 |
|------|----------|----------|------|------|
| audit.py | infrastructure/config/ | infrastructure/config/ | 保留 | 配置 |
| auth.py | infrastructure/config/ | infrastructure/config/ | 保留 | 配置 |
| auto_execute.py | infrastructure/config/ | infrastructure/config/ | 保留 | 配置 |
| auto_route.py | infrastructure/config/ | infrastructure/config/ | 保留 | 配置 |
| auto_trigger.py | infrastructure/config/ | infrastructure/config/ | 保留 | 配置 |
| equilibrium.py | infrastructure/config/ | infrastructure/config/ | 保留 | 配置 |
| memory.py | infrastructure/config/ | infrastructure/config/ | 保留 | 配置 |
| metrics.py | infrastructure/config/ | infrastructure/config/ | 保留 | 配置 |
| minio.py | infrastructure/config/ | infrastructure/config/ | 保留 | 配置 |
| neo4j.py | infrastructure/config/ | infrastructure/config/ | 保留 | 配置 |
| postgresql.py | infrastructure/config/ | infrastructure/config/ | 保留 | 配置 |
| qdrant.py | infrastructure/config/ | infrastructure/config/ | 保留 | 配置 |
| rabbitmq.py | infrastructure/config/ | infrastructure/config/ | 保留 | 配置 |
| redis.py | infrastructure/config/ | infrastructure/config/ | 保留 | 配置 |
| **sovereignty.py** | infrastructure/config/ | infrastructure/config/ | **审查** | 导入 security/models |
| udmr.py | infrastructure/config/ | infrastructure/config/ | 保留 | 配置 |

#### 4.3.2 routing/ — 需审查 local_model_health.py

| 文件 | 当前位置 | 目标位置 | 操作 | 理由 |
|------|----------|----------|------|------|
| fallback_router.py | infrastructure/routing/ | infrastructure/routing/ | 保留 | 具体实现 |
| hash_router.py | infrastructure/routing/ | infrastructure/routing/ | 保留 | 具体实现 |
| local_model_health.py | infrastructure/routing/ | infrastructure/routing/ | **审查** | 已废弃，仅做兼容导入 |
| ollama_health_adapter.py | infrastructure/routing/ | infrastructure/routing/ | 保留 | 具体实现 |
| semantic_router.py | infrastructure/routing/ | infrastructure/routing/ | 保留 | 具体实现 |

#### 4.3.3 messaging/ — 新目录（接收移动文件）

| 文件 | 来源 | 目标位置 | 操作 |
|------|------|----------|------|
| event_publisher.py | domain/events/publisher.py | infrastructure/messaging/ | 移动 |
| event_listener.py | domain/events/listener.py | infrastructure/messaging/ | 移动 |
| publish_result.py | domain/events/publish_result.py | infrastructure/messaging/ | 移动 |

#### 4.3.4 events/ — 新目录（接收移动文件）

| 文件 | 来源 | 目标位置 | 操作 |
|------|------|----------|------|
| event_store.py | domain/events/store.py | infrastructure/events/ | 移动 |

#### 4.3.5 storage/ — 位置正确

| 文件 | 当前位置 | 操作 |
|------|----------|------|
| file_memory_adapter.py | infrastructure/storage/ | 保留 |
| memory_index.py | infrastructure/storage/ | 保留 |
| memory_router.py | infrastructure/storage/ | 保留 |
| redis_snapshot_store.py | infrastructure/storage/ | 保留 |
| minio/* | infrastructure/storage/minio/ | 保留 |
| neo4j/* | infrastructure/storage/neo4j/ | 保留 |
| postgresql/* | infrastructure/storage/postgresql/ | 保留 |
| qdrant/* | infrastructure/storage/qdrant/ | 保留 |
| redis/* | infrastructure/storage/redis/ | 保留 |

#### 4.3.6 security/ — 需审查

| 文件 | 当前位置 | 操作 | 理由 |
|------|----------|------|------|
| approval_workflow.py | infrastructure/security/ | 保留 | 具体实现 |
| auth_service.py | infrastructure/security/ | 保留 | 具体实现 |
| compliance_service.py | infrastructure/security/ | 保留 | 具体实现 |
| data_sovereignty_service.py | infrastructure/security/ | 保留 | 具体实现 |
| encryption_service.py | infrastructure/security/ | 保留 | 具体实现 |
| integrity_service.py | infrastructure/security/ | 保留 | 具体实现 |
| intrusion_detector.py | infrastructure/security/ | 保留 | 具体实现 |
| jwt_service.py | infrastructure/security/ | 保留 | 具体实现 |
| memory_access_control.py | infrastructure/security/ | 保留 | 具体实现 |
| mfa_service.py | infrastructure/security/ | 保留 | 具体实现 |
| models.py | infrastructure/security/ | 保留 | 数据模型 |
| permission_middleware.py | infrastructure/security/ | 保留 | 具体实现 |
| permission_service.py | infrastructure/security/ | 保留 | 具体实现 |
| pipl_compliance.py | infrastructure/security/ | 保留 | 具体实现 |
| recovery_service.py | infrastructure/security/ | 保留 | 具体实现 |
| role_service.py | infrastructure/security/ | 保留 | 具体实现 |
| sensitive_data_detector.py | infrastructure/security/ | 保留 | 具体实现 |
| totp_generator.py | infrastructure/security/ | 保留 | 具体实现 |
| whitelist_service.py | infrastructure/security/ | 保留 | 具体实现 |
| backup_service.py | infrastructure/security/ | 保留 | 具体实现 |

---

### 4.4 Interfaces 层文件位置方案

#### 4.4.1 api/ — 位置正确

| 文件 | 当前位置 | 操作 | 理由 |
|------|----------|------|------|
| auth.py | interfaces/api/ | 保留 | FastAPI 端点（预期） |
| equilibrium_api.py | interfaces/api/ | 保留 | FastAPI 端点 |
| equilibrium_endpoints.py | interfaces/api/ | 保留 | FastAPI 端点 |
| monitoring.py | interfaces/api/ | 保留 | FastAPI 端点 |
| sovereignty_api.py | interfaces/api/ | 保留 | FastAPI 端点 |
| sovereignty_endpoints.py | interfaces/api/ | 保留 | FastAPI 端点 |

#### 4.4.2 event_listeners/ — 位置正确

| 文件 | 当前位置 | 操作 | 理由 |
|------|----------|------|------|
| auto_execute_completed_listener.py | interfaces/event_listeners/ | 保留 | 具体实现 |
| auto_route_listener.py | interfaces/event_listeners/ | 保留 | 具体实现 |
| auto_trigger_listener.py | interfaces/event_listeners/ | 保留 | 具体实现 |
| memory_changed_listener.py | interfaces/event_listeners/ | 保留 | 具体实现 |

#### 4.4.3 cli/ — 位置正确

| 文件 | 当前位置 | 操作 | 理由 |
|------|----------|------|------|
| (commands/) | interfaces/cli/ | 保留 | Typer 命令（预期） |

---

## 5. 迁移执行计划

### 5.1 Phase 1: Domain 层重构

```bash
# 1. 重命名 repositories/ → ports/
mv src/domain/repositories/ src/domain/ports/

# 2. 创建 domain/exceptions/ 内容
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

cat > src/domain/exceptions/memory_exceptions.py << 'EOF'
"""Memory domain exceptions."""

class MemoryNotFoundError(Exception):
    """Raised when a memory entity is not found."""
    pass

class MemoryVersionConflictError(Exception):
    """Raised when memory version conflict occurs during update."""
    pass
EOF

# 3. 创建 application/ports/ 目录并迁移 Protocol
mkdir -p src/application/ports/
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

### 5.2 Phase 2: 事件基础设施迁移

```bash
# 1. 创建 infrastructure/messaging/ 和 infrastructure/events/
mkdir -p src/infrastructure/messaging/
mkdir -p src/infrastructure/events/

# 2. 移动事件基础设施文件
mv src/domain/events/publisher.py src/infrastructure/messaging/event_publisher.py
mv src/domain/events/listener.py src/infrastructure/messaging/event_listener.py
mv src/domain/events/store.py src/infrastructure/events/event_store.py
mv src/domain/events/publish_result.py src/infrastructure/messaging/publish_result.py

# 3. 修改 domain/events/base.py — 移除序列化方法
```

### 5.3 Phase 3: 清理与验证

```bash
# 1. 更新所有 __init__.py 导出
# 2. 更新所有导入路径
# 3. 运行测试验证
poetry run pytest tests/ -v
poetry run mypy .
poetry run ruff check .
```

---

## 6. 影响范围

### 6.1 文件操作统计

| 操作类型 | 文件数 |
|----------|--------|
| 重命名目录 | 1 (repositories → ports) |
| 移动文件 | 17 |
| 新建文件 | 2 |
| 修改文件 | 1 (base.py) |

### 6.2 需更新的导入路径

| 层级 | 影响文件数（估计） |
|------|-------------------|
| domain/ | ~30 |
| application/ | ~15 |
| infrastructure/ | ~40 |
| interfaces/ | ~20 |
| tests/ | ~50 |
| **总计** | **~155 files** |

---

## 7. 验收标准

- [ ] `domain/repositories/` 目录重命名为 `domain/ports/`
- [ ] 9 个 Protocol 文件从 `domain/services/` 移至 `application/ports/`
- [ ] 4 个事件基础设施文件从 `domain/events/` 移至 `infrastructure/`
- [ ] `DomainEvent` 类不包含 `to_dict()` / `from_dict()` 方法
- [ ] `domain/exceptions/` 包含 `MemoryNotFoundError` 和 `MemoryVersionConflictError`
- [ ] 所有 3572 个测试通过
- [ ] `mypy .` 无错误
- [ ] `ruff check .` 无错误

---

## 8. 六边形架构视角

```
                        Driver Side (调用方)
┌─────────────────────────────────────────────────────────────┐
│  interfaces/          │     application/                  │
│  ┌─────────────────┐  │  ┌─────────────────────────────┐   │
│  │  FastAPI API    │  │  │  Use Cases / Services       │   │
│  │  CLI Commands   │  │  │  SixLayerStorageCoordinator │   │
│  │  EventListeners │  │  └──────────────┬──────────────┘   │
│  └───────┬─────────┘  │                 │                  │
└──────────┼────────────┘  ┌──────────────▼──────────────┐   │
           │               │  Driver Ports (应用层端口)    │   │
           │               │  AuditService Protocol       │   │
           │               │  AuthService Protocol        │   │
           │               └──────────────┬──────────────┘   │
           │                              │                  │
┌──────────┼──────────────────────────────┼──────────────────┐
│          │       domain/                 │                  │
│  ┌───────▼────────┐   ┌────────────────▼────────────────┐  │
│  │   Entities     │   │         Ports (领域端口)        │  │
│  │   Events       │   │  HealthCheckPort              │  │
│  │   Value Objects│   │  IntegrityPort                │  │
│  │                │   │  L0StoragePort                │  │
│  └───────┬────────┘   └──────────────┬─────────────────┘  │
│          │                          │                     │
│          │     ┌─────────────────────▼─────────────────┐     │
│          │     │        Domain Services              │     │
│          │     │  MemoryService                      │     │
│          │     │  AutoTriggerService                │     │
│          │     │  UDMRouter                          │     │
│          │     └─────────────────────────────────────┘     │
└──────────┼─────────────────────────────────────────────────┘
           │
┌──────────┼─────────────────────────────────────────────────┐
│          │     infrastructure/                            │
│  ┌───────▼─────────────────────────────────────────┐     │
│  │              Driven Ports (适配器实现)             │     │
│  │  ┌────────────┐ ┌──────────┐ ┌────────────────┐  │     │
│  │  │ PostgreSQL │ │  Redis  │ │     MinIO      │  │     │
│  │  │ Repository │ │  Cache  │ │  Repository   │  │     │
│  │  └────────────┘ └──────────┘ └────────────────┘  │     │
│  │  ┌────────────┐ ┌──────────┐ ┌────────────────┐  │     │
│  │  │  Qdrant    │ │  Neo4j   │ │ FileMemory     │  │     │
│  │  │  Vector    │ │  Graph   │ │  Adapter      │  │     │
│  │  └────────────┘ └──────────┘ └────────────────┘  │     │
│  └────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

---

## 9. 附录

### A. 关键原则

1. **领域层零外部依赖** — domain 只用 Python 标准库
2. **Port 接口定义在 domain，实现在 infrastructure** — 依赖倒置
3. **事件基础设施在 infrastructure** — 发布-订阅是技术机制，不是领域概念
4. **Protocol 定义在应用层或 domain** —取决于用途
   - 若被 domain 服务使用 → domain/ports/
   - 若被 application 服务使用 → application/ports/

### B. 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| Port 接口 | `XxxPort` 或 `XxxProtocol` | `HealthCheckPort`, `IntegrityPort` |
| Repository 接口 | `XxxRepositoryProtocol` | `MemoryMetadataRepositoryProtocol` |
| 领域服务 | `XxxService` | `MemoryService`, `AutoRouteService` |
| 领域异常 | `XxxError` | `MemoryNotFoundError` |
| 值对象 | `XxxContext` / `XxxDecision` | `AutoTriggerContext`, `RoutingDecision` |
| 事件基础设施 | `XxxPublisher` / `XxxListener` | `EventPublisher`, `EventListener` |
