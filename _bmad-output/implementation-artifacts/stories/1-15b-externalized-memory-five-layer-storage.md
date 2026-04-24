# Story 1.15b: 外部化记忆 - L0 记忆入口 + 六层存储协同实现

**Status:** `backlog`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 系统架构师,
**I want** 实现 L0 MEMORY.md 记忆入口与 L1-L5 六层存储协同,
**So that** 记忆分离原则得到实现，磁盘记忆=真相源。

### 业务价值

本 Story 是 Epic 1（企业级架构基础与合规）价值组 5（or.md 系统公理实现）的第五个故事，在 Story 1.15a（L1 显式确认压缩）完成后实现 L0 记忆入口与六层存储协同。核心价值：

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **L0 MEMORY.md 入口** | 索引入口（最多 200 行，超出自动截断保留最新） | 索引文件格式正确 |
| **Private/Group 记忆分离** | private 记忆用户私有，group 记忆团队共享 | RBAC 校验通过 |
| **L1 CRUD 操作** | 完整创建/读取/更新/删除，带版本冲突处理 | 乐观锁处理正确 |
| **MemoryChanged 事件下游** | 触发元数据同步、缓存失效、向量索引更新 | 事件处理≥99% 成功率 |
| **六层存储协同** | L0→L1→L2→L3→L4→L5 单向依赖链 | 层间协同正确 |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 1: 企业级架构基础与合规，价值组 5: or.md 系统公理实现，Story 1.15b

**or.md 公理追溯:** 系统公理二（外部化记忆：LLM 上下文=缓存，磁盘记忆=真相源），覆盖"L0 记忆入口 + 六层存储协同"阶段

**前置依赖:** Story 1.15a（L1 显式确认压缩）、Story 1.4（提供 L1 Redis）、Story 1.5（提供 L2 PostgreSQL 基础表结构）

**后续依赖:** Story 1.17（UDMR 基础路由）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: L0 MEMORY.md 索引入口

**Given** 用户记忆操作
**When** 写入 ~/.sisys/memory/*.md
**Then** 更新 MEMORY.md 索引

**验证标准/Validation Criteria:**
- [ ] MEMORY.md 格式正确（memory_id, name, memory_type, mtime）
- [ ] 索引行数限制（最多 200 行，超出自动截断）
- [ ] 截断策略（按 updated_at 倒序，保留最新 200 条）
- [ ] Private 索引：~/.sisys/memory/MEMORY.md
- [ ] Group 索引：~/.sisys/memory/group/MEMORY.md

### AC-2: Private/Group 记忆分离

**Given** 用户记忆访问请求
**When** 执行 private 或 group 记忆操作
**Then** RBAC 校验通过，记忆正确隔离

**验证标准/Validation Criteria:**
- [ ] Private 记忆（group_id=NULL）：读取/写入验证 owner == user_id
- [ ] Group 记忆（group_id != NULL）：读取/写入验证 user 是 group 成员
- [ ] MemoryAccessDeniedError：RBAC 校验失败时抛出
- [ ] 管理员权限：group 写入需要 admin 权限或 group 成员

### AC-3: L1 CRUD 操作

**Given** 用户记忆操作请求
**When** 执行 save/delete/update/query/list 操作
**Then** 记忆 CRUD 100% 正确

**验证标准/Validation Criteria:**
- [ ] MemoryService.save() - 创建新记忆（带 version=1）
- [ ] MemoryService.delete() - 删除记忆（软删除标记）
- [ ] MemoryService.update() - 更新记忆（version +1，乐观锁）
- [ ] MemoryService.query() - 查询单个记忆
- [ ] MemoryService.list() - 列出用户所有记忆
- [ ] 操作幂等性验证

### AC-4: 版本冲突处理（乐观锁）

**Given** 并发更新同一记忆
**When** 两个请求同时更新同一 memory_id
**Then** 只有一个成功，另一个抛出 VersionConflictError

**验证标准/Validation Criteria:**
- [ ] memory_metadata.version 字段存在
- [ ] UPSERT 时检查 version（version +1）
- [ ] VersionConflictError：并发冲突时抛出
- [ ] 用户确认后可强制覆盖（version 置为新值）

### AC-5: MemoryChanged 事件下游用例

**Given** 用户记忆操作完成
**When** MemoryChanged 事件发布
**Then** 下游监听器执行以下操作

**验证标准/Validation Criteria:**
- [ ] MemoryChangedListener 注册到事件总线
- [ ] 写入 memory_metadata（UPSERT，version +1）
- [ ] 写入 memory_change_history（append-only，change_type: create/update/delete）
- [ ] 失效 L1 Redis 缓存（redis.del("memory:{name}")）
- [ ] 可选：更新 L3 Qdrant 向量索引（文件 >500 时）

### AC-6: 六层存储协同

**Given** 记忆存储请求
**When** 数据流经 L0-L5 六层存储
**Then** 单向依赖链正确

**验证标准/Validation Criteria:**
- [ ] L0（文件系统）：~/.sisys/memory/*.md（记忆入口）
- [ ] L1（Redis）：memory:xxx 缓存（TTL 24h-30d）
- [ ] L2（PostgreSQL）：memory_metadata + memory_change_history
- [ ] L3（Qdrant）：向量索引（文件 >500 时）
- [ ] L4（MinIO）：WORM 对象存储（7 年）
- [ ] L5（Neo4j）：图关系索引（未来扩展）
- [ ] 层间单向依赖：L0→L1→L2→L3→L4→L5

### AC-7: 错误处理

**Given** 记忆操作异常
**When** 发生错误
**Then** 抛出正确的异常类型

**验证标准/Validation Criteria:**
- [ ] VersionConflictError：并发更新冲突
- [ ] MemoryAccessDeniedError：RBAC 校验失败
- [ ] MemoryNotFoundError：删除/更新不存在的记忆
- [ ] StorageWriteError：L0/L2 写入失败（重试最多 3 次）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] MemoryChanged 事件定义（`src/domain/events/memory_events.py`）— 复用 Story 1.15a 定义
  - 字段: event_id, memory_id, user_id, change_type (enum: create/update/delete), is_automatic, old_value, new_value, timestamp
  - event_type = "MemoryChanged"

#### 数据模型 (Data Models)
- [ ] Memory 实体（`src/domain/entities/memory.py`）— 复用 Story 1.15a 定义
  - 字段: memory_id, user_id, content, compressed_content, memory_type (enum: private/group), group_id, name, description, version, created_at, updated_at
- [ ] MemoryIndexEntry 值对象（`src/domain/value_objects/memory_index_entry.py`）— 复用 Story 1.15a 定义
  - 字段: memory_id, name, memory_type, mtime

#### L0 存储 (L0 Storage)
- [ ] L0MemoryStore 端口接口（`src/interfaces/storage/l0_memory_port.py`）— 复用 Story 1.15a 定义
  - 接口方法: `save(memory_id, content)`, `load(memory_id) -> str`, `delete(memory_id)`, `update_index(memory_entries: List[MemoryIndexEntry])`, `load_index() -> List[MemoryIndexEntry]`
- [ ] FileSystemMemoryAdapter 实现（`src/infrastructure/storage/file_system_memory_adapter.py`）— 复用 Story 1.15a 实现
  - 路径: ~/.sisys/memory/
  - MEMORY.md 索引文件（最多 200 行，超出自动截断保留最新）
  - 权限: 600

#### L1 存储 (L1 Storage)
- [ ] MemoryCacheRepository 仓储接口（`src/interfaces/cache/memory_cache_port.py`）
  - 接口方法: `set(key, value, ttl)`, `get(key) -> Optional[value]`, `delete(key)`
  - 定义在 interfaces 层

#### L2 存储 (L2 Storage)
- [ ] MemoryMetadataRepository 仓储接口（`src/domain/repositories/memory_metadata_repository.py`）— 复用 Story 1.15a 定义
  - 接口方法: `upsert(metadata)`, `find_by_id(memory_id) -> MemoryMetadata`, `find_by_user(user_id) -> List[MemoryMetadata]`, `delete(memory_id)`
- [ ] MemoryChangeHistoryRepository 仓储接口（`src/domain/repositories/memory_change_history_repository.py`）— 复用 Story 1.15a 定义
  - 接口方法: `append(history)`, `find_by_memory(memory_id) -> List[MemoryChangeHistory]`
  - append-only 模式，不可更新或删除

#### L3-L5 存储接口（占位）
- [ ] VectorIndexRepository 端口接口（`src/interfaces/search/vector_index_port.py`）
  - 接口方法: `upsert(memory_id, embedding)`, `search(query_embedding, top_k) -> List[memory_id]`
  - 定义在 interfaces 层（L3 Qdrant 实现）

#### 异常定义 (Exceptions)
- [ ] VersionConflictError（`src/domain/exceptions/memory_exceptions.py`）
- [ ] MemoryAccessDeniedError
- [ ] MemoryNotFoundError
- [ ] StorageWriteError

#### MemoryChangedListener（事件监听器）
- [ ] MemoryMetadataSyncListener（`src/infrastructure/listeners/memory_metadata_sync_listener.py`）
  - 监听 MemoryChanged 事件，执行 memory_metadata UPSERT
- [ ] MemoryChangeHistoryListener（`src/infrastructure/listeners/memory_change_history_listener.py`）
  - 监听 MemoryChanged 事件，执行 memory_change_history append-only
- [ ] MemoryCacheInvalidationListener（`src/infrastructure/listeners/memory_cache_invalidation_listener.py`）
  - 监听 MemoryChanged 事件，执行 Redis 缓存失效
- [ ] VectorIndexUpdateListener（`src/infrastructure/listeners/vector_index_update_listener.py`）
  - 监听 MemoryChanged 事件，当文件 >500 时更新 Qdrant 向量索引

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_story_1.15b.feature`（由 Dev agent 在 Task 0 创建）
- [ ] 覆盖场景:
  - Private/Group 记忆分离
  - L1 CRUD 操作
  - 版本冲突处理（乐观锁）
  - MemoryChanged 下游监听器
  - 六层存储协同
  - 错误处理

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证）

---

### TDD 循环约束（适用于每个 Task）

> **每个 Task 必须依次执行以下步骤，禁止跳过或颠倒顺序：**

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败，且失败原因符合预期 |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🔄 重构** | 优化代码（保持测试通过） | `ruff check` + `mypy` + `pytest` 全部通过 |

**禁止行为：**
- ❌ 先写代码后写测试（违反 TDD 测试先行原则）
- ❌ 将测试编写集中到最后一个 Task（违反 TDD 小步快跑原则）
- ❌ 跳过红阶段验证（未确认测试失败就直接写实现）

---

### 测试分类与归属

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | MemoryService | L1 CRUD + RBAC | `test_memory_service.py` | Task 1 |
| **TDD 单元测试** | MemoryChangedListener | 下游监听器 | `test_memory_changed_listener.py` | Task 1 |
| **TDD 单元测试** | MemoryCacheRepository | L1 缓存 | `test_memory_cache_port.py` | Task 2 |
| **TDD 单元测试** | FileSystemMemoryAdapter | L0 存储 | `test_file_system_memory_adapter.py` | Task 2 |
| **TDD 单元测试** | MemoryMetadataRepository | L2 存储 | `test_memory_metadata_repository.py` | Task 2 |
| **TDD 单元测试** | VectorIndexRepository | L3 向量索引 | `test_vector_index_port.py` | Task 2 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_story_1.15b.feature` | Task 0 |
| **SDD 架构验证** | 架构约束 | 六层存储约束 | `test_six_layer_storage.py` | Task 3 |
| **集成测试** | 端到端流程 | 六层存储协同 | `test_storage_integration.py` | Task 3 |

#### 测试隔离约束（必须遵守）

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**
> 参考 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md) §5.5 测试隔离约束。

**约束规则：**

| 约束类型 | 规则 | 违反后果 |
|---------|------|----------|
| **事务隔离** | 集成测试使用 transaction rollback | 数据泄漏导致随机失败 |
| **Schema 自创建** | fixture 内完成 Schema 初始化 | 依赖外部迁移，环境不一致 |
| **资源唯一性** | 测试数据使用 UUID 等唯一标识符 | ID 冲突或状态污染 |
| **外部服务隔离** | Redis/Neo4j/Qdrant 测试前清理或用 mock | 真实数据被污染 |
| **并行隔离** | 并行测试使用 UUID 前缀隔离资源 | 资源冲突导致并行失败 |
| **清理粒度** | 每个测试只清理自己创建的资源 | 误删其他测试资源 |
| **依赖声明** | Fixture 必须显式声明依赖 | 并行时清理顺序不确定 |
| **asyncio 上下文** | asyncio.Lock 使用类变量；处理 thread.ident 为 None | 锁失效或类型错误 |
| **pytest-asyncio** | 删除 scope=module 的 event_loop fixture | 与 auto mode 冲突 |
| **外部客户端** | 第三方 API 必须验证方法存在性 | AttributeError |

**禁止行为：**
- ❌ 集成测试手动 `delete`/`truncate`（应用 transaction rollback）
- ❌ autouse fixture 删除全局匹配资源（如 `test_*`）
- ❌ Fixture 假设清理顺序（必须显式声明依赖）
- ❌ asyncio.Lock 使用实例变量
- ❌ scope=module 的 event_loop fixture

**验证要求：**
- [ ] 并行测试 `pytest tests/ -n 8` 通过
- [ ] 连续5次运行无随机失败
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

> **目的：** 确保每个 AC 都有明确的 Task 和 Subtask 对应，避免遗漏或重复。

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | L0 MEMORY.md 索引入口 | Task 1 | Subtask 1.1-1.3（MemoryService 索引更新） | `test_memory_service.py` |
| AC-2 | Private/Group 记忆分离 | Task 1 | Subtask 1.4-1.6（RBAC 校验） | `test_memory_service.py` |
| AC-3 | L1 CRUD 操作 | Task 1 | Subtask 1.7-1.9（CRUD 操作） | `test_memory_service.py` |
| AC-4 | 版本冲突处理（乐观锁） | Task 1 | Subtask 1.10-1.12（乐观锁） | `test_memory_service.py` |
| AC-5 | MemoryChanged 事件下游用例 | Task 2 | Subtask 2.1-2.6（四个监听器） | `test_memory_changed_listener.py` |
| AC-6 | 六层存储协同 | Task 3 | Subtask 3.1-3.3（架构验证） | `test_six_layer_storage.py` |
| AC-7 | 错误处理 | Task 1 | Subtask 1.13-1.15（异常处理） | `test_memory_service.py` |

---

## 📋 Tasks / Subtasks 任务分解

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7

> **目的：** 在进入代码实现前，明确 Schema、API 契约、验收标准。

- [ ] Subtask 0.1: 定义异常类（VersionConflictError、MemoryAccessDeniedError、MemoryNotFoundError、StorageWriteError）
- [ ] Subtask 0.2: 定义 MemoryCacheRepository 端口接口（`src/interfaces/cache/memory_cache_port.py`）
- [ ] Subtask 0.3: 定义 VectorIndexRepository 端口接口（`src/interfaces/search/vector_index_port.py`）
- [ ] Subtask 0.4: 定义 MemoryChangedListener 四个监听器接口
- [ ] Subtask 0.5: 编写 Gherkin 验收测试 `tests/acceptance/test_story_1.15b.feature`（Dev agent 创建）
- [ ] Subtask 0.6: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: MemoryService 与 RBAC/CRUD

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-7

> **职责边界:** Task 1 负责 MemoryService（L1 CRUD + RBAC + 索引更新 + 异常处理）

#### TDD 循环 [A]：MemoryService - 索引更新

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/services/test_memory_service.py`（验证 MEMORY.md 更新） |
| 🟢 绿 | 实现 MemoryService 索引更新逻辑 |
| 🔄 重构 | 优化索引更新逻辑 |

- [ ] Subtask 1.1: 🔴 红 — 编写索引更新失败测试
- [ ] Subtask 1.2: 🟢 绿 — 实现索引更新逻辑
- [ ] Subtask 1.3: 🔄 重构 — 优化索引更新代码

#### TDD 循环 [B]：MemoryService - RBAC 校验

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 RBAC 校验失败测试 |
| 🟢 绿 | 实现 RBAC 校验逻辑（private/group 分离） |
| 🔄 重构 | 优化 RBAC 校验代码 |

- [ ] Subtask 1.4: 🔴 红 — 编写 RBAC 校验失败测试
- [ ] Subtask 1.5: 🟢 绿 — 实现 RBAC 校验逻辑
- [ ] Subtask 1.6: 🔄 重构 — 优化 RBAC 校验代码

#### TDD 循环 [C]：MemoryService - CRUD 操作

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 CRUD 操作失败测试 |
| 🟢 绿 | 实现 CRUD 操作（save/delete/update/query/list） |
| 🔄 重构 | 优化 CRUD 操作代码 |

- [ ] Subtask 1.7: 🔴 红 — 编写 CRUD 操作失败测试
- [ ] Subtask 1.8: 🟢 绿 — 实现 CRUD 操作
- [ ] Subtask 1.9: 🔄 重构 — 优化 CRUD 操作代码

#### TDD 循环 [D]：MemoryService - 乐观锁

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写版本冲突失败测试 |
| 🟢 绿 | 实现乐观锁（version +1） |
| 🔄 重构 | 优化版本冲突处理 |

- [ ] Subtask 1.10: 🔴 红 — 编写版本冲突失败测试
- [ ] Subtask 1.11: 🟢 绿 — 实现乐观锁
- [ ] Subtask 1.12: 🔄 重构 — 优化版本冲突处理

#### TDD 循环 [E]：MemoryService - 异常处理

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写异常处理失败测试 |
| 🟢 绿 | 实现异常抛出逻辑 |
| 🔄 重构 | 优化异常处理代码 |

- [ ] Subtask 1.13: 🔴 红 — 编写异常处理失败测试
- [ ] Subtask 1.14: 🟢 绿 — 实现异常抛出逻辑
- [ ] Subtask 1.15: 🔄 重构 — 优化异常处理代码

**完成标准/Definition of Done:**
- [ ] MemoryService 实现完成（CRUD + RBAC + 索引 + 异常）
- [ ] TDD 循环全部通过
- [ ] 记忆保存成功率 100%

---

### Task 2: MemoryChanged 监听器实现

**关联 AC:** AC-5

> **职责边界:** Task 2 负责四个 MemoryChanged 下游监听器

#### TDD 循环 [A]：MemoryMetadataSyncListener

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/listeners/test_memory_metadata_sync_listener.py` |
| 🟢 绿 | 实现 MemoryMetadataSyncListener |
| 🔄 重构 | 优化监听器代码 |

- [ ] Subtask 2.1: 🔴 红 — 编写 MemoryMetadataSyncListener 失败测试
- [ ] Subtask 2.2: 🟢 绿 — 实现 MemoryMetadataSyncListener
- [ ] Subtask 2.3: 🔄 重构 — 优化监听器代码

#### TDD 循环 [B]：MemoryChangeHistoryListener

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/listeners/test_memory_change_history_listener.py` |
| 🟢 绿 | 实现 MemoryChangeHistoryListener |
| 🔄 重构 | 优化监听器代码 |

- [ ] Subtask 2.4: 🔴 红 — 编写 MemoryChangeHistoryListener 失败测试
- [ ] Subtask 2.5: 🟢 绿 — 实现 MemoryChangeHistoryListener
- [ ] Subtask 2.6: 🔄 重构 — 优化监听器代码

#### TDD 循环 [C]：MemoryCacheInvalidationListener

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/listeners/test_memory_cache_invalidation_listener.py` |
| 🟢 绿 | 实现 MemoryCacheInvalidationListener |
| 🔄 重构 | 优化监听器代码 |

- [ ] Subtask 2.7: 🔴 红 — 编写 MemoryCacheInvalidationListener 失败测试
- [ ] Subtask 2.8: 🟢 绿 — 实现 MemoryCacheInvalidationListener
- [ ] Subtask 2.9: 🔄 重构 — 优化监听器代码

#### TDD 循环 [D]：VectorIndexUpdateListener

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/listeners/test_vector_index_update_listener.py` |
| 🟢 绿 | 实现 VectorIndexUpdateListener（文件 >500 时触发） |
| 🔄 重构 | 优化监听器代码 |

- [ ] Subtask 2.10: 🔴 红 — 编写 VectorIndexUpdateListener 失败测试
- [ ] Subtask 2.11: 🟢 绿 — 实现 VectorIndexUpdateListener
- [ ] Subtask 2.12: 🔄 重构 — 优化监听器代码

**完成标准/Definition of Done:**
- [ ] 四个监听器实现完成
- [ ] TDD 循环全部通过
- [ ] 事件处理成功率 ≥99%

---

### Task 3: 架构验证与集成测试

**关联 AC:** AC-6

> **职责边界:** Task 3 负责六边形架构验证和六层存储集成测试

#### TDD 循环 [A]：六边形架构验证

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/architecture/test_six_layer_storage.py`（验证架构约束） |
| 🟢 绿 | 实现架构验证逻辑（领域层零依赖、依赖方向检测） |
| 🔄 重构 | 优化架构验证器 |

- [ ] Subtask 3.1: 🔴 红 — 编写六层存储架构验证失败测试
- [ ] Subtask 3.2: 🟢 绿 — 实现六层存储架构验证逻辑
- [ ] Subtask 3.3: 🔄 重构 — 验证器优化

#### 集成测试

- [ ] Subtask 3.4: 创建 `tests/integration/test_storage_integration.py`（六层存储端到端）
- [ ] Subtask 3.5: 创建 `tests/integration/test_memory_changed_downstream.py`（事件下游集成）

**完成标准/Definition of Done:**
- [ ] 六层架构验证通过（领域层零依赖）
- [ ] 集成测试通过
- [ ] 覆盖率达标（架构层≥85%，集成测试≥75%）

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（端口与适配器）、事件驱动架构
- **系统公理二:** 外部化记忆（LLM 上下文=缓存，磁盘记忆=真相源）
  - L0 MEMORY.md：索引入口（最多 200 行，超出自动截断）
  - L1-L5 六层存储：单向依赖链
- **三层触发机制:**
  - L1 显式确认（用户主动，Story 1.15a）
  - L2 语义建议（系统建议+用户确认，V2）
  - L3 压缩触发（Checkpoint 自动，Epic 6/Story 6.3）
- **设计约束:**
  - 领域层零依赖外部框架
  - 依赖倒置：领域层定义接口，基础设施层实现
  - 事件总线双通道：Redis PubSub（实时）、RabbitMQ（持久化）
- **技术栈:**
  - Python 3.11+
  - L0 存储：文件系统（~/.sisys/memory/）
  - L1 存储：Redis（Story 1.4 已实现）
  - L2 存储：PostgreSQL（Story 1.5 已实现）
  - L3 存储：Qdrant（Story 1.6 已实现）
  - L4 存储：MinIO（Story 1.7 已实现）
  - L5 存储：Neo4j（Story 1.8 已实现）
  - 事件总线：Redis PubSub + RabbitMQ（Story 1.3 已实现）

### 六层存储架构

| 层级 | 存储类型 | 实现 | 用途 |
|------|---------|------|------|
| L0 | 文件系统 | ~/.sisys/memory/*.md | 记忆入口（原始记忆） |
| L1 | Redis | memory:xxx | 缓存（TTL 24h-30d） |
| L2 | PostgreSQL | memory_metadata + memory_change_history | 关系存储（元数据+历史） |
| L3 | Qdrant | 向量索引 | 向量搜索（文件 >500 时） |
| L4 | MinIO | WORM 对象存储 | 归档（7 年） |
| L5 | Neo4j | 图关系索引 | 关系追溯（未来扩展） |

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 1.15a: 外部化记忆 - L1 显式确认压缩](./1-15a-externalized-memory-context-compression.md)

**关键学习/Key Learnings:**
1. **配置模式复用** — OtelConfig.from_env() 模式应复用，MemoryConfig 采用相同 `from_env()` 类方法
2. **事件驱动解耦** — MemoryService 仅发布事件，不直接调用其他阶段
3. **六边形架构严格遵守** — Task 3 必须包含架构验证测试，确保领域层零依赖
4. **端口接口位置** — 端口接口定义在 interfaces 层，实现在 infrastructure 层
5. **依赖倒置原则** — 领域层定义仓储接口，基础设施层实现

**应用到本故事/Applied to This Story:**
- [ ] MemoryCacheRepository 端口在 interfaces 层，实现在 infrastructure 层（RedisCacheAdapter）
- [ ] VectorIndexRepository 端口在 interfaces 层，实现在 infrastructure 层（QdrantVectorIndexAdapter）
- [ ] 四个 MemoryChanged 监听器在 infrastructure 层实现
- [ ] Task 3 包含六层存储架构验证测试
- [ ] 测试隔离约束显式强调（asyncio.Lock 类变量、pytest-asyncio auto mode）

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── domain/
│   │   ├── events/
│   │   │   └── memory_events.py      # MemoryChanged 事件（复用 Story 1.15a）
│   │   ├── services/
│   │   │   └── memory_service.py     # MemoryService（扩展 CRUD + RBAC + 索引）
│   │   ├── entities/
│   │   │   └── memory.py             # Memory 实体（复用 Story 1.15a）
│   │   ├── value_objects/
│   │   │   └── memory_index_entry.py # MemoryIndexEntry 值对象（复用 Story 1.15a）
│   │   ├── repositories/
│   │   │   ├── memory_metadata_repository.py      # 接口（复用 Story 1.15a）
│   │   │   └── memory_change_history_repository.py # 接口（复用 Story 1.15a）
│   │   └── exceptions/
│   │       └── memory_exceptions.py  # 异常定义（新实现）
│   ├── infrastructure/
│   │   ├── config/
│   │   │   └── memory.py            # MemoryConfig（复用 Story 1.15a）
│   │   ├── listeners/
│   │   │   ├── memory_metadata_sync_listener.py      # MemoryMetadataSyncListener
│   │   │   ├── memory_change_history_listener.py    # MemoryChangeHistoryListener
│   │   │   ├── memory_cache_invalidation_listener.py # MemoryCacheInvalidationListener
│   │   │   └── vector_index_update_listener.py      # VectorIndexUpdateListener
│   │   ├── repositories/
│   │   │   ├── memory_metadata_repository_impl.py      # 实现（复用 Story 1.15a）
│   │   │   └── memory_change_history_repository_impl.py # 实现（复用 Story 1.15a）
│   │   └── cache/
│   │       └── redis_memory_cache_adapter.py  # MemoryCacheRepository 实现
│   └── interfaces/
│       ├── storage/
│       │   └── l0_memory_port.py     # L0MemoryStore 端口（复用 Story 1.15a）
│       ├── cache/
│       │   └── memory_cache_port.py  # MemoryCacheRepository 端口
│       └── search/
│           └── vector_index_port.py  # VectorIndexRepository 端口
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   │   ├── services/
│   │   │   │   └── test_memory_service.py
│   │   │   └── exceptions/
│   │   │       └── test_memory_exceptions.py
│   │   ├── infrastructure/
│   │   │   ├── listeners/
│   │   │   │   ├── test_memory_metadata_sync_listener.py
│   │   │   │   ├── test_memory_change_history_listener.py
│   │   │   │   ├── test_memory_cache_invalidation_listener.py
│   │   │   │   └── test_vector_index_update_listener.py
│   │   │   └── cache/
│   │   │       └── test_redis_memory_cache_adapter.py
│   │   ├── interfaces/
│   │   │   └── storage/
│   │   │       └── test_file_system_memory_adapter.py  # 复用 Story 1.15a
│   │   └── architecture/
│   │       └── test_six_layer_storage.py
│   ├── integration/
│   │   ├── test_storage_integration.py
│   │   └── test_memory_changed_downstream.py
│   └── acceptance/
│       ├── test_story_1.15b.feature
│       └── test_story_1.15b_steps.py
└── docs/
    └── developer/
        └── memory_five_layer_storage_guide.md    # 六层存储协同实施指南
```

### Git Intelligence Summary

**来源:** `git log` - 最近 5 个提交

| 提交 | 主题 | 关键模式 |
|------|------|---------|
| `05d32d3` | update | - |
| `f7dff53` | update | - |
| `73c8d50` | fix(test): 提高语义缓存 embedding 生成 entropy 到 64bits | 测试优化 |
| `b118f55` | feat(Epic5): 新增 Agent 评估与可观测性 Stories (5.7~5.10) | Epic 5 扩展 |
| `a5cb625` | update | - |

**可应用模式:**
1. **六边形架构严格分层** — domain/infrastructure/interfaces 层严格分离
2. **配置与实现分离** — Config 类与实现类分离
3. **事件驱动解耦** — 通过事件总线通信，不直接调用

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (create-story workflow) |
| **Version** | create-story workflow v1.0 |
| **Execution Date** | 2026-04-24 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Instructions** | `_bmad/bmm/workflows/4-implementation/create-story/instructions.xml` |
| **Template** | `_bmad/bmm/workflows/4-implementation/create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/1-15a-externalized-memory-context-compression.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取
- [x] 架构约束从 `architecture.md` 提取
- [x] or.md 系统公理二（六层存储协同）追溯完成
- [x] 前一个故事（1.15a）学习经验已整合
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] 六层存储架构已定义
- [x] 测试隔离约束显式强调

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/1-15b-externalized-memory-five-layer-storage.md`

**待创建的文件/To Be Created (Dev Story 实施):**

| 文件 | 描述 | 层级 |
|------|------|------|
| `src/domain/exceptions/memory_exceptions.py` | 异常定义（VersionConflictError、MemoryAccessDeniedError、MemoryNotFoundError、StorageWriteError） | Domain |
| `src/interfaces/cache/memory_cache_port.py` | MemoryCacheRepository 端口接口 | Interfaces |
| `src/interfaces/search/vector_index_port.py` | VectorIndexRepository 端口接口 | Interfaces |
| `src/infrastructure/cache/redis_memory_cache_adapter.py` | MemoryCacheRepository 实现 | Infrastructure |
| `src/infrastructure/listeners/memory_metadata_sync_listener.py` | MemoryMetadataSyncListener | Infrastructure |
| `src/infrastructure/listeners/memory_change_history_listener.py` | MemoryChangeHistoryListener | Infrastructure |
| `src/infrastructure/listeners/memory_cache_invalidation_listener.py` | MemoryCacheInvalidationListener | Infrastructure |
| `src/infrastructure/listeners/vector_index_update_listener.py` | VectorIndexUpdateListener | Infrastructure |
| `tests/unit/domain/services/test_memory_service.py` | MemoryService 单元测试 | Test |
| `tests/unit/domain/exceptions/test_memory_exceptions.py` | 异常单元测试 | Test |
| `tests/unit/infrastructure/listeners/test_memory_metadata_sync_listener.py` | MemoryMetadataSyncListener 测试 | Test |
| `tests/unit/infrastructure/listeners/test_memory_change_history_listener.py` | MemoryChangeHistoryListener 测试 | Test |
| `tests/unit/infrastructure/listeners/test_memory_cache_invalidation_listener.py` | MemoryCacheInvalidationListener 测试 | Test |
| `tests/unit/infrastructure/listeners/test_vector_index_update_listener.py` | VectorIndexUpdateListener 测试 | Test |
| `tests/unit/infrastructure/cache/test_redis_memory_cache_adapter.py` | RedisCacheAdapter 测试 | Test |
| `tests/unit/architecture/test_six_layer_storage.py` | 六层存储架构验证测试 | Test |
| `tests/integration/test_storage_integration.py` | 六层存储集成测试 | Test |
| `tests/integration/test_memory_changed_downstream.py` | 事件下游集成测试 | Test |
| `tests/acceptance/test_story_1.15b.feature` | Gherkin 验收测试 | Test |
| `tests/acceptance/test_story_1.15b_steps.py` | 验收测试步骤实现 | Test |
| `docs/developer/memory_five_layer_storage_guide.md` | 六层存储协同实施指南 | Docs |

**复用 Story 1.15a 文件（无需重新创建）:**
- `src/domain/events/memory_events.py` - MemoryChanged 事件
- `src/domain/entities/memory.py` - Memory 实体
- `src/domain/value_objects/memory_index_entry.py` - MemoryIndexEntry
- `src/domain/repositories/memory_metadata_repository.py` - 接口
- `src/domain/repositories/memory_change_history_repository.py` - 接口
- `src/interfaces/storage/l0_memory_port.py` - L0MemoryStore 端口
- `src/infrastructure/storage/file_system_memory_adapter.py` - FileSystemMemoryAdapter
- `src/infrastructure/repositories/memory_metadata_repository_impl.py` - 实现
- `src/infrastructure/repositories/memory_change_history_repository_impl.py` - 实现

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 1.15b |
| **Story Key** | 1-15b-externalized-memory-five-layer-storage |
| **File** | `_bmad-output/implementation-artifacts/stories/1-15b-externalized-memory-five-layer-storage.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 1: 企业级架构基础与合规 |
| **价值组** | 价值组 5: or.md 系统公理实现 |
| **优先级** | P0-15b（or.md 系统公理二） |
| **覆盖 FR** | or.md 系统公理二（外部化记忆） |

### 完成总结 Completion Summary

1. [ ] All tasks defined 所有任务定义完成
2. [ ] All acceptance criteria specified 所有验收标准已定义
3. [ ] Architecture constraints extracted 架构约束已提取
4. [ ] Previous story learnings integrated 前一个故事学习经验已整合
5. [ ] Sprint status synced to `ready-for-dev`

### 下一步 Next Steps

- [ ] Story created with `backlog` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `validate-create-story` 质量检查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**模板版本/Template Version:** 2.4.0
**创建日期/Created:** 2026-03-04
**最后更新/Last Updated:** 2026-04-24
**更新说明:**
- v2.5.0: 新建 Story 1.15b - L0 记忆入口 + 六层存储协同
