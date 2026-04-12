# Story 1-1: 六边形架构骨架

**Status:** `ready-for-dev`

> **Note:** SDD 规范验证为必选项，TDD 测试生成可参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md)。运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 系统架构师,
**I want** 实现领域驱动六边形架构骨架,
**So that** 领域逻辑与技术实现隔离，支持独立演进和测试。

### 业务价值

这是 Epic 1 的第一个故事，也是整个系统的技术基础。六边形架构的正确实施将：
- 确保领域层零外部依赖（FR-AR-01, FR-AR-04）
- 为后续所有 Story 提供清晰的代码组织结构
- 建立依赖倒置原则，使技术栈可独立替换
- 满足等保 2.0 和 SOX 合规对架构清晰度的要求

### 用户故事详细叙述

系统架构师需要创建一个清晰的代码骨架，使得：
1. 领域层（Domain）仅依赖 Python 标准库，不包含任何外部框架
2. 应用层（Application）编排领域逻辑，不直接依赖基础设施
3. 接口层（Interfaces）处理 CLI/API/事件监听输入
4. 基础设施层（Infrastructure）提供所有外部依赖的具体实现
5. 依赖方向严格遵循：基础设施层 → 应用层 → 领域层

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 六边形架构目录结构创建

**Given** 新项目初始化完成
**When** 创建领域层、应用层、接口层、基础设施层目录结构
**Then** 各层目录正确创建，包含 `__init__.py` 文件
**And** 领域层仅依赖 Python 标准库，不包含任何外部框架导入
**And** 各层之间依赖方向正确（基础设施层→应用层→领域层）

**验证标准/Validation Criteria:**
- [ ] `src/domain/` 目录存在，包含子目录：entities, value_objects, repositories, events, services
- [ ] `src/domain/value_objects/` 目录存在（用于值对象定义）
- [ ] `src/domain/exceptions.py` 文件存在（领域异常定义）
- [ ] `src/application/` 目录存在，包含子目录：use_cases, commands, queries, dto
- [ ] `src/application/commands/` 目录存在（CQRS 命令定义）
- [ ] `src/application/queries/` 目录存在（CQRS 查询定义）
- [ ] `src/interfaces/` 目录存在，可导入 application 和 domain 层
- [ ] `src/interfaces/__init__.py` 仅导出公开 CLI 命令和 API 路由，不暴露内部实现
- [ ] `src/infrastructure/` 目录存在，可导入所有层
- [ ] 依赖方向测试通过（使用 ast 模块扫描导入语句）

---

### AC-2: 领域层零依赖约束验证（FR-AR-01）

**Given** 领域层代码已创建
**When** 运行领域层零依赖测试
**Then** 领域层中没有任何文件导入外部框架（FastAPI、SQLAlchemy、Pydantic、Redis 等）
**And** 领域层仅使用 Python 标准库（typing、dataclasses、enum、uuid、datetime、abc 等）
**And** 测试报告输出领域层导入清单

**⚠️ 重要架构决策（P0-4 修复）：**
- **领域事件必须使用标准库定义**：`DomainEvent` 基类使用 `dataclass` + `uuid.UUID` + `datetime.datetime` 定义
- **Pydantic 仅用于边界层**：应用层/基础设施层使用 Pydantic V2 做校验、序列化/反序列化
- **领域事件与传输 DTO 必须分离**：领域事件是领域概念，传输 DTO 是技术概念
- **转换方式**：使用 `pydantic.TypeAdapter` 做无样板转换（`domain_event → event_dto → json`）

**验证标准/Validation Criteria:**
- [ ] 领域层导入扫描器工作正常，输出所有 import 语句
- [ ] 确认无外部框架导入（fastapi, sqlalchemy, pydantic, redis, qdrant, neo4j, minio, rabbitmq, prefect, langgraph 等）
- [ ] 测试失败时输出清晰的违规导入信息（文件路径、行号、违规导入名）
- [ ] `DomainEvent` 基类使用纯标准库定义（dataclass）
- [ ] 应用层定义 `EventDTO` 类骨架（使用 Pydantic V2，**占位实现**）
- [ ] EventDTO 仅包含基础字段：event_id, event_type, timestamp
- [ ] 提供 `from_domain_event()` 和 `to_domain_event()` 转换方法签名（**不实现完整序列化逻辑**）

---

### AC-3: 核心领域实体骨架 - StrategicPlan

**Given** 领域层目录已创建
**When** 定义 `StrategicPlan` 领域实体
**Then** 实体类使用纯 Python 实现（`dataclass` 或普通类）
**And** 实体包含基础属性：id、name、status、created_at、updated_at
**And** 实体包含业务方法：validate()、to_dict()、from_dict()
**And** 实体测试通过

**验证标准/Validation Criteria:**
- [ ] `StrategicPlan` 类可实例化
- [ ] validate() 方法验证必填字段
- [ ] to_dict()/from_dict() 支持序列化/反序列化
- [ ] 单元测试覆盖率≥90%

---

### AC-4: 领域异常骨架

**Given** 领域层实体已定义
**When** 定义领域异常类
**Then** 异常类使用纯 Python 实现（继承 `Exception`）
**And** 异常类位于 `src/domain/exceptions.py`
**And** 包含基础异常类型：`DomainError`、`ValidationError`、`ConcurrencyError`
**And** 异常类不依赖任何外部库

**验证标准/Validation Criteria:**
- [ ] `DomainError`、`ValidationError`、`ConcurrencyError` 可正确抛出和捕获
- [ ] 异常消息清晰表达错误原因
- [ ] 异常类测试通过

---

### AC-5: 值对象骨架

**Given** 领域层实体已定义
**When** 定义值对象
**Then** 值对象位于 `src/domain/value_objects/`
**And** 值对象特征：不可变、通过属性相等、无独立标识
**And** 值对象不依赖任何外部库
**And** 骨架 Story 使用 Python `enum.Enum` 实现简单值对象（如 `PlanStatus`）

**值对象实现策略（骨架 Story 简化）：**
- 使用 `enum.Enum` 定义简单值对象（`PlanStatus`: DRAFT, ACTIVE, REVIEW, APPROVED, ARCHIVED）
- 展示值对象核心特征：不可变、通过属性相等
- 完整值对象模式（如 Money、DateRange）在后续 Story 添加

**验证标准/Validation Criteria:**
- [ ] `PlanStatus` enum 定义正确
- [ ] 枚举值不可变
- [ ] 枚举相等基于值（非身份）
- [ ] `__hash__` 与 `__eq__` 一致（相同值产生相同哈希）
- [ ] 值对象可作为字典键和集合元素
- [ ] 值对象类型注解完整（支持 MyPy 检查）
- [ ] 值对象序列化/反序列化支持（to_dict/from_dict）
- [ ] 领域层测试覆盖值对象行为

---

### AC-6: 仓储接口骨架 - Repository Pattern（FR-AR-04）

**Given** 领域层实体已定义
**When** 定义仓储接口（抽象基类或 Protocol）
**Then** 仓储接口定义在领域层（`src/domain/repositories/`）
**And** 接口使用 ABC 或 Protocol 定义，不含具体实现
**And** 接口方法包含：save()、find_by_id()、find_all()、delete()
**And** 接口不依赖任何具体存储技术

**验证标准/Validation Criteria:**
- [ ] `PlanRepository` 接口定义在领域层
- [ ] 接口方法签名正确（save(entity)、find_by_id(id)、find_all(criteria)、delete(id)）
- [ ] 接口无具体实现代码（仅定义 abstract/Protocol 方法）
- [ ] 接口测试验证多态行为
- [ ] 接口契约测试：验证实现类正确实现接口方法
- [ ] 使用 `typing.runtime_checkable` 或 `abc.ABC` 验证实现符合性
- [ ] 契约测试失败场景：
  - [ ] 实现类缺少接口方法 → 测试失败
  - [ ] 实现类方法签名不匹配 → 测试失败
  - [ ] 实现类返回类型错误 → 测试失败
  - [ ] 实现类抛出未声明异常 → 测试失败

---

### AC-7: 领域服务接口骨架

**Given** 领域层实体和仓储接口已定义
**When** 定义领域服务接口
**Then** 接口定义在 `src/domain/services/`
**And** 接口使用 ABC 或 Protocol 定义
**And** 接口不包含具体实现
**And** 接口方法仅使用领域实体和值对象作为参数/返回值

**领域服务职责边界：**
- ✅ 处理跨多个领域实体的业务逻辑
- ✅ 执行领域规则验证（不适合放在单个实体内）
- ✅ 编排领域对象协作（不编排用例流程）
- ❌ 编排用例流程（这是应用层职责）
- ❌ 处理用户交互（这是接口层职责）
- ❌ 直接调用外部服务（必须通过接口）

**示例：PlanService 应处理：**
- 战略规划完整性校验（跨 Plan + Checkpoint + Task）
- BLM 流程阶段转换规则验证
- 战略依赖分析

**验证标准/Validation Criteria:**
- [ ] 至少定义一个示例领域服务接口（如 `PlanService`）
- [ ] 接口方法不依赖任何外部框架
- [ ] 接口方法仅使用领域实体/值对象作为参数/返回值
- [ ] 接口测试验证多态行为

---

### AC-8: 依赖注入容器骨架

**Given** 各层接口已定义
**When** 创建依赖注入容器
**Then** 使用依赖注入模式（DI Container 或手动组合根）
**And** 组合根（Composition Root）在应用入口（`src/cli.py` 为主入口，`src/main.py` 为可选 FastAPI 入口）组装依赖
**And** 接口与实现分离（领域层定义接口，基础设施层提供实现）
**And** 依赖注入配置可切换（如切换数据库、缓存实现）
**And** 本 Story 仅创建骨架，不绑定具体基础设施实现

**验证标准/Validation Criteria:**
- [ ] DI Container 类可实例化
- [ ] 组合根结构正确（`src/cli.py` 为主入口）
- [ ] 预留注册接口定义完整（`register_repositories()`, `register_services()` 等）
- [ ] DI 骨架测试通过
- [ ] 不在本 Story 绑定任何具体基础设施实现

---

### AC-9: 架构约束自动化测试

**Given** 代码骨架已创建
**When** 运行架构约束测试套件
**Then** 所有架构约束测试通过
**And** 测试输出清晰的架构合规报告

**测试覆盖:**
- [ ] 领域层零依赖测试（FR-AR-01）
- [ ] 依赖方向测试（infra → app → domain）
- [ ] 导入扫描测试（使用 ast 模块）
- [ ] 仓储接口位置测试（必须在领域层）
- [ ] 基础设施实现位置测试（必须在基础设施层）
- [ ] 循环依赖检测（使用 `pylint --disable=all --enable=cyclic-import`）

**架构合规报告格式：**
- 控制台输出：清晰列出所有检查项和结果（✅/❌）
- 可选：生成 JSON 报告（`tests/reports/architecture-compliance.json`）
- CI/CD 集成：输出 JUnit XML 格式（`tests/reports/architecture-compliance.xml`，CI 已集成 ruff + mypy）

**报告内容必须包含：**
- 检查项名称
- 检查结果（通过/失败）
- 失败详情（文件路径、行号、违规描述）
- 检查时间戳

**验证标准/Validation Criteria:**
- [ ] `tests/unit/architecture/test_hexagonal_architecture.py` 存在并全部通过
- [ ] `tests/unit/domain/test_strategic_plan.py` 存在并全部通过
- [ ] `tests/unit/domain/test_domain_event.py` 存在并全部通过
- [ ] `tests/unit/domain/test_exceptions.py` 存在并全部通过
- [ ] 测试输出包含架构合规报告（控制台 + 可选 JSON/XML）
- [ ] 任何架构违规（含循环依赖）都会导致测试失败
- [ ] 输出循环依赖链（如 A→B→C→A）

---

### AC-10: Makefile 和开发工作流

**Given** 项目骨架已创建
**When** 运行 Makefile 命令
**Then** `make setup` 安装所有开发依赖
**And** `make lint` 运行 ruff 检查
**And** `make type-check` 运行 mypy 检查
**And** `make test` 运行 pytest 并生成覆盖率报告
**And** `make test-architecture` 单独运行架构约束测试
**And** `make dev` 启动开发服务器

**验证标准/Validation Criteria:**
- [ ] 所有 Makefile 命令可执行
- [ ] `make test` 输出覆盖率报告（HTML + XML）
- [ ] `make test-architecture` 单独运行架构测试
- [ ] 预提交 hooks 配置正确

---

## 🏗️ SDD+TDD 融合开发

> 遵循 **SDD 规范驱动** + **TDD 测试驱动** 双轮开发模式。参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 了解完整的红 - 绿 - 重构循环。

### SDD 规范定义（Step 1）

#### 领域事件 Schema (Domain Events)
- [ ] 事件定义位于 `src/domain/events/`
- [ ] Pydantic 模型验证通过
- [ ] 事件命名符合规范（`[Aggregate][EventName]`，如 `UserCreated`）

#### API 契约 (API Contract)
- [ ] OpenAPI 定义位于 `docs/api/openapi.yaml`
- [ ] 契约测试通过（`tests/contract/test_api_contract.py`）
- [ ] API 版本管理正确（`/api/v1/[resource]`）

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_story_1_1.feature`
- [ ] 业务方评审通过
- [ ] 所有场景覆盖（Happy Path + Edge Cases）

---

### TDD 红 - 绿 - 重构循环（Step 2-4）

#### 红阶段 - 编写失败测试
- [ ] 根据验收标准编写测试初稿
- [ ] 验证测试失败（确认测试有效）
- [ ] 测试命名清晰表达业务意图

#### 绿阶段 - 最小实现
- [ ] 编写刚好让测试通过的代码
- [ ] 不追求完美，先跑通流程

#### 重构阶段 - 优化代码
- [ ] 保持测试通过的前提下优化代码
- [ ] 应用设计模式/架构原则
- [ ] 运行代码质量工具（ruff/black/mypy）

---

### 测试要求与质量门禁

#### 层测试要求
| 测试项 | 验证内容 | 测试文件 |
|--------|----------|----------|
| 领域层零依赖 | 领域层无外部框架导入 | `test_hexagonal_architecture.py` |
| 依赖方向 | infra→app→domain 正确 | `test_hexagonal_architecture.py` |
| 导入扫描 | 使用 ast 扫描所有 import | `test_hexagonal_architecture.py` |
| 领域实体 | StrategicPlan CRUD + 序列化 | `test_strategic_plan.py` |
| 仓储接口 | 接口定义正确，无实现 | `test_repository_interface.py` |
| 依赖注入 | DI 容器组装正确 | `test_dependency_injection.py` |

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **领域层覆盖率 ≥90%**（`pytest --cov=src/domain`）- **P1 阻断门禁**
- [ ] **应用层覆盖率 ≥85%**（`pytest --cov=src/application`）- **P1 阻断门禁**
- [ ] **集成测试覆盖率 ≥70%**（`pytest --cov=tests/integration`）
- [ ] **关键路径覆盖率 100%**（所有分支覆盖）

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试文件结构
| 测试类型 | 文件路径 | 说明 |
|---------|----------|------|
| 单元测试 | `tests/unit/architecture/test_hexagonal_architecture.py` | 架构约束测试 |
| 单元测试 | `tests/unit/domain/test_strategic_plan.py` | 领域实体测试 |
| 单元测试 | `tests/unit/domain/test_repository_interface.py` | 仓储接口测试 |
| 单元测试 | `tests/unit/application/test_dependency_injection.py` | 依赖注入测试 |
| 集成测试 | `tests/integration/test_layer_dependencies.py` | 层间依赖集成测试 |
| 验收测试 | `tests/acceptance/test_story_1_1.feature` | 业务价值验收测试 |

> **实施指南:** 参考 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md) 和 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md)

---

## 📋 Tasks / Subtasks 任务分解

### Task 1: 创建六边形架构目录结构

**关联 AC:** AC-1

- [ ] Subtask 1.1: 创建 `src/domain/` 目录及子目录（entities, value_objects, repositories, events, services）
- [ ] Subtask 1.2: 创建 `src/domain/exceptions.py`（领域异常定义）
- [ ] Subtask 1.3: 创建 `src/application/` 目录及子目录（use_cases, commands, queries, dto, di）
- [ ] Subtask 1.4: 创建 `src/interfaces/` 目录及子目录（cli, api, event_listeners）
- [ ] Subtask 1.5: 创建 `src/infrastructure/` 目录及子目录（database, cache, event_bus, external_services, storage）
- [ ] Subtask 1.6: 为所有目录创建 `__init__.py` 文件
- [ ] Subtask 1.7: `src/interfaces/__init__.py` 仅导出公开 CLI 命令和 API 路由

**完成标准/Definition of Done:**
- [ ] 所有目录和 `__init__.py` 文件创建
- [ ] 目录结构符合六边形架构规范
- [ ] 无循环依赖

---

### Task 2: 实现领域层代码（FR-AR-01）

**关联 AC:** AC-2, AC-3, AC-4, AC-5, AC-6, AC-7

> **注意：** 本 Task 仅关注**代码实现**，不编写测试（测试由 Task 5 负责）。

- [ ] Subtask 2.1: 创建 `StrategicPlan` 领域实体（纯 Python dataclass）
- [ ] Subtask 2.2: 创建 `DomainEvent` 事件基类（**纯标准库 dataclass**，不使用 Pydantic）
- [ ] Subtask 2.3: 创建领域异常类（`DomainError`, `ValidationError`, `ConcurrencyError`，继承 `Exception`）
- [ ] Subtask 2.4: 创建示例值对象（`PlanStatus` enum，展示值对象特征）
- [ ] Subtask 2.5: 创建 `PlanRepository` 仓储接口（ABC/Protocol）
- [ ] Subtask 2.6: 创建示例领域服务接口（如 `PlanService`）
- [ ] Subtask 2.7: 创建应用层 `EventDTO` 类骨架（使用 Pydantic V2，**占位实现**）

**完成标准/Definition of Done:**
- [ ] 领域实体和接口定义完整
- [ ] 零依赖测试通过
- [ ] 依赖方向测试通过
- [ ] 领域层覆盖率≥90%

---

### Task 3: 创建依赖注入骨架

**关联 AC:** AC-8

> **注意：** 作为"骨架" Story，本 Task 仅创建 DI 容器结构和组合根框架，
> 不绑定具体实现（基础设施层实现将在 Story 1.4-1.8 完成后添加）。

- [ ] Subtask 3.1: 创建 DI Container 类骨架（`src/application/di/container.py`）
- [ ] Subtask 3.2: 定义组合根结构（`src/cli.py` 作为主入口，`src/main.py` 作为可选 FastAPI 入口）
- [ ] Subtask 3.3: 为后续 Story 预留注册接口（`register_repositories()`, `register_services()` 等占位方法）
- [ ] Subtask 3.4: 编写 DI 骨架测试（验证容器可创建、注册接口可调用）

**完成标准/Definition of Done:**
- [ ] DI Container 类可实例化
- [ ] 组合根结构正确（`src/cli.py` 为主入口）
- [ ] 预留注册接口定义完整
- [ ] DI 骨架测试通过
- [ ] 不在本 Story 绑定任何具体基础设施实现

---

### Task 4: 创建 Makefile 和开发工作流

**关联 AC:** AC-10

- [ ] Subtask 4.1: 创建 Makefile（setup, lint, type-check, test, test-architecture, dev 命令）
- [ ] Subtask 4.2: 配置 pre-commit hooks
- [ ] Subtask 4.3: 配置测试工具（pytest.ini 或 pyproject.toml `[tool.pytest.ini_options]`）
- [ ] Subtask 4.4: 配置代码检查（ruff.toml 或 pyproject.toml `[tool.ruff]`）
- [ ] Subtask 4.5: 配置类型检查（mypy.ini 或 pyproject.toml `[tool.mypy]`）

**完成标准/Definition of Done:**
- [ ] 所有 Makefile 命令可执行
- [ ] pre-commit hooks 工作正常
- [ ] 代码质量工具配置正确
- [ ] 配置文件不重复（每个工具仅在一个位置配置）

---

### Task 5: 编写架构约束测试套件

**关联 AC:** AC-9

> **注意：** 本 Task 负责**所有架构约束测试**的编写和执行。
> Task 2 负责代码实现，Task 5 负责测试验证。

- [ ] Subtask 5.1: 创建 `tests/unit/architecture/test_hexagonal_architecture.py`
- [ ] Subtask 5.2: 实现 ast 导入扫描器（扫描所有 Python 文件的 import 语句）
- [ ] Subtask 5.3: 实现依赖方向验证器（验证 infra→app→domain）
- [ ] Subtask 5.4: 实现领域层零依赖验证器（检查无外部框架导入）
- [ ] Subtask 5.5: 安装并配置循环依赖检测工具（`pylint --disable=all --enable=cyclic-import`）
- [ ] Subtask 5.6: 实现架构合规报告生成器（控制台输出 + 可选 JSON/XML）
- [ ] Subtask 5.7: 运行完整测试套件并生成报告
- [ ] Subtask 5.8: 验证测试输出循环依赖链（如 A→B→C→A）

**完成标准/Definition of Done:**
- [ ] 所有架构约束测试通过
- [ ] 测试输出清晰的合规报告
- [ ] 任何架构违规都会导致测试失败

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（Ports and Adapters）+ 依赖倒置原则
- **设计约束:**
  - 领域层零外部依赖：仅使用 Python 标准库（typing、dataclasses、enum、uuid、datetime、abc 等）
  - **领域事件使用标准库定义**：`DomainEvent` 基类使用 `dataclass`，不使用 Pydantic
  - **Pydantic 仅用于边界层**：应用层/基础设施层使用 Pydantic V2 做校验、序列化/反序列化
  - **领域事件与传输 DTO 分离**：领域事件是领域概念，传输 DTO 是技术概念，使用 `TypeAdapter` 转换
  - 依赖方向严格遵循：基础设施层 → 应用层 → 领域层
  - 仓储接口定义在领域层，实现在基础设施层
  - 组合根在应用入口组装所有依赖
- **技术栈:**
  - Python 3.11+
  - FastAPI 0.104+（接口层，不在领域层）
  - Typer 0.24+（CLI 接口）
  - SQLAlchemy 2.0+（基础设施层）
  - Pydantic V2（应用层 DTO 验证，**不用于领域层**）
  - pytest + pytest-cov（测试框架）
  - ruff + mypy（代码质量工具）

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) - 决策 1 (ADR-001)

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **六边形架构** | 领域逻辑隔离、技术栈独立演进、测试友好 | 初期复杂度高 | ✅ 9/10 |
| 分层架构 | 简单直观 | 领域逻辑泄露、演进困难 | 6/10 |
| 微服务架构 | 独立部署 | 运维复杂度高、不适合 MVP | 5/10 |

**决策理由：**
1. 企业战略规划系统核心复杂度在于领域逻辑（BLM/BEM 模型、23 种战略工具、7 类 Agent 角色）
2. 需要满足 SOX/ISO27001 合规要求，领域逻辑必须与技术实现隔离
3. 支持长期演进，技术栈可独立替换

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── domain/                          # 领域层（零外部依赖）
│   │   ├── __init__.py
│   │   ├── entities/
│   │   │   ├── __init__.py
│   │   │   └── strategic_plan.py        # StrategicPlan 实体
│   │   ├── value_objects/               # 值对象定义
│   │   │   └── __init__.py
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   └── plan_repository.py       # PlanRepository 接口
│   │   ├── events/
│   │   │   ├── __init__.py
│   │   │   └── domain_event.py          # DomainEvent 基类（标准库 dataclass）
│   │   ├── services/
│   │   │   └── __init__.py
│   │   └── exceptions.py                # 领域异常（DomainError, ValidationError, ConcurrencyError）
│   ├── application/                     # 应用层
│   │   ├── __init__.py
│   │   ├── use_cases/
│   │   ├── commands/                    # CQRS 命令定义
│   │   │   └── __init__.py
│   │   ├── queries/                     # CQRS 查询定义
│   │   │   └── __init__.py
│   │   ├── dto/
│   │   │   ├── __init__.py
│   │   │   └── event_dto.py             # EventDTO（Pydantic V2，用于序列化/反序列化）
│   │   └── di/
│   │       └── container.py             # 依赖注入容器（骨架）
│   ├── interfaces/                      # 接口层
│   │   ├── __init__.py                  # 仅导出公开 CLI 命令和 API 路由
│   │   ├── cli/
│   │   ├── api/
│   │   └── event_listeners/
│   ├── infrastructure/                  # 基础设施层
│   │   ├── __init__.py
│   │   ├── database/                    # PostgreSQL 实现
│   │   ├── cache/                       # Redis 实现
│   │   ├── event_bus/                   # RabbitMQ + Redis 实现
│   │   ├── storage/                     # 五层存储实现
│   │   └── external_services/           # 外部服务适配器
│   ├── cli.py                           # 主入口（Typer CLI，组合根）
│   └── main.py                          # 可选入口（FastAPI，V1+ 启用）
├── tests/
│   ├── unit/
│   │   ├── architecture/
│   │   │   └── test_hexagonal_architecture.py  # 架构约束测试
│   │   ├── domain/
│   │   │   ├── test_strategic_plan.py          # 领域实体测试
│   │   │   ├── test_domain_event.py            # 领域事件测试
│   │   │   ├── test_exceptions.py              # 领域异常测试
│   │   │   └── test_repository_interface.py    # 仓储接口测试
│   │   └── application/
│   │       └── test_dependency_injection.py    # DI 测试
│   ├── integration/
│   │   └── test_layer_dependencies.py           # 层间集成测试
│   └── acceptance/
│       └── test_story_1_1.feature               # 业务验收测试
├── docs/
│   └── architecture/
├── Makefile
├── pyproject.toml
├── ruff.toml
├── mypy.ini
└── pytest.ini
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** Epic 0（开发基础设施）已全部完成

**关键学习/Key Learnings:**
1. **Epic 0 已完成所有开发基础设施**：K3S 集群、Gitea 代码托管、Harbor 镜像仓库、ArgoCD 持续部署、CI/CD Pipeline 模板、Gitea Runner 配置
2. **产品交付系统大部分完成**：Windows/Mac/Linux 安装包已实现，auto-diagnose-fix 和 config-wizard 已 ready-for-dev
3. **测试框架已搭建**：pytest 配置、Fixture 系统、Mock 框架已完成（Story 0.3）
4. **CI/CD 质量门禁已配置**：Ruff、MyPy、覆盖率门禁、安全扫描均已配置（Story 0.9）
5. **SDD+TDD 融合模式文档完善**：`docs/developer/sdd-tdd-fusion-guide.md`、`docs/developer/sdd-tdd-checklist.md` 已就绪

**应用到本故事/Applied to This Story:**
- [x] 复用已有的 pytest 配置（无需重新搭建）
- [x] 复用 CI/CD 质量门禁（ruff、mypy、覆盖率门禁）
- [x] 遵循 SDD+TDD 融合模式指南
- [x] 依赖 Epic 0 已部署的开发基础设施
- [x] 作为 Epic 1 的第一个故事，为后续所有 Story 奠定基础

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Qwen Code |
| **Version** | create-story workflow v6.2.0 |
| **Execution Date** | 2026-04-12 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Instructions** | `_bmad/bmm/workflows/4-implementation/create-story/instructions.xml` |
| **Template** | `_bmad/bmm/workflows/4-implementation/create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **PRD** | `_bmad-output/planning-artifacts/prd.md` |
| **UX 设计** | `_bmad-output/planning-artifacts/ux-design-specification.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/0-18-user-friendly-config-wizard.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取
- [x] 架构约束从 `architecture.md` 提取
- [x] 前一个故事学习经验整合
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/1-1-hexagonal-architecture-skeleton.md`

**待创建的文件/To Be Created (Dev Story 实施):**

**领域层（零外部依赖）：**
- `src/domain/entities/strategic_plan.py` - StrategicPlan 领域实体
- `src/domain/value_objects/plan_status.py` - PlanStatus 值对象（示例）
- `src/domain/repositories/plan_repository.py` - PlanRepository 接口
- `src/domain/events/domain_event.py` - DomainEvent 基类（**标准库 dataclass**）
- `src/domain/services/plan_service.py` - PlanService 接口（示例领域服务）
- `src/domain/exceptions.py` - 领域异常（DomainError, ValidationError, ConcurrencyError）

**应用层：**
- `src/application/di/container.py` - 依赖注入容器（骨架）
- `src/application/dto/event_dto.py` - EventDTO（**Pydantic V2**，用于序列化/反序列化）
- `src/application/commands/__init__.py` - CQRS 命令定义（占位）
- `src/application/queries/__init__.py` - CQRS 查询定义（占位）

**接口层：**
- `src/interfaces/__init__.py` - 仅导出公开 CLI 命令和 API 路由
- `src/cli.py` - 主入口（Typer CLI，组合根）
- `src/main.py` - 可选入口（FastAPI，V1+ 启用）

**基础设施层：**
- `src/infrastructure/storage/__init__.py` - 五层存储实现（占位）

**测试文件：**
- `tests/unit/architecture/test_hexagonal_architecture.py` - 架构约束测试
- `tests/unit/domain/test_strategic_plan.py` - 领域实体测试
- `tests/unit/domain/test_domain_event.py` - 领域事件测试
- `tests/unit/domain/test_exceptions.py` - 领域异常测试
- `tests/unit/domain/test_value_objects.py` - 值对象测试（含哈希/序列化）
- `tests/unit/domain/test_plan_repository.py` - 仓储接口测试（含契约测试失败场景）
- `tests/unit/domain/test_plan_service.py` - 领域服务接口测试
- `tests/unit/application/test_dependency_injection.py` - DI 测试
- `tests/integration/test_layer_dependencies.py` - 层间依赖集成测试
- `tests/acceptance/test_story_1_1.feature` - 业务验收测试
- `tests/reports/architecture-compliance.json` - 架构合规报告（JSON）
- `tests/reports/architecture-compliance.xml` - 架构合规报告（JUnit XML）

**配置文件：**
- `Makefile` - 开发工作流命令
- `pyproject.toml` - 项目配置（可能包含工具配置）
- `ruff.toml` 或 `pyproject.toml [tool.ruff]` - Ruff 配置
- `mypy.ini` 或 `pyproject.toml [tool.mypy]` - MyPy 配置
- `pytest.ini` 或 `pyproject.toml [tool.pytest]` - Pytest 配置

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 1.1 |
| **Story Key** | 1-1-hexagonal-architecture-skeleton |
| **File** | `_bmad-output/implementation-artifacts/stories/1-1-hexagonal-architecture-skeleton.md` |
| **Status** | `ready-for-dev` |
| **Epic** | Epic 1: 企业级架构基础与合规 |
| **价值组** | 价值组 2: 架构基础与事件驱动 |
| **优先级** | P0-1（Epic 1 的第一个 Story，基础依赖） |
| **覆盖 FR** | FR-AR-01（领域层零依赖）、FR-AR-04（仓储模式） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成
2. [x] All acceptance criteria specified 所有验收标准已定义（10 个独立 AC）
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [x] Sprint status synced to `ready-for-dev`
6. [x] P0 问题修复完成：
   - P0-1: 补充 `value_objects` 子目录
   - P0-2: 补充 `commands/` 和 `queries/` 子目录（CQRS 模式）
   - P0-3: 修复 pyproject.toml 重复配置引用
   - P0-4: DomainEvent 使用标准库定义，Pydantic 仅用于边界层
7. [x] P1 改进完成：
   - P1-1: `interfaces/__init__.py` 仅导出公开 API
   - P1-2: 补充领域异常定义（`exceptions.py`）
   - P1-3: 明确组合根位置（`cli.py` 为主入口）
   - P1-4: 增加 CI/CD 集成要求章节
   - P1-5: Task 3 改为依赖注入骨架实现
8. [x] 第一性原理分析修复完成：
   - AC-4: 领域异常骨架（独立 AC）
   - AC-5: 值对象骨架（独立 AC，使用 enum 简化）
   - AC-7: 领域服务接口骨架（独立 AC，增加职责边界）
   - AC-6: 增加接口契约测试失败场景
   - AC-9: 增加循环依赖检测（指定 pylint）
9. [x] 代码审查角斗场修复完成：
   - AC-7: 增加领域服务职责边界说明（✅ 处理跨实体逻辑，❌ 编排用例流程）
   - AC-5: 明确使用 enum 实现值对象（骨架 Story 简化）
   - Task 2 和 Task 5 分离职责（Task 2 写代码，Task 5 写测试）
   - AC-2: EventDTO 改为占位实现（仅基础字段 + 方法签名）
   - AC-9: 明确架构合规报告格式（控制台 + JSON/XML，CI 已集成 ruff + mypy）
   - AC-5: 增加值对象哈希/序列化测试
   - AC-6: 增加接口契约测试失败场景
   - AC-9/Task 5: 指定循环依赖检测工具（pylint）

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] Review the comprehensive story in this file
- [ ] Run `dev-story` 开始实施
- [ ] Run `code-review` 进行代码审查
- [ ] Optional: If Test Architect module installed, run `/bmad:tea:automate` after `dev-story` to generate guardrail tests

### CI/CD 集成要求

- [ ] 架构约束测试在 CI/CD 阶段 2（单元测试）**优先运行**
- [ ] 架构违规导致 CI/CD 立即失败（**P0 阻断门禁**）
- [ ] `make test-architecture` 命令在 CI/CD 中可调用
- [ ] 架构合规报告输出到 CI/CD 构建日志

---

**Story 1.1 是 Epic 1 的基础 Story，也是整个系统的架构基石。实施时需严格遵循六边形架构原则，确保领域层零依赖和正确的依赖方向。**
