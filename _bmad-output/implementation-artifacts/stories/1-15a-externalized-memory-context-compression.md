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

本 Story 是 Epic 1（企业级架构基础与合规）价值组 5（or.md 系统公理实现）的第四个故事，在 Story 1.14c（execute 实现）完成后实现 L1 显式确认压缩机制。核心价值：

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **用户主动记忆持久化** | 用户通过"记住..."命令主动保存记忆到 L0 文件系统 + L2 PostgreSQL | 记忆保存成功率 100% |
| **上下文压缩** | 将用户输入（≤500字）压缩至 ~150字，压缩率≥70% | 压缩率验证≥70%（允许 -5% 误差） |
| **MemoryChanged 事件** | 发布 is_automatic=False 的 MemoryChanged 事件，下游监听器同步元数据 | 事件发布成功率 ≥99% |
| **四种操作类型** | 支持保存/删除/修改/查询四种记忆操作 | CRUD 操作 100% 正确 |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 1: 企业级架构基础与合规，价值组 5: or.md 系统公理实现，Story 1.15a

**or.md 公理追溯:** 系统公理二（外部化记忆：LLM 上下文=缓存，磁盘记忆=真相源），覆盖"L1 显式确认压缩"阶段

**前置依赖:** Story 1.14c（execute 实现）、Story 1.4（提供 L1 Redis）、Story 1.5（提供 L2 PostgreSQL 基础）

**后续依赖:** Story 1.15b（L0 记忆入口 + 六层存储协同）、Story 1.17（UDMR 基础路由）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: L1 显式确认压缩触发

**Given** 用户说"记住 X"或"以后用 X"
**When** L1 显式确认压缩触发
**Then** 执行以下步骤：
0. **触发模式识别** — 识别以下用户指令模式：
   - `"记住..."` `"以后用..."` `"别忘了..."` `"这很重要，记住..."`
   - 正则匹配：`r'(记住|以后用|别忘了|这很重要，记住)\s*(.+)'` 提取 X
1. 提取"记住 X"中的 X 作为记忆核心内容（轻量级提取，≤500 字）
2. 压缩 X 至 ~150 字（保留核心语义，压缩率≥70%）
3. 写入 ~/.sisys/memory/*.md
4. 更新 MEMORY.md 索引
5. 发布 MemoryChanged(is_automatic=False)
6. 异步写入 L2 PostgreSQL（memory_metadata + memory_change_history）

**验证标准/Validation Criteria:**
- [ ] MemoryService.save() 实现（`src/domain/services/memory_service.py`）
- [ ] 轻量级内容提取（≤500 字验证）
- [ ] 压缩函数实现（压缩率≥70%）
- [ ] L0 文件系统写入（~/.sisys/memory/*.md）
- [ ] MEMORY.md 索引更新
- [ ] MemoryChanged(is_automatic=False) 事件发布

### AC-2: L1 四种操作类型

**Given** 用户记忆操作请求
**When** 用户发送"记住 X"（保存）、"不要记住 X"（删除）、"改成 X"（修改）、"你记得什么"（查询）
**Then** MemoryService 执行对应操作

**验证标准/Validation Criteria:**
- [ ] MemoryService.save() - 保存记忆
- [ ] MemoryService.delete() - 删除记忆
- [ ] MemoryService.update() - 修改记忆
- [ ] MemoryService.query() - 查询记忆
- [ ] MemoryService.list() - 列出所有记忆（"你记得什么"）
- [ ] 操作幂等性验证

### AC-3: 压缩率验证

**Given** 用户输入记忆内容
**When** 执行 L1 压缩
**Then** 压缩率≥70%（用户输入≤500 字 → 压缩后约 150 字，允许误差 -5%）

**验证标准/Validation Criteria:**
- [ ] 压缩率计算公式验证（1 - compressed_length / original_length ≥ 0.70）
- [ ] 压缩后内容语义保留验证
- [ ] 压缩延迟 P95<20ms（基准测试）

### AC-4: MemoryChanged 事件发布

**Given** 用户记忆操作完成
**When** MemoryService 发布 MemoryChanged 事件
**Then** 事件携带 is_automatic=False，触发下游用例

**验证标准/Validation Criteria:**
- [ ] MemoryChanged 事件定义（`src/domain/events/memory_events.py`）
- [ ] 事件字段: event_id, memory_id, user_id, change_type, is_automatic, old_value, new_value, timestamp
- [ ] 下游监听器注册（memory_metadata UPSERT、memory_change_history append-only）
- [ ] 事件发布成功率 ≥99%

### AC-5: L0 文件系统存储

**Given** 用户记忆内容
**When** 写入 L0 文件系统
**Then** 存储至 ~/.sisys/memory/*.md，更新 MEMORY.md 索引

**验证标准/Validation Criteria:**
- [ ] L0 文件系统路径验证（~/.sisys/memory/）
- [ ] Private 记忆: ~/.sisys/memory/{memory_id}.md
- [ ] Group 记忆: ~/.sisys/memory/group/{memory_id}.md
- [ ] MEMORY.md 索引格式（最多 200 行，超出自动截断）
- [ ] 文件权限验证（600，用户私有）

### AC-6: L2 PostgreSQL 存储

**Given** 用户记忆操作
**When** 异步写入 L2 PostgreSQL
**Then** 更新 memory_metadata 和 memory_change_history 表

**验证标准/Validation Criteria:**
- [ ] memory_metadata 表 UPSERT（name, description, type, path, version, mtime, owner, group_id）
- [ ] memory_change_history 表 append-only（change_type: create/update/delete）
- [ ] 异步写入（不阻塞主流程）
- [ ] 写入重试机制（最多 3 次）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] MemoryChanged 事件定义（`src/domain/events/memory_events.py`）
  - 字段: event_id, memory_id, user_id, change_type (enum: create/update/delete), is_automatic, old_value, new_value, timestamp
  - event_type = "MemoryChanged"
  - is_automatic = False（L1 用户主动触发）

#### 数据模型 (Data Models)
- [ ] MemoryService 服务类（`src/domain/services/memory_service.py`）
  - 方法: `save(user_id, content, memory_type, group_id) -> Memory`, `delete(memory_id, user_id)`, `update(memory_id, user_id, new_content)`, `query(memory_id, user_id) -> Memory`, `list(user_id) -> List[Memory]`
  - 职责: L1 显式确认压缩、四种操作、MemoryChanged 事件发布
- [ ] Memory 实体（`src/domain/entities/memory.py`）
  - 字段: memory_id, user_id, content, compressed_content, memory_type (enum: private/group), group_id, name, description, version, created_at, updated_at

#### L0 文件系统存储 (L0 Storage)
- [ ] L0MemoryStore 仓储接口（`src/domain/repositories/l0_memory_port.py`）
  - 接口方法: `save(memory_id, content)`, `load(memory_id) -> str`, `delete(memory_id)`, `update_index(memory_entries: List[MemoryIndexEntry])`, `load_index() -> List[MemoryIndexEntry]`
  - 定义在 domain/repositories 层（符合六边形架构：领域层定义仓储接口，基础设施层实现）
- [ ] FileSystemMemoryAdapter 实现（`src/infrastructure/storage/file_system_memory_adapter.py`）
  - 实现 L0MemoryStore 端口接口
  - 路径: ~/.sisys/memory/
  - MEMORY.md 索引文件（最多 200 行，超出自动截断保留最新）
  - 权限: 600
- [ ] MemoryIndexEntry 值对象（`src/domain/value_objects/memory_index_entry.py`）
  - 字段: memory_id, name, memory_type, mtime

#### L2 PostgreSQL 存储 (L2 Storage)
- [ ] MemoryMetadataRepository 仓储接口定义在 domain 层（`src/domain/repositories/memory_metadata_repository.py`）
  - 接口方法: `upsert(metadata)`, `find_by_id(memory_id) -> MemoryMetadata`, `find_by_user(user_id) -> List[MemoryMetadata]`, `delete(memory_id)`
  - 遵循六边形架构：领域层定义接口，基础设施层实现
- [ ] MemoryChangeHistoryRepository 仓储接口定义在 domain 层（`src/domain/repositories/memory_change_history_repository.py`）
  - 接口方法: `append(history)`, `find_by_memory(memory_id) -> List[MemoryChangeHistory]`
  - append-only 模式，不可更新或删除

#### 压缩器 (Compressor)
- [ ] MemoryCompressor 服务接口（`src/domain/services/memory_compressor_port.py`）
  - 接口方法: `compress(content, max_length) -> str`, `calculate_compression_ratio(original, compressed) -> float`
  - 定义在 domain/services 层（符合六边形架构：领域层定义服务接口，基础设施层实现）
- [ ] LLMCompressionAdapter 实现（`src/infrastructure/compression/llm_compression_adapter.py`）
  - 实现 MemoryCompressor 端口接口
  - 使用 LLM 进行语义压缩
  - 目标: ≤500字 → ~150字（压缩率≥70%）

#### 配置模型 (Configuration Models)
- [ ] MemoryConfig 配置（`src/infrastructure/config/memory.py`）
  - 环境变量: `MEMORY_L0_PATH`（默认 ~/.sisys/memory/）, `MEMORY_MAX_INPUT_CHARS`（默认 500）, `MEMORY_COMPRESSED_CHARS`（默认 150）, `MEMORY_INDEX_MAX_LINES`（默认 200）
  - 从环境变量读取（`from_env()` 方法）

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_story_1.15a.feature`（由 Dev agent 在 Task 0 创建）
- [ ] 覆盖场景:
  - 用户说"记住 X"触发 L1 压缩保存
  - 压缩率≥70% 验证
  - MemoryChanged(is_automatic=False) 事件发布
  - 四种操作: 保存/删除/修改/查询
  - L0 文件系统写入 ~/.sisys/memory/
  - L2 PostgreSQL 异步写入

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
| **TDD 单元测试** | MemoryService | L1 四种操作 | `test_memory_service.py` | Task 1 |
| **TDD 单元测试** | LLMCompressionAdapter | 压缩率验证 | `test_llm_compression_adapter.py` | Task 2 |
| **TDD 单元测试** | FileSystemMemoryAdapter | L0 文件存储 | `test_file_system_memory_adapter.py` | Task 2 |
| **TDD 单元测试** | MemoryChanged 事件 | 事件 Schema | `test_memory_events.py` | Task 1 |
| **TDD 单元测试** | MemoryMetadataRepository | L2 PostgreSQL | `test_memory_metadata_repository.py` | Task 2 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_story_1.15a.feature` | Task 0 |
| **SDD 架构验证** | 架构约束 | 六边形架构约束 | `test_memory_architecture.py` | Task 3 |
| **集成测试** | 端到端流程 | L1 压缩保存流程 | `test_compression_integration.py` | Task 3 |

#### 测试隔离约束（必须遵守）

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**
> 参考 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md) §5.5 测试隔离约束。

**约束规则：**

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **事务隔离** | 集成测试使用 transaction rollback | 数据泄漏导致随机失败 |
| **Schema 自创建** | fixture 内完成 Schema 初始化 | 依赖外部迁移，环境不一致 |
| **资源唯一性** | 测试数据使用 UUID 等唯一标识符 | ID 冲突或状态污染 |
| **外部服务隔离** | Redis/Neo4j/Qdrant 测试前清理或用 mock | 真实数据被污染 |
| **并行隔离** | 并行测试使用 UUID 前缀隔离资源；语义缓存测试用不同 embedding 向量 | 资源冲突导致并行失败 |
| **语义缓存隔离** | 语义缓存基于向量相似度，多测试用相同 embedding 会互相覆盖缓存 | 需要用 unique_cache_key 生成不同 embedding |
| **清理粒度** | 每个测试只清理自己创建的资源 | 误删其他测试资源 |
| **依赖声明** | Fixture 必须显式声明依赖 | 并行时清理顺序不确定 |
| **asyncio 上下文** | asyncio.Lock 类变量；处理 thread.ident 为 None | 锁失效或类型错误 |
| **pytest-asyncio** | 删除 scope=module 的 event_loop fixture | 与 auto mode 冲突 |
| **BDD async 配合** | BDD 步骤函数不使用 @pytest.mark.asyncio，用 event_loop.run_until_complete() 运行 async | 直接用 @pytest.mark.asyncio 会导致 BDD context 数据丢失 |
| **asyncio.run 使用** | 独立脚本用 asyncio.run()；pytest-xdist 并行测试中 BDD 步骤函数用 event_loop.run_until_complete() | asyncio.run() 创建新循环，并行测试时可能关闭错误循环 |
| **并发测试方法** | 单进程测试用 asyncio.run()；pytest-xdist 并行时 BDD 步骤用 event_loop fixture；真正并发测试在 async 函数内用 asyncio.gather() | 根据场景正确选择否则失败 |
| **外部客户端** | 第三方 API 必须验证方法存在性 | AttributeError |

**禁止行为：**
- ❌ 集成测试手动 `delete`/`truncate`（应用 transaction rollback）
- ❌ autouse fixture 删除全局匹配资源（如 `test_*`）
- ❌ Fixture 假设清理顺序（必须显式声明依赖）
- ❌ asyncio.Lock 使用实例变量
- ❌ scope=module 的 event_loop fixture
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- ❌ pytest-xdist 并行测试时，BDD 步骤函数内使用 asyncio.run()（应使用 event_loop fixture）

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
| AC-1 | L1 显式确认压缩触发 | Task 1 | Subtask 1.1-1.6（MemoryService 红→绿→重构） | `test_memory_service.py` |
| AC-2 | L1 四种操作类型 | Task 1 | Subtask 1.4-1.6（四种操作 红→绿→重构） | `test_memory_service.py` |
| AC-3 | 压缩率验证 | Task 2 | Subtask 2.1-2.3（LLMCompressionAdapter 红→绿→重构） | `test_llm_compression_adapter.py` |
| AC-4 | MemoryChanged 事件发布 | Task 1 | Subtask 1.7-1.9（MemoryChanged 事件 红→绿→重构） | `test_memory_events.py` |
| AC-5 | L0 文件系统存储 | Task 2 | Subtask 2.4-2.6（FileSystemMemoryAdapter 红→绿→重构） | `test_file_system_memory_adapter.py` |
| AC-6 | L2 PostgreSQL 存储 | Task 2 | Subtask 2.7-2.9（MemoryMetadataRepository 红→绿→重构） | `test_memory_metadata_repository.py` |

---

## 📋 Tasks / Subtasks 任务分解

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5, AC-6

> **目的：** 在进入代码实现前，明确 Schema、API 契约、验收标准。

- [ ] Subtask 0.1: 定义 MemoryChanged 事件 Schema（`src/domain/events/memory_events.py`）
- [ ] Subtask 0.2: 定义 Memory 实体（`src/domain/entities/memory.py`）
- [ ] Subtask 0.3: 定义 MemoryService 服务接口（`src/domain/services/memory_service.py`）
- [ ] Subtask 0.4: 定义 L0MemoryStore 仓储接口（`src/domain/repositories/l0_memory_port.py`）
- [ ] Subtask 0.5: 定义 FileSystemMemoryAdapter 实现（`src/infrastructure/storage/file_system_memory_adapter.py`）
- [ ] Subtask 0.6: 定义 MemoryCompressor 服务接口（`src/domain/services/memory_compressor_port.py`）
- [ ] Subtask 0.7: 定义 LLMCompressionAdapter 实现（`src/infrastructure/compression/llm_compression_adapter.py`）
- [ ] Subtask 0.8: 定义 MemoryMetadataRepository 仓储接口（`src/domain/repositories/memory_metadata_repository.py`）
- [ ] Subtask 0.9: 定义 MemoryChangeHistoryRepository 仓储接口（`src/domain/repositories/memory_change_history_repository.py`）
- [ ] Subtask 0.10: 定义 MemoryConfig 配置模型（`src/infrastructure/config/memory.py`）
- [ ] Subtask 0.11: 编写 Gherkin 验收测试 `tests/acceptance/test_story_1.15a.feature`（Dev agent 创建）
- [ ] Subtask 0.12: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: MemoryService 与 MemoryChanged 事件

**关联 AC:** AC-1, AC-2, AC-4

> **职责边界:** Task 1 负责 MemoryService（L1 四种操作）和 MemoryChanged 事件发布

#### TDD 循环 [A]：MemoryService - 保存操作

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/services/test_memory_service.py`（验证 save 操作） |
| 🟢 绿 | 实现 `src/domain/services/memory_service.py` - MemoryService.save() |
| 🔄 重构 | 添加类型注解和文档字符串 |

- [ ] Subtask 1.1: 🔴 红 — 编写 MemoryService.save() 失败测试
- [ ] Subtask 1.2: 🟢 绿 — 实现 MemoryService.save()（内容提取、压缩、存储）
- [ ] Subtask 1.3: 🔄 重构 — 优化保存逻辑

#### TDD 循环 [B]：MemoryService - 删除/修改/查询操作

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/services/test_memory_service.py`（验证 CRUD 操作） |
| 🟢 绿 | 实现 MemoryService.delete()/update()/query()/list() |
| 🔄 重构 | 优化操作逻辑 |

- [ ] Subtask 1.4: 🔴 红 — 编写 delete/update/query/list 失败测试
- [ ] Subtask 1.5: 🟢 绿 — 实现 delete/update/query/list 方法
- [ ] Subtask 1.6: 🔄 重构 — 优化 CRUD 逻辑

#### TDD 循环 [C]：MemoryChanged 事件

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/events/test_memory_events.py`（验证事件 Schema） |
| 🟢 绿 | 实现 MemoryChanged 事件类 |
| 🔄 重构 | 验证事件继承和子事件类型 |

- [ ] Subtask 1.7: 🔴 红 — 编写 MemoryChanged 事件失败测试
- [ ] Subtask 1.8: 🟢 绿 — 实现 MemoryChanged 事件 Schema
- [ ] Subtask 1.9: 🔄 重构 — 验证事件发布逻辑

**完成标准/Definition of Done:**
- [ ] MemoryService 实现完成（四种操作：save/delete/update/list）
- [ ] MemoryChanged 事件定义完成
- [ ] 记忆保存成功率 100%
- [ ] TDD 循环全部通过

---

### Task 2: 存储适配器与压缩器实现

**关联 AC:** AC-3, AC-5, AC-6

> **职责边界:** Task 2 负责 LLMCompressionAdapter（压缩率验证）、FileSystemMemoryAdapter（L0 存储）、MemoryMetadataRepository（L2 PostgreSQL）

#### TDD 循环 [A]：LLMCompressionAdapter 压缩器

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/compression/test_llm_compression_adapter.py`（验证压缩率≥70%） |
| 🟢 绿 | 实现 `src/infrastructure/compression/llm_compression_adapter.py` - LLMCompressionAdapter |
| 🔄 重构 | 优化压缩算法 |

- [ ] Subtask 2.1: 🔴 红 — 编写压缩率验证失败测试
- [ ] Subtask 2.2: 🟢 绿 — 实现 LLMCompressionAdapter（语义压缩，≤500字→~150字）
- [ ] Subtask 2.3: 🔄 重构 — 验证压缩率≥70%

#### TDD 循环 [B]：FileSystemMemoryAdapter L0 存储

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/storage/test_file_system_memory_adapter.py`（验证 L0 存储） |
| 🟢 绿 | 实现 `src/infrastructure/storage/file_system_memory_adapter.py` - FileSystemMemoryAdapter |
| 🔄 重构 | 添加路径验证和权限管理 |

- [ ] Subtask 2.4: 🔴 红 — 编写 L0 存储失败测试
- [ ] Subtask 2.5: 🟢 绿 — 实现 FileSystemMemoryAdapter（~/.sisys/memory/）
- [ ] Subtask 2.6: 🔄 重构 — 验证文件权限 600

#### TDD 循环 [C]：MemoryMetadataRepository L2 PostgreSQL

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/repositories/test_memory_metadata_repository.py`（验证 L2 存储） |
| 🟢 绿 | 实现 `src/infrastructure/repositories/memory_metadata_repository.py` - MemoryMetadataRepository |
| 🔄 重构 | 添加版本冲突处理（乐观锁） |

- [ ] Subtask 2.7: 🔴 红 — 编写 MemoryMetadataRepository 失败测试
- [ ] Subtask 2.8: 🟢 绿 — 实现 MemoryMetadataRepository（UPSERT + 乐观锁）
- [ ] Subtask 2.9: 🔄 重构 — 验证异步写入

**完成标准/Definition of Done:**
- [ ] LLMCompressionAdapter 实现完成（压缩率≥70%）
- [ ] FileSystemMemoryAdapter 实现完成（L0 ~/.sisys/memory/）
- [ ] MemoryMetadataRepository 实现完成（L2 PostgreSQL）
- [ ] 压缩延迟 P95<20ms
- [ ] TDD 循环全部通过

---

### Task 3: 架构验证与集成测试

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5, AC-6

> **职责边界:** Task 3 负责六边形架构验证和端到端集成测试

#### TDD 循环 [A]：六边形架构验证

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/architecture/test_memory_architecture.py`（验证架构约束） |
| 🟢 绿 | 实现架构验证逻辑（领域层零依赖、依赖方向检测） |
| 🔄 重构 | 优化架构验证器 |

- [ ] Subtask 3.1: 🔴 红 — 编写架构验证失败测试
- [ ] Subtask 3.2: 🟢 绿 — 实现架构验证逻辑
- [ ] Subtask 3.3: 🔄 重构 — 验证器优化

#### 集成测试

- [ ] Subtask 3.4: 创建 `tests/integration/test_compression_integration.py`（端到端 L1 压缩保存流程）
- [ ] Subtask 3.5: 创建 `tests/integration/test_memory_change_history.py`（memory_change_history append-only 验证）

**完成标准/Definition of Done:**
- [ ] 六边形架构验证通过（领域层零依赖）
- [ ] 集成测试通过
- [ ] 覆盖率达标（架构层≥85%，集成测试≥75%）

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（端口与适配器）、事件驱动架构
- **系统公理二:** 外部化记忆（LLM 上下文=缓存，磁盘记忆=真相源）
  - L1 显式确认压缩：用户主动"记住..."触发，压缩率≥70%
  - L0 文件系统：~/.sisys/memory/*.md（记忆入口）
  - L2 PostgreSQL：memory_metadata + memory_change_history
- **三层触发机制:**
  - L1 显式确认（用户主动，本 Story）
  - L2 语义建议（系统建议+用户确认，V2）
  - L3 压缩触发（Checkpoint 自动，Epic 6/Story 6.3）
- **设计约束:**
  - 领域层零依赖外部框架
  - 依赖倒置：领域层定义接口，基础设施层实现
  - 事件总线双通道：Redis PubSub（实时）、RabbitMQ（持久化）
- **技术栈:**
  - Python 3.11+
  - LLM 压缩：LiteLLM（统一代理）
  - L0 存储：文件系统（~/.sisys/memory/）
  - L2 存储：PostgreSQL（Story 1.5 已实现）
  - 事件总线：Redis PubSub + RabbitMQ（Story 1.3 已实现）

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) - ADR 相关决策

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **MemoryService 位于领域层** | 符合六边形架构，领域逻辑与技术解耦 | 需要依赖倒置 | ✅ 9/10 |
| MemoryService 位于应用层 | 实现简单 | 领域逻辑泄漏 | 6/10 |
| MemoryService 位于基础设施层 | 实现最简单 | 违反六边形架构 | 3/10 |

**决策**: MemoryService 位于领域层，通过依赖注入获取存储和压缩适配器。

### L1 与 L3 分离澄清

> ⚠️ **重要澄清**：L1 和 L3 是完全独立的触发机制！

**L1 显式确认压缩（本案 Story）:**
- 触发条件: 用户主动说"记住..."、"以后用 X"
- 执行时机: 用户显式命令
- 存储目标: L0 文件系统 + L2 PostgreSQL
- 压缩目标: ≤500字 → ~150字（压缩率≥70%）
- 事件: MemoryChanged(is_automatic=False)

**L3 Checkpoint 压缩（Epic 6 / Story 6.3）:**
- 触发条件: Checkpoint 创建时自动触发
- 执行时机: 系统自动
- 存储目标: StrategicArchive（六层存储）
- 压缩目标: 50K tokens → ~2K tokens
- 事件: CheckpointCreated（携带压缩后上下文）

**关键点**：
- L1 是用户主动触发，L3 是系统自动触发
- L1 存储用户认为重要的记忆，L3 存储会话推理轨迹
- 两者独立实现，互不影响

### L1 四种操作类型

| 操作 | 用户指令 | MemoryService 方法 | 描述 |
|------|---------|-------------------|------|
| 保存 | "记住..."、"以后用 X" | `save()` | 保存新记忆 |
| 删除 | "不要记住 X" | `delete()` | 删除记忆 |
| 修改 | "改成 X" | `update()` | 修改记忆 |
| 查询 | "你记得什么" | `list()` | 列出所有记忆 |

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── domain/
│   │   ├── events/
│   │   │   └── memory_events.py      # MemoryChanged 事件（新实现）
│   │   ├── services/
│   │   │   ├── memory_service.py     # MemoryService（核心逻辑）
│   │   │   └── memory_compressor_port.py # MemoryCompressor 服务接口
│   │   ├── entities/
│   │   │   └── memory.py             # Memory 实体
│   │   ├── repositories/
│   │   │   ├── l0_memory_port.py     # L0MemoryStore 仓储接口
│   │   │   ├── memory_metadata_repository.py      # MemoryMetadataRepository 仓储接口
│   │   │   └── memory_change_history_repository.py # MemoryChangeHistoryRepository 仓储接口
│   │   └── value_objects/
│   │       └── memory_index_entry.py # MemoryIndexEntry 值对象（MEMORY.md 索引条目）
│   ├── infrastructure/
│   │   ├── config/
│   │   │   └── memory.py            # MemoryConfig 配置（新实现）
│   │   ├── compression/
│   │   │   └── llm_compression_adapter.py # LLMCompressionAdapter
│   │   └── storage/
│   │       └── file_system_memory_adapter.py # FileSystemMemoryAdapter 实现
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   │   ├── services/
│   │   │   │   └── test_memory_service.py
│   │   │   └── events/
│   │   │       └── test_memory_events.py
│   │   ├── infrastructure/
│   │   │   ├── compression/
│   │   │   │   └── test_llm_compression_adapter.py
│   │   │   └── repositories/
│   │   │       ├── test_memory_metadata_repository.py
│   │   │       └── test_memory_change_history_repository.py
│   │   └── architecture/
│   │       └── test_memory_architecture.py
│   ├── integration/
│   │   ├── test_compression_integration.py
│   │   └── test_memory_change_history.py
│   └── acceptance/
│       ├── test_story_1.15a.feature
│       └── test_story_1.15a_steps.py
└── docs/
    └── developer/
        └── memory_context_compression_guide.md    # L1 显式确认压缩实施指南
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 1.14c: 自主调用循环 - execute](./1-14c-autonomous-invocation-execute.md)

**关键学习/Key Learnings:**
1. **配置模式复用** — OtelConfig.from_env() 模式应复用，MemoryConfig 采用相同 `from_env()` 类方法
2. **事件驱动解耦** — ExecuteService 仅发布事件，不直接调用其他阶段；MemoryService 应遵循相同模式
3. **六边形架构严格遵守** — Task 3 必须包含架构验证测试，确保领域层零依赖
4. **端口接口位置** — 端口接口定义在 interfaces 层（如 sandbox_port.py），实现在 infrastructure 层（如 docker_sandbox_adapter.py）
5. **依赖倒置原则** — 领域层定义仓储接口（MemoryMetadataRepository），基础设施层实现（memory_metadata_repository_impl.py）

**应用到本故事/Applied to This Story:**
- [ ] MemoryConfig 采用与 OtelConfig 相同的 `from_env()` 模式
- [ ] MemoryService 仅负责 L1 压缩和事件发布，不处理存储细节
- [ ] Task 3 包含架构验证测试（六边形架构约束检测）
- [ ] L0MemoryStore 仓储在 domain/repositories 层，实现在 infrastructure 层（FileSystemMemoryAdapter）
- [ ] MemoryCompressor 服务在 domain/services 层，实现在 infrastructure 层（LLMCompressionAdapter）
- [ ] 测试隔离约束显式强调（asyncio.Lock 类变量、pytest-asyncio auto mode）
- [ ] 压缩延迟 P95<20ms 基准测试验证

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
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/1-14c-autonomous-invocation-execute.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取
- [x] 架构约束从 `architecture.md` 提取
- [x] or.md 系统公理二（L1 显式确认压缩）追溯完成
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] 前一个故事学习经验已整合
- [x] L1 与 L3 分离关系已澄清
- [x] 测试隔离约束显式强调（asyncio.Lock/pytest-asyncio）
- [x] 压缩延迟基准测试方法明确（P95<20ms）
- [x] AC→Task 追溯矩阵 Subtask 编号修正完成
- [x] 触发模式识别逻辑添加完成
- [x] MemoryIndexEntry 值对象添加到项目结构

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/1-15a-externalized-memory-context-compression.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/domain/events/memory_events.py` - MemoryChanged 事件
- `src/domain/entities/memory.py` - Memory 实体
- `src/domain/services/memory_service.py` - MemoryService
- `src/domain/repositories/memory_metadata_repository.py` - MemoryMetadataRepository 接口（领域层定义）
- `src/domain/repositories/memory_change_history_repository.py` - MemoryChangeHistoryRepository 接口（领域层定义）
- `src/domain/repositories/l0_memory_port.py` - L0MemoryStore 仓储接口
- `src/domain/services/memory_compressor_port.py` - MemoryCompressor 服务接口
- `src/infrastructure/config/memory.py` - MemoryConfig
- `src/infrastructure/compression/llm_compression_adapter.py` - LLMCompressionAdapter（infrastructure 层实现）
- `src/infrastructure/storage/file_system_memory_adapter.py` - FileSystemMemoryAdapter（infrastructure 层实现）
- `src/infrastructure/repositories/memory_metadata_repository_impl.py` - MemoryMetadataRepository 实现
- `src/infrastructure/repositories/memory_change_history_repository_impl.py` - MemoryChangeHistoryRepository 实现
- `tests/unit/domain/services/test_memory_service.py` - MemoryService 单元测试
- `tests/unit/domain/events/test_memory_events.py` - MemoryChanged 事件单元测试
- `tests/unit/infrastructure/compression/test_llm_compression_adapter.py` - LLMCompressionAdapter 单元测试
- `tests/unit/infrastructure/storage/test_file_system_memory_adapter.py` - FileSystemMemoryAdapter 单元测试
- `tests/unit/infrastructure/repositories/test_memory_metadata_repository.py` - MemoryMetadataRepository 单元测试
- `tests/unit/infrastructure/repositories/test_memory_change_history_repository.py` - MemoryChangeHistoryRepository 单元测试
- `tests/unit/architecture/test_memory_architecture.py` - 架构验证测试
- `tests/integration/test_compression_integration.py` - 集成测试
- `tests/integration/test_memory_change_history.py` - memory_change_history 集成测试
- `tests/acceptance/test_story_1.15a.feature` - Gherkin 验收测试（由 Dev agent 在 Task 0 创建）
- `tests/acceptance/test_story_1.15a_steps.py` - 验收测试步骤实现（由 Dev agent 在 Task 0 创建）
- `docs/developer/memory_context_compression_guide.md` - L1 显式确认压缩实施指南

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
| **覆盖 FR** | or.md 系统公理二（外部化记忆） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成
2. [x] All acceptance criteria specified 所有验收标准已定义
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 对抗性审查修复（Adversarial Review Fixes）

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | AC→Task 追溯矩阵 Subtask 编号错误（AC-2 显示 Subtask 1.7-1.12 但 Task 1 只有 1.1-1.9） | P1 | 修正为 Subtask 1.4-1.6 |
| 2 | Task 1 DoD 中 MemoryChanged 引用 Subtask 1.13-1.15 不存在 | P1 | 修正为 Subtask 1.7-1.9 |
| 3 | 项目结构缺少 MemoryIndexEntry 值对象 | P2 | 添加 `src/domain/value_objects/memory_index_entry.py` |
| 4 | AC-1 缺少触发模式识别说明 | P2 | 添加触发正则模式和提取逻辑 |
| 5 | MemoryIndexEntry 位置与项目结构描述不符 | P2 | 已重构：将 MemoryIndexEntry 从 `l0_memory_port.py` 移至 `domain/value_objects/memory_index_entry.py` |

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [x] Story 审查完成，修复 2 个 P1 问题、3 个 P2 问题
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `validate-create-story` 质量检查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

## 📚 模板使用说明 Template Usage Guide

### 快速开始

1. 复制本模板到新文件
2. 替换所有 `[占位符]` 为实际内容
3. 根据 Story 类型调整覆盖率要求（见下表）
4. 确保 Task 0（SDD 规范定义）为必选前置
5. 每个 Task 包含自己的 TDD 循环（🔴红/🟢绿/🔄重构）
6. 填写 AC→Task→Subtask 追溯矩阵

### 适用场景与层类型对应关系

本模板适用于所有 Story 创建。根据六边形架构和 prd.md NFR 测试覆盖计划，Story 按层类型分类，每层有不同的测试要求：

| 层类型 | Story 类型 | Story 编号范围 | 覆盖率要求 | 测试重点 | 示例 |
|--------|-----------|---------------|-----------|---------|------|
| **架构层 (Architecture)** | 架构层 Story | Story 1.14-1.19 | ≥85% | 核心机制 (trigger/route/execute/memory) | Story 1.14c: execute |
| **领域层 (Domain)** | 领域层 Story | Story 1.x | ≥90% | 实体创建/状态转换/领域事件/不变量验证 | Story 1.1: 六边形架构骨架 |
| **基础设施层 (Infrastructure)** | 基础设施层 Story | Story 0.x, 1.4-1.8 | ≥75% | 连接测试/CRUD 操作/外部适配器/性能基准 | Story 1.4: Redis 缓存层 |
| **安全层 (Security)** | 安全层 Story | Story 1.9-1.12 | ≥85% | 认证/授权/RBAC/审计日志/渗透测试 | Story 1.9: RBAC 权限控制 |

> **注意：**
> 1. **层编号规则** — Story 0.x 为基础设施准备，Story 1.x 为领域层与安全/架构机制
> 2. **覆盖率要求** 源自 epics_v1.0.md CI/CD 质量门禁：整体≥80%，架构层≥85%，领域层≥90%，应用层≥85%，基础设施层≥75%
> 3. **Story 1.15a 定位** — 架构层 Story（外部化记忆核心机制），覆盖率要求：架构层≥85%，集成测试≥75%

### TDD 循环编写指南

每个 Task 的 TDD 循环应按以下模式编写：

```markdown
#### TDD 循环 [A]：[组件名称]

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_[component].py`（[具体测试场景]） |
| 🟢 绿 | 实现 `[Component]` 类/函数最小代码 |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [ ] Subtask [m.n]: 🔴 红 — 编写 [组件] 失败测试
- [ ] Subtask [m.n]: 🟢 绿 — 实现 [组件] 最小代码
- [ ] Subtask [m.n]: 🔄 重构 — 优化 [组件] 代码
```

**红阶段检查点：**
- 测试在实现之前编写
- 运行 `pytest` 确认测试失败
- 失败原因符合预期（如 `ModuleNotFoundError` 因为类还不存在）

**绿阶段检查点：**
- 只编写让测试通过的代码
- 不追求完美，先跑通流程
- 可以硬编码（如果能让测试通过）

**重构阶段检查点：**
- 保持测试通过的前提下优化
- 应用设计模式/架构原则
- 运行 `ruff check` + `mypy` 确认代码质量

### 相关文档 Related Documents

| 文档 | 说明 |
|------|------|
| [SDD+TDD 融合开发模式指南](./sdd-tdd-fusion-guide.md) | 开发模式详细说明与各层测试模板 |
| [SDD+TDD 实施检查清单](./sdd-tdd-checklist.md) | 实施步骤检查 |
| [预提交 Hooks 规范](./pre-commit-hooks.md) | 代码质量保障 |
| [架构设计文档](../../_bmad-output/planning-artifacts/architecture.md) | 六边形架构详细说明 |

---

**模板版本/Template Version:** 2.4.0
**创建日期/Created:** 2026-03-04
**最后更新/Last Updated:** 2026-04-24
**更新说明:**
- v2.6.0: MemoryIndexEntry 重构：从 `l0_memory_port.py` 移至 `domain/value_objects/memory_index_entry.py`
- v2.5.0: 修复 AC→Task 追溯矩阵 Subtask 编号错误；添加触发模式识别逻辑和 MemoryIndexEntry 值对象
- v2.4.0: 新增 LLM 压缩适配器测试隔离规则（Story 1.15a 实战经验）
- v2.3.0: 新增 BDD 验收测试与 pytest-asyncio 配合规则
- v2.2.0: 新增并行测试隔离规则（UUID 前缀隔离资源）
- v2.1.0: 新增测试隔离与数据清理约束
