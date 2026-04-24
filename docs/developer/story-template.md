# Story [编号]: [名称]

**Status:** `backlog`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** [角色/Role],
**I want** [功能/Feature],
**So that** [价值/Value].

### 业务价值

[简要说明本 Story 的业务价值和在 Epic 中的位置]

---

## ✅ Acceptance Criteria 验收标准

### AC-1: [验收标准标题]

**Given** [前置条件/Precondition]
**When** [触发动作/Trigger Action]
**Then** [预期结果/Expected Result]
**And** [额外断言/Additional Assertions]

**验证标准/Validation Criteria:**
- [ ] [具体验证项 1]
- [ ] [具体验证项 2]
- [ ] [具体验证项 3]

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] 事件定义位于 `src/domain/events/`
- [ ] Pydantic 模型验证通过
- [ ] 事件命名符合规范（`[Aggregate][EventName]`，如 `UserCreated`）

#### API 契约 (API Contract)
- [ ] OpenAPI 定义位于 `docs/api/openapi.yaml`
- [ ] 契约测试通过（`tests/contract/test_api_contract.py`）
- [ ] API 版本管理正确（`/api/v1/[resource]`）

#### 数据模型 (Data Models)
- [ ] 模型定义位于 `src/domain/entities/` 或对应层
- [ ] [描述数据模型要求]
- [ ] ...

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_story_x_y.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_story_x_y_steps.py`（BDD 步骤实现）
- [ ] 业务方评审通过
- [ ] 所有场景覆盖（Happy Path + Edge Cases）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试
- 同一中文文本可能需要同时支持 given/when 装饰器
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证）
- [ ] 规范文档通过人工评审或自动化校验

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

> **明确区分 TDD 单元测试 与 SDD 架构验证测试，避免混淆。**

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | [组件 A] | [验证内容描述] | `test_[component_a].py` | Task [N] |
| **TDD 单元测试** | [组件 B] | [验证内容描述] | `test_[component_b].py` | Task [N] |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_story_x_y.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_story_x_y_steps.py` | Task 0 |
| **SDD 架构验证** | [架构约束] | [约束描述] | `test_[architecture].py` | Task [N] |
| **集成测试** | [层间协作] | [协作描述] | `test_[integration].py` | Task [N] |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **[层类型] 层覆盖率 ≥ [目标值]%**（`pytest --cov=src/[layer]`）- **P1 阻断门禁**
  - 领域层：≥90%（关键业务逻辑，不变量验证）
  - 应用层：≥85%（核心业务流，事务管理）
  - 接口层：≥85%（API 路由，请求响应验证）
  - 基础设施层：≥75%（外部依赖适配，连接测试）
  - 安全层：≥85%（认证授权，渗透测试）
  - 架构层：≥85%（核心机制，路由决策）
- [ ] **集成测试覆盖率 ≥70%**（`pytest --cov=tests/integration`）
- [ ] **关键路径覆盖率 100%**（所有分支覆盖）

> ⚠️ **骨架 Story 覆盖率豁免：** 如果本 Story 为架构骨架（Skeleton），大量代码为空接口/占位类/`__init__.py`，
> 无法达到上述覆盖率指标。**请将覆盖率要求临时调整为：整体≥30%，[层类型] 层≥50%。**
> 从下一个非骨架 Story 开始恢复标准覆盖率要求。

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

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
| AC-1 | [描述] | Task [2] | [Subtask 简述] | `test_[file].py` |
| AC-1 | [描述] | Task [5] | [Subtask 简述] | `test_[file].py` |
| AC-2 | [描述] | Task [1] | [Subtask 简述] | `test_[file].py` |
| AC-2 | [描述] | Task [3] | [Subtask 简述] | `test_[file].py` |
...

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** [相关 AC]

> **目的：** 在进入代码实现前，明确 Schema、API 契约、验收标准。这是 SDD 规范驱动的基础。

- [ ] Subtask [m.n]: 定义领域事件 Schema（[关键属性]）
- [ ] Subtask [m.n]: 定义数据模型（[关键属性]）
- [ ] Subtask [m.n]: 创建/更新 `docs/api/openapi.yaml`
- [ ] Subtask [m.n]: 编写 Gherkin 验收测试 `tests/acceptance/test_story_x_y.feature`
- [ ] Subtask [m.n]: 编写 BDD 步骤实现 `tests/acceptance/test_story_x_y_steps.py`
- [ ] Subtask [m.n]: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: [任务名称]

**关联 AC:** [相关 AC]

> **[可选说明：** 如果本 Task 包含 Makefile/工具链配置，说明"工具先行"原则。]

#### TDD 循环 [A/B/C...]：[循环描述]

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 [测试文件]（[测试内容]） |
| 🟢 绿 | 实现 [组件/类] 最小代码 |
| 🔄 重构 | 优化代码，运行 `ruff` + `mypy` |

- [ ] Subtask [m.n]: 🔴 红 — 编写 [组件] 失败测试
- [ ] Subtask [m.n]: 🟢 绿 — 实现 [组件] 最小代码
- [ ] Subtask [m.n]: 🔄 重构 — 优化 [组件] 代码

**完成标准/Definition of Done:**
- [ ] [组件] 实现完成
- [ ] TDD 循环全部通过
- [ ] 覆盖率≥[目标值]%

---

### Task 2: [任务名称] — 含完整 TDD 循环

**关联 AC:** [相关 AC]

> ⚠️ **本 Task 包含自己的 TDD 循环，禁止将测试推迟到其他 Task。**

#### TDD 循环 [A]：[组件 A]

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_[component_a].py`（[测试场景]） |
| 🟢 绿 | 实现 `[ComponentA]` 类/函数最小代码 |
| 🔄 重构 | 添加类型注解、docstring、应用设计模式 |

- [ ] Subtask [m.n]: 🔴 红 — 编写 [组件 A] 失败测试
- [ ] Subtask [m.n]: 🟢 绿 — 实现 [组件 A]
- [ ] Subtask [m.n]: 🔄 重构 — 优化 [组件 A] 代码

#### TDD 循环 [B]：[组件 B]

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_[component_b].py`（[测试场景]） |
| 🟢 绿 | 实现 `[ComponentB]` 类/函数最小代码 |
| 🔄 重构 | 统一命名、添加类型注解 |

- [ ] Subtask [m.n]: 🔴 红 — 编写 [组件 B] 失败测试
- [ ] Subtask [m.n]: 🟢 绿 — 实现 [组件 B]
- [ ] Subtask [m.n]: 🔄 重构 — 优化 [组件 B] 代码

**完成标准/Definition of Done:**
- [ ] [组件 A] 和 [组件 B] 全部实现
- [ ] 所有 TDD 循环测试通过
- [ ] 覆盖率≥[目标值]%

---

### Task [N]: SDD 架构约束验证测试

**关联 AC:** [相关 AC]

> **性质说明：** 本 Task 不是 TDD 单元测试，而是 **SDD 规范验证测试**（验证架构/约束是否被遵守）。
> 它验证前面 Task 创建的代码是否符合 [架构/安全/合规] 规则。

#### 架构验证测试实现

- [ ] Subtask [m.n]: 创建 `tests/unit/[type]/test_[architecture].py`
- [ ] Subtask [m.n]: 实现 [验证器 A]（[验证内容]）
- [ ] Subtask [m.n]: 实现 [验证器 B]（[验证内容]）
- [ ] Subtask [m.n]: 实现循环依赖检测（**使用 ruff 的 `E` 规则或 `isort --check-only`，不引入 pylint**）
- [ ] Subtask [m.n]: 运行完整测试套件并生成报告

**完成标准/Definition of Done:**
- [ ] 所有架构/约束测试通过
- [ ] 测试输出清晰的合规报告
- [ ] 任何违规都会导致测试失败
- [ ] 循环依赖检测使用 ruff/isort（不引入额外工具）

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** [如 CQRS、Event Sourcing、Hexagonal 等]
- **设计约束:** [如领域层零依赖、依赖方向、仓储模式等]
- **技术栈:** [如 Python 3.11+、FastAPI 0.104+、SQLAlchemy 2.0+ 等]

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) - 决策 [N] (ADR-[XXX])

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **[选中方案]** | [优点] | [缺点] | ✅ [评分]/10 |
| [备选方案 A] | [优点] | [缺点] | [评分]/10 |
| [备选方案 B] | [优点] | [缺点] | [评分]/10 |

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   └── [layer]/
│       ├── [component].py      # 核心实现
│       └── __init__.py         # 模块导出
├── tests/
│   ├── unit/[layer]/
│   │   └── test_[component].py # 单元测试
│   ├── integration/
│   │   └── test_[integration].py # 集成测试
│   └── acceptance/
│       ├── test_story_x_y.feature   # Gherkin 场景
│       └── test_story_x_y_steps.py  # BDD 步骤实现
└── docs/
    └── [layer]/
        └── [component]_guide.md # 实施指南
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story [编号]-[名称]](./[编号]-[name].md)

**关键学习/Key Learnings:**
- [学习点 1]
- [学习点 2]
- [学习点 3]

**应用到本故事/Applied to This Story:**
- [ ] [应用点 1]
- [ ] [应用点 2]
- [ ] [应用点 3]

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | [模型名称，如 Qwen Code] |
| **Version** | create-story workflow v[版本] |
| **Execution Date** | [执行日期，如 2026-03-14] |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Instructions** | `_bmad/bmm/workflows/4-implementation/create-story/instructions.xml` |
| **Template** | `_bmad/bmm/workflows/4-implementation/create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/[编号]-[name].md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [ ] 故事需求从 `epics_v1.0.md` 提取
- [ ] 架构约束从 `architecture.md` 提取
- [ ] 前一个故事学习经验整合
- [ ] 状态设置为 `ready-for-dev`
- [ ] SDD+TDD 融合开发要求定义完成
- [ ] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/[编号]-[name].md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/[layer]/[component].py` - 核心实现
- `tests/unit/[layer]/test_[component].py` - 单元测试
- `tests/integration/test_[integration].py` - 集成测试
- `docs/[layer]/[component]_guide.md` - 实施指南

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | [编号] |
| **Story Key** | [编号]-[name] |
| **File** | `_bmad-output/implementation-artifacts/stories/[编号]-[name].md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic [N]: [Epic 名称] |
| **价值组** | [价值组名称] |
| **优先级** | [优先级] |
| **覆盖 FR** | [功能需求 ID] |

### 完成总结 Completion Summary

1. [ ] All tasks defined 所有任务定义完成
2. [ ] All acceptance criteria specified 所有验收标准已定义
3. [ ] Architecture constraints extracted 架构约束已提取
4. [ ] Previous story learnings integrated 前一个故事学习经验已整合
5. [ ] Sprint status synced to `ready-for-dev`

### 🔧 对抗性审查修复（Adversarial Review Fixes）

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | [问题描述] | P[N] | [修复方案] |

### 下一步 Next Steps

- [ ] Story created with `ready-for-dev` status
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
| **领域层 (Domain)** | 领域层 Story | Story 1.x | ≥90% | 实体创建/状态转换/领域事件/不变量验证 | Story 1.1: 六边形架构骨架 |
| **应用层 (Application)** | 应用层 Story | Story 2.x | ≥85% | 用例逻辑/命令处理/查询处理/事务管理 | Story 2.1: 用户注册用例 |
| **接口层 (Interfaces)** | 接口层 Story | Story 3.x | ≥85% | API 路由/请求响应验证/事件监听/错误处理 | Story 3.1: REST API |
| **基础设施层 (Infrastructure)** | 基础设施层 Story | Story 0.x, 1.4-1.8 | ≥75% | 连接测试/CRUD 操作/外部适配器/性能基准 | Story 1.4: Redis 缓存层 |
| **安全层 (Security)** | 安全层 Story | Story 1.9-1.12 | ≥85% | 认证/授权/RBAC/审计日志/渗透测试 | Story 1.9: RBAC 权限控制 |
| **架构层 (Architecture)** | 架构层 Story | Story 1.13-1.19 | ≥85% | 核心机制 (UDMR/EIP)/路由决策/多 Agent 协作 | Story 1.13: 统一动态模型路由 |

> **注意：**
> 1. **层编号规则** — Story 0.x 为基础设施准备，Story 1.x 为领域层与安全/架构机制，Story 2.x 为应用层，Story 3.x 为接口层
> 2. **覆盖率要求** 源自 epics_v1.0.md CI/CD 质量门禁：整体≥80%，领域层≥90%，应用层≥85%，基础设施层≥75%
> 3. **骨架 Story 覆盖率豁免** — 架构骨架 Story 临时降低覆盖率要求（整体≥30%，对应层≥50%），从下一个非骨架 Story 恢复
> 4. **循环依赖检测** — 统一使用 ruff/isort，不引入 pylint 等额外工具

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

**模板版本/Template Version:** 2.5.0
**创建日期/Created:** 2026-03-04
**最后更新/Last Updated:** 2026-04-24
**更新说明:**
- v2.5.0: 新增 BDD 步骤实现文件 `test_story_x_y_steps.py` 编写要求（Story 1.15b 实战经验）
- v2.4.0: 补充 asyncio.run() 使用场景说明（Story 1.4 实战经验）：(1) 独立脚本用 asyncio.run()，pytest-xdist 并行测试 BDD 步骤用 event_loop fixture；(2) 根据场景选择正确的并发测试手段；(3) asyncio.gather() 用于真正的并发测试
- v2.3.0: 新增 BDD 验收测试与 pytest-asyncio 配合规则（Story 1.14c 实战经验）：(1) BDD 步骤函数不用 @pytest.mark.asyncio；(2) 用 event_loop.run_until_complete() 运行 async；(3) 同一中文文本可能需要同时支持 given/when 装饰器
- v2.2.0: 新增并行测试隔离规则（Story 20-1 实战经验）：(1) UUID 前缀隔离资源；(2) autouse cleanup 陷阱；(3) asyncio.Lock 类变量规则；(4) pytest-asyncio auto mode 配置
- v2.1.0: 新增测试隔离与数据清理约束：(1) 强制使用 transaction rollback；(2) Schema 初始化必须在 fixture 内完成；(3) 禁止手动 delete/truncate
