# Story 20-5: 全局目录结构与序列化框架重构

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 系统架构师,
**I want** 实施全局目录结构重构与序列化框架重构,
**So that** 遵循六边形架构约束，实现领域层零外部依赖，确立序列化框架的 Serializable Protocol 方案。

### 业务价值

| 分组 | 现状 | 目标 |
|------|------|------|
| **目录命名** | `repositories/` 实际是 Port 接口 | 重命名为 `ports/` |
| **事件基础设施** | 混入领域层 | 移动到 `infrastructure/messaging/` |
| **Protocol 错位** | 纯接口混入 `domain/services/` | 移动到 `application/ports/` |
| **序列化职责混乱** | 领域实体直接实现序列化 | 采用 Serializable Protocol 方案 |
| **异常定义分散** | `MemoryNotFoundError` 在 `memory_service.py` | 集中到 `domain/exceptions/` |

### 方案背景

**来源**: `docs/developer/sisys-src-dir-refactor.md` v2.17（第七轮宗师级审查完成）

**问题覆盖**:

| 问题类型 | 问题描述 | 解决方案 |
|---------|---------|---------|
| P0-1 | `domain/repositories/` 命名不准确 | 重命名为 `domain/ports/` |
| P0-2 | 事件基础设施（publisher.py, listener.py, publish_result.py）混入领域 | 移动到 `infrastructure/messaging/` |
| P0-3 | `EventStore` ABC 应保留在 `domain/events/` | 是领域层 Port 接口定义 |
| P1-1 | 纯 Protocol 定义（AuditService, AuthService 等）混入 `domain/services/` | 移动到 `application/ports/` |
| P1-2 | `domain/events/base.py` 的 `to_dict()/from_dict()` 违反六边形架构 | 实现 Serializable Protocol |
| P1-3 | `CheckpointSnapshot` 的 `to_redis_hash()/from_redis_hash()` 领域层感知基础设施 | 实现 Serializable Protocol |
| P2-1 | `MemoryNotFoundError` 定义在 `memory_service.py` | 集中到 `domain/exceptions/` |
| P2-2 | `infrastructure/security/models.py` 命名混淆 | 重命名为 `value_objects.py` |
| P2-3 | `infrastructure/config/sovereignty.py` 跨层导入 | 新建 `domain/value_objects/sensitive_data.py` |

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 目录重命名 repositories → ports

**Given** 需要准确反映 Port 接口本质
**When** 重命名 `domain/repositories/` 为 `domain/ports/`
**Then** 所有导入路径更新，代码无断裂

**验证标准:**
- [ ] `domain/repositories/` 目录重命名为 `domain/ports/`
- [ ] 所有 `from src.domain.repositories` 导入更新为 `from src.domain.ports`
- [ ] `__init__.py` 导出正确
- [ ] `ruff check src/domain/` 通过

### AC-2: 事件基础设施移动到 infrastructure

**Given** 事件发布-订阅是技术机制，不是领域概念
**When** 移动事件基础设施文件
**Then** 3 个文件从 `domain/events/` 移动到 `infrastructure/messaging/`

**验证标准:**
- [ ] `domain/events/publisher.py` → `infrastructure/messaging/event_publisher.py`
- [ ] `domain/events/listener.py` → `infrastructure/messaging/event_listener.py`
- [ ] `domain/events/publish_result.py` → `infrastructure/messaging/publish_result.py`
- [ ] `EventStore` ABC 保留在 `domain/events/event_store.py`（是领域层 Port 接口）
- [ ] 所有导入路径更新

### AC-3: Protocol 文件移动到 application/ports

**Given** 纯接口定义应在应用层
**When** 移动 7 个 Protocol 文件
**Then** 从 `domain/services/` 移动到 `application/ports/`

**验证标准:**
- [ ] `audit_service.py` → `audit_port.py`
- [ ] `auth_service.py` → `auth_port.py`
- [ ] `permission_service.py` → `permission_port.py`
- [ ] `public_blackboard.py` → `public_blackboard_port.py`
- [ ] `semantic_cache.py` → `semantic_cache_port.py`
- [ ] `compressor_service.py` → `compressor_port.py`
- [ ] `text_extractor_service.py` → `text_extractor_port.py`
- [ ] 所有导入路径更新

### AC-4: Serializable Protocol 定义（domain 层）

**Given** 需要统一序列化抽象
**When** 定义 `Serializable` Protocol 和 `SerializationField`
**Then** 领域实体可实现该 Protocol

**验证标准:**
- [ ] `domain/ports/serialization.py` 定义 `Serializable` Protocol
- [ ] `domain/ports/serialization.py` 定义 `SerializationField` dataclass
- [ ] `get_serialization_type() -> str` 抽象方法
- [ ] `get_fields() -> list[SerializationField]` 抽象方法
- [ ] 领域层零外部依赖（仅用 dataclasses, typing, abc）

### AC-5: DomainEvent 实现 Serializable Protocol

**Given** 需要移除领域层的序列化方法
**When** 改造 `DomainEvent` 类
**Then** 实现 Serializable Protocol，无 `to_dict()/from_dict()` 方法

**验证标准:**
- [ ] `DomainEvent.get_serialization_type()` 返回 `event_type` 字段值
- [ ] `DomainEvent.get_fields()` 返回所有字段的 SerializationField 列表
- [ ] 移除 `to_dict()` 方法
- [ ] 移除 `from_dict()` 方法
- [ ] `__init_subclass__` 自动向 `TypeRegistry` 注册子类

### AC-6: CheckpointSnapshot 实现 Serializable Protocol

**Given** 需要移除领域层的 Redis 序列化方法
**When** 改造 `CheckpointSnapshot` 类
**Then** 实现 Serializable Protocol，无 `to_redis_hash()/from_redis_hash()` 方法

**验证标准:**
- [ ] `CheckpointSnapshot.get_serialization_type()` 返回 `"CheckpointSnapshot"`
- [ ] `CheckpointSnapshot.get_fields()` 返回所有字段的 SerializationField 列表
- [ ] 移除 `to_redis_hash()` 方法
- [ ] 移除 `from_redis_hash()` 方法

### AC-7: SerializationPort 定义（application 层）

**Given** 需要序列化抽象接口
**When** 定义 `SerializationPort` 抽象接口
**Then** 基础设施层实现该接口

**验证标准:**
- [ ] `application/ports/serialization.py` 定义 `SerializationPort[T]` 泛型抽象类
- [ ] `serialize(obj: T) -> Any` 抽象方法
- [ ] `deserialize(data: Any, target_type: type[T] | str) -> T` 抽象方法
- [ ] `can_handle(obj_or_type: Any) -> bool` 抽象方法

### AC-8: StandardSerializeRules 实现

**Given** 需要标准类型转换规则
**When** 实现 `StandardSerializeRules` 类
**Then** 提供 UUID、datetime、Enum 等标准类型转换

**验证标准:**
- [ ] `application/ports/serialization_rules.py` 定义 `StandardSerializeRules`
- [ ] `serialize_dataclass(obj)` 将 dataclass 转为 dict
- [ ] `_serialize_value(value)` 递归序列化（UUID→str, datetime→isoformat, Enum→value）
- [ ] 处理 list/dict 嵌套

### AC-9: TypeRegistry 实现

**Given** 需要类型注册表支持多态反序列化
**When** 实现 `TypeRegistry` 类
**Then** 根据类型标识符解析具体类型

**验证标准:**
- [ ] `application/ports/type_registry.py` 定义 `TypeRegistry`
- [ ] `register(type_id: str, typ: type)` 注册类型映射
- [ ] `resolve(type_id: str) -> type | None` 解析类型
- [ ] `auto_register_domain_events()` 自动注册所有 DomainEvent 子类

### AC-10: JsonSerializer 实现

**Given** SerializationPort 接口已定义
**When** 实现 `JsonSerializer`
**Then** 支持对象 ↔ JSON 字符串转换

**验证标准:**
- [ ] `infrastructure/serialization/json_serializer.py` 实现 `JsonSerializer`
- [ ] 实现 `SerializationPort` 接口
- [ ] `serialize()` → JSON 字符串
- [ ] `deserialize()` 从 JSON 字符串恢复对象
- [ ] `_resolve_type()` 使用 `TypeRegistry.resolve()`
- [ ] 正确处理 `is_union=True` 字段（UUID | None）

### AC-11: RedisHashSerializer 实现

**Given** SerializationPort 接口已定义
**When** 实现 `RedisHashSerializer`
**Then** 支持对象 ↔ Redis Hash（dict[str, str]）转换

**验证标准:**
- [ ] `infrastructure/serialization/redis_hash_serializer.py` 实现 `RedisHashSerializer`
- [ ] 实现 `SerializationPort` 接口
- [ ] `serialize()` → `dict[str, str]`（所有值为 string）
- [ ] `deserialize()` 从 dict[str, str] 恢复对象
- [ ] `_resolve_type()` 使用 `TypeRegistry.resolve()`
- [ ] 正确处理 `is_union=True` 字段

### AC-12: domain/exceptions/ 集中管理异常

**Given** 领域异常应集中定义
**When** 创建 `domain/exceptions/` 目录
**Then** `MemoryNotFoundError` 和 `MemoryVersionConflictError` 正确导出

**验证标准:**
- [ ] `domain/exceptions/__init__.py` 导出异常
- [ ] `domain/exceptions/memory_exceptions.py` 定义异常类
- [ ] `domain/services/memory_service.py` 从 `domain.exceptions` 导入

### AC-13: sovereignty.py 跨层导入修复

**Given** 配置层不应依赖安全服务层
**When** 修复 `infrastructure/config/sovereignty.py` 导入
**Then** 从 `domain.value_objects.sensitive_data` 导入

**验证标准:**
- [ ] 新建 `domain/value_objects/sensitive_data.py`
- [ ] `domain/value_objects/sensitive_data.py` 包含 `SensitiveDataType`, `DataResidency`, `WhitelistStatus`, `ApprovalStatus` 等值对象
- [ ] `infrastructure/security/models.py` 重命名为 `infrastructure/security/value_objects.py`
- [ ] `infrastructure/config/sovereignty.py` 从 `domain.value_objects.sensitive_data` 导入
- [ ] 所有导入 `security/value_objects.py` 的文件已更新

### AC-14: 调用方改造

**Given** 序列化器接管序列化职责
**When** 改造调用方代码
**Then** 使用序列化器而非直接调用实体方法

**验证标准:**
- [ ] `PostgreSQLEventStore` 使用 `JsonSerializer` 而非 `DomainEvent.from_dict()`
- [ ] `RedisSnapshotStore` 使用 `RedisHashSerializer` 而非 `CheckpointSnapshot.to_redis_hash()`
- [ ] `RedisSnapshotStore` 引用 `infrastructure/serialization/redis_hash_serializer.py`
- [ ] 所有测试通过

### AC-15: 六边形架构约束验证

**Given** 代码重构完成
**When** 运行架构检查
**Then** 领域层零外部依赖约束满足

**验证标准:**
- [ ] `ruff check src/domain/` 无外部依赖违规
- [ ] `mypy src/domain/` 类型检查通过
- [ ] 依赖方向正确（domain ← application ← infrastructure）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

**Task 0 完成标志：**
- [ ] 确认 `docs/developer/sisys-src-dir-refactor.md` v2.17 作为唯一规范来源
- [ ] 确认 9 个文件移动方案符合六边形架构约束
- [ ] 确认 9 个新建文件符合序列化框架设计
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证）

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 目录重命名 repositories → ports | Task 1 | Subtask 1.1-1.4 | `test_domain_ports_rename.py` |
| AC-2 | 事件基础设施移动到 infrastructure | Task 2 | Subtask 2.1-2.5 | `test_event_infra_move.py` |
| AC-3 | Protocol 文件移动到 application/ports | Task 3 | Subtask 3.1-3.9 | `test_protocol_file_move.py` |
| AC-4 | Serializable Protocol 定义 | Task 4 | Subtask 4.1-4.3 | `test_serializable_protocol.py` |
| AC-5 | DomainEvent 实现 Serializable Protocol | Task 5 | Subtask 5.1-5.6 | `test_domain_event_serialization.py` |
| AC-6 | CheckpointSnapshot 实现 Serializable Protocol | Task 6 | Subtask 6.1-6.5 | `test_checkpoint_snapshot_serialization.py` |
| AC-7 | SerializationPort 定义 | Task 7 | Subtask 7.1-7.3 | `test_serialization_port.py` |
| AC-8 | StandardSerializeRules 实现 | Task 8 | Subtask 8.1-8.3 | `test_serialize_rules.py` |
| AC-9 | TypeRegistry 实现 | Task 9 | Subtask 9.1-9.5 | `test_type_registry.py` |
| AC-10 | JsonSerializer 实现 | Task 10 | Subtask 10.1-10.5 | `test_json_serializer.py` |
| AC-11 | RedisHashSerializer 实现 | Task 11 | Subtask 11.1-11.5 | `test_redis_hash_serializer.py` |
| AC-12 | domain/exceptions/ 集中管理异常 | Task 12 | Subtask 12.1-12.4 | `test_domain_exceptions.py` |
| AC-13 | sovereignty.py 跨层导入修复 | Task 13 | Subtask 13.1-13.4 | `test_sovereignty_fix.py` |
| AC-14 | 调用方改造 | Task 14 | Subtask 14.1-14.4 | `test_caller_refactor.py` |
| AC-15 | 六边形架构约束验证 | Task 15 | Subtask 15.1-15.5 | `test_hexagonal_constraints.py` |

### Task 执行顺序与依赖关系

> ⚠️ **重要约束：** 虽然每个 Task 内部独立完成 TDD 循环，但 Task 之间存在依赖关系，必须按顺序执行。

| 阶段 | Task | 依赖说明 |
|------|------|----------|
| **阶段一：文件迁移** | Task 1-3 | 可并行执行文件移动操作 |
| **阶段二：序列化框架** | Task 4-11 | 依赖阶段一完成（`domain/ports/`, `application/ports/` 目录已存在） |
| **阶段三：收尾** | Task 12-15 | 依赖序列化框架完成 |

**依赖链：**
```
Task 1 (目录重命名) ─┬─→ Task 4 (Serializable Protocol) ─→ Task 5 → Task 6
                     │                                       ↓
Task 2 (事件基础设施)─┤           Task 7 (SerializationPort) ←←←←←←←←┘
                     │                   ↓
Task 3 (Protocol移动)─┴─→ Task 8 (StandardSerializeRules)
                            ↓
                     Task 9 (TypeRegistry) ─→ Task 10 → Task 11
                                                    ↓
                     Task 12 (exceptions) ← Task 13 (sovereignty)
                            ↓
                     Task 14 (调用方改造)
                            ↓
                     Task 15 (架构验证)
```

---

## 📋 Tasks / Subtasks 任务分解

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** 全部 AC

- [ ] Subtask 0.1: 确认方案文档 v2.17 版本
- [ ] Subtask 0.2: 确认 9 个文件移动方案符合六边形架构约束
- [ ] Subtask 0.3: 确认 9 个新建文件符合序列化框架设计
- [ ] Subtask 0.4: 编写 Gherkin 验收测试 `tests/acceptance/test_story_20_5.feature`
- [ ] Subtask 0.5: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准:**
- [ ] 方案文档版本确认
- [ ] 架构约束验证通过
- [ ] 验收测试红阶段确认

---

### Task 1: 目录重命名 repositories → ports

**关联 AC:** AC-1

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_domain_ports_rename.py` |
| 🟢 绿 | 执行 `mv src/domain/repositories/ src/domain/ports/` |
| 🔄 重构 | 更新所有导入路径 |

- [ ] Subtask 1.1: 🔴 红 — 编写测试验证 `domain/ports/` 存在
- [ ] Subtask 1.2: 🟢 绿 — 执行目录重命名
- [ ] Subtask 1.3: 🟢 绿 — 更新 `__init__.py` 导出
- [ ] Subtask 1.4: 🔄 重构 — 运行 `ruff check src/domain/` 验证

**完成标准:**
- [ ] 目录重命名完成
- [ ] 所有导入路径更新
- [ ] 测试通过

---

### Task 2: 事件基础设施移动到 infrastructure

**关联 AC:** AC-2

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_event_infra_move.py` |
| 🟢 绿 | 移动 3 个文件到 `infrastructure/messaging/` |
| 🔄 重构 | 更新所有导入路径 |

- [ ] Subtask 2.1: 🔴 红 — 编写测试验证文件目标位置
- [ ] Subtask 2.2: 🟢 绿 — 移动 `publisher.py` → `event_publisher.py`
- [ ] Subtask 2.3: 🟢 绿 — 移动 `listener.py` → `event_listener.py`
- [ ] Subtask 2.4: 🟢 绿 — 移动 `publish_result.py` → `publish_result.py`
- [ ] Subtask 2.5: 🔄 重构 — 更新所有导入路径，验证 `EventStore` 保留在 `domain/events/`

**完成标准:**
- [ ] 3 个文件移动完成
- [ ] `EventStore` ABC 保留在 `domain/events/`
- [ ] 所有导入路径更新

---

### Task 3: Protocol 文件移动到 application/ports

**关联 AC:** AC-3

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_protocol_file_move.py` |
| 🟢 绿 | 移动 7 个 Protocol 文件 |
| 🔄 重构 | 更新所有导入路径 |

- [ ] Subtask 3.1: 🔴 红 — 编写测试验证 `application/ports/` 目录
- [ ] Subtask 3.2: 🟢 绿 — 移动 `audit_service.py` → `audit_port.py`
- [ ] Subtask 3.3: 🟢 绿 — 移动 `auth_service.py` → `auth_port.py`
- [ ] Subtask 3.4: 🟢 绿 — 移动 `permission_service.py` → `permission_port.py`
- [ ] Subtask 3.5: 🟢 绿 — 移动 `public_blackboard.py` → `public_blackboard_port.py`
- [ ] Subtask 3.6: 🟢 绿 — 移动 `semantic_cache.py` → `semantic_cache_port.py`
- [ ] Subtask 3.7: 🟢 绿 — 移动 `compressor_service.py` → `compressor_port.py`
- [ ] Subtask 3.8: 🟢 绿 — 移动 `text_extractor_service.py` → `text_extractor_port.py`
- [ ] Subtask 3.9: 🔄 重构 — 更新所有导入路径

**完成标准:**
- [ ] 7 个 Protocol 文件移动完成
- [ ] 所有导入路径更新

---

### Task 4: Serializable Protocol 定义（domain 层）

**关联 AC:** AC-4

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_serializable_protocol.py` |
| 🟢 绿 | 实现 `Serializable` Protocol 和 `SerializationField` |
| 🔄 重构 | 运行 `ruff` + `mypy` |

- [ ] Subtask 4.1: 🔴 红 — 编写测试验证 Protocol 定义
- [ ] Subtask 4.2: 🟢 绿 — 创建 `domain/ports/serialization.py`
- [ ] Subtask 4.3: 🔄 重构 — 验证领域层零依赖

**完成标准:**
- [ ] `Serializable` Protocol 定义完成
- [ ] `SerializationField` dataclass 定义完成
- [ ] 领域层零外部依赖验证

---

### Task 5: DomainEvent 实现 Serializable Protocol

**关联 AC:** AC-5

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_domain_event_serialization.py` |
| 🟢 绿 — 移除 to_dict/from_dict，实现 Serializable | 实现 `get_serialization_type()` 和 `get_fields()` |
| 🔄 重构 | 运行 `ruff` + `mypy` |

- [ ] Subtask 5.1: 🔴 红 — 编写测试验证 `DomainEvent` 实现 Protocol
- [ ] Subtask 5.2: 🟢 绿 — 移除 `to_dict()` 和 `from_dict()` 方法
- [ ] Subtask 5.3: 🟢 绿 — 实现 `get_serialization_type()` 返回 `event_type`
- [ ] Subtask 5.4: 🟢 绿 — 实现 `get_fields()` 返回 SerializationField 列表
- [ ] Subtask 5.5: 🟢 绿 — 实现 `__init_subclass__` 自动向 `TypeRegistry` 注册
- [ ] Subtask 5.6: 🔄 重构 — 运行 `ruff` + `mypy`

**完成标准:**
- [ ] `DomainEvent` 实现 Serializable Protocol
- [ ] 序列化方法已移除
- [ ] TypeRegistry 自动注册生效

---

### Task 6: CheckpointSnapshot 实现 Serializable Protocol

**关联 AC:** AC-6

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_checkpoint_snapshot_serialization.py` |
| 🟢 绿 — 移除 to_redis_hash/from_redis_hash，实现 Serializable | 实现 `get_serialization_type()` 和 `get_fields()` |
| 🔄 重构 | 运行 `ruff` + `mypy` |

- [ ] Subtask 6.1: 🔴 红 — 编写测试验证 `CheckpointSnapshot` 实现 Protocol
- [ ] Subtask 6.2: 🟢 绿 — 移除 `to_redis_hash()` 和 `from_redis_hash()` 方法
- [ ] Subtask 6.3: 🟢 绿 — 实现 `get_serialization_type()` 返回 `"CheckpointSnapshot"`
- [ ] Subtask 6.4: 🟢 绿 — 实现 `get_fields()` 返回 SerializationField 列表
- [ ] Subtask 6.5: 🔄 重构 — 运行 `ruff` + `mypy`

**完成标准:**
- [ ] `CheckpointSnapshot` 实现 Serializable Protocol
- [ ] Redis 序列化方法已移除

---

### Task 7: SerializationPort 定义（application 层）

**关联 AC:** AC-7

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_serialization_port.py` |
| 🟢 绿 | 实现 `SerializationPort` 抽象接口 |
| 🔄 重构 | 运行 `ruff` + `mypy` |

- [ ] Subtask 7.1: 🔴 红 — 编写测试验证 `SerializationPort` 接口
- [ ] Subtask 7.2: 🟢 绿 — 创建 `application/ports/serialization.py`
- [ ] Subtask 7.3: 🔄 重构 — 验证接口定义正确

**完成标准:**
- [ ] `SerializationPort[T]` 泛型抽象类定义完成
- [ ] 3 个抽象方法定义完成

---

### Task 8: StandardSerializeRules 实现

**关联 AC:** AC-8

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_serialize_rules.py` |
| 🟢 绿 | 实现 `StandardSerializeRules` 类 |
| 🔄 重构 | 运行 `ruff` + `mypy` |

- [ ] Subtask 8.1: 🔴 红 — 编写测试验证类型转换规则
- [ ] Subtask 8.2: 🟢 绿 — 创建 `application/ports/serialization_rules.py`
- [ ] Subtask 8.3: 🔄 重构 — 验证嵌套类型处理

**完成标准:**
- [ ] `StandardSerializeRules` 实现完成
- [ ] UUID、datetime、Enum 转换正确
- [ ] 嵌套类型处理正确

---

### Task 9: TypeRegistry 实现

**关联 AC:** AC-9

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_type_registry.py` |
| 🟢 绿 | 实现 `TypeRegistry` 类 |
| 🔄 重构 | 运行 `ruff` + `mypy` |

- [ ] Subtask 9.1: 🔴 红 — 编写测试验证类型注册和解析
- [ ] Subtask 9.2: 🟢 绿 — 创建 `application/ports/type_registry.py`
- [ ] Subtask 9.3: 🟢 绿 — 实现 `register()` 和 `resolve()`
- [ ] Subtask 9.4: 🟢 绿 — 实现 `auto_register_domain_events()`
- [ ] Subtask 9.5: 🔄 重构 — 验证 DomainEvent 子类自动注册

**完成标准:**
- [ ] `TypeRegistry` 实现完成
- [ ] DomainEvent 子类自动注册生效

---

### Task 10: JsonSerializer 实现

**关联 AC:** AC-10

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_json_serializer.py` |
| 🟢 绿 | 实现 `JsonSerializer` 类 |
| 🔄 重构 | 运行 `ruff` + `mypy` |

- [ ] Subtask 10.1: 🔴 红 — 编写测试验证 JSON 序列化/反序列化
- [ ] Subtask 10.2: 🟢 绿 — 创建 `infrastructure/serialization/json_serializer.py`
- [ ] Subtask 10.3: 🟢 绿 — 实现 `serialize()` 和 `deserialize()`
- [ ] Subtask 10.4: 🟢 绿 — 实现 `_resolve_type()` 使用 TypeRegistry
- [ ] Subtask 10.5: 🔄 重构 — 验证 Union 类型处理

**完成标准:**
- [ ] `JsonSerializer` 实现完成
- [ ] Union 类型（UUID | None）处理正确

---

### Task 11: RedisHashSerializer 实现

**关联 AC:** AC-11

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_redis_hash_serializer.py` |
| 🟢 绿 | 实现 `RedisHashSerializer` 类 |
| 🔄 重构 | 运行 `ruff` + `mypy` |

- [ ] Subtask 11.1: 🔴 红 — 编写测试验证 Redis Hash 序列化/反序列化
- [ ] Subtask 11.2: 🟢 绿 — 创建 `infrastructure/serialization/redis_hash_serializer.py`
- [ ] Subtask 11.3: 🟢 绿 — 实现 `serialize()` 和 `deserialize()`
- [ ] Subtask 11.4: 🟢 绿 — 实现 `_resolve_type()` 使用 TypeRegistry
- [ ] Subtask 11.5: 🔄 重构 — 验证 Union 类型处理

**完成标准:**
- [ ] `RedisHashSerializer` 实现完成
- [ ] 所有值为 string 类型

---

### Task 12: domain/exceptions/ 集中管理异常

**关联 AC:** AC-12

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_domain_exceptions.py` |
| 🟢 绿 | 创建 `domain/exceptions/` 目录和文件 |
| 🔄 重构 | 更新 `memory_service.py` 导入 |

- [ ] Subtask 12.1: 🔴 红 — 编写测试验证异常定义
- [ ] Subtask 12.2: 🟢 绿 — 创建 `domain/exceptions/__init__.py`
- [ ] Subtask 12.3: 🟢 绿 — 创建 `domain/exceptions/memory_exceptions.py`
- [ ] Subtask 12.4: 🔄 重构 — 更新 `memory_service.py` 导入路径

**完成标准:**
- [ ] 异常集中管理完成
- [ ] 导入路径更新正确

---

### Task 13: sovereignty.py 跨层导入修复

**关联 AC:** AC-13

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_sovereignty_fix.py` |
| 🟢 绿 | 执行重命名和新建文件 |
| 🔄 重构 | 更新 sovereignty.py 导入 |

- [ ] Subtask 13.1: 🔴 红 — 编写测试验证导入路径
- [ ] Subtask 13.2: 🟢 绿 — 新建 `domain/value_objects/sensitive_data.py`
- [ ] Subtask 13.3: 🟢 绿 — 重命名 `security/models.py` → `security/value_objects.py`
- [ ] Subtask 13.4: 🔄 重构 — 更新 `sovereignty.py` 导入路径

**完成标准:**
- [ ] 跨层导入修复完成
- [ ] 领域层值对象位于正确位置

---

### Task 14: 调用方改造

**关联 AC:** AC-14

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_caller_refactor.py` |
| 🟢 绿 | 改造 PostgreSQLEventStore 和 RedisSnapshotStore |
| 🔄 重构 | 验证序列化器使用正确 |

- [ ] Subtask 14.1: 🔴 红 — 编写测试验证序列化器调用
- [ ] Subtask 14.2: 🟢 绿 — 改造 `PostgreSQLEventStore` 使用 `JsonSerializer`
- [ ] Subtask 14.3: 🟢 绿 — 改造 `RedisSnapshotStore` 使用 `RedisHashSerializer`
- [ ] Subtask 14.4: 🔄 重构 — 运行完整测试

**完成标准:**
- [ ] 调用方使用序列化器
- [ ] 所有测试通过

---

### Task 15: 六边形架构约束验证

**关联 AC:** AC-15

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 运行架构检查工具 |
| 🟢 绿 | 修复架构违规 |
| 🔄 重构 | 最终验证 |

- [ ] Subtask 15.1: 🔴 红 — 运行 `ruff check src/domain/`
- [ ] Subtask 15.2: 🟢 绿 — 修复领域层外部依赖
- [ ] Subtask 15.3: 🔴 红 — 运行 `mypy src/domain/`
- [ ] Subtask 15.4: 🟢 绿 — 修复类型检查错误
- [ ] Subtask 15.5: 🔄 重构 — 最终验证所有测试通过

**完成标准:**
- [ ] Ruff 检查通过
- [ ] MyPy 类型检查通过
- [ ] 所有测试通过

---

## 测试分类与归属

| 测试类型 | 验证内容 | 测试文件 | 对应 Task |
|---------|----------|----------|-----------|
| TDD | 目录重命名 | `test_domain_ports_rename.py` | Task 1 |
| TDD | 事件基础设施移动 | `test_event_infra_move.py` | Task 2 |
| TDD | Protocol 文件移动 | `test_protocol_file_move.py` | Task 3 |
| TDD | Serializable Protocol | `test_serializable_protocol.py` | Task 4 |
| TDD | DomainEvent 序列化改造 | `test_domain_event_serialization.py` | Task 5 |
| TDD | CheckpointSnapshot 序列化改造 | `test_checkpoint_snapshot_serialization.py` | Task 6 |
| TDD | SerializationPort | `test_serialization_port.py` | Task 7 |
| TDD | StandardSerializeRules | `test_serialize_rules.py` | Task 8 |
| TDD | TypeRegistry | `test_type_registry.py` | Task 9 |
| TDD | JsonSerializer | `test_json_serializer.py` | Task 10 |
| TDD | RedisHashSerializer | `test_redis_hash_serializer.py` | Task 11 |
| TDD | domain/exceptions | `test_domain_exceptions.py` | Task 12 |
| TDD | sovereignty.py 修复 | `test_sovereignty_fix.py` | Task 13 |
| TDD | 调用方改造 | `test_caller_refactor.py` | Task 14 |
| 架构 | 六边形约束验证 | `test_hexagonal_constraints.py` | Task 15 |

---

## 测试要求与质量门禁

### 覆盖率要求
- [ ] **整体覆盖率 ≥80%**（如为骨架 Story 则豁免至 ≥30%）
- [ ] **领域层覆盖率 ≥90%**
- [ ] **应用层覆盖率 ≥85%**
- [ ] **基础设施层覆盖率 ≥75%**

### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`)
- [ ] **MyPy 类型检查通过**（`mypy src/`)
- [ ] **无循环依赖**

### 测试隔离约束
- [ ] 集成测试使用 transaction rollback
- [ ] fixture 内完成 Schema 初始化
- [ ] 测试数据使用 UUID 唯一标识
- [ ] 外部服务用 Mock

---

## 📝 Dev Notes 开发笔记

### 架构约束（来自 project-context.md）

1. **领域层零依赖**: domain/ 仅用 Python 标准库
2. **六边形架构**: Domain 层定义 Port 接口，Infrastructure 层实现
3. **EVD (Event-Driven)**: 领域事件与事件基础设施分离
4. **依赖倒置**: Domain/Application 定义接口，Infrastructure 实现接口
5. **序列化是适配器责任**: 领域实体实现 Serializable Protocol，序列化器在 infrastructure 层

### 序列化框架设计原则

| 组件 | 位置 | 职责 |
|------|------|------|
| Serializable Protocol | `domain/ports/serialization.py` | 领域实体实现，提供字段元数据 |
| SerializationField | `domain/ports/serialization.py` | 字段序列化元数据（is_uuid, is_datetime 等） |
| SerializationPort | `application/ports/serialization.py` | 序列化抽象接口 |
| StandardSerializeRules | `application/ports/serialization_rules.py` | 标准类型转换规则 |
| TypeRegistry | `application/ports/type_registry.py` | 类型注册表，支持多态反序列化 |
| JsonSerializer | `infrastructure/serialization/json_serializer.py` | JSON 字符串序列化器 |
| RedisHashSerializer | `infrastructure/serialization/redis_hash_serializer.py` | Redis Hash 序列化器 |

### 与 Story 20-2/20-3/20-4 的关系

| Story | 主题 | 与 20-5 的关系 |
|-------|------|---------------|
| 20-2 | event-messaging-refactor | 事件消息基础设施重构 |
| 20-3 | uni-dual-channel-eventbus | 统一双通道事件总线 |
| 20-4 | uni-async-refactor | 统一异步 Port 适配器 |
| **20-5** | **src-dir-refactor** | **全局目录结构与序列化框架** |

### 前一个故事学习经验

**来源:** Story 20-4-uni-async-refactor

**关键学习/Key Learnings:**
- Port 接口使用 ABC 父类（名义子类型优于结构子类型）
- I/O 密集型方法使用 async + aiofiles/to_thread
- CPU 密集型方法保持 sync（不阻塞事件循环）
- 依赖注入链完整验证

**应用到本故事/Applied to This Story:**
- [x] Port 接口使用 ABC 父类
- [x] 领域层零外部依赖严格遵守
- [x] 依赖倒置原则正确应用
- [x] 序列化器实现与接口分离

---

## 📚 参考资料

- [Source: docs/developer/sisys-src-dir-refactor.md] — v2.17 重构方案
- [Source: _bmad-output/planning-artifacts/architecture.md] — 六边形架构文档
- [Source: _bmad-output/project-context.md] — 项目上下文
- [Source: src/domain/events/base.py] — DomainEvent（待改造）
- [Source: src/domain/entities/checkpoint_snapshot.py] — CheckpointSnapshot（待改造）
- [Source: src/domain/repositories/] — 现有 Port 接口位置
- [Source: _bmad-output/implementation-artifacts/stories/20-4-uni-async-refactor.md] — 前一个故事

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | MiniMax-M2 |
| **Version** | story-template.md v2.5.0 |
| **Execution Date** | 2026-05-03 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/20-4-uni-async-refactor.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |
| **方案文档** | `docs/developer/sisys-src-dir-refactor.md` |

### 完成清单 Completion Notes List

- [x] 故事需求从方案文档提取
- [x] 架构约束从 architecture.md 提取
- [x] 前一个故事学习经验整合
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/20-5-src-dir-refactor.md`

**待创建的文件/To Be Created (Dev Story 实施):**

| 文件 | 说明 | 对应 Task |
|------|------|-----------|
| `domain/ports/serialization.py` | Serializable Protocol, SerializationField | Task 4 |
| `application/ports/serialization.py` | SerializationPort | Task 7 |
| `application/ports/serialization_rules.py` | StandardSerializeRules | Task 8 |
| `application/ports/type_registry.py` | TypeRegistry | Task 9 |
| `infrastructure/serialization/__init__.py` | 模块导出 | Task 10 |
| `infrastructure/serialization/json_serializer.py` | JsonSerializer | Task 10 |
| `infrastructure/serialization/redis_hash_serializer.py` | RedisHashSerializer | Task 11 |
| `domain/exceptions/__init__.py` | 异常导出 | Task 12 |
| `domain/exceptions/memory_exceptions.py` | 异常定义 | Task 12 |
| `domain/value_objects/sensitive_data.py` | 敏感数据类型值对象 | Task 13 |
| `tests/unit/domain/ports/test_serializable_protocol.py` | Serializable Protocol 测试 | Task 4 |
| `tests/unit/domain/events/test_domain_event_serialization.py` | DomainEvent 序列化测试 | Task 5 |
| `tests/unit/domain/entities/test_checkpoint_snapshot_serialization.py` | CheckpointSnapshot 序列化测试 | Task 6 |
| `tests/unit/application/ports/test_serialization_port.py` | SerializationPort 测试 | Task 7 |
| `tests/unit/application/ports/test_serialize_rules.py` | StandardSerializeRules 测试 | Task 8 |
| `tests/unit/application/ports/test_type_registry.py` | TypeRegistry 测试 | Task 9 |
| `tests/unit/infrastructure/serialization/test_json_serializer.py` | JsonSerializer 测试 | Task 10 |
| `tests/unit/infrastructure/serialization/test_redis_hash_serializer.py` | RedisHashSerializer 测试 | Task 11 |
| `tests/unit/domain/exceptions/test_domain_exceptions.py` | 异常测试 | Task 12 |
| `tests/unit/infrastructure/config/test_sovereignty_fix.py` | sovereignty.py 修复测试 | Task 13 |
| `tests/unit/test_caller_refactor.py` | 调用方改造测试 | Task 14 |
| `tests/unit/test_hexagonal_constraints.py` | 六边形架构约束测试 | Task 15 |
| `tests/acceptance/test_story_20_5.feature` | Gherkin 验收测试 | Task 0 |

**待移动的文件/To Be Moved:**

| 原路径 | 目标路径 | 对应 Task |
|--------|----------|-----------|
| `domain/repositories/` | `domain/ports/` | Task 1 |
| `domain/events/publisher.py` | `infrastructure/messaging/event_publisher.py` | Task 2 |
| `domain/events/listener.py` | `infrastructure/messaging/event_listener.py` | Task 2 |
| `domain/events/publish_result.py` | `infrastructure/messaging/publish_result.py` | Task 2 |
| `domain/services/audit_service.py` | `application/ports/audit_port.py` | Task 3 |
| `domain/services/auth_service.py` | `application/ports/auth_port.py` | Task 3 |
| `domain/services/permission_service.py` | `application/ports/permission_port.py` | Task 3 |
| `domain/services/public_blackboard.py` | `application/ports/public_blackboard_port.py` | Task 3 |
| `domain/services/semantic_cache.py` | `application/ports/semantic_cache_port.py` | Task 3 |
| `domain/services/compressor_service.py` | `application/ports/compressor_port.py` | Task 3 |
| `domain/services/text_extractor_service.py` | `application/ports/text_extractor_port.py` | Task 3 |
| `infrastructure/security/models.py` | `infrastructure/security/value_objects.py` | Task 13 |

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 20-5 |
| **Story Key** | 20-5-src-dir-refactor |
| **File** | `_bmad-output/implementation-artifacts/stories/20-5-src-dir-refactor.md` |
| **Status** | `ready-for-dev` |
| **Epic** | Epic 20: 重大重构 |
| **价值组** | Epic 20 全局目录结构与序列化框架 |
| **优先级** | P0 |
| **预估工时** | 约 3-4d（文件移动 + 序列化框架） |
| **覆盖 FR** | N/A（非功能性重构） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（15 Tasks + Task 0 SDD）
2. [x] All acceptance criteria specified 所有验收标准已定义（15 ACs）
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 对抗性审查修复（Adversarial Review Fixes）

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | P0-1: 目录重命名影响 155 个文件导入 | P0 | 按 Task 分批执行，每批后运行测试 |
| 2 | P0-2: EventStore ABC 位置确认 | P0 | 保留在 domain/events/，是 Port 接口定义 |
| 3 | P1-1: PostgreSQLEventStore 改造依赖序列化器 | P1 | Task 10/11 先完成，Task 14 后执行 |
| 4 | P2-1: DomainEvent 多态反序列化衔接 | P2 | `__init_subclass__` 自动向 TypeRegistry 注册 |
| 5 | P0-3: Task 执行顺序与依赖关系未明确 | P0 | 新增"Task 执行顺序与依赖关系"章节，明确三阶段执行流程 |
| 6 | P2-2: AC-13 验证标准不完整 | P2 | 补充值对象迁移验证和导入方更新验证 |
| 7 | P2-3: AC-14 缺少 RedisSnapshotStore 引用验证 | P2 | 补充 `RedisSnapshotStore` 引用 `infrastructure/serialization/redis_hash_serializer.py` 验证 |

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story 20-5` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `validate-create-story` 质量检查
- [ ] 实施顺序：**阶段一**（Task 1-3 文件迁移）→ **阶段二**（Task 4-11 序列化框架）→ **阶段三**（Task 12-15 收尾）

---

**模板版本/Template Version:** 2.5.0
**创建日期/Created:** 2026-05-03
**最后更新/Last Updated:** 2026-05-03
**更新说明:**
- v1.0.0: 初始版本，基于 sisys-src-dir-refactor.md v2.17 创建
