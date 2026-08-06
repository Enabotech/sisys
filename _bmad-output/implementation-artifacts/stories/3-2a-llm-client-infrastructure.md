# Story 3.2a: LLM Client 基础设施

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 系统架构师,
**I want** 系统具备统一 LLM Client 基础设施（端口 + 结构化输出 + 容错机制 + 模型路由集成）,
**So that** 所有需要 LLM 调用的 Story（实体抽取、摘要生成、Agent 推理）复用同一套可靠的基础设施。

### 业务价值

本 Story 是 Epic 3（智能检索与知识发现）的**公共基础设施 Story**，也是 Epic 3 检索流水线中首个 LLM 相关 Story。它为后续所有需要 LLM 调用的 Story（Story 3.2b 实体抽取、Story 3.6 契约化摘要、Story 3.7 检索相关性评估、Story 5.1+ Agent 推理等）提供统一的 LLM 调用能力。

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **统一 LLM 调用端口** | 所有 LLM 调用通过统一端口，隔离具体实现 | `LLMClientPort` 协议定义 + 端口注册 |
| **结构化输出** | 支持 Pydantic Schema 驱动的结构化输出，自动重试修复 | `structured_generate()` 返回验证后的 Pydantic 对象 |
| **容错机制** | 熔断器 + 指数退避重试，防止连锁故障 | Closed→Open→Half-Open 三态转换，3 次重试 |
| **UDMR 路由集成** | 复用 Story 1.17 的 UDMR 路由决策，按 route_type 选择本地/云端模型 | `LLMClient` 接收 `CloudModelConfig` 作为配置 |
| **异常体系** | 统一异常分类，与项目异常体系集成 | LLMAPIError/LLMResponseError/LLMConfigError |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 3: 智能检索与知识发现，Story 3.2a

**前置依赖:** Story 1.17（UDMR 基础路由 ✅ done）— 提供 `CloudModelConfig` 配置模型和路由决策能力

**后续依赖:** Story 3.2b（实体抽取）、Story 3.6（契约化摘要）、Story 3.7（检索相关性评估）、Story 5.3+（Agent 推理）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: LLM 端口契约定义

**Given** 系统需要统一的 LLM 调用抽象
**When** 定义 `LLMClientPort` 协议
**Then** 包含 `generate()` 和 `structured_generate()` 两个核心方法
**And** `LLMConfig` 值对象封装调用参数（api_type、model、endpoint、api_key、temperature、max_tokens、timeout）
**And** `LLMResponse` 值对象封装响应结果（content、finish_reason、usage、model）
**And** 所有领域层定义零外部依赖（仅 Python 标准库 + Protocol）
**And** `structured_generate()` 的 `response_schema` 参数使用 `type[Any]` 而非 `type[BaseModel]`（领域层不依赖 pydantic）

**验证标准/Validation Criteria:**
- [ ] `LLMClientPort` Protocol 定义于 `src/domain/ports/llm_client.py`
- [ ] `LLMConfig` frozen dataclass 定义于同一文件，不包含 `from_cloud_model_config()` 方法（该转换逻辑放在 infrastructure 层）
- [ ] `LLMResponse` frozen dataclass 定义于同一文件
- [ ] `generate(prompt, config?)` — 标准 LLM 文本生成
- [ ] `structured_generate(prompt, response_schema, config?)` — 结构化输出，`response_schema: type[Any]`
- [ ] `close()` — 释放资源
- [ ] 端口注册于 `composition_root.py`，通过 `register_port()` 注册为 `llm_client` 端口

### AC-2: LLM 异常体系

**Given** LLM 调用过程中可能发生多种错误
**When** 定义 LLM 异常类
**Then** 继承项目统一异常层次结构
**And** 分配唯一异常编码

**验证标准/Validation Criteria:**
- [ ] `LLMAPIError`（EXCEPTION_330）— 继承 `ThirdPartyError`，对应 LLM API HTTP 4xx/5xx
- [ ] `LLMResponseError`（EXCEPTION_331）— 继承 `ExternalException`，对应响应解析错误
- [ ] `LLMConfigError`（EXCEPTION_332）— 继承 `ExternalException`，对应配置错误
- [ ] 异常编码在 `_code_ranges.py` 注册，无碰撞
- [ ] 异常在 `__init__.py` 导出，在 `EXCEPTION_HTTP_MAP` 注册

### AC-3: LLM 客户端实现（LiteLLM）

**Given** LLMClientPort 端口已定义
**When** 实现 `LitellmLLMClient`
**Then** 使用 LiteLLM 库调用 LLM API
**And** 支持 `api_type: openai / anthropic / openai_responses` 三种格式
**And** 支持 `config`（单配置）或 `configs`（多配置，用于 UDMR 回退）
**And** 集成 `CircuitBreaker` 熔断器（5 次连续失败 → 断开 30 秒）
**And** 集成 `tenacity` 指数退避重试（3 次：1s → 2s → 4s）
**And** `structured_generate()` 的 `response_schema` 参数类型为 `type[Any]`（领域层不依赖 pydantic）

**验证标准/Validation Criteria:**
- [ ] `LitellmLLMClient` 实现 `LLMClientPort` 位于 `src/infrastructure/external_services/llm/litellm_llm_client.py`
- [ ] `generate()` 方法调用 `litellm.acompletion()`
- [ ] `structured_generate()` 使用 `instructor` 或 LiteLLM 原生 `response_format` 实现 Pydantic Schema 结构化输出
- [ ] 熔断器状态正确转换（Closed→Open→Half-Open→Closed）
- [ ] 重试仅对可恢复错误生效（500/502/503/504/超时/网络故障）
- [ ] 异常映射：httpx/litellm 原始异常 → 领域异常

### AC-4: UDMR 路由集成

**Given** Story 1.17 已提供 UDMR 路由决策和 CloudModelConfig
**When** `LitellmLLMClient` 接收 UDMR 路由结果
**Then** 根据 `route_type` 选择对应的模型配置
**And** 云端优先时使用 `CloudModelConfig` 初始化 LLM 调用
**And** 本地回退时使用本地模型配置
**And** 熔断器状态与 UDMR 健康检查联动

**验证标准/Validation Criteria:**
- [ ] `LitellmLLMClient` 支持 `configs: list[CloudModelConfig]` 多配置模式
- [ ] `_call_with_fallback()` 按 UDMR 路由顺序尝试
- [ ] 云端失败后自动回退到下一个可用配置
- [ ] 回退错误信息传递到 `LLMResponse`

### AC-5: 端口注册与 DI 集成

**Given** 所有组件实现完成
**When** 在 `composition_root.py` 注册
**Then** `llm_client` 端口注册为 SINGLETON
**And** 通过 `Resolver` 可正确解析
**And** 端口契约测试通过

**验证标准/Validation Criteria:**
- [ ] `composition_root.py` 注册 `llm_client` 端口
- [ ] `shutdown()` 中关闭 `llm_client` 的 HTTP 连接池
- [ ] 端口契约测试 `tests/contracts/test_port_contract_llm_client.py` 通过
- [ ] `src/domain/ports/__init__.py` 导出 `LLMClientPort`

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

本 Story **不新增**领域事件。LLM 客户端是基础设施层组件，不产生领域事件。
- （跳过）事件定义位于 `src/domain/events/`

#### 数据模型 (Data Models)

**新建值对象（领域层）：**
- [ ] `LLMConfig` frozen dataclass（`src/domain/ports/llm_client.py`）
  - 字段: `api_type: Literal["openai", "anthropic", "openai_responses"]`
  - `model: str` — 模型名称
  - `endpoint: str | None = None` — API 端点
  - `api_key: str | None = None` — API 密钥
  - `temperature: float = 0.7` — 采样温度
  - `max_tokens: int | None = None` — 最大 Token 数
  - `timeout: float = 600.0` — 请求超时（秒）
  - ⚠️ **设计约束：** `LLMConfig` 是领域层值对象，不引用 `CloudModelConfig`（infrastructure 层）。
    `CloudModelConfig → LLMConfig` 转换逻辑放在 infrastructure 层 `litellm_llm_client.py` 中，
    遵循 `build_cost_calculator()` 模式（infrastructure 层提取原始值，调用 domain 层工厂方法）。
  - `from_env() -> LLMConfig` — 从环境变量构建（用于独立测试）

- [ ] `LLMResponse` frozen dataclass（`src/domain/ports/llm_client.py`）
  - 字段: `content: str` — 生成内容
  - `finish_reason: str | None = None` — 完成原因
  - `usage: dict | None = None` — Token 消耗统计
  - `model: str | None = None` — 实际使用的模型

#### 统一端口定义注册与管理 (Port Contract)

**新建端口：**
- [ ] `LLMClientPort`（`src/domain/ports/llm_client.py`）
  - 方法: `async generate(prompt: str, config: LLMConfig | None = None) -> LLMResponse`
  - 方法: `async structured_generate(prompt: str, response_schema: type[Any], config: LLMConfig | None = None) -> Any`
  - 方法: `async close() -> None`
  - 版本: v1.0.0, owner: foundation-team
  - 端口契约测试: `tests/contracts/test_port_contract_llm_client.py`

**端口契约清单（强制）：**

| 端口名称 | 版本 | Owner | 注册 | 解析 | 契约测试 | 状态 |
|---------|------|-------|------|------|---------|------|
| LLMClientPort | v1.0.0 | foundation-team | 新建 | 新建 | 新建 | **新建** |

#### 领域异常契约 (Domain Exception Contract)

**新建异常类（`src/domain/exceptions/llm_exceptions.py`）：**

| 异常类 | 编码 | 继承 | HTTP 映射 | 说明 |
|--------|------|------|-----------|------|
| `LLMAPIError` | EXCEPTION_330 | `ThirdPartyError` | 502 | LLM API HTTP 4xx/5xx 错误 |
| `LLMResponseError` | EXCEPTION_331 | `ExternalException` | 502 | 响应解析错误（JSON/Pydantic Schema） |
| `LLMConfigError` | EXCEPTION_332 | `ExternalException` | 500 | 配置错误（API Key 缺失、endpoint 无效等） |

**编码分配验证：**
- `external` 子域范围：301-399 ✅
- `embedding` 占用 306-308，`sandbox` 占用 309-319，`ocr` 占用 320-329
- **LLM 分配 330-339** — 紧接 OCR 之后，预留 10 个编码
- 运行 `grep -r "EXCEPTION_33[0-9]" src/domain/exceptions/` 确认无碰撞

- [ ] 归属模块与基类 — LLM 调用属于外部服务，`LLMAPIError` 继承 `ThirdPartyError`，`LLMResponseError`/`LLMConfigError` 直接继承 `ExternalException`
- [ ] 唯一编码分配 — 330/331/332，确认无碰撞
- [ ] 构造器参数设计 — 携带 `model`、`endpoint`、`status_code` 等上下文
- [ ] 编码注册 — 在 `_code_ranges.py` 的 `_CLASS_TO_SUBDOMAIN` 中注册；新增 `llm` 子域范围 (330, 339)
- [ ] 导出完整性 — `__init__.py` + `EXCEPTION_HTTP_MAP`
- [ ] 测试覆盖 — 构造/`to_dict()`/HTTP 映射/编码唯一性

#### 六边形架构约束（必须遵守）

> **执行顺序：** 所有实现 Task 仅可依赖下述层间方向。领域层不得引入任何第三方依赖。

**四层架构定义**
| 层次 | 目录 | 本 Story 职责 |
|------|------|-------------|
| domain | `src/domain/` | LLMClientPort 端口 + LLMConfig/LLMResponse 值对象 + LLM 异常 |
| application | `src/application/` | 无新增（LLM Client 是基础设施，应用层通过端口注入使用） |
| infrastructure | `src/infrastructure/` | LitellmLLMClient 实现 + 熔断器复用 |
| interfaces | `src/interfaces/` | 无新增 |

**依赖方向矩阵**
| 起点 \ 终点 | domain | application | infrastructure |
|------------|--------|-------------|----------------|
| **domain (LLMClientPort)** | — | ✗ 禁止 | ✗ 禁止 |
| **application (消费方)** | ✓ 允许 | — | ✗ 禁止 |
| **infrastructure (LitellmLLMClient)** | ✓ 允许 | ✓ 允许 | — |

**领域层零依赖原则** — `src/domain/ports/llm_client.py` 仅依赖：
- Python 标准库（`dataclasses`, `uuid`, `typing`）
- `typing.Protocol` / `@runtime_checkable`
- 领域值对象（`LLMConfig`, `LLMResponse`）
- 不依赖：`pydantic`, `litellm`, `httpx`, `instructor`, `tenacity`, `CloudModelConfig`

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 功能测试文件：`tests/acceptance/test_acceptance_llm_client.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_llm_client.py`
- [ ] 业务方评审通过
- [ ] 覆盖场景:
  - Happy Path: LLM 文本生成成功
  - Happy Path: 结构化输出（Pydantic Schema）成功
  - Edge Case: 熔断器断开后快速失败
  - Edge Case: 云端不可用时回退本地模型
  - Edge Case: 重试耗尽后抛出异常
  - Edge Case: 配置错误（API Key 缺失）

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
| **TDD 单元测试** | LLMClientPort + LLMConfig + LLMResponse | 端口契约、值对象构造、工厂方法 | `test_llm_client_port.py` | Task 1 |
| **TDD 单元测试** | LLM 异常 | 构造/属性/to_dict()/HTTP 映射 | `test_llm_exceptions.py` | Task 1 |
| **TDD 单元测试** | LitellmLLMClient | generate/structured_generate/熔断器/重试/UDPR 集成 | `test_litellm_llm_client.py` | Task 2 |
| **TDD 单元测试** | LitellmLLMClient 异常映射 | 异常转换正确性 | `test_llm_client_error_mapping.py` | Task 2 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_llm_client.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_llm_client.py` | Task 0 |
| **TDD 契约测试** | LLMClientPort | 端口注册/解析/契约门禁 | `test_port_contract_llm_client.py` | Task 0 |
| **TDD 领域异常测试** | LLM 异常 | 编码唯一性/子域范围 | `test_error_code_uniqueness.py` + `test_code_ranges.py` | Task 1 |
| **SDD 架构验证** | 六边形架构约束 | 依赖方向、零依赖 | `test_arch_llm_client.py` | Task 3 |
| **集成测试** | LLM Client 管线 | 端到端 LLM 调用流程 | `test_integration_llm_client.py` | Task 3 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **领域层覆盖率 ≥90%**（`pytest --cov=src/domain/ports/llm_client.py`）
- [ ] **基础设施层覆盖率 ≥75%**（`pytest --cov=src/infrastructure/external_services/llm/`）
- [ ] **集成测试覆盖率 ≥70%**（`pytest --cov=tests/integration/test_integration_llm_client.py`）

> ⚠️ **骨架 Story 覆盖率豁免：** 本 Story 为基础设施层实现，非骨架 Story，需达到标准覆盖率要求。

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **外部服务隔离** | LLM API 使用 AsyncMock，熔断器使用独立实例 | 真实 API 调用导致失败 |
| **配置隔离** | 每个测试使用独立的 LLMConfig 实例 | 配置污染 |
| **资源唯一性** | 测试数据使用 UUID 等唯一标识符 | ID 冲突 |
| **并行隔离** | 并行测试使用 UUID 前缀隔离资源 | 资源冲突 |
| **BDD async 配合** | BDD 步骤函数用 event_loop.run_until_complete() | context 数据丢失 |

**验证要求：**
- [ ] 并行测试 `poetry run pytest tests/ -n 8` 通过
- [ ] 连续 5 次运行无随机失败
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | LLM 端口契约定义（LLMClientPort/LLMConfig/LLMResponse） | Task 1 | Subtask 1.1-1.3 | `test_llm_client_port.py` |
| AC-2 | LLM 异常体系（LLMAPIError/LLMResponseError/LLMConfigError） | Task 1 | Subtask 1.4-1.6 | `test_llm_exceptions.py` |
| AC-3 | LitellmLLMClient 实现（generate/structured_generate/熔断器/重试） | Task 2 | Subtask 2.1-2.3 | `test_litellm_llm_client.py` |
| AC-3 | 异常映射（httpx/litellm → 领域异常） | Task 2 | Subtask 2.4-2.5 | `test_llm_client_error_mapping.py` |
| AC-4 | UDMR 路由集成（多配置回退、CloudModelConfig 转换） | Task 2 | Subtask 2.6-2.7 | `test_litellm_llm_client.py` |
| AC-5 | 端口注册与 DI 集成（composition_root + 契约测试） | Task 3 | Subtask 3.1-3.3 | `test_port_contract_llm_client.py` |
| AC-5 | 架构约束验证 + 集成测试 | Task 3 | Subtask 3.4-3.6 | `test_arch_llm_client.py` + `test_integration_llm_client.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5

> **目的：** 在进入代码实现前，明确 Schema、API 契约、端口契约、验收标准与六边形架构边界。

- [ ] Subtask 0.1: 定义 LLM 端口契约（LLMClientPort/LLMConfig/LLMResponse）设计
- [ ] Subtask 0.2: 定义 LLM 异常体系设计（LLMAPIError/LLMResponseError/LLMConfigError）
- [ ] Subtask 0.3: 定义 `_code_ranges.py` 新增 `llm` 子域（330-339）
- [ ] Subtask 0.4: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_llm_client.feature`
- [ ] Subtask 0.5: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_llm_client.py`
- [ ] Subtask 0.6: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: 领域层端口 + 值对象 + 异常（领域层）

**关联 AC:** AC-1, AC-2

> **领域层零外部依赖：** 本 Task 所有代码位于 `src/domain/`，仅使用 Python 标准库。
> 禁止导入：pydantic, litellm, httpx, instructor, tenacity 等任何第三方库。

#### TDD 循环 [A]：LLMClientPort + LLMConfig + LLMResponse

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/ports/test_llm_client_port.py`（端口契约 + 值对象构造 + 工厂方法） |
| 🟢 绿 | 实现 `src/domain/ports/llm_client.py`（LLMClientPort + LLMConfig + LLMResponse） |
| 🔄 重构 | 优化类型注解，运行 `ruff` + `mypy` |

- [ ] Subtask 1.1: 🔴 红 — 编写 LLMClientPort 失败测试
  - `LLMConfig` frozen dataclass 构造（所有字段默认值正确）
  - `LLMConfig.from_env()` 从环境变量解析
  - `LLMResponse` frozen dataclass 构造
  - `LLMClientPort` Protocol 结构验证（`generate()` / `structured_generate()` / `close()` 方法签名）
  - `@runtime_checkable` 可用
  - **注意：** `CloudModelConfig → LLMConfig` 转换测试在 Task 2 的 UDMR 集成测试中，不在领域层测试
- [ ] Subtask 1.2: 🟢 绿 — 实现 LLMClientPort + LLMConfig + LLMResponse
- [ ] Subtask 1.3: 🔄 重构 — 优化代码，运行 `ruff` + `mypy`

#### TDD 循环 [B]：LLM 异常体系

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/exceptions/test_llm_exceptions.py`（异常构造 + to_dict + HTTP 映射） |
| 🟢 绿 | 实现 `src/domain/exceptions/llm_exceptions.py`（LLMAPIError/LLMResponseError/LLMConfigError） |
| 🔄 重构 | 更新 `__init__.py` + `_code_ranges.py` + `EXCEPTION_HTTP_MAP`，运行 `ruff` + `mypy` |

- [ ] Subtask 1.4: 🔴 红 — 编写 LLM 异常失败测试
  - `LLMAPIError` 构造（含 model/endpoint/status_code 上下文）
  - `LLMResponseError` 构造（含 model/response 上下文）
  - `LLMConfigError` 构造（含 config_key 上下文）
  - `to_dict()` 序列化正确
  - HTTP 映射正确（330→502, 331→502, 332→500）
  - 编码唯一性（`test_error_code_uniqueness.py` 中确认无碰撞）
  - 子域范围（`test_code_ranges.py` 中新增 llm 子域）
- [ ] Subtask 1.5: 🟢 绿 — 实现 LLM 异常类
  - 创建 `src/domain/exceptions/llm_exceptions.py`
  - 更新 `src/domain/exceptions/__init__.py` 导出
  - 更新 `src/domain/exceptions/_code_ranges.py` 新增 `llm` 子域 (330, 339)
  - 更新 `src/interfaces/api/exception_handlers.py` 的 `EXCEPTION_HTTP_MAP`
- [ ] Subtask 1.6: 🔄 重构 — 运行 `ruff check` + `mypy` + `pytest tests/unit/domain/exceptions/ -v`

**完成标准/Definition of Done:**
- [ ] LLMClientPort + LLMConfig + LLMResponse 实现完成
- [ ] LLM 异常体系实现完成（LLMAPIError/LLMResponseError/LLMConfigError）
- [ ] TDD 循环全部通过
- [ ] 编码无碰撞验证通过
- [ ] 领域层覆盖率≥90%

---

### Task 2: 基础设施层 LLM 客户端实现

**关联 AC:** AC-3, AC-4

> **基础设施层依赖：** 本 Task 代码位于 `src/infrastructure/`，可使用 litellm、httpx、tenacity、instructor 等第三方库。
> **核心模式参考：** `EmbeddingAPIClient`（`embedding_api_client.py`）的 httpx + tenacity + CircuitBreaker 模式。
> **熔断器复用：** 直接复用 `src/infrastructure/external_services/embedding/circuit_breaker.py` 的 `CircuitBreaker` 类。

#### TDD 循环 [A]：LitellmLLMClient — 核心实现

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/external_services/llm/test_litellm_llm_client.py` |
| 🟢 绿 | 实现 `src/infrastructure/external_services/llm/litellm_llm_client.py` |
| 🔄 重构 | 优化容错逻辑，运行 `ruff` + `mypy` |

- [ ] Subtask 2.1: 🔴 红 — 编写 LitellmLLMClient 失败测试
  - **Happy Path:** `generate()` 成功返回 `LLMResponse`
  - **Happy Path:** `structured_generate()` 返回 Pydantic Schema 验证后的对象
  - **熔断器:** Closed → 连续 5 次失败 → Open → 30s 后 → Half-Open → 探测成功 → Closed
  - **熔断器:** Open 状态时快速失败（`CircuitBreakerOpenError` → `ServiceUnavailableError`）
  - **重试:** 500/502/503/504 状态码触发重试（3 次：1s → 2s → 4s）
  - **重试:** 超时触发重试
  - **重试:** 重试耗尽后抛出领域异常
  - **非重试错误:** 400/401/403 不重试（客户端错误）
  - **关闭状态:** 客户端关闭后调用抛出 `ServiceUnavailableError`
  - **配置:** `config` 单配置模式
  - **配置:** `configs` 多配置模式（UDMR 回退）
- [ ] Subtask 2.2: 🟢 绿 — 实现 LitellmLLMClient
  - 核心方法: `generate()`, `structured_generate()`, `close()`
  - 熔断器集成: `before_call()`, `on_success()`, `on_failure()`
  - 重试集成: `tenacity.AsyncRetrying` 指数退避
  - 配置管理: `_build_acompletion_kwargs()` 构建 litellm 参数
  - 多配置回退: `_call_with_fallback()` 按顺序尝试
- [ ] Subtask 2.3: 🔄 重构 — 优化代码，运行 `ruff` + `mypy`

#### TDD 循环 [B]：异常映射

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/external_services/llm/test_llm_client_error_mapping.py` |
| 🟢 绿 | 实现 `LitellmLLMClient._map_llm_error()` 异常映射 |
| 🔄 重构 | 统一异常转换逻辑，运行 `ruff` + `mypy` |

- [ ] Subtask 2.4: 🔴 红 — 编写异常映射失败测试
  - `litellm.APIConnectionError` → `ServiceUnavailableError`
  - `litellm.APITimeoutError` → `TimeoutError`
  - `litellm.AuthenticationError` → `LLMAPIError`（含 status_code=401）
  - `litellm.RateLimitError` → `LLMAPIError`（含 status_code=429）
  - `litellm.BadRequestError` → `LLMAPIError`（含 status_code=400）
  - `litellm.InternalServerError` → `LLMAPIError`（含 status_code=500）
  - JSON 解析错误 → `LLMResponseError`
  - Pydantic Schema 验证错误 → `LLMResponseError`
  - 配置错误（API Key 缺失）→ `LLMConfigError`
- [ ] Subtask 2.5: 🟢 绿 — 实现异常映射
- [ ] Subtask 2.6: 🔄 重构 — 运行 `ruff` + `mypy`

#### TDD 循环 [C]：UDMR 路由集成

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 在 `test_litellm_llm_client.py` 中追加 UDMR 集成测试 |
| 🟢 绿 | 实现 `_call_with_fallback()` 多配置回退逻辑 |
| 🔄 重构 | 优化回退策略，运行 `ruff` + `mypy` |

- [ ] Subtask 2.7: 🔴 红 — 编写 UDMR 集成失败测试
  - `CloudModelConfig` → `LLMConfig` 转换正确
  - 多配置 `configs` 按 UDMR 路由顺序尝试
  - 第一个配置失败时自动回退到第二个配置
  - 所有配置都失败时抛出 `ServiceUnavailableError`
  - 回退原因记录到日志
- [ ] Subtask 2.8: 🟢 绿 — 实现 UDMR 集成
- [ ] Subtask 2.9: 🔄 重构 — 运行 `ruff` + `mypy`

**完成标准/Definition of Done:**
- [ ] LitellmLLMClient 实现完成（generate/structured_generate/close）
- [ ] 熔断器 + 指数退避重试集成完成
- [ ] 异常映射完整（所有 litellm 异常 → 领域异常）
- [ ] UDMR 路由集成完成（多配置回退）
- [ ] TDD 循环全部通过
- [ ] 基础设施层覆盖率≥75%

---

### Task 3: 端口注册 + 架构验证 + 集成测试

**关联 AC:** AC-5

> **性质说明：** 本 Task 包含 DI 注册、端口契约测试、架构约束验证和集成测试。

#### 端口注册与 DI 集成

- [ ] Subtask 3.1: 更新 `src/domain/ports/__init__.py` 导出 `LLMClientPort`、`LLMConfig`、`LLMResponse`
- [ ] Subtask 3.2: 更新 `src/composition_root.py` 注册 `llm_client` 端口
  - `register_port(name="llm_client", version="v1.0.0", interface=LLMClientPort, impl=lambda resolver: LitellmLLMClient(configs=UDMRConfig.from_env().cloud_configs, local_model=UDMRConfig.from_env().local_model, llm_timeout=UDMRConfig.from_env().llm_timeout), ...)`
  - 生命周期: SINGLETON
  - Owner: foundation-team
  - `shutdown()` 中关闭 `llm_client` 的 HTTP 连接池

#### 端口契约测试

- [ ] Subtask 3.3: 创建 `tests/contracts/test_port_contract_llm_client.py`
  - 验证 `llm_client` 端口已注册到 Registry
  - 验证 `Resolver` 可解析 `llm_client`
  - 验证 `LLMClientPort` 方法签名正确

#### 架构验证测试

- [ ] Subtask 3.4: 创建 `tests/unit/architecture/test_arch_llm_client.py`
  - 验证 `src/domain/ports/llm_client.py` 零外部依赖（仅标准库）
  - 验证 `LLMClientPort` 位于领域层
  - 验证 `LitellmLLMClient` 位于基础设施层
  - 验证依赖方向正确（infrastructure → domain）

#### 集成测试

- [ ] Subtask 3.5: 创建 `tests/integration/test_integration_llm_client.py`
  - 端到端：LLM 调用流程（Mock LLM API）
  - 熔断器 + 重试协同工作
  - 多配置回退流程
  - 异常映射链路（litellm 异常 → 领域异常 → HTTP 响应）

**完成标准/Definition of Done:**
- [ ] `composition_root.py` 注册 `llm_client` 端口
- [ ] 端口契约测试通过
- [ ] 所有架构约束测试通过
- [ ] 集成测试通过
- [ ] 领域层零外部依赖

---

### Task 4: 开发结束验收测试

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5

> **性质说明：** 本 Task 是对 Story 收尾阶段的交付物与完成清单进行最终验收。

- [ ] Subtask 4.1: 场景 1 — 验证 `src` 完成清单的逐项确认
  - `src/domain/ports/llm_client.py` — LLMClientPort + LLMConfig + LLMResponse
  - `src/domain/exceptions/llm_exceptions.py` — LLMAPIError/LLMResponseError/LLMConfigError
  - `src/domain/exceptions/__init__.py` — 导出 LLM 异常
  - `src/domain/exceptions/_code_ranges.py` — 新增 llm 子域
  - `src/domain/ports/__init__.py` — 导出 LLMClientPort
  - `src/infrastructure/external_services/llm/litellm_llm_client.py` — LitellmLLMClient
  - `src/infrastructure/external_services/llm/__init__.py` — 导出 LitellmLLMClient
  - `src/composition_root.py` — 注册 llm_client 端口 + shutdown() 关闭
  - `src/interfaces/api/exception_handlers.py` — EXCEPTION_HTTP_MAP 更新
- [ ] Subtask 4.2: 场景 2 — 验证 `tests/unit`、`tests/contracts`、`tests/acceptance` 完成清单
  - `tests/unit/domain/ports/test_llm_client_port.py`
  - `tests/unit/domain/exceptions/test_llm_exceptions.py`
  - `tests/unit/infrastructure/external_services/llm/test_litellm_llm_client.py`
  - `tests/unit/infrastructure/external_services/llm/test_llm_client_error_mapping.py`
  - `tests/unit/architecture/test_arch_llm_client.py`
  - `tests/contracts/test_port_contract_llm_client.py`
  - `tests/integration/test_integration_llm_client.py`
  - `tests/acceptance/test_acceptance_llm_client.feature`
  - `tests/acceptance/test_acceptance_llm_client.py`
- [ ] Subtask 4.3: 运行开发结束验收测试并确认通过
- [ ] Subtask 4.4: 运行 `poetry run pytest --tb=short -q`、`poetry run ruff check src/`、`poetry run mypy src/`

**完成标准/Definition of Done:**
- [ ] `src` 完成清单已逐项验证确认
- [ ] `tests` 完成清单已逐项验证确认
- [ ] 开发结束验收测试通过
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 与 Story 1.17 UDMR 的集成设计

**核心集成点：**

```
UDMR 路由决策（Story 1.17）
    │
    ▼  route_type: "cloud" | "local"
    │  selected_model: str
    │  cloud_configs: list[CloudModelConfig]
    │
    ▼
LitellmLLMClient（本 Story）
    ├─ configs: list[CloudModelConfig]  ← 来自 UDMRConfig
    ├─ config: LLMConfig                ← 单配置模式（from_cloud_model_config）
    │
    ├─ generate() / structured_generate()
    │   ├─ 熔断器检查（before_call）
    │   ├─ 指数退避重试（tenacity）
    │   ├─ LiteLLM.acompletion() 调用
    │   └─ 异常映射（litellm → 领域异常）
    │
    └─ _call_with_fallback()
        ├─ 云端优先（按 UDMR 路由顺序）
        ├─ 云端失败 → 下一个配置
        └─ 全部失败 → 抛出 ServiceUnavailableError
```

**配置流：**
```
UDMRConfig.from_env()
    │
    ├─ .cloud_configs → list[CloudModelConfig]
    │       │
    │       ▼  （转换逻辑在 infrastructure 层 litellm_llm_client.py 中）
    │       遵循 build_cost_calculator() 模式：提取原始值，调用领域层构造
    │   LLMConfig(api_type=cfg.api_type, model=cfg.model, endpoint=cfg.endpoint, ...)
    │
    └─ .local_model → str
            │
            ▼
    LLMConfig(model="qwen2.5:7b", api_type="openai", endpoint="http://localhost:11434")
```

**异常流：**
```
litellm.APITimeoutError
    │
    ▼  _map_llm_error()
TimeoutError (EXCEPTION_302)
    │
    ▼ 熔断器记录
CircuitBreaker.on_failure()
    │
    ▼ 重试（3次）
tenacity.AsyncRetrying
    │
    ▼ 重试耗尽
最终异常抛出 → 调用方处理
```

**异常映射表：**

| LiteLLM 异常 | 领域异常 | HTTP 状态码 | 可重试 |
|-------------|---------|------------|--------|
| `APIConnectionError` | `ServiceUnavailableError` (303) | 503 | ✅ 是 |
| `APITimeoutError` | `TimeoutError` (302) | 504 | ✅ 是 |
| `InternalServerError` | `LLMAPIError` (330) | 502 | ✅ 是（500/502/503/504 可重试） |
| `RateLimitError` | `LLMAPIError` (330) | 429 | ❌ 否（429 客户端限流，非服务端可恢复错误） |
| `AuthenticationError` | `LLMAPIError` (330) | 401 | ❌ 否（401 客户端认证错误） |
| `BadRequestError` | `LLMAPIError` (330) | 400 | ❌ 否（400 客户端请求错误） |
| JSON 解析错误 | `LLMResponseError` (331) | 502 | ❌ 否 |
| Schema 验证错误 | `LLMResponseError` (331) | 502 | ❌ 否 |
| API Key 缺失 | `LLMConfigError` (332) | 500 | ❌ 否 |

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（端口与适配器）
- **设计约束:**
  - 领域层零外部依赖（`LLMClientPort` 仅使用 Python 标准库）
  - 依赖倒置：领域层定义 `LLMClientPort`，基础设施层实现 `LitellmLLMClient`
  - UDMR 路由集成：`LitellmLLMClient` 消费 UDMR 路由决策，不自行决策
- **技术栈:**
  - Python 3.11+
  - LiteLLM ^1.28.0（pyproject.toml 已声明）
  - httpx（pyproject.toml 已声明）
  - tenacity（⚠️ 当前为传递依赖，需要升级为直接依赖 — `embedding_api_client.py` 已使用，Story 3.2a 也需使用）
  - instructor（⚠️ 当前未在 pyproject.toml 中声明。实施时需选择：① 加入 instructor 依赖，或 ② 改用 LiteLLM 原生 `response_format` 参数实现结构化输出）

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) §4.3, [`interface-design.md`](../../_bmad-output/planning-artifacts/interface-design.md) §8

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **LiteLLM 统一调用 + 本地熔断器/重试** | 实现简单、LiteLLM 已声明依赖、支持 100+ 模型 | 额外抽象层 | ✅ 8/10 |
| 裸 httpx 直接调用各 API | 最轻量、无额外依赖 | 需要自实现多 API 格式适配 | 5/10 |
| LangChain LLM 封装 | 生态丰富 | 重量级、与 LangGraph 耦合 | 4/10 |

### 已有可复用组件

| 组件 | 文件路径 | 说明 |
|------|---------|------|
| CircuitBreaker | `src/infrastructure/external_services/embedding/circuit_breaker.py` | 通用熔断器，可直接复用 |
| CloudModelConfig | `src/infrastructure/config/udmr.py` | UDMR 云端模型配置 |
| UDMRConfig | `src/infrastructure/config/udmr.py` | UDMR 全局配置 |
| HealthCheckPort | `src/domain/ports/health_check.py` | 健康检查端口（已注册） |
| CloudHealthChecker | `src/infrastructure/external_services/llm/cloud_health_checker.py` | 云端健康检查（已注册） |
| EmbeddingAPIClient | `src/infrastructure/external_services/embedding/embedding_api_client.py` | 参考模式：httpx + tenacity + CircuitBreaker |

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── domain/
│   │   ├── ports/
│   │   │   ├── __init__.py                    # 更新：导出 LLMClientPort
│   │   │   └── llm_client.py                  # 新建：LLMClientPort + LLMConfig + LLMResponse
│   │   └── exceptions/
│   │       ├── __init__.py                    # 更新：导出 LLM 异常
│   │       ├── _code_ranges.py                # 更新：新增 llm 子域 (330-339)
│   │       └── llm_exceptions.py              # 新建：LLMAPIError/LLMResponseError/LLMConfigError
│   ├── infrastructure/
│   │   └── external_services/
│   │       └── llm/
│   │           ├── __init__.py                # 更新：导出 LitellmLLMClient
│   │           └── litellm_llm_client.py      # 新建：LitellmLLMClient 实现
│   ├── interfaces/
│   │   └── api/
│   │       └── exception_handlers.py           # 更新：EXCEPTION_HTTP_MAP 新增 LLM 异常
│   └── composition_root.py                    # 更新：注册 llm_client 端口 + shutdown()
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   │   ├── ports/
│   │   │   │   └── test_llm_client_port.py    # 新建：端口 + 值对象测试
│   │   │   └── exceptions/
│   │   │       └── test_llm_exceptions.py      # 新建：LLM 异常测试
│   │   └── infrastructure/
│   │       └── external_services/
│   │           └── llm/
│   │               ├── test_litellm_llm_client.py      # 新建：客户端核心测试
│   │               └── test_llm_client_error_mapping.py # 新建：异常映射测试
│   ├── contracts/
│   │   └── test_port_contract_llm_client.py   # 新建：端口契约测试
│   ├── integration/
│   │   └── test_integration_llm_client.py     # 新建：集成测试
│   └── acceptance/
│       ├── test_acceptance_llm_client.feature # 新建：Gherkin 验收测试
│       └── test_acceptance_llm_client.py      # 新建：BDD 步骤实现
```

### 环境变量设计

本 Story 复用 Story 1.17 的 UDMR 环境变量配置，无需新增环境变量。

```bash
# UDMR 配置（Story 1.17）— 已定义，本 Story 直接使用
export UDMR_ENABLED=true
export UDMR_LOCAL_FIRST=false
export UDMR_LOCAL_MODEL=qwen2.5:7b
export UDMR_LLM_TIMEOUT=600
export UDMR_HEALTHCHECK_INTERVAL=300

# 云端模型配置（Story 1.17）— 已定义，本 Story 用于 LLM 调用
export UDMR_CLOUD_0_ENABLED=true
export UDMR_CLOUD_0_API_TYPE=openai
export UDMR_CLOUD_0_ENDPOINT=https://api.deepseek.com
export UDMR_CLOUD_0_API_KEY=""
export UDMR_CLOUD_0_MODEL=deepseek-v4-flash
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 1.17: UDMR 基础路由](./1-17-udmr-basic-routing.md)

**关键学习/Key Learnings:**
1. **EmbeddingAPIClient 模式** — `embedding_api_client.py` 的 httpx + tenacity + CircuitBreaker 模式是 LLM Client 的完美参考模板。尤其是 `_is_retryable_http_error()` 判断逻辑和 `_encode()` 的分层容错设计（熔断器检查 → 指数退避重试 → 响应结构校验）
2. **CircuitBreaker 复用** — `circuit_breaker.py` 是通用组件，可直接复用，LLM Client 不需要重新实现
3. **CloudModelConfig 复用** — Story 1.17 已定义了 `CloudModelConfig` frozen dataclass。LLM Client 在 infrastructure 层通过提取原始值（api_type、model、endpoint、api_key 等）来构造 `LLMConfig` 领域值对象，遵循 `build_cost_calculator()` 模式（infrastructure 层提取原始值 → 调用 domain 层构造器），不违反领域层零依赖原则
4. **DI 注册模式** — composition_root.py 使用 `register_port()` + lambda resolver 模式，LLM Client 应遵循相同模式
5. **异常体系规范** — 项目异常体系有严格的编码分配和注册流程，新增 LLM 异常必须遵循 `_code_ranges.py` + `__init__.py` + `EXCEPTION_HTTP_MAP` 完整流程
6. **领域层零依赖** — 端口定义（`LLMClientPort`）和值对象（`LLMConfig`/`LLMResponse`）仅使用 Python 标准库

**应用到本故事/Applied to This Story:**
- [ ] 遵循 `EmbeddingAPIClient` 的 httpx + tenacity + CircuitBreaker 容错模式
- [ ] 直接复用 `CircuitBreaker` 类（不重新实现）
- [ ] `CloudModelConfig → LLMConfig` 转换在 infrastructure 层实现（遵循 `build_cost_calculator()` 模式）
- [ ] 通过 `register_port()` 注册 `llm_client` 端口
- [ ] 严格遵循异常编码注册流程
- [ ] `structured_generate()` 使用 `type[Any]` 而非 `type[BaseModel]`（领域层零依赖）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (create-story workflow) |
| **Version** | create-story workflow v1.0 |
| **Execution Date** | 2026-08-06 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **接口设计** | `docs/architecture/interface-design.md` |
| **异常设计** | `docs/architecture/sisys-uni-exception-design.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/1-17-udmr-basic-routing.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取
- [x] 架构约束从 `architecture.md` 提取
- [x] 前一个故事学习经验整合（Story 1.17 UDMR）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] 已有可复用组件清单明确
- [x] 与 Story 1.17 UDMR 集成设计完整
- [x] 端口契约清单定义完成
- [x] 异常体系设计完成（编码 330-332）

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/3-2a-llm-client-infrastructure.md`

**待创建的文件 (Dev Story 实施):**
- `src/domain/ports/llm_client.py` — LLMClientPort + LLMConfig + LLMResponse
- `src/domain/exceptions/llm_exceptions.py` — LLMAPIError/LLMResponseError/LLMConfigError
- `src/infrastructure/external_services/llm/litellm_llm_client.py` — LitellmLLMClient 实现
- `tests/unit/domain/ports/test_llm_client_port.py` — 端口单元测试
- `tests/unit/domain/exceptions/test_llm_exceptions.py` — 异常单元测试
- `tests/unit/infrastructure/external_services/llm/test_litellm_llm_client.py` — 客户端单元测试
- `tests/unit/infrastructure/external_services/llm/test_llm_client_error_mapping.py` — 异常映射测试
- `tests/unit/architecture/test_arch_llm_client.py` — 架构约束测试
- `tests/contracts/test_port_contract_llm_client.py` — 端口契约测试
- `tests/integration/test_integration_llm_client.py` — 集成测试
- `tests/acceptance/test_acceptance_llm_client.feature` — Gherkin 验收测试
- `tests/acceptance/test_acceptance_llm_client.py` — BDD 步骤实现

**更新的文件/Updated Files:**
- `src/domain/ports/__init__.py` — 导出 LLMClientPort/LLMConfig/LLMResponse
- `src/domain/exceptions/__init__.py` — 导出 LLM 异常
- `src/domain/exceptions/_code_ranges.py` — 新增 llm 子域 (330-339)
- `src/infrastructure/external_services/llm/__init__.py` — 导出 LitellmLLMClient
- `src/interfaces/api/exception_handlers.py` — EXCEPTION_HTTP_MAP 新增 LLM 异常
- `src/composition_root.py` — 注册 llm_client 端口 + shutdown() 关闭

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 3.2a |
| **Story Key** | 3-2a-llm-client-infrastructure |
| **File** | `_bmad-output/implementation-artifacts/stories/3-2a-llm-client-infrastructure.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 3: 智能检索与知识发现 |
| **价值组** | 智能检索与溯源 |
| **优先级** | P0-1c（公共基础设施，关键路径） |
| **覆盖 FR** | FR-SR-02（实体抽取基础），FR-CP-05（UDMR 路由集成） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成
2. [x] All acceptance criteria specified 所有验收标准已定义
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [x] Sprint status synced to `ready-for-dev`

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

## 🔧 文档审查修复 Docs Review Fixes [Round 1]

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | `structured_generate()` 的 `response_schema: type[BaseModel]` 违反领域层零外部依赖原则 | **P0** | 改为 `type[Any]`，类型安全由基础设施层 `instructor`/LiteLLM 保证 |
| 2 | `LLMConfig.from_cloud_model_config()` 在 domain 层引用 infrastructure 层的 `CloudModelConfig`，违反依赖方向 | **P0** | 移除 domain 层的 `from_cloud_model_config()` 方法。转换逻辑移至 infrastructure 层 `litellm_llm_client.py` 中，遵循 `build_cost_calculator()` 模式 |
| 3 | `tenacity` 未在 `pyproject.toml` 中声明（仅传递依赖），但 Story 3.2a 直接依赖它 | **P1** | 标注为待升级的直接依赖，实施时需在 `pyproject.toml` 中显式声明 |
| 4 | `instructor` 未在 `pyproject.toml` 中声明，但 AC-3 要求使用 `instructor` 实现结构化输出 | **P1** | 修正 AC-3 描述，增加"instructor 或 LiteLLM 原生 response_format"两种方案，实施时决策 |
| 5 | 异常映射表中 `RateLimitError`/`AuthenticationError`/`BadRequestError` 的 HTTP 状态码误标为 502 | **P1** | 修正为实际 HTTP 状态码（429/401/400），仅保留最终抛出的领域异常映射为 502 |
| 6 | architecture.md 中规划的 LLM 目录结构（多适配器模式）与 Story 3.2a（单一 LiteLLM 客户端）不一致 | **P2** | 保留 Story 3.2a 设计，添加说明标注与 architecture.md 的差异 |

---

**故事版本/Story Version:** v1.1.0
**创建日期/Created:** 2026-08-06
**最后更新/Last Updated:** 2026-08-06
**更新说明/Description:**
- v1.1.0: Round 1 审查修复 — P0: `structured_generate()` 签名改为 `type[Any]` 避免领域层依赖 pydantic；P0: 移除 `from_cloud_model_config()` 方法，转换逻辑移至 infrastructure 层；P1: 修正异常映射表 HTTP 状态码；P1: 标注 tenacity 和 instructor 依赖状态；P2: 标注与 architecture.md 目录结构差异
- v1.0.0: 创建故事文件

<!-- 仅用作跟踪故事文件模板修订记录，故事开发时[务必删除]此段 -->
