# Story 1.15b: 外部化记忆 - L0 记忆入口 + 六层存储协同实现

**Status:** `backlog` → `ready-for-dev`

> **Note:** 本 Story 是 Story 1.15a 的后续实现，承接 L1 显式确认压缩后的存储协同。
> 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 系统架构师,
**I want** 实现 L0 MEMORY.md 记忆入口与 L1-L5 六层存储协同,
**So that** 记忆分离原则得到实现，磁盘记忆=真相源。

### 业务价值

本 Story 是 Epic 1（企业级架构基础与合规）价值组 5（or.md 系统公理实现）的第五个故事，在 Story 1.15a（trigger→压缩）完成后实现六层存储协同。核心价值：

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **L0 MEMORY.md 入口** | 索引驱动各层存储访问，路径规范统一 | 索引格式正确、路由生效 |
| **Private/Group 分离** | 多租户隔离，private 记忆仅用户可见，group 记忆团队共享 | RBAC 校验通过 |
| **六层存储协同** | L0-L5 各层按职责存储，层间单向依赖 | 层间协同测试通过 |
| **事件驱动下游** | MemoryChanged 事件触发元数据同步、缓存失效 | 事件处理成功率 ≥99% |
| **完整 CRUD** | 创建/读取/更新/删除，带版本冲突处理（乐观锁） | 所有 CRUD 测试通过 |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 1: 企业级架构基础与合规，价值组 5: or.md 系统公理实现，Story 1.15b

**or.md 公理追溯:** 系统公理二（外部化记忆：LLM 上下文=缓存，磁盘记忆=真相源），覆盖"公理二 L0 记忆入口"

**前置依赖:** Story 1.15a（提供 L1 显式确认压缩）、Story 1.4（提供 L1 Redis）、Story 1.5（提供 L2 PostgreSQL 基础表结构）

**后续依赖:** Story 6.3（Checkpoint 快照创建 - L3 压缩触发）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: L0 MEMORY.md 入口

**Given** 用户记忆系统初始化
**When** L0 入口层执行
**Then** 执行以下职责：
  1. MEMORY.md 索引入口（`~/.sisys/memory/MEMORY.md`）
  2. 索引格式：`- [Title](type/uuid.md) — one-line hook`
  3. 路由策略：按 type 分类（user/feedback/project/reference）
  4. 文本扫描：正则匹配记忆名称
**And** 截断策略：超过 200 行时保留最新 200 行（按写入顺序，最后写入的行在文件末尾）

**验证标准/Validation Criteria:**
- [ ] MEMORY.md 索引文件创建（`src/infrastructure/storage/memory_index.py`）
- [ ] 索引格式验证（每行 `- [Title](type/uuid.md) — hook`）
- [ ] 截断策略实现（超过 200 行保留最新）
- [ ] 路由策略（按 type 分类文件夹）

### AC-2: Private/Group 记忆分离

**Given** 用户创建记忆
**When** 记忆按可见性分类
**Then** Private 记忆存储于 `~/.sisys/memory/{type}/`
**And** Group 记忆存储于 `~/.sisys/memory/group/{type}/`
**And** RBAC 校验：
  - private 记忆（group_id=NULL）：读取/写入验证 owner == user_id
  - group 记忆（group_id != NULL）：读取/写入验证用户是 group 成员或有管理员权限

**验证标准/Validation Criteria:**
- [ ] Private 路径策略（`~/.sisys/memory/{type}/`）
- [ ] Group 路径策略（`~/.sisys/memory/group/{type}/`）
- [ ] Private RBAC 校验（owner == user_id）
- [ ] Group RBAC 校验（group 成员或管理员）
- [ ] MemoryAccessDeniedError 抛出条件正确

### AC-3: 六层存储协同

**Given** 记忆操作触发
**When** 六层存储协同执行
**Then** 各层按职责存储：
  - L0 文件系统：实际记忆内容（.md 文件）+ MEMORY.md 索引
  - L1 Redis：记忆缓存（TTL 24h-30d，key 格式 `memory:user:{user_id}:{name}`）
  - L2 PostgreSQL：memory_metadata + memory_change_history
  - L3 Qdrant：嵌入向量（文件 >500 字时）
  - L4 MinIO：StrategicArchive（7 年 WORM）
  - L5 Neo4j：知识图谱关系

**验证标准/Validation Criteria:**
- [ ] L0 文件系统写入（`src/infrastructure/storage/file_memory_adapter.py`）- Story 1.15a 已实现
- [ ] L1 Redis 缓存（key 格式 `memory:user:{user_id}:{name}`）
- [ ] L2 PostgreSQL 元数据（memory_metadata UPSERT）
- [ ] L2 历史记录（memory_change_history append-only）
- [ ] 层间单向依赖验证（L0 → L2，不存在反向依赖）
- [ ] 六层存储架构测试（`test_six_layer_storage.py`）

### AC-4: MemoryChanged 事件下游处理

**Given** 记忆操作完成（保存/删除/修改）
**When** MemoryChanged 事件发布
**Then** 下游监听器触发：
  1. 写入 memory_metadata（UPSERT，version + 1）
  2. 写入 memory_change_history（append-only）
  3. 失效 L1 Redis 缓存（`redis.del("memory:user:{user_id}:{name}")`）
  4. 可选：更新 L3 Qdrant 向量索引（文件 >500 字时）

**验证标准/Validation Criteria:**
- [ ] MemoryChangedListener 下游监听器（`src/interfaces/event_listeners/memory_changed_listener.py`）- Story 1.15a 已实现
- [ ] MemoryMetadataRepository UPSERT（`src/infrastructure/repositories/memory_metadata_repository.py`）- Story 1.15a 已实现
- [ ] MemoryChangeHistoryRepository append-only（`src/infrastructure/repositories/memory_change_history_repository.py`）- Story 1.15a 已实现
- [ ] Redis 缓存失效（L1）
- [ ] 事件处理成功率 ≥99%

### AC-5: 记忆操作触发索引与缓存

**Given** 用户发起记忆操作
**When** MemoryService 执行 CRUD 操作
**Then** 触发以下协同行为：
  - 创建（save）：触发 MemoryIndex 索引更新 + Redis 缓存写入 + MemoryChanged 事件
  - 读取（list/get）：从 MemoryIndex 读取路由，从 Redis 缓存获取（缓存命中）
  - 更新（update）：触发 MemoryIndex 索引更新 + Redis 缓存失效 + MemoryChanged 事件
  - 删除（delete）：触发 MemoryIndex 索引清理 + Redis 缓存失效 + MemoryChanged 事件

**说明：** MemoryService CRUD 操作已在 Story 1.15a 实现，本 AC 聚焦于 CRUD 触发后的索引协同和缓存管理。

**验证标准/Validation Criteria:**
- [ ] MemoryService.save() 触发 MemoryIndex 更新
- [ ] MemoryService.save() 触发 Redis 缓存写入
- [ ] MemoryService.list() 从 MemoryIndex 获取路由
- [ ] MemoryService.list() 从 Redis 缓存获取（缓存命中）
- [ ] MemoryService.update() 触发 MemoryIndex 更新
- [ ] MemoryService.update() 触发 Redis 缓存失效
- [ ] MemoryService.delete() 触发 MemoryIndex 清理
- [ ] MemoryService.delete() 触发 Redis 缓存失效
- [ ] 版本冲突处理（重试最多 3 次，3 次仍冲突抛出 MemoryVersionConflictError）

### AC-6: 性能要求

**Given** 记忆操作执行
**When** 性能指标测量
**Then** 满足以下要求：
  - Redis TTL 24h-30d（测量：redis TTL 命令）
  - MinIO WORM 7 年（测量：Object Lock 配置）
  - L0→L2 元数据同步延迟 <100ms（异步写入）
  - 记忆保存成功率 100%

**验证标准/Validation Criteria:**
- [ ] Redis TTL 验证（24h-30d）
- [ ] MinIO WORM 配置验证（7 年 Object Lock）
- [ ] L0→L2 同步延迟 <100ms
- [ ] 记忆保存成功率 100%（memory_metadata 记录存在）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] MemoryChanged 事件定义（`src/domain/events/memory_events.py`）- Story 1.15a 已实现
- [ ] MemoryChangedListener 下游监听器接口（`src/interfaces/event_listeners/memory_changed_listener.py`）- Story 1.15a 已实现

#### 数据模型 (Data Models)
- [ ] MemoryMetadata 实体（`src/domain/entities/memory_metadata.py`）- Story 1.15a 已实现
- [ ] MemoryChangeHistory 实体（`src/domain/entities/memory_change_history.py`）- Story 1.15a 已实现
- [ ] MemoryService 服务类（`src/domain/services/memory_service.py`）- Story 1.15a 已实现

#### L0 入口实现 (L0 Memory Entry)
- [ ] **MemoryIndex 索引管理**（`src/infrastructure/storage/memory_index.py`）
  - 索引位置：`~/.sisys/memory/MEMORY.md`
  - 路径优先级（XDG 规范）：
    1. `$XDG_CONFIG_HOME/sisys/memory/`（若 XDG_CONFIG_HOME 已设置）
    2. `$HOME/.config/sisys/memory/`（XDG 默认路径）
    3. `$HOME/.sisys/memory/`（向后兼容旧版本）
  - 索引格式：`- [Title](type/uuid.md) — one-line hook`
  - 截断策略：超过 200 行时保留最新 200 行（按写入顺序，最后写入的行在文件末尾）
  - 更新时机：每次 save/update/delete 后更新索引
- [ ] **MemoryRouter 路由策略**（`src/infrastructure/storage/memory_router.py`）
  - 路径优先级（XDG 规范）：
    1. `$XDG_CONFIG_HOME/sisys/memory/`（若 XDG_CONFIG_HOME 已设置）
    2. `$HOME/.config/sisys/memory/`（XDG 默认路径）
    3. `$HOME/.sisys/memory/`（向后兼容旧版本）
  - 记忆类型路径：
    1. Private：`{base_path}/{type}/{uuid}.md`（如 `~/.sisys/memory/user/abc123.md`）
    2. Group：`{base_path}/group/{type}/{uuid}.md`（如 `~/.sisys/memory/group/user/abc123.md`）
  - type 分类：user/feedback/project/reference
  - 索引分离：Private 用 `{base_path}/MEMORY.md`，Group 用 `{base_path}/group/MEMORY.md`

#### RBAC 校验 (Access Control)
- [ ] **MemoryAccessControl 访问控制**（`src/infrastructure/security/memory_access_control.py`）
  - Private 记忆校验：owner == user_id
  - Group 记忆校验：用户是 group 成员或有管理员权限
  - 异常类型：MemoryAccessDeniedError

#### 存储适配器 (Storage Adapters)
- [ ] FileMemoryAdapter L0 文件系统适配器（`src/infrastructure/storage/file_memory_adapter.py`）- Story 1.15a 已实现
- [ ] MemoryMetadataRepository L2 PostgreSQL 仓储（`src/infrastructure/repositories/memory_metadata_repository.py`）- Story 1.15a 已实现
- [ ] MemoryChangeHistoryRepository L2 历史记录仓储（`src/infrastructure/repositories/memory_change_history_repository.py`）- Story 1.15a 已实现
- [ ] RedisMemoryCache L1 缓存（`src/infrastructure/cache/redis_memory_cache.py`）
  - Key 格式：`memory:user:{user_id}:{name}`
  - TTL：24h-30d（随机值避免雪崩）
  - 失效：MemoryChanged 事件触发
- [ ] QdrantMemoryVector L3 向量存储（`src/infrastructure/vector/qdrant_memory_vector.py`）
  - 嵌入向量生成（文件 >500 字时）
  - 混合检索支持
- [ ] StrategicArchiveStorage L4 对象存储（`src/infrastructure/storage/strategic_archive_storage.py`）
  - MinIO WORM 存储（7 年）
  - Checkpoint 归档
- [ ] KnowledgeGraphStorage L5 图存储（`src/infrastructure/graph/knowledge_graph_storage.py`）
  - Neo4j 知识图谱
  - 实体关系存储

#### 配置模型 (Configuration Models)
- [ ] MemoryConfig 配置（`src/infrastructure/config/memory.py`）- Story 1.15a 已实现

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_story_1.15b.feature`（由 Dev agent 在 Task 0 创建）
- [ ] 覆盖场景：
  - L0 MEMORY.md 入口（索引、路由、截断）
  - Private/Group 分离（RBAC 校验）
  - 六层存储协同（L0-L5 各层职责）
  - MemoryChanged 事件下游处理
  - 完整 CRUD 操作
  - 版本冲突处理

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
| **TDD 单元测试** | MemoryIndex | 索引管理 | `test_memory_index.py` | Task 1 |
| **TDD 单元测试** | MemoryRouter | 路由策略 | `test_memory_router.py` | Task 1 |
| **TDD 单元测试** | MemoryAccessControl | RBAC 校验 | `test_memory_access_control.py` | Task 1 |
| **TDD 单元测试** | RedisMemoryCache | L1 缓存 | `test_redis_memory_cache.py` | Task 2 |
| **TDD 单元测试** | SixLayerStorage | 六层协同 | `test_six_layer_storage.py` | Task 2 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_story_1.15b.feature` | Task 0 |
| **SDD 架构验证** | 六层架构 | 依赖方向验证 | `test_memory_architecture.py` | Task 3 |
| **集成测试** | 事件总线 | 端到端存储流程 | `test_storage_integration.py` | Task 3 |

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

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | L0 MEMORY.md 入口 | Task 1 | Subtask 1.1-1.3（MemoryIndex 红→绿→重构） | `test_memory_index.py` |
| AC-1 | MemoryRouter 路由策略 | Task 1 | Subtask 1.4-1.6（MemoryRouter 红→绿→重构） | `test_memory_router.py` |
| AC-2 | RBAC 访问控制 | Task 1 | Subtask 1.7-1.9（MemoryAccessControl 红→绿→重构） | `test_memory_access_control.py` |
| AC-3 | 六层存储协同 | Task 2 | Subtask 2.1-2.3（SixLayerStorage 红→绿→重构） | `test_six_layer_storage.py` |
| AC-4 | RedisMemoryCache L1 缓存 | Task 2 | Subtask 2.4-2.6（RedisMemoryCache 红→绿→重构） | `test_redis_memory_cache.py` |
| AC-5 | 记忆操作触发索引与缓存 | Task 1, Task 2 | Subtask 1.7-1.9 + 2.4-2.6 | `test_memory_index.py` + `test_redis_memory_cache.py` |
| AC-6 | 性能要求 | Task 3 | Subtask 3.1-3.3（性能基准测试 红→绿→重构） | `test_storage_performance.py` |

---

## 📋 Tasks / Subtasks 任务分解

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5, AC-6

> **目的：** 在进入代码实现前，明确 Schema、API 契约、验收标准。

- [ ] Subtask 0.1: 定义 MemoryIndex 索引管理（`src/infrastructure/storage/memory_index.py`）
- [ ] Subtask 0.2: 定义 MemoryRouter 路由策略（`src/infrastructure/storage/memory_router.py`）
- [ ] Subtask 0.3: 定义 MemoryAccessControl 访问控制（`src/infrastructure/security/memory_access_control.py`）
- [ ] Subtask 0.4: 定义 RedisMemoryCache L1 缓存（`src/infrastructure/cache/redis_memory_cache.py`）
- [ ] Subtask 0.5: 编写 Gherkin 验收测试 `tests/acceptance/test_story_1.15b.feature`（Dev agent 创建）
- [ ] Subtask 0.6: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: L0 入口与 RBAC 校验

**关联 AC:** AC-1, AC-2

> **职责边界:** Task 1 负责 MemoryIndex（索引管理）、MemoryRouter（路由策略）、MemoryAccessControl（RBAC 校验）

#### TDD 循环 [A]：MemoryIndex 索引管理

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/storage/test_memory_index.py`（验证索引格式、截断策略） |
| 🟢 绿 | 实现 `src/infrastructure/storage/memory_index.py` - MemoryIndex |
| 🔄 重构 | 优化索引更新逻辑 |

- [ ] Subtask 1.1: 🔴 红 — 编写 MemoryIndex 失败测试
- [ ] Subtask 1.2: 🟢 绿 — 实现 MemoryIndex（索引格式、截断策略）
- [ ] Subtask 1.3: 🔄 重构 — 优化索引更新逻辑

#### TDD 循环 [B]：MemoryRouter 路由策略

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/storage/test_memory_router.py`（验证路径策略） |
| 🟢 绿 | 实现 `src/infrastructure/storage/memory_router.py` - MemoryRouter |
| 🔄 重构 | 优化路由逻辑 |

- [ ] Subtask 1.4: 🔴 红 — 编写 MemoryRouter 失败测试
- [ ] Subtask 1.5: 🟢 绿 — 实现 MemoryRouter（Private/Group 路径）
- [ ] Subtask 1.6: 🔄 重构 — 验证路由逻辑

#### TDD 循环 [C]：MemoryAccessControl RBAC 校验

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/security/test_memory_access_control.py`（验证 RBAC） |
| 🟢 绿 | 实现 `src/infrastructure/security/memory_access_control.py` - MemoryAccessControl |
| 🔄 重构 | 优化权限校验逻辑 |

- [ ] Subtask 1.7: 🔴 红 — 编写 MemoryAccessControl 失败测试
- [ ] Subtask 1.8: 🟢 绿 — 实现 MemoryAccessControl（Private/Group RBAC）
- [ ] Subtask 1.9: 🔄 重构 — 添加 MemoryAccessDeniedError 异常处理

**完成标准/Definition of Done:**
- [ ] MemoryIndex 实现完成（索引格式、截断策略）
- [ ] MemoryRouter 实现完成（Private/Group 路径）
- [ ] MemoryAccessControl 实现完成（RBAC 校验）
- [ ] TDD 循环全部通过

---

### Task 2: 六层存储协同

**关联 AC:** AC-3, AC-4

> **职责边界:** Task 2 负责 SixLayerStorage（六层协同）、RedisMemoryCache（L1 缓存）

#### TDD 循环 [A]：SixLayerStorage 六层协同

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/architecture/test_six_layer_storage.py`（验证层间依赖） |
| 🟢 绿 | 实现六层存储协同逻辑 |
| 🔄 重构 | 验证层间单向依赖链 |

- [ ] Subtask 2.1: 🔴 红 — 编写 SixLayerStorage 失败测试
- [ ] Subtask 2.2: 🟢 绿 — 实现六层存储协同
- [ ] Subtask 2.3: 🔄 重构 — 验证层间依赖方向

#### TDD 循环 [B]：RedisMemoryCache L1 缓存

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/cache/test_redis_memory_cache.py`（验证缓存操作） |
| 🟢 绿 | 实现 `src/infrastructure/cache/redis_memory_cache.py` - RedisMemoryCache |
| 🔄 重构 | 优化缓存 TTL 和失效逻辑 |

- [ ] Subtask 2.4: 🔴 红 — 编写 RedisMemoryCache 失败测试
- [ ] Subtask 2.5: 🟢 绿 — 实现 RedisMemoryCache（L1 缓存）
- [ ] Subtask 2.6: 🔄 重构 — 验证 TTL 和失效逻辑

**完成标准/Definition of Done:**
- [ ] SixLayerStorage 实现完成（层间协同）
- [ ] RedisMemoryCache 实现完成（L1 缓存）
- [ ] TDD 循环全部通过

---

### Task 3: 架构验证与性能基准

**关联 AC:** AC-5, AC-6

> **职责边界:** Task 3 负责性能基准测试（六层存储性能）和六边形架构验证

#### TDD 循环 [A]：性能基准测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/performance/test_storage_performance.py`（验证性能要求） |
| 🟢 绿 | 实现性能优化（异步写入、批量操作） |
| 🔄 重构 | 性能调优 |

- [ ] Subtask 3.1: 🔴 红 — 编写性能基准失败测试
  - Redis TTL 测试（24h-30d）
  - L0→L2 同步延迟测试（<100ms）
  - 记忆保存成功率测试（100%）
- [ ] Subtask 3.2: 🟢 绿 — 实现性能优化
  - 异步写入优化
  - 批量操作优化
- [ ] Subtask 3.3: 🔄 重构 — 性能调优

#### TDD 循环 [B]：六边形架构验证

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/architecture/test_memory_architecture.py`（验证架构约束） |
| 🟢 绿 | 实现架构验证逻辑（依赖方向检测） |
| 🔄 重构 | 优化架构验证器 |

- [ ] Subtask 3.4: 🔴 红 — 编写架构验证失败测试
- [ ] Subtask 3.5: 🟢 绿 — 实现架构验证逻辑
- [ ] Subtask 3.6: 🔄 重构 — 验证器优化

#### 集成测试

- [ ] Subtask 3.7: 创建 `tests/integration/test_storage_integration.py`（端到端六层存储流程）

**测试策略：**
| 层级 | 测试方式 | 说明 |
|------|---------|------|
| L0 文件系统 | 真实文件 | 使用临时目录 fixture，验证索引和文件操作 |
| L1 Redis | 真实 Redis | 验证缓存写入/失效逻辑（使用 UUID 前缀隔离） |
| L2 PostgreSQL | transaction rollback | 验证 metadata/history 写入 |
| L3 Qdrant | 真实 Qdrant | 验证向量写入和检索（使用 collection 前缀隔离） |
| L4 MinIO | 真实 MinIO | 验证 StrategicArchive 归档（使用 bucket 前缀隔离） |
| L5 Neo4j | 真实 Neo4j | 验证知识图谱写入（使用 label 前缀隔离） |

**隔离要求：**
- 每个测试使用 UUID 前缀隔离资源
- 外部服务（Redis/PostgreSQL/Qdrant/MinIO/Neo4j）在 fixture 内清理
- 真实服务测试确保并行测试通过（`pytest -n 8`）

**完成标准/Definition of Done:**
- [ ] Redis TTL 24h-30d 验证通过
- [ ] L0→L2 同步延迟 <100ms 验证通过
- [ ] 记忆保存成功率 100% 验证通过
- [ ] 六边形架构验证通过
- [ ] 集成测试通过

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（端口与适配器）、事件驱动架构
- **系统公理二:** 外部化记忆（LLM 上下文=缓存，磁盘记忆=真相源）
  - L0 入口：MEMORY.md 作为统一入口，索引驱动各层存储访问
  - L1 显式确认：轻量级压缩（≤500字→~150字）
  - L3 Checkpoint：重量级压缩（~50K tokens→~2K tokens）
- **六层存储架构:**
  - L0 文件系统：MEMORY.md 索引 + 实际记忆文件
  - L1 Redis：会话状态、语义缓存、公共黑板（TTL 24h-30d）
  - L2 PostgreSQL：memory_metadata + memory_change_history
  - L3 Qdrant：嵌入向量（文件 >500 字时）
  - L4 MinIO：StrategicArchive（7 年 WORM）
  - L5 Neo4j：知识图谱关系
- **设计约束:**
  - 领域层零依赖外部框架
  - 依赖倒置：领域层定义接口，基础设施层实现
  - 层间单向依赖：L0 → L1/L2/L3/L4/L5，不存在反向依赖

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) - ADR 相关决策

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **MEMORY.md 作为统一入口** | 索引驱动各层访问，启动快速 | 需要额外索引维护 | ✅ 9/10 |
| Private/Group 路径分离 | 多租户隔离清晰 | 路径复杂度增加 | 8/10 |
| Redis TTL 随机值 | 避免雪崩效应 | 缓存过期时间不确定 | 8/10 |

**决策**: MEMORY.md 作为**统一入口**，索引驱动各层存储访问。

### ADR: 存储同步策略决策

**问题**: L0 文件系统和 L2 PostgreSQL 同步策略？

| 评估维度 | 同步写入 | 异步写入 | 事务写入 |
|---------|---------|---------|---------|
| 一致性 | 高 | 中 | 高 |
| 延迟 | 高 | 低 | 中 |
| 复杂度 | 低 | 中 | 高 |
| **采用** | ❌ 不采用 | ✅ **采用** | ❌ 不采用 |

**决策**: 使用**异步写入**：
1. L0 文件系统同步写入（优先保证 LLM 上下文可用）
2. L2 PostgreSQL 异步写入（通过事务发件箱模式）
3. MemoryChanged 事件与 L0 写入同事务提交
4. 下游监听器处理 L2 异步写入

### L0 截断策略澄清

> ⚠️ **重要澄清**：MEMORY.md 索引截断策略！

**策略：**
- 索引文件最多 200 行
- 超出时保留最新 200 行（按写入顺序，最后写入的行在文件末尾）
- 截断时机：每次 save/update/delete 后检查并截断

**设计原理**：
- LLM 上下文限制（启动时加载 MEMORY.md）
- 索引仅用于快速扫描，实际内容在 .md 文件中
- 保留最新 200 条确保热点记忆可用
- "最新"定义：文件末尾追加模式，最后写入的行在文件末尾，截断时移除最旧的行（文件开头）

### 与 Story 1.15a 的关系

> ⚠️ **重要澄清**：本 Story 与 Story 1.15a 的分工！

**Story 1.15a (L1 显式确认压缩) - 已完成:**
- L1TextExtractor 文本提取器
- L1Compressor 压缩器
- MemoryService.save/delete/update/list
- FileMemoryAdapter L0 文件系统
- MemoryMetadataRepository L2
- MemoryChangeHistoryRepository L2
- MemoryChanged 事件

**Story 1.15b (L0 入口 + 六层存储协同) - 本 Story:**
- MemoryIndex 索引管理（MEMORY.md 入口）
- MemoryRouter 路由策略（Private/Group 路径）
- MemoryAccessControl RBAC 校验
- RedisMemoryCache L1 缓存
- 六层存储协同
- 事件下游处理完善

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── domain/
│   │   ├── events/
│   │   │   └── memory_events.py      # MemoryChanged 事件（Story 1.15a 已实现）
│   │   ├── entities/
│   │   │   ├── memory_metadata.py   # MemoryMetadata 实体（Story 1.15a 已实现）
│   │   │   └── memory_change_history.py # MemoryChangeHistory 实体（Story 1.15a 已实现）
│   │   ├── services/
│   │   │   └── memory_service.py    # MemoryService（Story 1.15a 已实现）
│   │   └── repositories/
│   │       └── memory_repository.py # MemoryRepository 接口（领域层定义）
│   ├── application/
│   │   └── text_processing/
│   │       ├── l1_text_extractor.py # L1TextExtractor（Story 1.15a 已实现）
│   │       └── l1_compressor.py     # L1Compressor（Story 1.15a 已实现）
│   ├── infrastructure/
│   │   ├── config/
│   │   │   └── memory.py            # MemoryConfig（Story 1.15a 已实现）
│   │   ├── storage/
│   │   │   ├── file_memory_adapter.py # FileMemoryAdapter L0（Story 1.15a 已实现）
│   │   │   ├── memory_index.py      # MemoryIndex 索引管理（新实现）
│   │   │   └── memory_router.py     # MemoryRouter 路由策略（新实现）
│   │   ├── cache/
│   │   │   └── redis_memory_cache.py # RedisMemoryCache L1 缓存（新实现）
│   │   ├── security/
│   │   │   └── memory_access_control.py # MemoryAccessControl RBAC（新实现）
│   │   └── repositories/
│   │       ├── memory_metadata_repository.py # MemoryMetadataRepository L2（Story 1.15a 已实现）
│   │       └── memory_change_history_repository.py # MemoryChangeHistoryRepository L2（Story 1.15a 已实现）
│   └── interfaces/
│       └── event_listeners/
│           └── memory_changed_listener.py # MemoryChangedListener（Story 1.15a 已实现）
├── tests/
│   ├── unit/
│   │   ├── infrastructure/
│   │   │   ├── storage/
│   │   │   │   ├── test_memory_index.py      # MemoryIndex 单元测试
│   │   │   │   ├── test_memory_router.py     # MemoryRouter 单元测试
│   │   │   │   └── test_file_memory_adapter.py # FileMemoryAdapter 单元测试（Story 1.15a）
│   │   │   ├── cache/
│   │   │   │   └── test_redis_memory_cache.py # RedisMemoryCache 单元测试
│   │   │   └── security/
│   │   │       └── test_memory_access_control.py # MemoryAccessControl 单元测试
│   │   ├── architecture/
│   │   │   ├── test_six_layer_storage.py    # 六层存储单元测试
│   │   │   └── test_memory_architecture.py   # 架构验证测试
│   │   └── performance/
│   │       └── test_storage_performance.py  # 性能基准测试
│   ├── integration/
│   │   └── test_storage_integration.py      # 集成测试
│   └── acceptance/
│       ├── test_story_1.15b.feature         # Gherkin 验收测试
│       └── test_story_1.15b_steps.py        # 验收测试步骤实现
└── docs/
    └── developer/
        └── externalized_memory_guide.md    # 外部化记忆实施指南
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 1.15a: 外部化记忆 - L1 显式确认压缩](./1-15a-externalized-memory-context-compression.md)

**关键学习/Key Learnings:**
1. **配置模式复用** — OtelConfig.from_env() 模式应复用，MemoryConfig 采用相同 `from_env()` 类方法
2. **事件驱动解耦** — MemoryService 仅负责 CRUD，不处理下游逻辑；下游监听器处理元数据同步
3. **六边形架构严格遵守** — Task 3 必须包含架构验证测试，确保层间依赖方向正确
4. **测试隔离约束显式强调** — asyncio.Lock 类变量、pytest-asyncio auto mode 规则必须在 Story 中明确
5. **混合压缩边界条件** — ≤200字直接规则压缩，>200字 LLM 压缩

**应用到本故事/Applied to This Story:**
- [x] MemoryConfig 采用与 OtelConfig 相同的 `from_env()` 模式
- [x] MemoryIndex 仅负责索引管理，不处理存储逻辑
- [x] Task 3 包含架构验证测试（层间依赖方向检测）
- [x] 测试隔离约束显式强调（asyncio.Lock/pytest-asyncio）
- [x] Redis 缓存 key 格式统一为 `memory:user:{user_id}:{name}`
- [x] XDG 路径规范正确实现（$XDG_CONFIG_HOME > $HOME/.config > $HOME/.sisys）
- [x] L0 截断策略明确（超过 200 行保留最新）

### Git Intelligence Summary

**来源:** `git log` - 最近 5 个提交

| 提交 | 主题 | 关键模式 |
|------|------|---------|
| `67d28b5` | fix(test): 使用 CREATE SCHEMA IF NOT EXISTS 避免并发冲突 | Schema 创建模式 |
| `bb5a2d4` | fix(test): pg_config 和 setup_schema 改为 session-scoped | 测试 fixture 模式 |
| `ba8d0b7` | Merge branch 'main' of https://gitea.sisys.local/sisys/sisys | 合并模式 |
| `26f468a` | refactor: 将 MemoryService 测试移至 integration 目录 | 测试组织模式 |
| `13eb5b9` | test: 添加 L0 真实文件系统集成测试 | 集成测试模式 |

**可应用模式:**
1. **Schema 并发安全** — 使用 `CREATE SCHEMA IF NOT EXISTS` 避免并发冲突
2. **测试 fixture session-scoped** — pg_config 和 setup_schema 改为 session-scoped
3. **真实文件系统集成测试** — L0 文件系统使用真实文件而非 mock

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (create-story workflow) |
| **Version** | create-story workflow v1.0 |
| **Execution Date** | 2026-04-26 |

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
- [x] or.md 系统公理二（L0 入口）追溯完成
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] 前一个故事学习经验已整合
- [x] L0/L1/L3 分离关系已澄清
- [x] 测试隔离约束显式强调（asyncio.Lock/pytest-asyncio）
- [x] 六层存储架构已明确
- [x] Redis TTL 随机值策略已定义
- [x] L0 截断策略已明确（按写入顺序）
- [x] XDG 路径规范已添加
- [x] L3/L4/L5 依赖标注已完成
- [x] AC-5 职责已聚焦（触发索引/缓存协同）
- [x] 集成测试策略已明确

### 文件清单 File List

**创建的文件/Created Files (Dev Story 实施):**
- `src/infrastructure/storage/memory_index.py` - MemoryIndex 索引管理
- `src/infrastructure/storage/memory_router.py` - MemoryRouter 路由策略
- `src/infrastructure/security/memory_access_control.py` - MemoryAccessControl RBAC
- `src/infrastructure/cache/redis_memory_cache.py` - RedisMemoryCache L1 缓存
- `src/infrastructure/vector/qdrant_memory_vector.py` - QdrantMemoryVector L3 向量存储
- `src/infrastructure/storage/strategic_archive_storage.py` - StrategicArchiveStorage L4 对象存储
- `src/infrastructure/graph/knowledge_graph_storage.py` - KnowledgeGraphStorage L5 图存储
- `tests/unit/infrastructure/storage/test_memory_index.py` - MemoryIndex 单元测试
- `tests/unit/infrastructure/storage/test_memory_router.py` - MemoryRouter 单元测试
- `tests/unit/infrastructure/security/test_memory_access_control.py` - MemoryAccessControl 单元测试
- `tests/unit/infrastructure/cache/test_redis_memory_cache.py` - RedisMemoryCache 单元测试
- `tests/unit/vector/test_qdrant_memory_vector.py` - QdrantMemoryVector 单元测试
- `tests/unit/infrastructure/storage/test_strategic_archive_storage.py` - StrategicArchiveStorage 单元测试
- `tests/unit/graph/test_knowledge_graph_storage.py` - KnowledgeGraphStorage 单元测试
- `tests/unit/architecture/test_six_layer_storage.py` - 六层存储单元测试
- `tests/unit/architecture/test_memory_architecture.py` - 架构验证测试
- `tests/unit/performance/test_storage_performance.py` - 性能基准测试
- `tests/integration/test_storage_integration.py` - 集成测试
- `tests/acceptance/test_story_1.15b.feature` - Gherkin 验收测试
- `tests/acceptance/test_story_1.15b_steps.py` - 验收测试步骤实现

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/infrastructure/storage/__init__.py` - 添加 MemoryIndex, MemoryRouter 导出
- `src/infrastructure/security/__init__.py` - 添加 MemoryAccessControl 导出
- `src/infrastructure/cache/__init__.py` - 添加 RedisMemoryCache 导出
- `src/infrastructure/vector/__init__.py` - 添加 QdrantMemoryVector 导出
- `src/infrastructure/graph/__init__.py` - 添加 KnowledgeGraphStorage 导出

**已存在的文件（来自 Story 1.15a）:**
- `src/domain/events/memory_events.py` - MemoryChanged 事件
- `src/domain/entities/memory_metadata.py` - MemoryMetadata 实体
- `src/domain/entities/memory_change_history.py` - MemoryChangeHistory 实体
- `src/domain/services/memory_service.py` - MemoryService
- `src/domain/repositories/memory_repository.py` - MemoryRepository 接口
- `src/domain/services/text_extractor_service.py` - TextExtractorService
- `src/domain/services/compressor_service.py` - CompressorService
- `src/application/text_processing/l1_text_extractor.py` - L1TextExtractor
- `src/application/text_processing/l1_compressor.py` - L1Compressor
- `src/infrastructure/config/memory.py` - MemoryConfig
- `src/infrastructure/storage/file_memory_adapter.py` - FileMemoryAdapter
- `src/infrastructure/repositories/memory_metadata_repository.py` - MemoryMetadataRepository
- `src/infrastructure/repositories/memory_change_history_repository.py` - MemoryChangeHistoryRepository
- `src/interfaces/event_listeners/memory_changed_listener.py` - MemoryChangedListener

---

## 📚 Project Context Reference

> **来源:** [`project-context.md`](../../_bmad-output/project-context.md)

### 关键约束速查

| 约束类型 | 约束内容 | 来源 |
|---------|---------|------|
| **架构原则** | 六边形架构，领域层零依赖 | architecture.md §3.1 |
| **系统公理二** | 外部化记忆（LLM 上下文=缓存，磁盘记忆=真相源） | architecture.md §3.2 |
| **六层存储架构** | L0-L5 各层按职责存储，层间单向依赖 | architecture.md §11.2 |
| **事件驱动** | 事务发件箱模式，事件处理幂等性 | architecture.md §3.3 |
| **测试覆盖率** | 架构层≥85%，集成测试≥75% | sdd-tdd-checklist.md §5 |
| **L0 截断策略** | 超过 200 行保留最新 | architecture.md §11.2.3 |

### 关键路径依赖

```
Story 1.14a (trigger) → Story 1.14b (route) → Story 1.14c (execute)
                                                            ↓
                                          Story 1.15a (外部化记忆 - L1 压缩) ← 已完成
                                                            ↓
                                          Story 1.15b (外部化记忆 - L0 入口) ← 本 Story
                                                            ↓
                                          Story 6.3 (Checkpoint - L3 压缩)
```

### 六层存储架构（来自 architecture.md §11.2）

| 层级 | 技术 | 存储内容 | TTL | 相关 Story |
|------|------|---------|-----|-----------|
| **L0 记忆入口** | 文件系统 | MEMORY.md 索引、路由策略 | 永久 | Story 1.15b |
| **L1 高速缓存** | Redis | 会话状态、语义缓存、公共黑板、记忆缓存 | 24h-30d | Story 1.4 |
| **L2 关系存储** | PostgreSQL | memory_metadata、memory_change_history | 永久 | Story 1.5 |
| **L3 向量存储** | Qdrant | 嵌入向量、混合检索 payload | 永久 | Story 1.6 |
| **L4 对象存储** | MinIO | 原始文档、StrategicArchive | 7 年 | Story 1.7 |
| **L5 图存储** | Neo4j | 知识图谱、实体关系 | 永久 | Story 1.8 |

**注意：** L1-L5 层存储均已在各自 Story 中实现并部署，本 Story 需实现与各层的协同机制。

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 1.15b |
| **Story Key** | 1-15b-externalized-memory-five-layer-storage |
| **File** | `_bmad-output/implementation-artifacts/stories/1-15b-externalized-memory-five-layer-storage.md` |
| **Status** | `backlog` → `ready-for-dev` |
| **Epic** | Epic 1: 企业级架构基础与合规 |
| **价值组** | 价值组 5: or.md 系统公理实现 |
| **优先级** | P0-15b（or.md 系统公理二） |
| **覆盖 FR** | or.md 系统公理二（L0 入口） |
| **依赖 Story** | Story 1.15a（提供 L1 显式确认压缩）、Story 1.4（提供 L1 Redis）、Story 1.5（提供 L2 PostgreSQL） |
| **前置条件** | L1 显式确认压缩已实现、L1 Redis 缓存层已实现、L2 PostgreSQL 表结构已定义 |
| **后续 Story** | Story 6.3（Checkpoint 快照创建 - L3 压缩触发） |
| **覆盖率要求** | 架构层≥85%，集成测试≥75% |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成
2. [x] All acceptance criteria specified 所有验收标准已定义
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [x] Sprint status synced to `ready-for-dev`
6. [x] 测试隔离约束显式强调
7. [x] 六层存储架构已明确
8. [x] L0 截断策略已明确（按写入顺序）
9. [x] XDG 路径规范已添加
10. [x] L3/L4/L5 依赖已标注
11. [x] AC-5 职责已聚焦（触发索引/缓存协同）
12. [x] 集成测试策略已明确

---

## 📚 相关文档 Related Documents

| 文档 | 说明 |
|------|------|
| [SDD+TDD 融合开发模式指南](./sdd-tdd-fusion-guide.md) | 开发模式详细说明与各层测试模板 |
| [SDD+TDD 实施检查清单](./sdd-tdd-checklist.md) | 实施步骤检查 |
| [or.md 系统公理二](../planning-artifacts/or.md) | 系统公理定义 |
| [Story 1.15a: 外部化记忆 - L1 显式确认压缩](./1-15a-externalized-memory-context-compression.md) | 前置 Story |
| [Story 6.3: Checkpoint 快照创建](../planning-artifacts/) | L3 压缩触发 Story（待创建） |
| [架构文档 - 六层存储架构](../../_bmad-output/planning-artifacts/architecture.md#112-存储架构设计) | 存储架构设计 |

---

**模板版本/Template Version:** 2.12.0
**创建日期/Created:** 2026-04-26
**最后更新/Last Updated:** 2026-04-26
**更新说明:**
- v2.12.0: 修正 L1-L5 为必选层（不是可选），添加 L3/L4/L5 存储适配器定义，更新测试策略为真实服务测试
- v2.11.0: 修复审查问题：(1) 截断策略明确为"按写入顺序"；(2) 添加 XDG 路径规范；(3) L3/L4/L5 标注依赖 Story；(4) AC-5 聚焦索引协同和缓存管理；(5) 添加集成测试策略说明；(6) 更新追溯矩阵
- v2.10.0: 初始版本 - Story 1.15b L0 入口 + 六层存储协同实现，基于 Story 1.15a 和架构文档创建
