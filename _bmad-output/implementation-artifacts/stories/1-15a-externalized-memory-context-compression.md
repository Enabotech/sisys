# Story 1.15a: 外部化记忆 - L1 显式确认压缩实现

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 系统架构师,
**I want** 实现 L1 显式确认压缩机制（用户主动说"记住..."）,
**So that** 用户主动记忆得到持久化，上下文压缩率≥70%。

### 业务价值

本 Story 是 Epic 1（企业级架构基础与合规）价值组 5（or.md 系统公理实现）的第四个故事，在 Story 1.14a/b/c（trigger→route→execute）完成后实现外部化记忆机制。核心价值：

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **L1 显式确认压缩** | 用户主动记忆得到持久化，上下文压缩率≥70% | 压缩率≥70%（允许误差 -5%） |
| **双层存储写入** | L0 文件系统 + L2 PostgreSQL 协同存储 | 记忆保存成功率 100% |
| **事件驱动同步** | MemoryChanged 事件触发元数据同步和缓存失效 | 事件发布成功率 ≥99% |
| **四操作 CRUD** | 支持保存/删除/修改/查询四种记忆操作 | 所有操作测试通过 |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 1: 企业级架构基础与合规，价值组 5: or.md 系统公理实现，Story 1.15a

**or.md 公理追溯:** 系统公理二（外部化记忆：LLM 上下文=缓存，磁盘记忆=真相源），覆盖"公理二 L1 显式确认压缩"

**前置依赖:** Story 1.4（提供 L1 Redis）、Story 1.5（提供 L2 PostgreSQL 基础表结构）

**后续依赖:** Story 1.15b（外部化记忆 - L0 入口 + 六层存储协同）、Story 6.3（Checkpoint 快照创建 - L3 压缩触发）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: L1 压缩流程

**Given** 用户说"记住 X"（如"记住，以后用 bun 而不是 npm"）
**When** 用户主动记忆触发 L1 显式确认压缩
**Then** 执行步骤：
  1. MemoryService.save() 保存用户记忆
  2. 提取"以后用 bun 而不是 npm"作为记忆核心（≤500 字）
  3. 压缩 X 至 ~150 字（压缩率≥70%）
  4. 写入 ~/.sisys/memory/*.md（实际内容）
  5. 更新 MEMORY.md 索引
  6. MemoryChanged 事件发布（is_automatic=False）
**And** 记忆持久化至 L0 文件系统 + L2 PostgreSQL
**And** LLM 上下文仅保留压缩后的相关信息

**验证标准/Validation Criteria:**
- [ ] MemoryService 事件监听器注册（`src/domain/services/memory_service.py`）
- [ ] L1TextExtractor 文本提取器实现（`src/application/text_processing/l1_text_extractor.py`）
- [ ] L1Compressor 压缩器实现（`src/application/text_processing/l1_compressor.py`）
- [ ] 压缩率≥70%（用户输入≤500 字 → 压缩后≥150 字，允许误差 -5%）
- [ ] 压缩延迟 P95<20ms（测量方式：LLM 任务中采样 100 次）

### AC-2: 双层存储写入

**Given** L1 压缩完成
**When** 压缩后记忆准备写入
**Then** 同时写入 L0 文件系统和 L2 PostgreSQL
**And** L0 写入：~/.sisys/memory/*.md（实际内容）+ MEMORY.md 索引
**And** L2 异步写入：memory_metadata + memory_change_history

**验证标准/Validation Criteria:**
- [ ] FileMemoryAdapter 文件系统适配器（`src/infrastructure/storage/file_memory_adapter.py`）
- [ ] MemoryMetadataRepository L2 存储（`src/infrastructure/repositories/memory_metadata_repository.py`）
- [ ] MemoryChangeHistoryRepository L2 历史记录（`src/infrastructure/repositories/memory_change_history_repository.py`）
- [ ] L0 写入成功率 100%
- [ ] L2 异步写入成功率 ≥99%
- [ ] 记忆保存成功率 100%

### AC-3: MemoryChanged 事件发布

**Given** 记忆操作完成（保存/删除/修改）
**When** MemoryService 发布 MemoryChanged 事件
**Then** 事件携带 is_automatic=False
**And** 下游监听器触发：
  1. 写入 memory_metadata（UPSERT，version + 1）
  2. 写入 memory_change_history（append-only）
  3. 失效 L1 Redis 缓存（`redis.del("memory:user:{user_id}:{memory_name}")`）

**验证标准/Validation Criteria:**
- [ ] MemoryChanged 事件定义（`src/domain/events/memory_events.py`）
  - 遵循现有事件命名规范：`event_type: str = field(default="MemoryChanged", init=False)`
  - 实现 `__post_init__` 设置 aggregate_id 和 aggregate_type
  - 字段: event_id, memory_id, user_id, change_type, is_automatic, old_value, new_value, timestamp
  - change_type: create/update/delete
  - is_automatic=False（标识用户主动操作）
- [ ] MemoryChangedListener 下游监听器（`src/interfaces/event_listeners/memory_changed_listener.py`）
- [ ] 事务发件箱模式（MemoryChanged 事件与业务操作同事务提交）
  - 复用现有 `OutboxEntity`（`src/infrastructure/entities/outbox.py`）- 遵循 Story 1.3 方案 A 彻底隔离
  - 字段: id, event_id, event_type, payload, status, created_at, published_at, retry_count, max_retries, error_message
  - status: pending → published / failed
  - 后台处理器: 复用 `AsyncOutboxPoller`（`src/infrastructure/events/async_outbox_poller.py`）
  - **重要**：领域层通过 `OutboxRepository` 接口（`src/domain/repositories/outbox.py`）操作，不直接引用 OutboxEntity
- [ ] 事件发布成功率 ≥99%
- [ ] L1 Redis 缓存 key 格式: `memory:user:{user_id}:{memory_name}`

### AC-4: L1 四种操作 CRUD

**Given** 用户记忆系统
**When** 用户发起不同类型的记忆操作
**Then** 支持四种操作：
  - 保存（记住 X）：创建新记忆
  - 删除（不要记住 X）：删除已有记忆
  - 修改（改成 X）：更新已有记忆
  - 查询（你记得什么）：列出用户所有记忆

**验证标准/Validation Criteria:**
- [ ] MemoryService.save() 保存操作
- [ ] MemoryService.delete() 删除操作
- [ ] MemoryService.update() 修改操作
- [ ] MemoryService.list() 查询操作
- [ ] 所有 CRUD 操作通过 MemoryChanged 事件同步
- [ ] 版本冲突处理（乐观锁，version + 1 on update）
  - 检测到冲突后：重试最多 3 次，每次重新读取最新 version
  - 3 次仍冲突：抛出 `MemoryVersionConflictError`

### AC-5: 性能要求

**Given** 用户说"记住 X"触发压缩
**When** L1 压缩流程执行
**Then** 压缩率≥70%（用户输入≤500 字 → 压缩后≥150 字，允许误差 -5%）
**And** 压缩延迟 P95<20ms
**And** 记忆保存成功率 100%

**验证标准/Validation Criteria:**
- [ ] 压缩率测试（`test_compression_ratio`）- 使用 mock LLM 返回固定压缩结果
- [ ] 压缩延迟 P95<20ms（使用 `pytest-benchmark` 测量，1000 次采样；CI 环境使用 mock跳过）
- [ ] 记忆保存成功率 100%（1000 次连续保存测试；CI 环境使用 mock LLM）

### AC-6: L1 vs L3 分离

**Given** 外部化记忆系统
**When** 记忆触发条件不同时
**Then** L1 和 L3 有明确分离：
  - L1（本 Story）：用户主动触发（"记住..."），轻量级压缩（≤500字→~150字）
  - L3（Epic 6/Story 6.3）：Checkpoint 自动触发，重量级压缩（~50K tokens→~2K tokens）
**And** L1 无需 PersistentNote，直接压缩
**And** L3 需要 PersistentNoteTaker 生成 note_id/entities/summary/lineage

**验证标准/Validation Criteria:**
- [ ] L1Compressor 仅处理轻量级压缩（≤500 字输入）
- [ ] L1 操作无 PersistentNote 依赖
- [ ] L3 压缩逻辑不在本 Story 范围内（由 Story 6.3 实现）
- [ ] 架构文档明确区分 L1/L2/L3 触发机制

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] MemoryChanged 事件定义（`src/domain/events/memory_events.py`）
  - **命名规范**：遵循现有事件模式
    - `event_type: str = field(default="MemoryChanged", init=False)` — 事件类型字段
    - 实现 `__post_init__` 设置 aggregate_id 和 aggregate_type（如 `object.__setattr__(self, "aggregate_id", self.memory_id)`）
  - 字段: event_id, memory_id, user_id, change_type, is_automatic, old_value, new_value, timestamp
  - change_type: create/update/delete
  - is_automatic=False（标识用户主动操作）
- [ ] MemoryChangedListener 下游监听器接口（`src/interfaces/event_listeners/memory_changed_listener.py`）

#### 数据模型 (Data Models)
- [ ] MemoryMetadata 实体（`src/domain/entities/memory_metadata.py`）
  - 字段: id (UUID), name, description, type, path, version, mtime, created_at, updated_at
  - name: VARCHAR(255)，唯一约束
  - type: `user` | `feedback` | `project` | `reference`
  - path: `{type}/{memory_id}.md`（相对于 base_path，如 `feedback/bun-npm.md`）
  - version 字段用于乐观锁（version + 1 on update）
- [ ] MemoryChangeHistory 实体（`src/domain/entities/memory_change_history.py`）
  - 字段: id (UUID), memory_name, version, changed_at, changed_by, change_type, changed_fields (JSONB), diff_summary, archived_ref
  - append-only（历史记录不可删除/修改，但 delete 操作本身会作为新条目记录，change_type='delete'）
  - changed_fields: `{"name": ["旧值", "新值"], ...}`（JSONB 格式）
  - diff_summary: 变更摘要，如 `"name: foo -> bar"`
  - archived_ref: L4 归档引用（可选）
- [ ] MemoryService 服务类（`src/domain/services/memory_service.py`）
  - 方法: save(), delete(), update(), list()
  - 职责: 接收用户记忆请求、协调压缩（通过协议注入）、双层写入、发布 MemoryChanged 事件
  - **依赖倒置**: 通过 TextExtractorProtocol 和 CompressorProtocol 注入压缩逻辑，不直接依赖 application 层
  - **事件发布**: 通过 EventPublisherProtocol 注入（如 `EventPublisherProtocol | None = None`）

#### L1 压缩处理 (L1 Compression)
- [ ] **协议定义（领域层）**:
  - TextExtractorProtocol（`src/domain/services/text_extractor_protocol.py`）- 文本提取接口
  - CompressorProtocol（`src/domain/services/compressor_protocol.py`）- 压缩接口
  - 使用 Protocol 实现依赖倒置（复用 TriggerService 模式）
- [ ] L1TextExtractor 文本提取器（`src/application/text_processing/l1_text_extractor.py`）
  - 实现 TextExtractorProtocol
  - 从"记住 X"中提取 X 作为记忆核心内容
  - 输入限制: ≤500 字
  - **支持模式**:
    - "记住 X" → 提取 X
    - "记住了 X" → 提取 X
    - "以后用 X" → 提取 X
    - "要记住 X" → 提取 X
    - "别忘了 X" → 提取 X
    - "改成 X" → 提取 X（用于修改操作）
    - "不要记住 X" → 触发删除操作
  - **提取策略**: 正则优先 + LLM fallback（边界情况如"记住abc"无空格）
- [ ] L1Compressor 压缩器（`src/application/text_processing/l1_compressor.py`）
  - 实现 CompressorProtocol
  - 轻量级压缩: X → ~150 字（压缩率≥70%）
  - 目标: 保留核心语义，去除冗余

#### 存储适配器 (Storage Adapters)
- [ ] FileMemoryAdapter L0 文件系统适配器（`src/infrastructure/storage/file_memory_adapter.py`）
  - **路径优先级**:
    1. `$XDG_CONFIG_HOME/sisys/memory/`（若 XDG_CONFIG_HOME 已设置）
    2. `$HOME/.config/sisys/memory/`（XDG 默认路径）
    3. `$HOME/.sisys/memory/`（向后兼容旧版本）
  - **目录结构**: `{base_path}/{type}/{memory_id}.md`
    - type: `user/` | `feedback/` | `project/` | `reference/`（类型隔离文件夹）
    - memory_id: UUID v4 格式（如 `550e8400-e29b-41d4-a716-446655440000.md`）
    - **设计原理**: 类型文件夹隔离语义，memory_id (UUID) 保证唯一性（避免冲突），符合架构 §11.2.2 描述
  - **MD 文件内容模板**:
    ```yaml
    ---
    name: {语义名称（≤6 英文单词，'-'分割，如 feedback-poetry-env）}
    description: {一句话描述（≤50 字，用作 MEMORY.md hook）}
    type: {user|feedback|project|reference}
    originSessionId: {UUID}
    ---
    {完整记忆内容（用户输入的原始或压缩后内容，不超过 200 行）}
    ```
  - **MEMORY.md 索引**:
    - 位置: `{base_path}/MEMORY.md`
    - 格式: `- [{name}]({type}/{memory_id}.md) — {description}`
    - name: ≤6 英文单词，`-` 分割（如 `feedback-poetry-env`）
    - description: ≤50 字
    - 截断策略: 超过 200 行时保留最新 200 行
    - 更新时机: 每次 save/update/delete 后更新索引
    - 一致性保证: 读取时从文件加载，索引仅用于快速扫描
  - **多租户隔离**: private 记忆存储于 `{base_path}/private/{type}/`，group 记忆存储于 `{base_path}/group/{type}/`
- [ ] MemoryMetadataRepository L2 PostgreSQL 仓储（`src/infrastructure/repositories/memory_metadata_repository.py`）
- [ ] MemoryChangeHistoryRepository L2 历史记录仓储（`src/infrastructure/repositories/memory_change_history_repository.py`）

#### 配置模型 (Configuration Models)
- [ ] MemoryConfig 配置（`src/infrastructure/config/memory.py`）
  - 环境变量: `MEMORY_L0_PATH`（默认 ~/.sisys/memory）、`MEMORY_L1_CACHE_TTL`、`COMPRESSION_MIN_RATIO`
  - 从环境变量读取（`from_env()` 方法，复用 OtelConfig 模式）

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_story_1.15a.feature`（由 Dev agent 在 Task 0 创建）
- [ ] 覆盖场景:
  - L1 压缩流程（记住 X → 压缩 → 写入 L0 + L2）
  - 四种操作 CRUD（保存/删除/修改/查询）
  - MemoryChanged 事件发布（is_automatic=False）
  - 双层存储一致性
  - 压缩率≥70%
  - L1 vs L3 分离验证

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
| **TDD 单元测试** | L1TextExtractor | 文本提取 | `test_l1_text_extractor.py` | Task 1 |
| **TDD 单元测试** | L1Compressor | 压缩率 | `test_l1_compressor.py` | Task 1 |
| **TDD 单元测试** | MemoryService | CRUD 操作 | `test_memory_service.py` | Task 1 |
| **TDD 单元测试** | FileMemoryAdapter | L0 写入 | `test_file_memory_adapter.py` | Task 2 |
| **TDD 单元测试** | MemoryMetadataRepository | L2 存储 | `test_memory_metadata_repository.py` | Task 2 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_story_1.15a.feature` | Task 0 |
| **SDD 架构验证** | L1/L3 分离 | 六边形架构约束 | `test_memory_architecture.py` | Task 3 |
| **集成测试** | 事件总线 | 端到端 L1 压缩流程 | `test_compression_integration.py` | Task 3 |

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
| AC-1 | L1 压缩流程 | Task 1 | Subtask 1.1-1.3（L1TextExtractor 红→绿→重构） | `test_l1_text_extractor.py` |
| AC-1 | L1Compressor 压缩器 | Task 1 | Subtask 1.4-1.6（L1Compressor 红→绿→重构） | `test_l1_compressor.py` |
| AC-1 | MemoryService CRUD | Task 1 | Subtask 1.7-1.9（MemoryService 红→绿→重构） | `test_memory_service.py` |
| AC-2 | 双层存储写入 | Task 2 | Subtask 2.1-2.3（FileMemoryAdapter 红→绿→重构） | `test_file_memory_adapter.py` |
| AC-2 | L2 PostgreSQL 存储 | Task 2 | Subtask 2.4-2.6（MemoryMetadataRepository 红→绿→重构） | `test_memory_metadata_repository.py` |
| AC-3 | MemoryChanged 事件 | Task 2 | Subtask 2.7-2.9（MemoryChanged 事件 红→绿→重构） | `test_memory_events.py` |
| AC-4 | 四种操作 CRUD | Task 1 | Subtask 1.7-1.9（MemoryService 红→绿→重构） | `test_memory_service.py` |
| AC-5 | 性能要求 | Task 3 | Subtask 3.1-3.3（性能基准测试 红→绿→重构） | `test_compression_performance.py` |
| AC-6 | L1 vs L3 分离 | Task 3 | Subtask 3.4-3.6（六边形架构验证 红→绿→重构） | `test_memory_architecture.py` |

---

## 📋 Tasks / Subtasks 任务分解

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5, AC-6

> **目的：** 在进入代码实现前，明确 Schema、API 契约、验收标准。

- [ ] Subtask 0.1: 定义 MemoryChanged 事件 Schema（`src/domain/events/memory_events.py`）
- [ ] Subtask 0.2: 定义 MemoryMetadata 实体（`src/domain/entities/memory_metadata.py`）
- [ ] Subtask 0.3: 定义 MemoryChangeHistory 实体（`src/domain/entities/memory_change_history.py`）
- [ ] Subtask 0.4: 定义 MemoryService 服务接口（`src/domain/services/memory_service.py`）
- [ ] Subtask 0.5: 定义 L1TextExtractor 文本提取器（`src/application/text_processing/l1_text_extractor.py`）
- [ ] Subtask 0.6: 定义 L1Compressor 压缩器（`src/application/text_processing/l1_compressor.py`）
- [ ] Subtask 0.7: 定义 FileMemoryAdapter L0 文件系统适配器（`src/infrastructure/storage/file_memory_adapter.py`）
- [ ] Subtask 0.8: 定义 MemoryMetadataRepository L2 仓储（`src/infrastructure/repositories/memory_metadata_repository.py`）
- [ ] Subtask 0.9: 定义 MemoryChangeHistoryRepository L2 历史记录仓储（`src/infrastructure/repositories/memory_change_history_repository.py`）
- [ ] Subtask 0.10: 定义 MemoryConfig 配置模型（`src/infrastructure/config/memory.py`）
- [ ] Subtask 0.11: 编写 Gherkin 验收测试 `tests/acceptance/test_story_1.15a.feature`（Dev agent 创建）
- [ ] Subtask 0.12: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: L1 压缩流程与 CRUD 操作

**关联 AC:** AC-1, AC-4

> **职责边界:** Task 1 负责 L1TextExtractor（文本提取）、L1Compressor（压缩）、MemoryService（CRUD）

#### TDD 循环 [A]：L1TextExtractor 文本提取

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/text_processing/test_l1_text_extractor.py`（验证"记住 X"提取） |
| 🟢 绿 | 实现 `src/application/text_processing/l1_text_extractor.py` - L1TextExtractor |
| 🔄 重构 | 优化提取逻辑，支持多种表达方式 |

- [ ] Subtask 1.1: 🔴 红 — 编写 L1TextExtractor 失败测试
- [ ] Subtask 1.2: 🟢 绿 — 实现 L1TextExtractor（从"记住 X"中提取 X）
- [ ] Subtask 1.3: 🔄 重构 — 优化提取逻辑

#### TDD 循环 [B]：L1Compressor 压缩器

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/text_processing/test_l1_compressor.py`（验证压缩率≥70%） |
| 🟢 绿 | 实现 `src/application/text_processing/l1_compressor.py` - L1Compressor |
| 🔄 重构 | 优化压缩算法，验证压缩率稳定性 |

- [ ] Subtask 1.4: 🔴 红 — 编写 L1Compressor 失败测试
- [ ] Subtask 1.5: 🟢 绿 — 实现 L1Compressor（压缩率≥70%）
- [ ] Subtask 1.6: 🔄 重构 — 验证压缩率稳定性

#### TDD 循环 [C]：MemoryService CRUD

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/services/test_memory_service.py`（验证 save/delete/update/list） |
| 🟢 绿 | 实现 `src/domain/services/memory_service.py` - MemoryService |
| 🔄 重构 | 优化事件发布逻辑，添加版本冲突处理 |

- [ ] Subtask 1.7: 🔴 红 — 编写 MemoryService 失败测试
- [ ] Subtask 1.8: 🟢 绿 — 实现 MemoryService（save/delete/update/list）
- [ ] Subtask 1.9: 🔄 重构 — 添加版本冲突处理（乐观锁）

**完成标准/Definition of Done:**
- [ ] L1TextExtractor 实现完成
- [ ] L1Compressor 实现完成（压缩率≥70%）
- [ ] MemoryService 实现完成（四种 CRUD 操作）
- [ ] TDD 循环全部通过

---

### Task 2: 双层存储写入与事件发布

**关联 AC:** AC-2, AC-3

> **职责边界:** Task 2 负责 FileMemoryAdapter（L0 文件系统）、MemoryMetadataRepository（L2 PostgreSQL）、MemoryChanged 事件

#### TDD 循环 [A]：FileMemoryAdapter L0 文件系统

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/storage/test_file_memory_adapter.py`（验证 ~/.sisys/memory 写入） |
| 🟢 绿 | 实现 `src/infrastructure/storage/file_memory_adapter.py` - FileMemoryAdapter |
| 🔄 重构 | 优化文件操作，添加错误处理 |

- [ ] Subtask 2.1: 🔴 红 — 编写 FileMemoryAdapter 失败测试
- [ ] Subtask 2.2: 🟢 绿 — 实现 FileMemoryAdapter（~/.sisys/memory/*.md 写入）
- [ ] Subtask 2.3: 🔄 重构 — 优化文件操作

#### TDD 循环 [B]：MemoryMetadataRepository L2 存储

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/repositories/test_memory_metadata_repository.py`（验证 L2 存储） |
| 🟢 绿 | 实现 `src/infrastructure/repositories/memory_metadata_repository.py` - MemoryMetadataRepository |
| 🔄 重构 | 添加 UPSERT 和版本冲突处理 |

- [ ] Subtask 2.4: 🔴 红 — 编写 MemoryMetadataRepository 失败测试
- [ ] Subtask 2.5: 🟢 绿 — 实现 MemoryMetadataRepository（L2 PostgreSQL）
- [ ] Subtask 2.6: 🔄 重构 — 验证 UPSERT 和版本冲突处理

#### TDD 循环 [C]：MemoryChanged 事件

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/events/test_memory_events.py`（验证 MemoryChanged 事件 Schema） |
| 🟢 绿 | 实现 `src/domain/events/memory_events.py` - MemoryChanged 事件 |
| 🔄 重构 | 验证事件继承和子事件类型 |

- [ ] Subtask 2.7: 🔴 红 — 编写 MemoryChanged 事件失败测试
- [ ] Subtask 2.8: 🟢 绿 — 实现 MemoryChanged 事件 Schema
- [ ] Subtask 2.9: 🔄 重构 — 验证事件发布逻辑

**完成标准/Definition of Done:**
- [ ] FileMemoryAdapter 实现完成
- [ ] MemoryMetadataRepository 实现完成
- [ ] MemoryChangeHistoryRepository 实现完成
- [ ] MemoryChanged 事件定义完成
- [ ] L0 + L2 双层存储一致性验证
- [ ] TDD 循环全部通过

---

### Task 3: 架构验证与性能基准

**关联 AC:** AC-5, AC-6

> **职责边界:** Task 3 负责性能基准测试（L1 压缩率≥70%、压缩延迟 P95<20ms）和六边形架构验证（L1/L3 分离）

#### TDD 循环 [A]：性能基准测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/performance/test_compression_performance.py`（验证性能要求，使用 pytest-benchmark） |
| 🟢 绿 | 实现性能优化（压缩算法优化、并行写入） |
| 🔄 重构 | 性能调优 |

- [ ] Subtask 3.1: 🔴 红 — 编写性能基准失败测试
  - 压缩率测试（`test_compression_ratio`）
  - 压缩延迟测试（`test_compression_latency`）
  - 记忆保存成功率测试（`test_save_success_rate`）
- [ ] Subtask 3.2: 🟢 绿 — 实现性能优化
  - LLM 压缩调用优化（批量压缩、缓存压缩结果）
  - 异步写入优化（aiofiles 异步文件操作）
- [ ] Subtask 3.3: 🔄 重构 — 性能调优
  - 运行 `pytest-benchmark --compare` 对比优化前后性能
  - 确认 P95 延迟达标

#### TDD 循环 [B]：六边形架构验证（L1/L3 分离）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/architecture/test_memory_architecture.py`（验证架构约束） |
| 🟢 绿 | 实现架构验证逻辑（L1/L3 分离检测、依赖方向检测） |
| 🔄 重构 | 优化架构验证器 |

- [ ] Subtask 3.4: 🔴 红 — 编写架构验证失败测试
- [ ] Subtask 3.5: 🟢 绿 — 实现架构验证逻辑
- [ ] Subtask 3.6: 🔄 重构 — 验证器优化

#### 集成测试

- [ ] Subtask 3.7: 创建 `tests/integration/test_compression_integration.py`（端到端 L1 压缩流程）

**完成标准/Definition of Done:**
- [ ] 压缩率≥70%（允许误差 -5%）
- [ ] 压缩延迟 P95<20ms
- [ ] 记忆保存成功率 100%
- [ ] L1 vs L3 分离验证通过
- [ ] 六边形架构验证通过
- [ ] 集成测试通过

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（端口与适配器）、事件驱动架构
- **系统公理二:** 外部化记忆（LLM 上下文=缓存，磁盘记忆=真相源）
  - L1 显式确认：轻量级压缩（≤500字→~150字），无需 PersistentNote
  - L3 Checkpoint：重量级压缩（~50K tokens→~2K tokens），需要 PersistentNoteTaker
  - 压缩前必须持久化，防止信息丢失
  - 上下文压缩率目标：≥70%
- **三层触发机制:**
  - L1（本 Story）：用户主动（"记住..."），写入 L0 + L2
  - L2（V2）：系统建议+用户确认，写入 L0 草稿
  - L3（Epic 6/Story 6.3）：Checkpoint 自动触发，写入 StrategicArchive
- **设计约束:**
  - 领域层零依赖外部框架
  - 依赖倒置：领域层定义接口，基础设施层实现
  - 事件总线双通道：Redis PubSub（实时）、RabbitMQ（持久化）
- **技术栈:**
  - Python 3.11+
  - L0 文件系统：~/.sisys/memory/*.md
  - L1 Redis：会话状态缓存（Story 1.4 已实现）
  - L2 PostgreSQL：memory_metadata + memory_change_history（Story 1.5 已实现）
  - 压缩延迟目标：P95<20ms

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) - ADR 相关决策

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **MemoryService 位于领域层** | 符合六边形架构，领域逻辑与技术解耦 | 需要依赖倒置 | ✅ 9/10 |
| MemoryService 位于应用层 | 实现简单 | 领域逻辑泄漏 | 6/10 |
| MemoryService 位于基础设施层 | 实现最简单 | 违反六边形架构 | 3/10 |

**决策**: MemoryService 位于**领域层**，通过仓储接口访问存储实现。

### ADR: L1 压缩技术选型决策

**问题**: L1 压缩使用 LLM 还是规则压缩？

| 评估维度 | LLM 压缩 | 规则压缩（正则/模板） | 混合压缩 |
|---------|---------|---------------------|---------|
| 压缩质量 | 高（保留语义） | 中（仅去除冗余） | 高 |
| 延迟 | 高（P95>100ms） | 低（P95<5ms） | 中 |
| 成本 | 高（LLM API 调用） | 低（本地计算） | 中 |
| **采用** | ❌ 不采用 | ❌ 不采用 | ✅ **MVP 采用** |

**决策**: MVP 使用**混合压缩**：
1. 第一步：规则压缩（正则去除停用词、重复空格等，P95<5ms）
2. 第二步：判断规则压缩后内容长度
   - 若 ≤200 字：直接使用规则压缩结果（无需 LLM）
   - 若 >200 字：LLM 压缩至 ~150 字（P95<20ms）
3. 目标：整体压缩率≥70%，延迟 P95<20ms
4. **LLM 压缩提示词**（必须严格遵守）:
   ```
   system: "你是一个文本压缩助手。请将以下内容压缩至约150字，保留核心语义，去除冗余描述。"
   user: "{原始文本}"
   ```

**LLM 压缩优化**（若 Story 1.17 未完成，则使用 LiteLLM 默认配置）:
- 使用 LiteLLM 统一接口（依赖 Story 1.17 UDMR 路由完成后）
- 压缩结果缓存（相同内容不重复压缩）
- 批量压缩（多条记忆一次 LLM 调用）

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

### L1 vs L3 分离澄清

> ⚠️ **重要澄清**：L1 和 L3 是完全不同的压缩机制，必须严格分离！

**L1 显式确认（本 Story）:**
- **触发**: 用户主动说"记住..."、"以后用 X"
- **输入**: 轻量级内容（≤500 字）
- **压缩**: 轻量级压缩（~150 字，压缩率≥70%）
- **实现**: L1TextExtractor + L1Compressor
- **依赖**: 无需 PersistentNote

**L3 Checkpoint 压缩（Epic 6/Story 6.3）:**
- **触发**: Checkpoint 创建时自动触发
- **输入**: 重量级内容（~50K tokens）
- **压缩**: 重量级压缩（~2K tokens，压缩率≥96%）
- **实现**: PersistentNoteTaker + LLMContextCompressor
- **依赖**: 需要 PersistentNoteTaker 生成 note_id/entities/summary/lineage

**关键区别**:

| 维度 | L1（本 Story） | L3（Story 6.3） |
|------|---------------|----------------|
| 触发方式 | 用户主动 | 系统自动 |
| 输入规模 | ≤500 字 | ~50K tokens |
| 输出规模 | ~150 字 | ~2K tokens |
| 压缩率目标 | ≥70% | ≥96% |
| PersistentNote | 不需要 | 需要 |
| 实施 Story | Story 1.15a | Story 6.3 |

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── domain/
│   │   ├── events/
│   │   │   └── memory_events.py      # MemoryChanged 事件（新实现）
│   │   ├── entities/
│   │   │   ├── memory_metadata.py   # MemoryMetadata 实体（新实现）
│   │   │   └── memory_change_history.py # MemoryChangeHistory 实体（新实现）
│   │   ├── services/
│   │   │   └── memory_service.py     # MemoryService（核心逻辑）
│   │   └── repositories/
│   │       └── memory_repository.py # MemoryRepository 接口（领域层定义）
│   ├── application/
│   │   └── text_processing/
│   │       ├── l1_text_extractor.py # L1TextExtractor 文本提取器（新实现）
│   │       └── l1_compressor.py     # L1Compressor 压缩器（新实现）
│   ├── infrastructure/
│   │   ├── config/
│   │   │   └── memory.py            # MemoryConfig 配置（新实现）
│   │   ├── storage/
│   │   │   └── file_memory_adapter.py # FileMemoryAdapter L0 文件系统（新实现）
│   │   └── repositories/
│   │       ├── memory_metadata_repository.py # MemoryMetadataRepository L2（新实现）
│   │       └── memory_change_history_repository.py # MemoryChangeHistoryRepository L2（新实现）
│   └── interfaces/
│       └── event_listeners/
│           └── memory_changed_listener.py # MemoryChangedListener 下游监听器
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   │   ├── services/
│   │   │   │   └── test_memory_service.py
│   │   │   └── events/
│   │   │       └── test_memory_events.py
│   │   ├── application/
│   │   │   └── text_processing/
│   │   │       ├── test_l1_text_extractor.py
│   │   │       └── test_l1_compressor.py
│   │   ├── infrastructure/
│   │   │   ├── storage/
│   │   │   │   └── test_file_memory_adapter.py
│   │   │   └── repositories/
│   │   │       ├── test_memory_metadata_repository.py
│   │   │       └── test_memory_change_history_repository.py
│   │   ├── architecture/
│   │   │   └── test_memory_architecture.py
│   │   └── performance/
│   │       └── test_compression_performance.py
│   ├── integration/
│   │   └── test_compression_integration.py
│   └── acceptance/
│       ├── test_story_1.15a.feature
│       └── test_story_1.15a_steps.py
└── docs/
    └── developer/
        └── externalized_memory_guide.md    # 外部化记忆实施指南
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 1.14c: 自主调用循环 - execute](./1-14c-autonomous-invocation-execute.md)

**关键学习/Key Learnings:**
1. **配置模式复用** — OtelConfig.from_env() 模式应复用，MemoryConfig 采用相同 `from_env()` 类方法
2. **事件驱动解耦** — ExecuteService 仅负责执行，不处理 route 逻辑；MemoryService 应遵循相同模式
3. **六边形架构严格遵守** — Task 3 必须包含架构验证测试，确保 L1/L3 分离
4. **性能基准测试** — execute 性能要求 P95<100ms/50ms，L1 压缩 P95<20ms，需独立基准测试
5. **测试隔离约束显式强调** — asyncio.Lock 类变量、pytest-asyncio auto mode 规则必须在 Story 中明确

**本故事修正/Story Corrections:**
> 以下问题已在本次审查中修正：

6. **L1 vs L3 分离澄清** — L1 是轻量级压缩（≤500字→~150字），L3 是重量级压缩（~50K tokens→~2K tokens）
7. **MemoryChanged 事件 is_automatic=False** — 明确标识用户主动操作
8. **双层存储异步写入** — L0 同步写入优先，L2 异步写入通过事务发件箱模式
9. **混合压缩技术选型** — 规则压缩 + LLM 压缩混合，目标压缩率≥70%，延迟 P95<20ms

**应用到本故事/Applied to This Story:**
- [x] MemoryConfig 采用与 OtelConfig 相同的 `from_env()` 模式
- [x] MemoryService 仅负责记忆 CRUD，不处理 L3 压缩逻辑
- [x] Task 3 包含架构验证测试（L1/L3 分离检测）
- [x] 性能基准测试验证压缩率≥70%、压缩延迟 P95<20ms（CI 使用 mock）
- [x] 测试隔离约束显式强调（asyncio.Lock/pytest-asyncio）
- [x] MemoryChanged 事件 is_automatic=False 标识用户主动操作
- [x] 双层存储异步写入（L0 同步 + L2 异步）
- [x] Redis 缓存 key 格式统一为 `memory:user:{user_id}:{memory_name}`
- [x] XDG 路径规范正确实现（$XDG_CONFIG_HOME > $HOME/.config > $HOME/.sisys）
- [x] 混合压缩边界条件明确（≤200字直接规则压缩，>200字 LLM 压缩）
- [x] LLM 压缩提示词已定义
- [x] 版本冲突重试策略明确（3次重试后抛异常）

### Git Intelligence Summary

**来源:** `git log` - 最近 5 个提交

| 提交 | 主题 | 关键模式 |
|------|------|---------|
| `c02aef1` | build: automatic update of sisys-app-dev | 自动化构建 |
| `944d33f` | fix: auth.py refresh_token endpoint uses Form() | 表单解析修复 |
| `b982e6a` | build: automatic update of sisys-app-dev | 自动化构建 |
| `dce3ffa` | build: automatic update of sisys-app-dev | 自动化构建 |
| `6a2c23d` | update | - |

**可应用模式:**
1. **六边形架构严格分层** — domain/infrastructure/application 层严格分离
2. **配置与实现分离** — Config 类与实现类分离
3. **事件驱动解耦** — 通过事件总线通信，不直接调用
4. **测试隔离模式** — UUID 前缀隔离资源，pytest-asyncio auto mode

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
|--------|-----|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Instructions** | `_bmad/bmm/workflows/4-implementation/create-story/instructions.xml` |
| **Template** | `_bmad/bmm/workflows/4-implementation/create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/1-14c-autonomous-invocation-execute.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [ ] 故事需求从 `epics_v1.0.md` 提取
- [ ] 架构约束从 `architecture.md` 提取
- [ ] or.md 系统公理二（L1 显式确认）追溯完成
- [ ] 状态设置为 `ready-for-dev`
- [ ] SDD+TDD 融合开发要求定义完成
- [ ] 项目结构对齐统一规范
- [ ] 前一个故事学习经验已整合
- [ ] L1 vs L3 分离关系已澄清
- [ ] 测试隔离约束显式强调（asyncio.Lock/pytest-asyncio）
- [ ] 性能基准测试方法明确（pytest-benchmark）
- [ ] 混合压缩技术选型明确（规则压缩 + LLM 压缩）

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/1-15a-externalized-memory-context-compression.md`
- `src/domain/events/memory_events.py` - MemoryChanged 事件
- `src/domain/entities/memory_metadata.py` - MemoryMetadata 实体
- `src/domain/entities/memory_change_history.py` - MemoryChangeHistory 实体
- `src/domain/services/memory_service.py` - MemoryService
- `src/domain/repositories/memory_repository.py` - MemoryRepository 接口（领域层定义）
- `src/domain/services/text_extractor_protocol.py` - TextExtractorProtocol（文本提取接口，用于依赖倒置）
- `src/domain/services/compressor_protocol.py` - CompressorProtocol（压缩接口，用于依赖倒置）
- `src/application/text_processing/l1_text_extractor.py` - L1TextExtractor
- `src/application/text_processing/l1_compressor.py` - L1Compressor
- `src/infrastructure/config/memory.py` - MemoryConfig
- `src/infrastructure/storage/file_memory_adapter.py` - FileMemoryAdapter
- `src/infrastructure/repositories/memory_metadata_repository.py` - MemoryMetadataRepository
- `src/infrastructure/repositories/memory_change_history_repository.py` - MemoryChangeHistoryRepository
- `src/interfaces/event_listeners/memory_changed_listener.py` - MemoryChangedListener
- `tests/unit/domain/services/test_memory_service.py` - MemoryService 单元测试
- `tests/unit/domain/events/test_memory_events.py` - MemoryChanged 事件单元测试
- `tests/unit/application/text_processing/test_l1_text_extractor.py` - L1TextExtractor 单元测试
- `tests/unit/application/text_processing/test_l1_compressor.py` - L1Compressor 单元测试
- `tests/unit/infrastructure/storage/test_file_memory_adapter.py` - FileMemoryAdapter 单元测试
- `tests/unit/infrastructure/repositories/test_memory_metadata_repository.py` - MemoryMetadataRepository 单元测试
- `tests/unit/architecture/test_memory_architecture.py` - 架构验证测试
- `tests/unit/performance/test_compression_performance.py` - 性能基准测试
- `tests/integration/test_compression_integration.py` - 集成测试
- `tests/acceptance/test_story_1.15a.feature` - Gherkin 验收测试（由 Dev agent 在 Task 0 创建）
- `tests/acceptance/test_story_1.15a_steps.py` - 验收测试步骤实现（由 Dev agent 在 Task 0 创建）
- `docs/developer/externalized_memory_guide.md` - 外部化记忆实施指南

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/infrastructure/repositories/memory_change_history_repository.py` - MemoryChangeHistoryRepository L2 历史记录仓储
- `tests/unit/infrastructure/repositories/test_memory_change_history_repository.py` - MemoryChangeHistoryRepository 单元测试

**更新的文件/Updated Files:**
- `src/domain/events/__init__.py` - 添加 MemoryChanged 事件导出
- `src/domain/entities/__init__.py` - 添加 MemoryMetadata, MemoryChangeHistory 导出
- `src/domain/services/__init__.py` - 添加 MemoryService, TextExtractorProtocol, CompressorProtocol 导出
- `src/domain/repositories/__init__.py` - 添加 MemoryRepository 导出
- `src/application/text_processing/__init__.py` - 添加 L1TextExtractor, L1Compressor 导出
- `src/infrastructure/config/__init__.py` - 添加 MemoryConfig 导出
- `src/infrastructure/storage/__init__.py` - 添加 FileMemoryAdapter 导出
- `src/infrastructure/repositories/__init__.py` - 添加 MemoryMetadataRepository, MemoryChangeHistoryRepository 导出
- `src/interfaces/event_listeners/__init__.py` - 添加 memory_changed_listener 导出

---

## 📚 Project Context Reference

> **来源:** [`project-context.md`](../../_bmad-output/project-context.md)

### 关键约束速查

| 约束类型 | 约束内容 | 来源 |
|---------|---------|------|
| **架构原则** | 六边形架构，领域层零依赖 | architecture.md §3.1 |
| **系统公理二** | 外部化记忆（LLM 上下文=缓存，磁盘记忆=真相源） | architecture.md §3.2 |
| **三层触发机制** | L1 用户主动/L2 系统建议/L3 Checkpoint 自动 | architecture.md §3.2 |
| **事件驱动** | 事务发件箱模式，事件处理幂等性 | architecture.md §3.3 |
| **测试覆盖率** | 架构层≥85%，集成测试≥75% | sdd-tdd-checklist.md §5 |
| **压缩延迟** | P95<20ms | epics_v1.0.md Story 1.15a |
| **压缩率** | ≥70%（允许误差 -5%） | epics_v1.0.md Story 1.15a |

### 关键路径依赖

```
Story 1.14a (trigger) → Story 1.14b (route) → Story 1.14c (execute)
                                                            ↓
                                          Story 1.15a (外部化记忆 - L1) ← 本 Story
                                                            ↓
                                          Story 1.15b (外部化记忆 - L0 入口)
                                                            ↓
                                          Story 6.3 (Checkpoint - L3 压缩)
```

### L1 压缩体系（来自 architecture.md §11.2.6）

| 层次 | 触发类型 | 触发条件 | 写入目标 | 版本 | 压缩率 |
|------|---------|---------|---------|------|-------|
| **L1 显式确认** | 用户主动 | 用户说"记住..." | L0 + L2 | MVP（本 Story） | ≥70% |
| **L2 语义建议** | 系统建议+用户确认 | 检测重复偏好 | L0 草稿 | V2 | - |
| **L3 压缩触发** | 系统自动 | Checkpoint 创建 | StrategicArchive | Epic 6/Story 6.3 | ≥96% |

### 六层存储架构（来自 architecture.md §8.2）

| 层级 | 技术 | 存储内容 | TTL | 相关 Story |
|------|------|---------|-----|-----------|
| **L0 记忆入口** | 文件系统 | MEMORY.md 索引、路由策略 | 永久 | Story 1.15b |
| **L1 高速缓存** | Redis | 会话状态、语义缓存、公共黑板、记忆缓存 | 24h-30d | Story 1.4 |
| **L2 关系存储** | PostgreSQL | memory_metadata、memory_change_history | 永久 | Story 1.5 |
| **L3 向量存储** | Qdrant | 嵌入向量、混合检索 payload | 永久 | Story 1.6 |
| **L4 对象存储** | MinIO | 原始文档、StrategicArchive | 7 年 | Story 1.7 |
| **L5 图存储** | Neo4j | 知识图谱、实体关系 | 永久 | Story 1.8 |

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 1.15a |
| **Story Key** | 1-15a-externalized-memory-context-compression |
| **File** | `_bmad-output/implementation-artifacts/stories/1-15a-externalized-memory-context-compression.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 1: 企业级架构基础与合规 |
| **价值组** | 价值组 5: or.md 系统公理实现 |
| **优先级** | P0-15a（or.md 系统公理二） |
| **覆盖 FR** | or.md 系统公理二（L1 显式确认压缩） |
| **依赖 Story** | Story 1.4（提供 L1 Redis）、Story 1.5（提供 L2 PostgreSQL 基础表结构） |
| **前置条件** | L1 Redis 缓存层已实现、 L2 PostgreSQL 表结构已定义 |
| **后续 Story** | Story 1.15b（外部化记忆 - L0 入口 + 六层存储协同）、Story 6.3（Checkpoint 快照创建） |
| **覆盖率要求** | 架构层≥85%，集成测试≥75% |

### 完成总结 Completion Summary

1. [ ] All tasks defined 所有任务定义完成
2. [ ] All acceptance criteria specified 所有验收标准已定义
3. [ ] Architecture constraints extracted 架构约束已提取
4. [ ] Previous story learnings integrated 前一个故事学习经验已整合
5. [ ] Sprint status synced to `ready-for-dev`
6. [ ] 测试隔离约束显式强调
7. [ ] 性能基准测试方法明确
8. [ ] L1 vs L3 分离关系已澄清

### 🔧 对抗性审查修复（Adversarial Review Fixes）

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有修复项。

| # | 问题 | 严重度 | 修复方案 | 状态 |
|---|------|--------|----------|------|
| 1 | L1 vs L3 分离不明确 | P1 | 添加"L1 vs L3 分离澄清"章节，明确区分两种压缩机制 | ✅ |
| 2 | MemoryChanged 事件 is_automatic 未明确 | P1 | 明确 MemoryChanged 事件 is_automatic=False 标识用户主动操作 | ✅ |
| 3 | Redis 缓存 key 格式不一致 | P1 | 统一为 `memory:user:{user_id}:{memory_name}` | ✅ |
| 4 | XDG 路径规范错误 | P1 | 修正为正确优先级：XDG_CONFIG_HOME > .config > .sisys | ✅ |
| 5 | 双层存储同步策略未明确 | P2 | 添加 ADR 存储同步策略决策，明确 L0 同步 + L2 异步 | ✅ |
| 6 | L1 压缩技术选型未明确 | P2 | 添加 ADR L1 压缩技术选型决策，明确混合压缩方案 | ✅ |
| 7 | 混合压缩边界条件未定义 | P2 | 明确 ≤200字直接规则压缩，>200字 LLM 压缩 | ✅ |
| 8 | LLM 压缩提示词缺失 | P2 | 添加具体 system prompt 定义 | ✅ |
| 9 | 文件清单重复 | P2 | 清理重复的 MemoryMetadataRepository 条目 | ✅ |
| 10 | MemoryChangeHistory append-only 矛盾 | P2 | 澄清 delete 操作记录为新条目，change_type='delete' | ✅ |
| 11 | 性能基准测试 CI 可行性 | P2 | 明确 CI 使用 mock LLM，跳过真实 API 调用 | ✅ |
| 12 | 版本冲突处理策略缺失 | P2 | 明确 3 次重试后抛出 MemoryVersionConflictError | ✅ |
| 13 | 事务发件箱实现细节缺失 | P2 | 添加发件箱表结构和后台处理器说明 | ✅ |
| 14 | 测试隔离约束未显式强调 | P2 | 添加"测试隔离约束"章节，明确 asyncio.Lock 类变量、pytest-asyncio auto mode 等规则 | ✅ |

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `validate-create-story` 质量检查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

## 📚 相关文档 Related Documents

| 文档 | 说明 |
|------|------|
| [SDD+TDD 融合开发模式指南](./sdd-tdd-fusion-guide.md) | 开发模式详细说明与各层测试模板 |
| [SDD+TDD 实施检查清单](./sdd-tdd-checklist.md) | 实施步骤检查 |
| [or.md 系统公理二](../planning-artifacts/or.md) | 系统公理定义 |
| [Story 1.14c: 自主调用循环 - execute](./1-14c-autonomous-invocation-execute.md) | 前置 Story |
| [Story 1.15b: 外部化记忆 - L0 入口](./1-15b-externalized-memory-five-layer-storage.md) | 后续 Story（待创建） |
| [Story 6.3: Checkpoint 快照创建](../planning-artifacts/) | L3 压缩触发 Story（待创建） |

---

**模板版本/Template Version:** 2.7.0
**创建日期/Created:** 2026-04-24
**最后更新/Last Updated:** 2026-04-25
**更新说明:**
- v2.7.0: 修复 P1 架构一致性问题：(1) L0 文件命名采用方案 C（类型文件夹 + UUID：`{type}/{uuid}.md`）；(2) MEMORY.md 索引格式统一为 Markdown 链接格式 `- [name](type/uuid.md) — hook`（符合架构 §11.2.3）；(3) 补充多租户隔离（private/group 路径）
- v2.6.0: 修复一致性/命名规范问题：(1) MemoryChanged 事件命名遵循现有模式（event_type field + __post_init__）；(2) OutboxEntity 路径修正为 src/infrastructure/entities/outbox.py（遵循 Story 1.3 方案 A）；(3) 补充 OutboxRepository 接口引用
- v2.5.1: 修复 P1/P2 审查问题：(1) Redis key 格式统一；(2) XDG 路径规范修正；(3) 混合压缩边界条件明确；(4) LLM 压缩提示词定义；(5) 版本冲突重试策略；(6) 事务发件箱细节；(7) CI mock 策略
- v2.5.0: Story 1.15a 完整版本 - 实现 L1 显式确认压缩：(1) L1TextExtractor 文本提取器 + L1Compressor 压缩器（压缩率≥70%）；(2) MemoryService CRUD 操作（save/delete/update/list）；(3) FileMemoryAdapter L0 文件系统 + MemoryMetadataRepository L2 PostgreSQL 双层存储；(4) MemoryChanged 事件发布（is_automatic=False）；(5) 六边形架构验证（L1/L3 分离）；(6) 性能基准测试 P95<20ms；(7) 混合压缩技术选型（规则压缩 + LLM 压缩）
