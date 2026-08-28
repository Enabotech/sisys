# Story 4.1: 战略工具注册

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 工具工程师,
**I want** 系统注册 23 种战略工具（PESTEL/波特五力/$APPEALS/竞争对手分析/价值链分析/VRIO/安索夫矩阵/SWOT-TOWS/GE-麦肯锡矩阵/SPACE 矩阵/情景规划/价值曲线/价值主张画布/商业模式画布/破坏性创新模型/BSC/战略地图/组织设计框架/依赖关系图/RACI 矩阵/甘特图/KPI/变革管理模型）,
**So that** Agent 可以调用这些工具执行战略分析。

### 业务价值

本 Story 是 Epic 4（战略工具箱）的第一个故事（P0-1），对应 FR-ST-01（注册 23 种战略工具）。它是整个战略工具箱的基石——后续 Story 4.2 工具链编排、4.3 Schema 验证、4.4 沙箱执行、4.5 红蓝辩论均依赖本 Story 注册的工具元数据。

**现有资产（已就绪，本 Story 直接利用）：**
- `Tool` 领域实体已定义（`src/domain/entities/tool.py`）— 包含 `tool_id`、`name`、`category`、`input_schema`、`output_schema`、`status`、`version` 字段及不变量校验
- `ToolCategory` 枚举已定义（`ANALYSIS`、`GENERATION`、`VALIDATION`、`VISUALIZATION`、`OTHER`）
- `ToolStatus` 枚举已定义（`ACTIVE`、`DEPRECATED`、`MAINTENANCE`）
- `ToolExecuted` 领域事件已定义（`src/domain/events/tool_events.py`）
- `Tool` 实体单元测试已存在（`tests/unit/domain/entities/test_tool.py`）
- `SandboxExecutor` 端口已定义（`src/domain/ports/sandbox_executor.py`）— 后续沙箱执行使用
- `PortRegistry` + `PortSpec` 机制已就绪（`src/domain/ports/registry.py`）
- `composition_root.py` 引导注册机制已就绪

**本 Story 的核心任务：**
- **扩展现有 `ToolCategory` 枚举**，新增 5 个战略工具箱分类：`ENVIRONMENT_ANALYSIS`（环境分析）、`COMPETITIVE_ANALYSIS`（竞争分析）、`STRATEGIC_SELECTION`（战略选择）、`BUSINESS_MODEL`（商业模式）、`EXECUTION_MANAGEMENT`（执行管理）
- **定义 `ToolRepositoryPort` 端口**（领域层），提供工具的增删查存能力
- **定义 `ToolRegistryService` 端口**（应用层），封装 23 种工具的注册逻辑与元数据查询
- **实现 `InMemoryToolRepository`**（基础设施层），作为 MVP 阶段的内存仓储实现
- **实现 23 种战略工具的注册元数据**（含唯一标识、名称、分类、输入/输出 JSON Schema、描述）
- **在 `composition_root.py` 中注册端口**，完成依赖注入
- **创建 Gherkin 验收测试**，验证 23 种工具全部可注册、可查询、分类正确

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **工具元数据注册** | 23 种战略工具可被系统识别和调用 | 23 种工具全部注册成功 |
| **工具分类管理** | 按 5 大类别组织工具，支持按类查询 | 分类查询返回正确工具列表 |
| **工具 Schema 定义** | 每种工具有明确的输入/输出契约 | 所有工具 input_schema/output_schema 非空 |
| **工具查询接口** | Agent 可按 ID/名称/分类检索工具 | 查询延迟 P95<100ms |
| **端口注册与 DI** | 遵循六边形架构，端口统一注册 | composition_root 注册成功 |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 4: 战略工具箱，Story 4.1

**前置依赖:**
- Story 1.1（六边形架构骨架 ✅ 已实现）— 提供 `PortRegistry`、`PortSpec`、`composition_root.py` 基础设施
- Story 1.7（MinIO 对象层 ✅ 已实现）— 后续工具执行日志存储（本 Story 不直接依赖）

**后续依赖:**
- Story 4.2（工具链编排 DAG）— 依赖本 Story 注册的工具元数据
- Story 4.3（工具 Schema 验证）— 依赖本 Story 定义的 input/output schema
- Story 4.4（Docker 沙箱执行）— 依赖本 Story 注册的工具标识
- Story 5.1（CEO Agent 实例化）— Agent 调用工具需本 Story 注册

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 23 种战略工具全部注册

**Given** 系统已启动，工具注册服务已初始化
**When** 执行工具注册引导流程
**Then** 23 种战略工具全部注册成功
**And** 每种工具有唯一 `tool_id`（UUID）、`name`（中英文名称）、`category`（分类）、`input_schema`（JSON Schema）、`output_schema`（JSON Schema）
**And** 注册成功率 100%

**验证标准/Validation Criteria:**
- [ ] 23 种工具全部可查询，总数 = 23
- [ ] 每种工具 `tool_id` 为唯一 UUID
- [ ] 每种工具 `name` 非空且在 23 种工具列表中唯一
- [ ] 每种工具 `category` 属于 `ToolCategory` 枚举值
- [ ] 每种工具 `input_schema` 和 `output_schema` 为有效 JSON Schema 字典
- [ ] 所有工具 `status` 默认为 `ACTIVE`
- [ ] 所有工具 `version` 默认为 `1.0.0`

### AC-2: 按分类查询工具

**Given** 23 种战略工具已注册
**When** 按分类（`ENVIRONMENT_ANALYSIS`、`COMPETITIVE_ANALYSIS`、`STRATEGIC_SELECTION`、`BUSINESS_MODEL`、`EXECUTION_MANAGEMENT`）查询
**Then** 返回该分类下所有工具列表
**And** 各分类工具数量与架构文档一致

**验证标准/Validation Criteria:**
- [ ] `ENVIRONMENT_ANALYSIS` 返回 3 种工具（PESTEL、波特五力、$APPEALS）
- [ ] `COMPETITIVE_ANALYSIS` 返回 3 种工具（竞争对手分析、价值链分析、VRIO 框架）
- [ ] `STRATEGIC_SELECTION` 返回 6 种工具（安索夫矩阵、SWOT-TOWS、GE-麦肯锡矩阵、SPACE 矩阵、情景规划、价值曲线分析）
- [ ] `BUSINESS_MODEL` 返回 3 种工具（价值主张画布、商业模式画布、破坏性创新模型）
- [ ] `EXECUTION_MANAGEMENT` 返回 8 种工具（BSC、战略地图、组织设计框架、依赖关系图、RACI 矩阵、甘特图、KPI、变革管理模型）
- [ ] 分类查询延迟 P95<100ms

### AC-3: 按 ID/名称查询工具

**Given** 23 种战略工具已注册
**When** 按 `tool_id` 或 `name` 查询单个工具
**Then** 返回完整工具元数据
**And** 查询不存在的工具时抛出 `ToolNotFoundError`

**验证标准/Validation Criteria:**
- [ ] 按 `tool_id` 精确查询返回正确工具
- [ ] 按 `name` 精确查询返回正确工具
- [ ] 查询不存在的 `tool_id` 抛出 `ToolNotFoundError`
- [ ] 查询不存在的 `name` 抛出 `ToolNotFoundError`

### AC-4: 端口注册与依赖注入

**Given** 工具注册服务已实现
**When** 应用启动时执行 `composition_root.bootstrap()`
**Then** `ToolRepositoryPort` 和 `ToolRegistryServicePort` 端口正确注册
**And** 端口可通过 `PortRegistry` 查询到

**验证标准/Validation Criteria:**
- [ ] `tool_repository` 端口已注册（SCOPED 生命周期，tool-team 负责）
- [ ] `tool_registry_service` 端口已注册（SCOPED 生命周期，tool-team 负责）
- [ ] `PortRegistry.get("tool_repository")` 返回非空 `PortSpec`
- [ ] `PortRegistry.get("tool_registry_service")` 返回非空 `PortSpec`
- [ ] 端口契约测试通过（`tests/contracts/test_port_contract_tool.py`）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [x] 事件定义位于 `src/domain/events/`
- [x] `ToolExecuted` 已定义（`src/domain/events/tool_events.py`），含 `tool_id`、`execution_result`、`cost_audit`
- [x] 本 Story 无需新增领域事件（工具注册是静态元数据操作，不触发领域事件）

#### 数据模型 (Data Models)
- [x] `Tool` 实体已定义（`src/domain/entities/tool.py`）
- [ ] 扩展 `ToolCategory` 枚举，新增 5 个战略工具箱分类
- [ ] 定义 23 种工具的元数据常量（`src/domain/entities/strategic_tool_catalog.py`）

#### 统一端口定义注册与管理 (Port Contract)

| 端口名称 | 版本 | 接口 | 实现模块 | 生命周期 | Owner | 状态 |
|---------|------|------|---------|---------|-------|------|
| `tool_repository` | v1.0.0 | `ToolRepositoryPort` | `src.infrastructure.storage.inmemory.tool_repository.InMemoryToolRepository` | SCOPED | tool-team | 新建 |
| `tool_registry_service` | v1.0.0 | `ToolRegistryServicePort` | `src.application.services.tool_registry_service.ToolRegistryService` | SCOPED | tool-team | 新建 |

- [ ] 端口契约定义位于 `src/domain/ports/tool_repository.py` 和 `src/application/ports/tool_registry_service.py`
- [ ] 端口注册中心位于 `src/domain/ports/registry.py`，所有端口登记为 `PortSpec`
- [ ] 端口实现仅在 `src/composition_root.py` 统一注册
- [ ] 端口契约测试通过（`tests/contracts/test_port_contract_tool.py`）
- [ ] 接口命名符合单一职责
- [ ] 端口具备唯一名称、版本、owner、兼容策略
- [ ] 跨模块调用仅依赖抽象接口

#### 端口契约清单执行约束（强制）
- [ ] 本模板中的端口清单是唯一事实源
- [ ] 禁止新增未登记端口，禁止语义重复端口
- [ ] 每个端口必须同时具备 contract、registry、resolver、contract test、owner、version
- [ ] 未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)

> **原则**：异常是领域契约的一部分。本 Story 新增的领域异常必须在 Task 0 中完成设计。

**新增异常：**

| 异常类 | 编码 | 基类 | 归属模块 | 用途 |
|--------|------|------|---------|------|
| `ToolNotFoundError` | EXCEPTION_250 | `BusinessException` | business | 按 ID/名称查询工具不存在 |
| `ToolAlreadyExistsError` | EXCEPTION_251 | `ConflictError` | business | 注册已存在的工具（同 ID 或同名） |

- [ ] 归属模块与基类 — `business` 模块，继承 `BusinessException` / `ConflictError`
- [ ] 唯一编码分配 — 从子域编码范围选取（运行 `grep -r "EXCEPTION_25" src/domain/exceptions/` 验证无碰撞）
- [ ] 构造器参数设计 — 携带 `tool_id` / `tool_name`，通过 `context` 字典暴露
- [ ] 消息安全性审查 — 错误消息不泄露内部实现细节
- [ ] 编码注册 — 在 `_code_ranges.py` 的 `_CLASS_TO_SUBDOMAIN` 字典中注册
- [ ] 导出完整性 — 模块 `__all__` + 包 `__init__.py` 导入 + `EXCEPTION_HTTP_MAP` 映射
- [ ] 测试覆盖 — 构造/`to_dict()`/HTTP 映射/编码唯一性 + 子域范围测试全部通过

#### 六边形架构约束（必须遵守）

**四层架构定义**
| 层次 | 目录 | 职责 |
|------|------|------|
| domain | `src/domain/` | 核心业务逻辑，零外部依赖 |
| application | `src/application/` | 用例编排 |
| interfaces | `src/interfaces/` | 适配器 |
| infrastructure | `src/infrastructure/` | 技术实现 |

**依赖方向矩阵**
| 起点 \ 终点 | domain | application | interfaces | infrastructure |
|-------------|--------|-------------|------------|----------------|
| **domain** | — | ✗ 禁止 | ✗ 禁止 | ✗ 禁止 |
| **application** | ✓ 允许 | — | ✗ 禁止 | ✗ 禁止 |
| **interfaces** | ✓ 允许 | ✓ 允许 | — | ✗ 禁止 |
| **infrastructure** | ✓ 允许 | ✓ 允许 | ✗ 禁止 | — |

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_acceptance_strategic_tool_registration.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_strategic_tool_registration.py`
- [ ] 所有场景覆盖（AC-1 ~ AC-4 的 Happy Path + Edge Cases）
- [ ] Edge Cases 包含：工具不存在（ToolNotFoundError）、重复注册（ToolAlreadyExistsError）、分类查询空结果

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

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | ToolCategory 枚举扩展 | 5 个新分类值存在且唯一 | `tests/unit/domain/entities/test_tool.py` | Task 1 |
| **TDD 单元测试** | StrategicToolCatalog | 23 种工具元数据完整、Schema 有效 | `tests/unit/domain/entities/test_strategic_tool_catalog.py` | Task 2 |
| **TDD 单元测试** | ToolRepositoryPort | 端口方法签名、Protocol 合规 | `tests/contracts/test_port_contract_tool.py` | Task 3 |
| **TDD 单元测试** | InMemoryToolRepository | CRUD 操作、查询、异常 | `tests/unit/infrastructure/storage/test_inmemory_tool_repository.py` | Task 4 |
| **TDD 单元测试** | ToolRegistryService | 注册、查询、分类过滤 | `tests/unit/application/services/test_tool_registry_service.py` | Task 5 |
| **TDD 领域异常** | ToolNotFoundError/ToolAlreadyExistsError | 构造/to_dict/HTTP 映射 | `tests/unit/domain/exceptions/test_business_exceptions.py` | Task 3 |
| **TDD 验收测试** | Gherkin 场景 | AC-1~AC-4 业务价值验收 | `tests/acceptance/test_acceptance_strategic_tool_registration.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `tests/acceptance/test_acceptance_strategic_tool_registration.py` | Task 0 |
| **TDD 契约测试** | 端口契约 / registry / contract gate | 端口注册、版本、兼容性 | `tests/contracts/test_port_contract_tool.py` | Task 6 |
| **TDD 契约测试** | Composition Root 注册 | 端口 bootstrap 注册成功 | `tests/contracts/test_port_contract_tool.py` | Task 6 |
| **SDD 架构验证** | 六边形架构约束 | 依赖方向、零依赖 | `tests/unit/architecture/test_arch_tool.py` | Task 7 |
| **集成测试** | 工具注册全链路 | 端口→服务→仓储→实体 | `tests/integration/test_integration_tool_registration.py` | Task 7 |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）
- [ ] **领域层覆盖率 ≥90%**（`pytest --cov=src/domain`）
- [ ] **应用层覆盖率 ≥85%**（`pytest --cov=src/application`）
- [ ] **基础设施层覆盖率 ≥75%**（`pytest --cov=src/infrastructure`）
- [ ] **集成测试覆盖率 ≥70%**

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`poetry run ruff check src/`）
- [ ] **MyPy 类型检查通过**（`poetry run mypy src/`）
- [ ] **无 P0/P1 级别问题**
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 23 种战略工具全部注册 | Task 2 | Subtask 2.1-2.4 | `test_strategic_tool_catalog.py` |
| AC-1 | 23 种战略工具全部注册 | Task 4 | Subtask 4.1-4.3 | `test_inmemory_tool_repository.py` |
| AC-1 | 23 种战略工具全部注册 | Task 5 | Subtask 5.1-5.3 | `test_tool_registry_service.py` |
| AC-2 | 按分类查询工具 | Task 5 | Subtask 5.4-5.5 | `test_tool_registry_service.py` |
| AC-3 | 按 ID/名称查询工具 | Task 4 | Subtask 4.4-4.5 | `test_inmemory_tool_repository.py` |
| AC-3 | 按 ID/名称查询工具 | Task 5 | Subtask 5.6-5.7 | `test_tool_registry_service.py` |
| AC-4 | 端口注册与依赖注入 | Task 6 | Subtask 6.1-6.4 | `test_port_contract_tool.py` |
| AC-1~AC-4 | 开发结束验收 | Task 8 | Subtask 8.1-8.4 | `test_acceptance_strategic_tool_registration.feature` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4

> **目的：** 在进入代码实现前，明确 Schema、API 契约、端口契约、验收标准与六边形架构边界。

- [ ] Subtask 0.1: 定义 `ToolCategory` 枚举扩展（5 个新分类值 + 映射关系）
- [ ] Subtask 0.2: 定义 `ToolRepositoryPort` Protocol 签名（`save`、`get_by_id`、`get_by_name`、`list_all`、`list_by_category`、`delete`）
- [ ] Subtask 0.3: 定义 `ToolRegistryServicePort` Protocol 签名（`register_all`、`get_tool`、`get_tools_by_category`、`list_all_tools`、`tool_count`）
- [ ] Subtask 0.4: 定义 `ToolNotFoundError` 和 `ToolAlreadyExistsError` 异常（编码、基类、构造器）
- [ ] Subtask 0.5: 定义 23 种工具元数据常量结构（`StrategicToolCatalog`）
- [ ] Subtask 0.6: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_strategic_tool_registration.feature`
- [ ] Subtask 0.7: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_strategic_tool_registration.py`
- [ ] Subtask 0.8: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: ToolCategory 枚举扩展

**关联 AC:** AC-1, AC-2

> **目的：** 扩展现有 `ToolCategory` 枚举，新增 5 个战略工具箱分类。

#### TDD 循环 A：ToolCategory 枚举扩展

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_tool.py` 中 ToolCategory 新分类测试（5 个新值存在、互不冲突） |
| 🟢 绿 | 在 `ToolCategory` 枚举中添加 5 个新分类值 |
| 🔄 重构 | 运行 `ruff check` + `mypy` |

- [ ] Subtask 1.1: 🔴 红 — 编写 ToolCategory 新分类失败测试
- [ ] Subtask 1.2: 🟢 绿 — 扩展 `ToolCategory` 枚举（`ENVIRONMENT_ANALYSIS`、`COMPETITIVE_ANALYSIS`、`STRATEGIC_SELECTION`、`BUSINESS_MODEL`、`EXECUTION_MANAGEMENT`）
- [ ] Subtask 1.3: 🔄 重构 — 运行 `ruff check` + `mypy` + 确认测试通过

**完成标准/Definition of Done:**
- [ ] `ToolCategory` 包含 10 个枚举值（5 原有 + 5 新增）
- [ ] TDD 循环全部通过
- [ ] 覆盖率≥90%

---

### Task 2: StrategicToolCatalog 23 种工具元数据定义

**关联 AC:** AC-1, AC-2

> **目的：** 定义 23 种战略工具的完整元数据常量，作为注册的数据源。
>
> **设计依据：** 架构文档 `sisys-core-domain-design.md` §17.2.2 定义了 23 种战略工具的分类、名称、输入/输出 Schema 描述。
> 本 Task 将这些描述转化为具体的 JSON Schema 定义和 `Tool` 实例常量。
>
> **23 种工具的实现策略：**
> - **元数据注册（本 Story）：** 定义每种工具的 `Tool` 实例（ID、名称、分类、描述、input/output JSON Schema）
> - **执行逻辑（后续 Story）：** 工具的实际执行逻辑由 `ToolExecutionEngine`（§17.2.3）在沙箱中完成
> - **Skills SOP（后续 Story）：** 每种工具的详细操作手册（Think→Code→Execute→Observe→Validate 流程）在 Skills 系统中定义
>
> 本 Story **仅负责注册工具元数据**，不实现工具的具体计算逻辑。工具的执行是 LLM Agent 在沙箱中生成代码并执行的过程（参见 §17.2.3 工具标准工作流）。

#### TDD 循环 A：StrategicToolCatalog 定义

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_strategic_tool_catalog.py`（23 种工具全部存在、分类正确、Schema 非空） |
| 🟢 绿 | 创建 `src/domain/entities/strategic_tool_catalog.py`，定义 23 种工具元数据 |
| 🔄 重构 | 优化命名、添加类型注解 |

- [ ] Subtask 2.1: 🔴 红 — 编写 StrategicToolCatalog 失败测试（总数=23、每种工具字段完整）
- [ ] Subtask 2.2: 🟢 绿 — 创建 `strategic_tool_catalog.py`，定义 `TOOL_CATALOG: list[Tool]` 常量
- [ ] Subtask 2.3: 🔄 重构 — 优化元数据结构、添加中文注释

#### TDD 循环 B：工具 Schema 定义

> **Schema 设计原则：**
> - 每种工具的 `input_schema` 描述 Agent 调用该工具时需要提供的输入参数
> - 每种工具的 `output_schema` 描述工具执行后返回的结构化输出
> - Schema 使用 JSON Schema Draft-07 格式，后续 Story 4.3 会用 Pydantic V2 进行强校验
> - 输入 Schema 中的字段名和类型与架构文档 §17.2.2 的描述对齐

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 Schema 有效性测试（每个工具 input_schema/output_schema 为有效 JSON Schema） |
| 🟢 绿 | 为 23 种工具定义 input/output JSON Schema |
| 🔄 重构 | 统一 Schema 格式、去除重复定义 |

**23 种工具 Schema 定义清单：**

| # | 工具标识 | input_schema 关键字段 | output_schema 关键字段 |
|---|---------|----------------------|----------------------|
| 1 | pestel | `macro_environment: object`（political/economic/social/technological/environmental/legal 六维度） | `analysis_report: object`（六维度评分 + 影响评估 + 机会威胁矩阵） |
| 2 | porters_five_forces | `industry_data: object`（supplier_power/buyer_power/competitive_rivalry/threat_of_substitution/threat_of_new_entry） | `five_forces_analysis: object`（五力评分 + 行业吸引力 + 战略建议） |
| 3 | appeals | `customer_needs: object`（8 个维度 + 权重） | `appeals_analysis: object`（九维度评分 + 优先级排序 + 改进建议） |
| 4 | competitor_analysis | `competitor_info: array`（竞争对手列表 + 能力指标） | `competitor_radar: object`（能力雷达图数据 + 竞争定位） |
| 5 | value_chain_analysis | `enterprise_data: object`（主要活动 + 支持活动 + 成本结构） | `value_chain_analysis: object`（各环节价值贡献 + 竞争优势来源） |
| 6 | vrio_framework | `resources: array`（资源/能力清单 + VRIO 四维度评估） | `vrio_assessment: object`（竞争优势分类 + 持续性评估） |
| 7 | ansoff_matrix | `market_product_data: object`（现有/新产品 × 现有/新市场） | `growth_strategy: object`（四象限定位 + 推荐战略 + 风险评估） |
| 8 | swot_tows | `internal_factors: object`（优势/劣势）+ `external_factors: object`（机会/威胁） | `tows_matrix: object`（SO/WO/ST/WT 四策略 + 优先级） |
| 9 | ge_mckinsey_matrix | `business_units: array`（业务单元 + 行业吸引力 + 竞争实力） | `portfolio_map: object`（九宫格定位 + 投资/收割/剥离建议） |
| 10 | space_matrix | `strategic_factors: object`（CA/IS/ES/FS 四维度） | `space_positioning: object`（进取/保守/防御/竞争定位） |
| 11 | scenario_planning | `trends: array`（关键不确定因素 + 趋势数据） | `scenarios: array`（多情景方案 + 概率 + 应对策略） |
| 12 | value_curve_analysis | `competition_data: object`（竞争对手 + 价值要素评分） | `value_curve: object`（差异化曲线 + 创新机会） |
| 13 | value_proposition_canvas | `customer_profile: object`（痛点/收益/工作）+ `value_map: object`（产品/痛点缓解/收益创造） | `fit_assessment: object`（匹配度评分 + 改进建议） |
| 14 | business_model_canvas | `business_model: object`（九宫格：客户细分/价值主张/渠道/客户关系/收入来源/核心资源/关键活动/合作伙伴/成本结构） | `canvas_assessment: object`（各维度评分 + 一致性分析） |
| 15 | disruptive_innovation_model | `technology_market_data: object`（技术成熟度/市场格局/颠覆潜力） | `innovation_assessment: object`（颠覆类型判断 + 战略建议） |
| 16 | bsc_balanced_scorecard | `strategic_objectives: object`（财务/客户/内部流程/学习成长四维度目标） | `bsc_metrics: object`（KPI 指标 + 目标值 + 权重 + 行动计划） |
| 17 | strategy_map | `bsc_indicators: object`（四维度指标 + 因果关系） | `strategy_visualization: object`（战略地图节点 + 因果箭头 + 主题卡片） |
| 18 | organizational_design_framework | `org_structure: object`（组织架构 + 职能 + 汇报关系） | `design_recommendation: object`（匹配度评估 + 优化建议） |
| 19 | dependency_graph | `task_list: array`（任务列表 + 依赖关系） | `dependency_network: object`（DAG 图 + 关键路径 + 风险节点） |
| 20 | raci_matrix | `roles_tasks: object`（角色列表 + 任务列表 + 分配关系） | `raci_matrix: object`（RACI 分配表 + 冲突检测 + 建议） |
| 21 | gantt_chart | `project_plan: object`（任务列表 + 依赖 + 工期 + 资源） | `gantt_visualization: object`（时间线 + 里程碑 + 关键路径） |
| 22 | kpi | `business_objectives: object`（业务目标 + 基线数据） | `kpi_definitions: array`（KPI 列表 + 目标值 + 权重 + 监控频率） |
| 23 | change_management_model | `change_data: object`（变革内容 + 利益相关者 + 阻力分析） | `change_roadmap: object`（变革路径 + 里程碑 + 沟通计划 + 风险缓解） |

- [ ] Subtask 2.4: 🔴 红 — 编写 Schema 有效性测试（JSON Schema Draft-07 校验）
- [ ] Subtask 2.5: 🟢 绿 — 按上表定义 23 种工具的 input/output JSON Schema
- [ ] Subtask 2.6: 🔄 重构 — 运行 `ruff check` + `mypy`

**完成标准/Definition of Done:**
- [ ] `StrategicToolCatalog` 包含 23 种工具元数据
- [ ] 所有工具 `input_schema`/`output_schema` 为有效 JSON Schema（Draft-07）
- [ ] 所有工具 `category` 属于扩展后的 `ToolCategory` 枚举
- [ ] Schema 字段名与架构文档 §17.2.2 描述对齐
- [ ] 覆盖率≥90%

---

### Task 3: 领域异常定义

**关联 AC:** AC-3

> **目的：** 定义 `ToolNotFoundError` 和 `ToolAlreadyExistsError` 领域异常。

#### TDD 循环 A：ToolNotFoundError

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写异常测试（构造、to_dict、编码唯一性） |
| 🟢 绿 | 创建 `ToolNotFoundError` 异常类 |
| 🔄 重构 | 运行 `ruff check` + `mypy` |

- [ ] Subtask 3.1: 🔴 红 — 编写 `ToolNotFoundError` 失败测试
- [ ] Subtask 3.2: 🟢 绿 — 创建 `ToolNotFoundError`（EXCEPTION_250，继承 `BusinessException`）
- [ ] Subtask 3.3: 🔄 重构 — 优化异常消息、添加 context 字典

#### TDD 循环 B：ToolAlreadyExistsError

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写异常测试（构造、to_dict、编码唯一性） |
| 🟢 绿 | 创建 `ToolAlreadyExistsError` 异常类 |
| 🔄 重构 | 运行 `ruff check` + `mypy` |

- [ ] Subtask 3.4: 🔴 红 — 编写 `ToolAlreadyExistsError` 失败测试
- [ ] Subtask 3.5: 🟢 绿 — 创建 `ToolAlreadyExistsError`（EXCEPTION_251，继承 `ConflictError`）
- [ ] Subtask 3.6: 🔄 重构 — 运行异常编码唯一性测试

**完成标准/Definition of Done:**
- [ ] `ToolNotFoundError` 和 `ToolAlreadyExistsError` 定义完成
- [ ] 编码无碰撞（`test_error_code_uniqueness.py` 通过）
- [ ] 导出完整性（`__all__`、`__init__.py`、`EXCEPTION_HTTP_MAP`）
- [ ] 覆盖率≥90%

---

### Task 4: ToolRepositoryPort + InMemoryToolRepository

**关联 AC:** AC-1, AC-3

> **目的：** 定义工具仓储端口并实现内存仓储。

#### TDD 循环 A：ToolRepositoryPort 定义

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写端口契约测试（Protocol 方法签名、`@runtime_checkable`） |
| 🟢 绿 | 创建 `src/domain/ports/tool_repository.py`，定义 `ToolRepositoryPort` Protocol |
| 🔄 重构 | 运行 `ruff check` + `mypy` |

- [ ] Subtask 4.1: 🔴 红 — 编写 `ToolRepositoryPort` 契约测试
- [ ] Subtask 4.2: 🟢 绿 — 创建 `ToolRepositoryPort` Protocol（`save`、`get_by_id`、`get_by_name`、`list_all`、`list_by_category`、`delete`）
- [ ] Subtask 4.3: 🔄 重构 — 优化方法签名、添加 docstring

#### TDD 循环 B：InMemoryToolRepository 实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_inmemory_tool_repository.py`（CRUD、查询、异常） |
| 🟢 绿 | 创建 `src/infrastructure/storage/inmemory/tool_repository.py` |
| 🔄 重构 | 运行 `ruff check` + `mypy` |

- [ ] Subtask 4.4: 🔴 红 — 编写 `InMemoryToolRepository` 失败测试
- [ ] Subtask 4.5: 🟢 绿 — 实现 `InMemoryToolRepository`（`save`、`get_by_id`、`get_by_name`、`list_all`、`list_by_category`、`delete`）
- [ ] Subtask 4.6: 🔄 重构 — 优化内存存储、添加并发安全注释

**完成标准/Definition of Done:**
- [ ] `ToolRepositoryPort` Protocol 定义完成
- [ ] `InMemoryToolRepository` 实现完成
- [ ] 所有 CRUD 操作测试通过
- [ ] 覆盖率≥90%

---

### Task 5: ToolRegistryServicePort + ToolRegistryService 实现

**关联 AC:** AC-1, AC-2, AC-3

> **目的：** 定义工具注册服务端口并实现注册逻辑。

#### TDD 循环 A：ToolRegistryServicePort 定义

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写端口契约测试 |
| 🟢 绿 | 创建 `src/application/ports/tool_registry_service.py` |
| 🔄 重构 | 运行 `ruff check` + `mypy` |

- [ ] Subtask 5.1: 🔴 红 — 编写 `ToolRegistryServicePort` 契约测试
- [ ] Subtask 5.2: 🟢 绿 — 创建 `ToolRegistryServicePort` Protocol（`register_all`、`get_tool`、`get_tools_by_category`、`list_all_tools`、`tool_count`）
- [ ] Subtask 5.3: 🔄 重构 — 优化方法签名

#### TDD 循环 B：ToolRegistryService 实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_tool_registry_service.py`（注册 23 种工具、查询、分类过滤） |
| 🟢 绿 | 创建 `src/application/services/tool_registry_service.py` |
| 🔄 重构 | 运行 `ruff check` + `mypy` |

- [ ] Subtask 5.4: 🔴 红 — 编写 `ToolRegistryService` 失败测试
- [ ] Subtask 5.5: 🟢 绿 — 实现 `ToolRegistryService`（从 `StrategicToolCatalog` 加载并注册到 `ToolRepositoryPort`）
- [ ] Subtask 5.6: 🔄 重构 — 优化注册流程、添加日志

#### TDD 循环 C：分类查询与异常处理

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写分类查询测试（5 个分类返回正确数量）和异常测试（ToolNotFoundError） |
| 🟢 绿 | 实现分类查询和异常抛出逻辑 |
| 🔄 重构 | 运行 `ruff check` + `mypy` |

- [ ] Subtask 5.7: 🔴 红 — 编写分类查询和异常测试
- [ ] Subtask 5.8: 🟢 绿 — 实现 `get_tools_by_category` 和 `get_tool`（不存在时抛 `ToolNotFoundError`）
- [ ] Subtask 5.9: 🔄 重构 — 运行完整测试套件

**完成标准/Definition of Done:**
- [ ] `ToolRegistryServicePort` Protocol 定义完成
- [ ] `ToolRegistryService` 实现完成
- [ ] 23 种工具注册、查询、分类过滤全部通过
- [ ] 覆盖率≥85%

---

### Task 6: Composition Root 端口注册

**关联 AC:** AC-4

> **目的：** 在 `composition_root.py` 中注册 `tool_repository` 和 `tool_registry_service` 端口。

#### TDD 循环 A：端口注册

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写端口注册测试（`bootstrap()` 后 `PortRegistry.get()` 返回非空） |
| 🟢 绿 | 在 `composition_root.py` 中添加端口注册代码 |
| 🔄 重构 | 运行 `ruff check` + `mypy` |

- [ ] Subtask 6.1: 🔴 红 — 编写端口注册失败测试
- [ ] Subtask 6.2: 🟢 绿 — 在 `composition_root.py` 中注册 `tool_repository`（SCOPED）和 `tool_registry_service`（SCOPED）
- [ ] Subtask 6.3: 🔄 重构 — 优化注册顺序、添加注释

#### TDD 循环 B：端口解析验证

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写端口解析测试（通过 `PortRegistry` 获取端口并验证接口合规） |
| 🟢 绿 | 确认端口解析正确 |
| 🔄 重构 | 运行完整测试套件 |

- [ ] Subtask 6.4: 🔴 红 — 编写端口解析测试
- [ ] Subtask 6.5: 🟢 绿 — 验证端口解析返回正确的 `PortSpec`
- [ ] Subtask 6.6: 🔄 重构 — 运行 `ruff check` + `mypy`

**完成标准/Definition of Done:**
- [ ] `tool_repository` 端口已注册
- [ ] `tool_registry_service` 端口已注册
- [ ] 端口解析测试通过
- [ ] 覆盖率≥85%

---

### Task 7: 架构约束验证测试 + 集成测试

**关联 AC:** AC-1, AC-4

> **目的：** 验证六边形架构约束和端到端集成。

#### SDD 架构验证测试

- [ ] Subtask 7.1: 创建 `tests/unit/architecture/test_arch_tool.py`
- [ ] Subtask 7.2: 实现依赖方向验证（domain 层无外部依赖）
- [ ] Subtask 7.3: 实现端口注册验证（所有端口在 `composition_root.py` 中注册）
- [ ] Subtask 7.4: 实现循环依赖检测（使用 ruff `E` 规则）
- [ ] Subtask 7.5: 运行完整测试套件

#### 集成测试

- [ ] Subtask 7.6: 创建 `tests/integration/test_integration_tool_registration.py`
- [ ] Subtask 7.7: 实现端到端工具注册流程测试（bootstrap → register_all → query → verify count=23）
- [ ] Subtask 7.8: 运行集成测试

**完成标准/Definition of Done:**
- [ ] 所有架构约束测试通过
- [ ] 集成测试通过
- [ ] 测试输出清晰的合规报告

---

### Task 8: 开发结束验收测试

**关联 AC:** AC-1, AC-2, AC-3, AC-4

> **目的：** 收尾阶段最终验收。

#### 开发结束验收测试实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写收尾验收场景 |
| 🟢 绿 | 实现 BDD 步骤 |
| 🔄 重构 | 收敛场景命名、统一断言 |

- [ ] Subtask 8.1: 场景 1 — 验证 `src` 完成清单（ToolCategory、StrategicToolCatalog、ToolRepositoryPort、InMemoryToolRepository、ToolRegistryService、异常类）
- [ ] Subtask 8.2: 场景 2 — 验证 `tests` 完成清单（unit/contracts/integration/acceptance）
- [ ] Subtask 8.3: 运行开发结束验收测试
- [ ] Subtask 8.4: 运行 `pytest`、`ruff check`、`mypy` 收尾校验

**完成标准/Definition of Done:**
- [ ] `src` 完成清单已逐项验证
- [ ] `tests` 完成清单已逐项验证
- [ ] 开发结束验收测试通过
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../docs/architecture/architecture.md)

- **架构模式:** 领域驱动六边形架构（DDD + Hexagonal Architecture）
- **设计约束:** 领域层零外部依赖、依赖方向矩阵、端口注册与 DI 注入
- **接口治理:** 统一端口注册（PortSpec）、Registry/Resolver/ContractGate、Composition Root 装配、契约优先、版本化兼容
- **技术栈:** Python 3.11+、FastAPI 0.104+、Pydantic V2（Schema 验证）、dataclass（领域层）

### 关键架构决策

**来源:** [`architecture.md`](../../docs/architecture/architecture.md) - §17.2 战略工具箱

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **内存仓储（MVP）** | 零外部依赖、启动快、易测试 | 不持久化、重启丢失 | ✅ 9/10（MVP 阶段） |
| PostgreSQL 仓储 | 持久化、支持并发 | 需数据库、启动慢 | 7/10（V1 阶段） |
| Redis 仓储 | 高性能、支持 TTL | 非持久化、内存消耗 | 6/10（缓存场景） |

### 项目结构说明 Project Structure

```
src/
├── domain/
│   ├── entities/
│   │   ├── tool.py                     # Tool 实体（已有）
│   │   └── strategic_tool_catalog.py   # 23 种工具元数据（本 Story 新建）
│   ├── events/
│   │   └── tool_events.py              # ToolExecuted 事件（已有）
│   ├── exceptions/
│   │   ├── business_exceptions.py      # ToolNotFoundError（本 Story 新建）
│   │   └── conflict_errors.py          # ToolAlreadyExistsError（本 Story 新建）
│   └── ports/
│       └── tool_repository.py          # ToolRepositoryPort Protocol（本 Story 新建）
├── application/
│   ├── ports/
│   │   └── tool_registry_service.py    # ToolRegistryServicePort Protocol（本 Story 新建）
│   └── services/
│       └── tool_registry_service.py    # ToolRegistryService 实现（本 Story 新建）
├── infrastructure/
│   └── storage/
│       └── inmemory/
│           └── tool_repository.py      # InMemoryToolRepository（本 Story 新建）
└── composition_root.py                 # 端口注册（本 Story 修改）
```

### 23 种战略工具完整清单

**来源:** [`sisys-core-domain-design.md`](../../docs/architecture/sisys-core-domain-design.md) - §17.2.2

| 序号 | 分类 | 工具名称 | 英文标识 | 输入 Schema | 输出 Schema | 优先级 |
|------|------|---------|---------|-----------|-----------|--------|
| 1 | ENVIRONMENT_ANALYSIS | PESTEL 分析 | pestel | 宏观环境数据 | 六维度分析报告 | P0 |
| 2 | ENVIRONMENT_ANALYSIS | 波特五力 | porters_five_forces | 行业竞争数据 | 五力模型分析 | P0 |
| 3 | ENVIRONMENT_ANALYSIS | $APPEALS | appeals | 客户需求数据 | 九维度需求分析 | P0 |
| 4 | COMPETITIVE_ANALYSIS | 竞争对手分析 | competitor_analysis | 竞争对手信息 | 能力雷达图 | P0 |
| 5 | COMPETITIVE_ANALYSIS | 价值链分析 | value_chain_analysis | 企业内部数据 | 价值环节分析 | P1 |
| 6 | COMPETITIVE_ANALYSIS | VRIO 框架 | vrio_framework | 资源能力清单 | 竞争力评估 | P1 |
| 7 | STRATEGIC_SELECTION | 安索夫矩阵 | ansoff_matrix | 市场/产品数据 | 增长战略建议 | P0 |
| 8 | STRATEGIC_SELECTION | SWOT-TOWS | swot_tows | 内外因素分析 | 策略匹配矩阵 | P0 |
| 9 | STRATEGIC_SELECTION | GE-麦肯锡矩阵 | ge_mckinsey_matrix | 业务单元数据 | 业务组合图谱 | P0 |
| 10 | STRATEGIC_SELECTION | SPACE 矩阵 | space_matrix | 战略定位数据 | 定位分析结果 | P1 |
| 11 | STRATEGIC_SELECTION | 情景规划 | scenario_planning | 趋势数据 | 多情景方案集 | P1 |
| 12 | STRATEGIC_SELECTION | 价值曲线分析 | value_curve_analysis | 竞争数据 | 差异化曲线 | P1 |
| 13 | BUSINESS_MODEL | 价值主张画布 | value_proposition_canvas | 客户痛点数据 | 价值主张地图 | P0 |
| 14 | BUSINESS_MODEL | 商业模式画布 | business_model_canvas | 商业模式数据 | 九宫格画布 | P0 |
| 15 | BUSINESS_MODEL | 破坏性创新模型 | disruptive_innovation_model | 技术/市场数据 | 创新类型判断 | P1 |
| 16 | EXECUTION_MANAGEMENT | BSC 平衡计分卡 | bsc_balanced_scorecard | 战略目标 | 四维度指标 | P0 |
| 17 | EXECUTION_MANAGEMENT | 战略地图 | strategy_map | BSC 指标 | 战略可视化图 | P1 |
| 18 | EXECUTION_MANAGEMENT | 组织设计框架 | organizational_design_framework | 组织架构数据 | 组织匹配建议 | P1 |
| 19 | EXECUTION_MANAGEMENT | 依赖关系图 | dependency_graph | 任务列表 | 依赖关系网络 | P1 |
| 20 | EXECUTION_MANAGEMENT | RACI 矩阵 | raci_matrix | 角色任务数据 | 职责分配矩阵 | P1 |
| 21 | EXECUTION_MANAGEMENT | 甘特图 | gantt_chart | 项目计划 | 进度可视化图 | P1 |
| 22 | EXECUTION_MANAGEMENT | KPI | kpi | 业务目标 | 关键绩效指标 | P0 |
| 23 | EXECUTION_MANAGEMENT | 变革管理模型 | change_management_model | 变革数据 | 变革路径图 | P2 |

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 3-9-semantic-cache](./3-9-semantic-cache.md)

**关键学习/Key Learnings:**
1. **端口升级机制** — `PortRegistry.register()` 对同名端口冲突则抛 `ConflictError`，必须先 `unregister()` 再重新注册
2. **降级策略是非功能性需求的核心** — API 调用失败时返回原始结果，不阻断主流程
3. **异常体系设计** — 展示了异常编码分配和子域注册的完整流程
4. **端口生命周期管理** — SCOPED 适用于有状态端口，SINGLETON 适用于无状态端口
5. **Composition Root 注册模式** — `register_port()` 使用 lambda 工厂函数或字符串延迟加载

**应用到本故事/Applied to This Story:**
- [x] 工具仓储使用 SCOPED 生命周期（每个请求独立实例，避免状态泄漏）
- [x] 工具注册服务使用 SCOPED 生命周期（每次 bootstrap 创建新实例）
- [x] 异常编码从 EXCEPTION_250 开始分配（避开已有编码范围）
- [x] Composition Root 使用字符串延迟加载 `InMemoryToolRepository`
- [x] 工具注册失败时抛出 `ToolAlreadyExistsError`，不静默忽略

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | kimi-k3 (Claude Code) |
| **Version** | create-story workflow v1.0 |
| **Execution Date** | 2026-08-27 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `.claude/skills/bmad-create-story/workflow.md` |
| **Template** | `.claude/skills/bmad-create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `docs/architecture/architecture.md` |
| **核心域设计** | `docs/architecture/sisys-core-domain-design.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/3-9-semantic-cache.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取
- [x] 架构约束从 `architecture.md` 和 `sisys-core-domain-design.md` 提取
- [x] 前一个故事学习经验整合（3-9-semantic-cache）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] 23 种工具清单与架构文档一致
- [x] 端口契约清单与 PortSpec 模式对齐
- [x] 领域异常编码分配完成（EXCEPTION_250/251）

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/4-1-strategic-tool-registration-tools.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/domain/entities/strategic_tool_catalog.py` - 23 种工具元数据常量
- `src/domain/ports/tool_repository.py` - ToolRepositoryPort Protocol
- `src/application/ports/tool_registry_service.py` - ToolRegistryServicePort Protocol
- `src/application/services/tool_registry_service.py` - ToolRegistryService 实现
- `src/infrastructure/storage/inmemory/tool_repository.py` - InMemoryToolRepository 实现
- `src/domain/exceptions/business_exceptions.py` - ToolNotFoundError
- `src/domain/exceptions/conflict_errors.py` - ToolAlreadyExistsError
- `tests/unit/domain/entities/test_strategic_tool_catalog.py` - 工具目录单元测试
- `tests/unit/infrastructure/storage/test_inmemory_tool_repository.py` - 仓储单元测试
- `tests/unit/application/services/test_tool_registry_service.py` - 服务单元测试
- `tests/contracts/test_port_contract_tool.py` - 端口契约测试
- `tests/unit/architecture/test_arch_tool.py` - 架构约束测试
- `tests/integration/test_integration_tool_registration.py` - 集成测试
- `tests/acceptance/test_acceptance_strategic_tool_registration.feature` - Gherkin 场景
- `tests/acceptance/test_acceptance_strategic_tool_registration.py` - BDD 步骤实现

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 4.1 |
| **Story Key** | 4-1-strategic-tool-registration-tools |
| **File** | `_bmad-output/implementation-artifacts/stories/4-1-strategic-tool-registration-tools.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 4: 战略工具箱 |
| **价值组** | 战略工具执行能力 |
| **优先级** | P0-1 |
| **覆盖 FR** | FR-ST-01 |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（9 个 Task，含 Task 0 SDD 规范）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1 ~ AC-4）
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes

> 待代码审查后填写

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| - | - | - | - |

---

### 🔍 代码审查发现 Review Findings

> 待代码审查后填写

**审查日期:** -
**审查模式:** full（Blind Hunter + Edge Case Hunter + Acceptance Auditor）

#### 需决策 Decision Needed

- [ ] - 待填写

#### 已修复 Patch

- [ ] - 待填写

#### 已推迟 Defer

- [ ] - 待填写

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.0.0
**创建日期/Created:** 2026-08-27
**最后更新/Last Updated:** 2026-08-27
**更新说明/Description:**
- v1.0.0: 创建故事文件 — 战略工具注册，Epic 4 首个 P0 故事
