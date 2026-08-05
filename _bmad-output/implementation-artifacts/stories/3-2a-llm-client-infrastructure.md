# Story 3-2a: LLM Client 基础设施

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 系统架构师,
**I want** 系统具备统一 LLM Client 基础设施（领域端口 + litellm 多厂商调用 + 结构化输出 + 熔断 + 重试 + 异常映射）,
**So that** 所有需要 LLM 调用的 Story（实体抽取、摘要生成、Agent 推理）复用同一套可靠的基础设施，并与 UDMR 框架（Story 1.17）无缝衔接。

### 业务价值

Story 3-2a 是 Epic 3（智能检索与知识发现）的**公共基础设施**，优先级 P0-1c。本 Story 为 Epic 3 及后续 Epic 的所有 LLM 调用提供统一的调用入口和容错机制。

**与 UDMR 框架的关系（关键架构衔接）：**

```
Story 1.17 (已完成)                      Story 3.2a (本 Story)                  Story 3.2b/3.6 等 (调用方)
┌─────────────────────┐            ┌──────────────────────────┐            ┌──────────────────┐
│ UDMRService         │            │ LLMClientPort            │            │ EntityExtractor  │
│ ├ L1 合规检查        │ ──决定用──→ │ ├ structured_generate()   │←──调用───→ │ SummaryGenerator │
│ ├ L2 - (Epic 11)    │  哪个模型   │ ├ litellm + Pydantic      │            │ RelevanceEval    │
│ ├ L3 静态路由 ←───── │ ───配置───→ │ ├ 熔断器 + 重试          │            │ AgentReasoning   │
│ └ RoutingDecided     │            │ └ 异常映射                │            └──────────────────┘
│                      │            │                          │
│ CloudModelConfig ───→│ ──转换───→ │ LLMConfig (领域层值对象)   │
│ (基础设施层 frozen)    │            │ (领域层 frozen)           │
└─────────────────────┘            └──────────────────────────┘
```

> **⚠️ 架构角色澄清：**
> - **Story 1.17 (UDMR)** = **路由层**：决定用哪个模型（本地 vs 云端，哪个云端模型）。已完成。
> - **Story 3.2a (LLM Client)** = **执行层**：实际执行 LLM API 调用。本 Story 交付。
> - UDMR 产出 `CloudModelConfig`（选定模型 + endpoint + api_key），LLMClient 消费此配置执行实际调用。
> - MVP 阶段 UDMR 为带外模式（仅审计日志），LLMClientPort 也可独立配置使用（直接环境变量），两种配置方式并存。

**核心交付：**
- **领域端口**：`LLMClientPort` — 统一 LLM 调用抽象，支持 `structured_generate()`（结构化输出）和 `generate()`（自由文本）
- **配置模型**：`LLMConfig` — 领域层值对象（`@dataclass(frozen=True)`），支持从 `CloudModelConfig` 转换和从环境变量构造
- **多厂商支持**：通过 litellm 统一网关，支持 `openai`/`anthropic`/`openai_responses` 三种 api_type（SBOM Story 1.17 的 LLM API 兼容性调研）
- **基础设施实现**：`LitellmLLMClient` — 实现 `LLMClientPort`，litellm + Pydantic JSON Mode 结构化输出
- **容错机制**：参考 `EmbeddingAPIClient` [Source: src/infrastructure/external_services/embedding/embedding_api_client.py] — 熔断器（连续5次失败断开30秒）+ 指数退避重试（3次：1s→2s→4s）
- **异常体系**：新增 LLM 专属异常 — `LLMAPIError`（EXCEPTION_330）/ `LLMResponseError`（EXCEPTION_331）/ `LLMConfigError`（EXCEPTION_332）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: LLMConfig 领域值对象（复用 CloudModelConfig）

**Given** Story 1.17 已交付 `CloudModelConfig`（frozen dataclass，位于 `src/infrastructure/config/udmr.py`）
**And** 领域层零外部依赖约束
**When** 定义 `LLMConfig`（`src/domain/ports/llm_client.py`）
**Then** `LLMConfig` 为 `@dataclass(frozen=True)`
**And** 字段为 `CloudModelConfig` 的领域层镜像：`api_type` / `model` / `endpoint` / `api_key` / `temperature` / `max_tokens` / `timeout`
**And** 支持类方法 `from_cloud_model_config(c: CloudModelConfig, timeout: float = 30.0) -> LLMConfig` 从 UDMR 配置转换
**And** 支持类方法 `from_env() -> LLMConfig` 从独立环境变量构造（`LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` 等）
**And** `from_env()` 在缺失 `api_key` 或 `endpoint+model` 时抛出 `LLMConfigError`（EXCEPTION_332）
**And** 领域层零外部依赖（dataclass/typing 为标准库）

**验证标准/Validation Criteria:**
- [ ] `LLMConfig` 位于 `src/domain/ports/llm_client.py`
- [ ] 字段列表：`api_type: Literal["openai", "anthropic", "openai_responses"] = "openai"` / `model: str = ""` / `endpoint: str = ""` / `api_key: str = ""` / `temperature: float = 0.7` / `max_tokens: int | None = None` / `timeout: float = 30.0`
- [ ] `from_cloud_model_config()` 仅复制字段，不引入基础设施层依赖（类型通过参数传入）
- [ ] `from_env()` 读取 `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` / `LLM_API_TYPE` / `LLM_MAX_TOKENS` / `LLM_TEMPERATURE` / `LLM_TIMEOUT`
- [ ] LLMConfigError 位于 `src/domain/exceptions/llm_exceptions.py`，继承 `ConfigurationError`（EXCEPTION_332）

### AC-2: LLMClientPort 端口定义（领域层）

**Given** 领域层需要抽象 LLM 调用能力
**When** 定义 `LLMClientPort` 协议
**Then** 端口位于 `src/domain/ports/llm_client.py`（与 LLMConfig 同文件）
**And** 包含两个核心方法：
  - `structured_generate(prompt: str, response_schema: type, config: LLMConfig | None = None) -> LLMResponse`
  - `generate(prompt: str, config: LLMConfig | None = None) -> LLMResponse`（自由文本，无需 schema 验证）
**And** 支持 `close()` 释放资源
**And** 支持 `async with` 上下文管理器
**And** `LLMResponse` 为 `@dataclass(frozen=True)`（`content: str` / `finish_reason: str` / `usage: dict[str, int | None]` / `model: str`）
**And** `usage` 字段对标 litellm 返回结构：`{"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}`（字段值可为 None 表示单厂商未返回）

**验证标准/Validation Criteria:**
- [ ] `LLMClientPort` 定义为 `@runtime_checkable` Protocol
- [ ] 方法命名不绑定特定 LLM 厂商术语
- [ ] `LLMResponse` 领域层零外部依赖

### AC-3: LitellmLLMClient 基础设施实现

**Given** LLM API endpoint 已配置（通过 `LLMConfig` 或 `CloudModelConfig`）
**When** 调用 `LitellmLLMClient.structured_generate(prompt, response_schema, config)`
**Then** 使用 litellm `acompletion` API 以 `response_format={"type": "json_object", "schema": ...}` 模式调用
**And** 返回的 JSON 通过 `response_schema.model_validate_json()` 验证（Pydantic Schema 约束）
**And** 支持三种 api_type：`openai`（直接传递）/ `anthropic`（system 提取 + max_tokens 注入 + 认证适配）/ `openai_responses`（增量流式处理 + 状态管理）
**And** api_type 适配逻辑参考 Story 1.17 Dev Notes 中的 "统一抽象层架构" 和 "Anthropic 格式关键差异" [Source: _bmad-output/implementation-artifacts/stories/1-17-udmr-basic-routing.md §Anthropic 格式关键差异]
**And** 熔断器（连续 5 次失败断开 30 秒）保护
**And** 指数退避重试（3 次：1s→2s→4s，白名单模式：仅 `{500, 502, 503, 504}` + `httpx.TimeoutException` + `httpx.TransportError` 可重试）
**And** 所有其他异常（包括 4xx 客户端错误、Pydantic 验证失败、网络不可达等）一律不重试，直接映射为领域异常
**And** 对标 `EmbeddingAPIClient._is_retryable_http_error` 的白名单策略 [Source: embedding_api_client.py:51-66]
**And** `close()` 释放 httpx 客户端资源
**And** 构造参数支持 `config: LLMConfig | None` / `circuit_breaker: CircuitBreaker | None` / `retry_max_attempts: int = 3` 等

**验证标准/Validation Criteria:**
- [ ] `LitellmLLMClient` 位于 `src/infrastructure/external_services/llm/litellm_llm_client.py`
- [ ] 显式实现 `LLMClientPort` 协议
- [ ] 容错模式参考 `EmbeddingAPIClient`（`_is_retryable_http_error` → `_is_retryable_llm_error`）
- [ ] 熔断器由 `LitellmLLMClient` 内部构造 `CircuitBreaker(name="llm")`，对标 `EmbeddingAPIClient` 的私有构造模式
- [ ] 重试使用 `tenacity.AsyncRetrying`（与 EmbeddingAPIClient 一致）
- [ ] `_map_llm_error()` 内联异常映射（**对标 EmbeddingAPIClient 的内联 `_map_exception` 模式**，不使用 `ErrorMapper` 外部映射）
- [ ] 支持 `async with` 上下文管理器

### AC-4: LLM 专属异常体系

**Given** LLM API 调用可能产生多种错误类型
**When** 映射 LLM 原生错误到领域异常
**Then** 新增以下领域异常：

| 异常类型 | 编码 | 继承 | HTTP | 使用场景 |
|---------|------|------|------|----------|
| `LLMAPIError` | EXCEPTION_330 | `ThirdPartyError` | 502 | LLM API 传输层错误（429 速率限制/401 认证失败/500+ 服务端错误） |
| `LLMResponseError` | EXCEPTION_331 | `ThirdPartyError` | 502 | LLM API 响应格式/内容错误（400 context_length/invalid_request / JSON 不匹配 Schema） |
| `LLMConfigError` | EXCEPTION_332 | `ConfigurationError` | 500 | LLM 配置错误（缺少 api_key/endpoint/model，api_type 非法） |

**并复用已有异常：**

| 异常类型 | 编码 | 使用场景 |
|---------|------|----------|
| `TimeoutError` | EXCEPTION_302 | LLM API 超时（复用已有，不新增） |
| `ServiceUnavailableError` | EXCEPTION_303 | 熔断器已断开（复用已有，不新增） |
| `NetworkError` | EXCEPTION_102 | 网络连接错误（复用已有，不新增） |

**验证标准/Validation Criteria:**
- [ ] `LLMAPIError` 构造器接受 `retry_after: float | None` / `endpoint: str | None` / `http_status: int | None` 可选参数
- [ ] `LLMResponseError` 构造器接受 `schema_type: str | None` / `raw_content: str | None` 可选参数
- [ ] 遵循 `sisys-uni-exception-design.md §3.12` 三阶段注册清单（设计 A1-A6 / 实现 B1-B7 / 验证 C1-C7）
- [ ] 更新 `_code_ranges.py` 新增 `llm` 子域（330–339）
- [ ] EXCEPTION_HTTP_MAP 显式声明映射
- [ ] 编码唯一性 + 子域范围测试通过

### AC-5: Composition Root 注册

**Given** LLM Client 基础设施已实现
**When** 在 `src/composition_root.py` 注册
**Then** `llm_client` 端口注册为 SINGLETON（全局唯一，缓存 httpx 连接池）
**And** 熔断器由 `LitellmLLMClient` 内部构造（`CircuitBreaker(name="llm")`），**不做独立端口注册**（对标 `EmbeddingAPIClient` 模式：熔断器是其内部私有组件 [Source: src/infrastructure/external_services/embedding/embedding_api_client.py:118-123]）
**And** `LLMConfig` 通过 lambda 工厂注入：
  - 优先从 `UDMRConfig.from_env()` 的第一个 enabled 云端配置转换（`LLMConfig.from_cloud_model_config(first_enabled_cloud, timeout=config.llm_timeout)`）
  - 如无云端配置，从 `LLMConfig.from_env()` 独立环境变量构造
**And** 现有测试全部保持通过（无回归）

**验证标准/Validation Criteria:**
- [ ] `llm_client` 端口名：`llm_client`，version: `v1.0.0`，owner: `search-team`
- [ ] 生命周期：`SINGLETON`
- [ ] 熔断器**不作为独立端口注册**（对标 embedding 模式：私有构造，不暴露到 PortRegistry）
- [ ] 端口契约测试同步更新

### AC-6: 验收测试

**Given** LLM API 可访问
**When** 调用 `llm_client.structured_generate(prompt, response_schema, config)`
**Then** 返回验证通过的 `LLMResponse`
**And** Happy Path + 以下边缘情况通过测试：
- API Key 无效（401）→ `LLMAPIError`（context={"http_status": 401, "endpoint": ...})
- 速率限制（429）→ `LLMAPIError`（context={"retry_after": ...})
- 上下文过长（400）→ `LLMResponseError`
- 服务端错误（5xx）→ 重试后抛出 `LLMAPIError`
- 熔断器断开 → 快速失败（`ServiceUnavailableError`）
- 无效的 JSON 响应 → `LLMResponseError`（response 不匹配 schema）
- URL 错误 → `LLMConfigError`

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [x] LLM Client 基础设施为纯查询操作，不产生领域事件

#### 数据模型 (Data Models)
- [ ] **新增** `LLMConfig` dataclass（`src/domain/ports/llm_client.py`）：
  - 字段：`api_type: Literal["openai", "anthropic", "openai_responses"] = "openai"` / `model: str = ""` / `endpoint: str = ""` / `api_key: str = ""` / `temperature: float = 0.7` / `max_tokens: int | None = None` / `timeout: float = 30.0`
  - 类方法 `from_cloud_model_config(c: CloudModelConfig, timeout: float = 30.0) -> LLMConfig`
  - 类方法 `from_env() -> LLMConfig`
  - **关键设计决策：`LLMConfig` 是 `CloudModelConfig`（基础设施层 frozen dataclass）的领域层镜像** — 字段一致但定义在领域层，确保领域层零外部依赖
- [ ] **新增** `LLMResponse` dataclass（`src/domain/ports/llm_client.py`）：
  - 字段：`content: str` / `finish_reason: str` / `usage: dict[str, int | None]` / `model: str`
  - `frozen=True`（不可变）

#### 统一端口定义注册与管理 (Port Contract)
- [ ] **新增** `LLMClientPort`（`src/domain/ports/llm_client.py`）：
  - `@runtime_checkable` Protocol
  - `structured_generate(prompt: str, response_schema: type, config: LLMConfig | None = None) -> LLMResponse`
  - `generate(prompt: str, config: LLMConfig | None = None) -> LLMResponse`
  - `close() -> None`
- [ ] **端口注册** — 在 `src/composition_root.py` 中注册 `llm_client` 和 `llm_circuit_breaker`
- [ ] **端口契约门禁**（`src/domain/ports/contract_gate.py`）：新端口变更通过兼容性检查
- [ ] **端口契约测试**（`tests/contracts/test_port_contract_llm_client.py`）

**端口契约清单：**

| 端口名称 | 版本 | 接口 | 实现模块 | 生命周期 | Owner |
|---------|------|------|----------|----------|-------|
| `llm_client` | v1.0.0 | `LLMClientPort` | `LitellmLLMClient` | SINGLETON | search-team |

> **⚠️ 熔断器不作为独立端口注册**：对标 `EmbeddingAPIClient` 模式（`CircuitBreaker` 为其内部私有组件 [Source: embedding_api_client.py:118-123]），`LitellmLLMClient` 在构造器中自行创建 `CircuitBreaker(name="llm")`，不暴露到 PortRegistry。

#### 领域异常契约 (Domain Exception Contract)

> **策略：新增 LLM 子域异常（EXCEPTION_330–339）**，遵循 `sisys-uni-exception-design.md §3.12` 三阶段注册清单。编码遵循 `_code_ranges.py` 的 `CODE_RANGES` 表。
> **⚠️ 编码选择理由：** OCR 子域已占用 320–329（`OCRConnectionError`=320, `OCRProcessingError`=321），external 大范围 301–399 中 330–339 为空闲区间。

**新增异常清单：**

| 异常类型 | 编码 | 继承 | HTTP | 关键 context 字段 |
|---------|------|------|------|------------------|
| `LLMAPIError` | EXCEPTION_330 | `ThirdPartyError` | 502 | `http_status`, `endpoint`, `retry_after` |
| `LLMResponseError` | EXCEPTION_331 | `ThirdPartyError` | 502 | `schema_type`, `raw_content`（截断至500字符） |
| `LLMConfigError` | EXCEPTION_332 | `ConfigurationError` | 500 | `missing_fields`, `invalid_value` |

**设计决策：**
- 不新增 `LLMRateLimitError`、`LLMAuthenticationError` 等细粒度异常 — 通过 `LLMAPIError` 的 `context` 字典携带差异化信息，降低异常类爆炸风险
- 不新增 `LLMTimeoutError` — 复用 `TimeoutError`（EXCEPTION_302），语义一致
- `LLMConfigError` 继承 `ConfigurationError` 而非 `ExternalException` — 配置错误应在启动时捕获，属于系统配置问题

#### 六边形架构约束（必须遵守）
> **执行顺序：** 所有实现 Task 仅可依赖下述层间方向。领域层不得引入任何第三方依赖。

**四层架构定义**
| 层次 | 目录 | 职责 |
|------|------|------|
| domain | `src/domain/` | 核心业务逻辑，零外部依赖 |
| application | `src/application/` | 用例编排 |
| interfaces | `src/interfaces/` | 适配器 |
| infrastructure | `src/infrastructure/` | 技术实现 |

**领域层零依赖原则**
- 领域层（`src/domain/`）仅使用 Python 标准库
- 禁止导入 pydantic（Pydantic Schema 仅作为 `type` 参数传入，领域层不实例化）
- 禁止导入 litellm / httpx / tenacity

**依赖方向矩阵**
| 起点 \ 终点         | domain | application | interfaces | infrastructure |
|--------------------|--------|-------------|------------|----------------|
| **domain**         | —      | ✗ 禁止      | ✗ 禁止     | ✗ 禁止         |
| **application**    | ✓ 允许 | —           | ✗ 禁止     | ✗ 禁止         |
| **interfaces**     | ✓ 允许 | ✓ 允许      | —          | ✗ 禁止         |
| **infrastructure** | ✓ 允许 | ✓ 允许      | ✗ 禁止     | —              |

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_acceptance_llm_client.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_llm_client.py`
- [ ] 覆盖场景（Happy Path + Edge Cases）：
  - 结构化输出（Pydantic Schema 验证通过）
  - 自由文本生成（无 Schema 验证）
  - API Key 无效（401 → `LLMAPIError`）
  - 速率限制（429 → `LLMAPIError`）
  - 上下文过长（400 → `LLMResponseError`）
  - 服务端错误（503 → 重试后异常）
  - 配置错误（url 不合法 → `LLMConfigError`）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证）

---

### TDD 循环约束（适用于每个 Task）

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败，且失败原因符合预期 |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🔄 重构** | 优化代码（保持测试通过） | `ruff check` + `mypy` + `pytest` 全部通过 |

---

### 测试分类与归属

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | LLMConfig | from_env / from_cloud_model_config / 异常 | `test_llm_config.py` | Task 1 |
| **TDD 单元测试** | LitellmLLMClient | structured_generate / generate / 重试 / 熔断 / 异常映射 / close | `test_litellm_llm_client.py` | Task 2 |
| **TDD 单元测试** | LLM 异常体系 | 构造/to_dict()/cause 链 / HTTP 映射 | `test_llm_exceptions.py` | Task 1 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_llm_client.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_llm_client.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | `src` 与测试目录完成清单最终确认 | `test_acceptance_llm_client.feature` | Task 6 |
| **TDD 验收测试** | 收尾 BDD 步骤实现 | 完成清单断言与步骤函数 | `test_acceptance_llm_client.py` | Task 6 |
| **TDD 契约测试** | 端口契约 / registry / resolver | 端口注册/版本/lifetime/owner | `test_port_contract_llm_client.py` | Task 0 |
| **TDD 领域异常测试** | 层次结构 | 构造/属性/to_dict()/cause 链 | `test_llm_exceptions.py` | Task 1 |
| **TDD 领域异常测试** | 编码唯一性 | 所有异常类 code 无碰撞 | `test_error_code_uniqueness.py` | Task 1 |
| **TDD 领域异常测试** | 编码子域范围 | 子域范围/继承链一致性 | `test_code_ranges.py` | Task 1 |
| **SDD 架构验证** | 六边形架构约束 | 依赖方向、零依赖 | `test_arch_llm_client.py` | Task 5 |
| **集成测试** | 端到端 LLM 调用 | 真实 LLM API 调用 + 结构化输出 | `test_integration_llm_client.py` | Task 6 |

---

### 测试要求与质量门禁

#### 覆盖率要求
- [ ] **整体覆盖率 ≥80%**（P0 阻断门禁）
- [ ] **领域层覆盖率 ≥90%**（端口、异常、数据模型）
- [ ] **基础设施层覆盖率 ≥75%**（LitellmLLMClient 实现）
- [ ] **集成测试覆盖率 ≥70%**
- [ ] **关键路径覆盖率 100%**（正常调用 / 重试 / 熔断 / 异常映射）

#### 代码质量门禁
- [ ] Ruff 检查通过（`ruff check src/`）
- [ ] MyPy 类型检查通过（`mypy src/`）
- [ ] 预提交 Hooks 通过（`pre-commit run --all-files`）

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | LLMConfig + from_env/from_cloud_model_config | Task 1 | Subtask 1.1-1.4 | `test_llm_config.py` |
| AC-2 | LLMClientPort + LLMResponse 端口定义 | Task 1 | Subtask 1.5-1.7 | `test_port_contract_llm_client.py` |
| AC-3 | LitellmLLMClient 实现 + 重试 + 熔断 + api_type 适配 | Task 2 | Subtask 2.1-2.12 | `test_litellm_llm_client.py` |
| AC-4 | LLM 异常体系 | Task 1 | Subtask 1.8-1.11 | `test_llm_exceptions.py` |
| AC-5 | Composition Root 注册 | Task 3 | Subtask 3.1-3.3 | `test_port_contract_llm_client.py` |
| AC-6 | 验收测试 | Task 0 + Task 6 | Subtask 0.2-0.4 + 6.2-6.4 | `test_acceptance_llm_client.feature` + `.py` |

---

## 📋 Tasks / Subtasks 任务分解

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-6

- [ ] Subtask 0.1: 创建 `src/domain/ports/llm_client.py`（`LLMClientPort` + `LLMConfig` + `LLMResponse` 类型存根文件）
- [ ] Subtask 0.2: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_llm_client.feature`
- [ ] Subtask 0.3: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_llm_client.py`
- [ ] Subtask 0.4: 运行验收测试，确认失败（🔴 红阶段验证）

---

### Task 1: 领域层 — LLMConfig + LLMClientPort + 异常体系

**关联 AC:** AC-1, AC-2, AC-4

#### TDD 循环 A：LLMConfig 领域值对象

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_llm_config.py`（默认值 / frozen / from_env / from_cloud_model_config / 异常） |
| 🟢 绿 | 实现 `LLMConfig` frozen dataclass + `from_env()` + `from_cloud_model_config()` |
| 🔄 重构 | 添加完整 docstring + 类型注解 |

- [ ] Subtask 1.1: 🔴 红 — 编写 `tests/unit/domain/ports/test_llm_config.py`
- [ ] Subtask 1.2: 🟢 绿 — 实现 `LLMConfig` + `LLMResponse` dataclass
- [ ] Subtask 1.3: 🔄 重构 — Google 风格全中文 docstring

#### TDD 循环 B：LLMClientPort 端口定义

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_port_contract_llm_client.py`（Protocol 检查 / 方法签名 / @runtime_checkable） |
| 🟢 绿 | 实现 `LLMClientPort` Protocol |
| 🔄 重构 | 添加方法 docstring |

- [ ] Subtask 1.4: 🔴 红 — 编写端口契约测试
- [ ] Subtask 1.5: 🟢 绿 — 实现 `LLMClientPort`
- [ ] Subtask 1.6: 🔄 重构

#### TDD 循环 C：LLM 异常体系

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_llm_exceptions.py`（构造/to_dict/HTTP 映射/编码碰撞） |
| 🟢 绿 | 实现 `LLMAPIError` / `LLMResponseError` / `LLMConfigError` |
| 🔄 重构 | 注册 `_code_ranges.py` / `__init__.py` / `EXCEPTION_HTTP_MAP` |

- [ ] Subtask 1.7: 🔴 红 — 编写 `tests/unit/domain/exceptions/test_llm_exceptions.py`
- [ ] Subtask 1.8: 🟢 绿 — 实现 `src/domain/exceptions/llm_exceptions.py`
- [ ] Subtask 1.9: 🔄 重构 — 更新 `_code_ranges.py`（新增 llm 子域 330-339）/ `__init__.py` / `EXCEPTION_HTTP_MAP`
- [ ] Subtask 1.10: 运行 `pytest tests/unit/domain/exceptions/ -v`（编码唯一性 + 子域范围）

**完成标准/Definition of Done:**
- [ ] `LLMConfig` / `LLMResponse` / `LLMClientPort` 定义完成
- [ ] 3 个 LLM 异常完成三阶段注册
- [ ] 编码唯一性 + 子域范围测试通过

---

### Task 2: 基础设施层 — LitellmLLMClient 实现

**关联 AC:** AC-3

> **容错模式参考：** `EmbeddingAPIClient` [Source: src/infrastructure/external_services/embedding/embedding_api_client.py]
> **api_type 适配参考：** Story 1.17 Dev Notes "统一抽象层架构" 和 "Anthropic 格式关键差异" [Source: _bmad-output/implementation-artifacts/stories/1-17-udmr-basic-routing.md]

#### TDD 循环 A：核心调用 + 结构化输出

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写基本调用测试（`patch("litellm.acompletion")` / 结构化输出 / 自由文本 / close / async with） |
| 🟢 绿 | 实现 `LitellmLLMClient.structured_generate()` + `generate()` |
| 🔄 重构 | 添加 docstring、type hints |

- [ ] Subtask 2.1: 🔴 红 — Mock 模式：`patch("litellm.acompletion")` + `MagicMock` 构造 mock_response
- [ ] Subtask 2.2: 🟢 绿 — 实现 `structured_generate()`（litellm `acompletion` + `response_schema.model_validate_json()`）+ `generate()` + `close()`
- [ ] Subtask 2.3: 🔄 重构

#### TDD 循环 B：api_type 适配器（openai / anthropic / openai_responses）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写适配测试（openai 直接传递 / anthropic system 提取 + max_tokens 注入 / openai_responses 增量流式） |
| 🟢 绿 | 实现 `_adapt_request_for_api_type()` 内部方法 |
| 🔄 重构 | 适配逻辑抽取为独立辅助函数 |

- [ ] Subtask 2.4: 🔴 红 — 编写 api_type 适配测试
- [ ] Subtask 2.5: 🟢 绿 — 实现 api_type 适配逻辑
- [ ] Subtask 2.6: 🔄 重构

#### TDD 循环 C：重试机制

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写重试测试（5xx 重试 / Timeout 重试 / Transport 重试 / 4xx 不重试 / Pydantic 验证失败不重试） |
| 🟢 绿 | 集成 `tenacity.AsyncRetrying` + `_is_retryable_llm_error` |
| 🔄 重构 | 对齐 `_is_retryable_http_error` 模式 |

- [ ] Subtask 2.7: 🔴 红
- [ ] Subtask 2.8: 🟢 绿 — `_is_retryable_llm_error`: 500/502/503/504 + httpx.TimeoutException + httpx.TransportError → 可重试
- [ ] Subtask 2.9: 🔄 重构

#### TDD 循环 D：熔断器集成

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写熔断器测试（连续5次失败断开 / 断开后快速失败 / 恢复 / 半开→闭合） |
| 🟢 绿 | 集成 `CircuitBreaker`（before_call / on_success / on_failure） |
| 🔄 重构 | 优化异常信息 |

- [ ] Subtask 2.10: 🔴 红
- [ ] Subtask 2.11: 🟢 绿
- [ ] Subtask 2.12: 🔄 重构

#### TDD 循环 E：异常映射（内联模式，对标 EmbeddingAPIClient）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写异常映射测试（401→LLMAPIError / 429→LLMAPIError / 400→LLMResponseError / 500+→LLMAPIError / Timeout→TimeoutError） |
| 🟢 绿 | 实现 `_map_llm_error()` 内联方法（**对标 EmbeddingAPIClient 的内联 `_map_exception` 模式，不使用外部 ErrorMapper**） |
| 🔄 重构 | |

- [ ] Subtask 2.13: 🔴 红
- [ ] Subtask 2.14: 🟢 绿 — `_map_llm_error()` 从 litellm 响应提取错误信息并映射为 LLMAPIError/LLMResponseError
- [ ] Subtask 2.15: 🔄 重构

**完成标准/Definition of Done:**
- [ ] `LitellmLLMClient` 全部实现（核心调用 + api_type 适配 + 重试 + 熔断 + 异常映射）
- [ ] 覆盖率：基础设施层 ≥75%

---

### Task 3: Composition Root 注册

**关联 AC:** AC-5

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 端口契约测试（端口在注册表中不存在 → 失败） |
| 🟢 绿 | 在 `src/composition_root.py` 注册 `llm_client` + `llm_circuit_breaker` |
| 🔄 重构 | 验证端口版本/owner/lifetime |

- [ ] Subtask 3.1: 🔴 红 — 扩展 `tests/contracts/test_port_contract_llm_client.py`
- [ ] Subtask 3.2: 🟢 绿 — 注册端口：
  ```python
  register_port(
      name="llm_client",
      version="v1.0.0",
      interface=LLMClientPort,
      impl=lambda resolver: LitellmLLMClient(
          config=_build_llm_config(),
      ),
      module="src.infrastructure.external_services.llm.litellm_llm_client",
      lifetime=Lifetime.SINGLETON,
      owner="search-team",
      tags=("llm", "client"),
  )
  ```

  并在 `shutdown()` 函数中新增 LLM Client 资源清理（对标 embedding_service 的 shutdown 模式 [Source: composition_root.py:1722-1728]）：
  ```python
  # 关闭 llm_client HTTP 客户端连接池
  try:
      llm = resolver.resolve("llm_client")
      if llm is not None:
          await llm.close()
          logger.info("Closed llm_client")
  except Exception as e:
      logger.error("Failed to close llm_client: %s", e)
  ```

  其中 `_build_llm_config()` 辅助函数实现：
  ```python
  def _build_llm_config() -> LLMConfig:
      """按优先顺序构造 LLMConfig：UDMR 云端配置 → 独立环境变量"""
      udmr_config = UDMRConfig.from_env()
      # 找到第一个 enabled 的云端模型
      for cloud in udmr_config.cloud_configs:
          if cloud.enabled:
              return LLMConfig.from_cloud_model_config(cloud, timeout=udmr_config.llm_timeout)
      # 降级：从独立环境变量构造
      return LLMConfig.from_env()
  ```
- [ ] Subtask 3.3: 🔄 重构 — 验证现有测试无回归

**完成标准/Definition of Done:**
- [ ] `llm_client` 端口注册完成
- [ ] 端口契约测试通过
- [ ] 已有测试全部通过（无回归）

---

### Task 4: SDD 架构约束验证测试

**关联 AC:** 六边形架构合规

- [ ] Subtask 4.1: 创建 `tests/unit/architecture/test_arch_llm_client.py`
- [ ] Subtask 4.2: 验证 `src/domain/ports/llm_client.py` 零外部依赖（不导入 pydantic/litellm/httpx）
- [ ] Subtask 4.3: 验证 `src/domain/exceptions/llm_exceptions.py` 零外部依赖
- [ ] Subtask 4.4: 验证 `LitellmLLMClient` 可访问领域层端口
- [ ] Subtask 4.5: 使用 `import-linter` 验证新模块不违反 `.importlinter` 规则

---

### Task 5: 集成测试 + 验收测试收尾

**关联 AC:** AC-6

- [ ] Subtask 5.1: 编写 `tests/integration/test_integration_llm_client.py`
  - 真实 LLM API 调用（不可用时 `pytest.skip`）
  - 每个测试自包含（创建→调用→验证）
- [ ] Subtask 5.2: 验收测试收尾 — 验证 `src` 和测试目录完成清单
- [ ] Subtask 5.3: 运行 `pytest`、`ruff check`、`mypy` 收尾校验

---

## 📝 Dev Notes 开发笔记

### 与 Story 1.17 (UDMR 基础路由) 的衔接

**前置依赖：** Story 1.17 已交付以下可复用组件 [Source: _bmad-output/implementation-artifacts/stories/1-17-udmr-basic-routing.md]:

| 组件 | 路径 | 本 Story 使用方式 |
|------|------|------------------|
| `CloudModelConfig` | `src/infrastructure/config/udmr.py` | `LLMConfig.from_cloud_model_config()` 的输入源 |
| `UDMRConfig` | `src/infrastructure/config/udmr.py` | `_build_llm_config()` 读取 `cloud_configs[0]` + `llm_timeout` |
| `CircuitBreaker` | `src/infrastructure/external_services/embedding/circuit_breaker.py` | 熔断器由 LitellmLLMClient 内部构造（`CircuitBreaker(name="llm")`），对标 embedding 模式，不做独立端口注册 |
| API 兼容性调研 | Story 1.17 Dev Notes §LLM API 兼容性调研 | `LitellmLLMClient` 的 api_type 适配逻辑设计依据 |
| Anthropic 格式差异表 | Story 1.17 Dev Notes §Anthropic 格式关键差异 | `_adapt_request_for_api_type()` 实现依据 |

**衔接架构图：**

```
UDMR (Story 1.17)                    LLM Client (Story 3.2a)               调用方 (Story 3.2b+)
═══════════════════                  ══════════════════════               ═══════════════════
                              ┌─→  LLMConfig.from_cloud_model_config()
                              │       (CloudModelConfig → LLMConfig 转换)
UDMRConfig.from_env() ────────┤
  ├ cloud_configs[0] ────────┘
  ├ llm_timeout
  └ ...

                              LLMConfig.from_env()  ←── 独立环境变量
                              (LLM_API_KEY / LLM_BASE_URL / LLM_MODEL / ...)
                                      │
                                      ▼
                              LitellmLLMClient (LLMClientPort 实现)
                              ├ structured_generate(prompt, schema, config)
                              ├ generate(prompt, config)
                              ├ CircuitBreaker(name="llm")
                              └ tenacity.AsyncRetrying
                                      │
                                      ▼
                              LLM API (via litellm)
                              ├ openai → openai/DeepSeek/GLM/Qwen/Ollama
                              ├ anthropic → Anthropic/MiniMax
                              └ openai_responses → OpenAI Responses API
```

**配置优先级：**
1. UDMR 云端配置（`UDMR_CLOUD_0_*` → `CloudModelConfig` → `LLMConfig.from_cloud_model_config()`）
2. 独立环境变量（`LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` 等 → `LLMConfig.from_env()`）

两种配置方式并存，调用方可通过 `config` 参数覆盖全局默认。

### LLMConfig vs CloudModelConfig 关系

| 维度 | CloudModelConfig (Story 1.17) | LLMConfig (本 Story) |
|------|-------------------------------|----------------------|
| 位置 | `src/infrastructure/config/udmr.py` | `src/domain/ports/llm_client.py` |
| 层次 | 基础设施层 | 领域层 |
| 类型 | `@dataclass(frozen=True)` | `@dataclass(frozen=True)` |
| 字段 | `api_type`, `endpoint`, `api_key`, `model`, `enabled`, `max_tokens`, `temperature`, `price_per_input_1k_tokens`, `price_per_output_1k_tokens` | `api_type`, `endpoint`, `api_key`, `model`, `temperature`, `max_tokens`, `timeout` |
| 用途 | UDMR 配置存储 | LLM 调用参数 |
| 转换 | — | `LLMConfig.from_cloud_model_config(c, timeout=T)` |

> **⚠️ 设计说明（LLMConfig 放在 domain/ports/ vs infrastructure/config/）：**
> - `EmbeddingConfig` 在 `infrastructure/config/embedding.py` 中，作为 `EmbeddingAPIClient` 的配置输入
> - `LLMConfig` 选择放在 `domain/ports/llm_client.py` 中，基于两个理由：
>   1. **R1（领域层统一抽象基础端口）**：`LLMConfig` 是 `LLMClientPort` 的方法参数类型，端口定义在领域层，其参数类型也应在其文件内
>   2. **可复用性**：多个 Story（3-2b, 3-6, 4-5, 5-1）的应用层服务注入 `LLMClientPort` 时可直接构造 `LLMConfig` 覆盖全局默认，无需依赖基础设施层
> - `from_cloud_model_config()` 和 `from_env()` 通过参数类型注入绕过基础设施层依赖（`CloudModelConfig` 类型从调用方传入）

### 关键架构决策

**ADR: litellm + Pydantic JSON Mode vs instructor SDK**

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **litellm + Pydantic JSON Mode** | 项目已依赖 litellm ^1.28.0；多厂商统一网关；无需额外依赖；ipynb `response_format` 支持 | Pydantic 验证需手动调用 | ✅ 9/10 |
| instructor SDK | 自动重试修复；深度 Pydantic 集成；支持流式结构化输出 | 额外依赖（非项目已有）；不兼容所有 litellm 模型 | 7/10 |
| 直接 openai/anthropic SDK | 原生功能完整 | 多厂商调用需适配层；增加依赖链 | 5/10 |

**决策理由：** 项目 `pyproject.toml` 已依赖 `litellm ^1.28.0` 和 `httpx ^0.27.0`。litellm 内置 `response_format` 支持（JSON Mode + Schema），与 instructor 功能等效。`response_schema: type` 参数接受 Pydantic `BaseModel` 子类作为 type hint，领域层 Protocol 仅将其视为不可变类型引用（不实例化、不导入 pydantic），结构化输出的 Pydantic 验证在基础设施层 `LitellmLLMClient.structured_generate()` 内执行。

**ADR: LLM 异常不按 HTTP 状态码细分**

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **LLMAPIError (330) + LLMResponseError (331) + LLMConfigError (332)** | 简洁；调用方通过 context 字典获取详细信息 | context 字典非结构化 | ✅ 8/10 |
| 按 HTTP 状态码细分（LLMRateLimitError/LLMAuthenticationError/LLMContextLengthError...） | 调用方类型匹配精确 | 异常类爆炸（~10+类）；新增状态码需新增类 | 5/10 |

### 项目结构说明

```
src/
├── domain/
│   ├── exceptions/
│   │   └── llm_exceptions.py          # 🆕 LLMAPIError / LLMResponseError / LLMConfigError
│   └── ports/
│       └── llm_client.py              # 🆕 LLMClientPort + LLMConfig + LLMResponse
│
├── infrastructure/
│   ├── config/
│   │   └── udmr.py                    # 复用 Story 1.17: CloudModelConfig + UDMRConfig
│   ├── external_services/
│   │   ├── embedding/
│   │   │   └── circuit_breaker.py    # 复用: CircuitBreaker (name="llm")
│   │   └── llm/
│   │       ├── __init__.py            # 更新：导出 LitellmLLMClient
│   │       ├── litellm_llm_client.py  # 🆕 LitellmLLMClient（内联熔断器+异常映射）
│   │       └── cloud_health_checker.py # 复用 Story 1.17: CloudHealthChecker
│
└── composition_root.py                # 更新：注册 llm_client

tests/
├── unit/
│   ├── domain/
│   │   ├── ports/
│   │   │   └── test_llm_config.py              # 🆕 LLMConfig/LLMResponse 测试
│   │   └── exceptions/
│   │       └── test_llm_exceptions.py           # 🆕 LLM 异常测试
│   ├── infrastructure/
│   │   └── external_services/
│   │       └── llm/
│   │           └── test_litellm_llm_client.py   # 🆕 LitellmLLMClient 测试
│   └── architecture/
│       └── test_arch_llm_client.py              # 🆕 架构约束测试
├── integration/
│   └── test_integration_llm_client.py           # 🆕 集成测试
├── contracts/
│   └── test_port_contract_llm_client.py         # 🆕 端口契约测试
└── acceptance/
    ├── test_acceptance_llm_client.feature       # 🆕 Gherkin 场景
    └── test_acceptance_llm_client.py            # 🆕 BDD 步骤实现
```

### 前一个故事学习经验

**来源:** Story 3-1b (BM25 稀疏检索 + RRF 融合) + Story 1.17 (UDMR 基础路由)

**关键学习:**
- **端口契约三方法模式**（Story 3-1b）：端口存在性 → 方法签名 → 元数据验证
- **降级策略**（Story 3-1b）：单路失败降级为单路，双路失败才抛异常 → LLM Client：主模型失败不降级（Story 3-2a 为基础设施，降级策略在 UDMR 层实现）
- **Mock 模式**（Story 3-1b）：`patch("httpx.AsyncClient.post")` → `patch("litellm.acompletion")` 对标
- **BDD async 约束**（Story 3-1b）：不使 `@pytest.mark.asyncio`，用 `event_loop.run_until_complete()`
- **熔断器复用**（Story 1.17）：`CircuitBreaker(name="embedding")` → `CircuitBreaker(name="llm")`，命名区分分布实例
- **api_type 适配**（Story 1.17 Dev Notes）：三种格式的差异处理（认证/请求/响应转换）

**应用到本故事:**
- [ ] 熔断器复用 `CircuitBreaker`（`name="llm"`）
- [ ] 重试使用 `tenacity.AsyncRetrying`
- [ ] api_type 适配器实现（openai 直接传递 / anthropic system 提取 + max_tokens 注入 / openai_responses 增量流式）
- [ ] Mock 模式：`patch("litellm.acompletion")`
- [ ] BDD 步骤：`event_loop.run_until_complete()`
- [ ] LLMConfig 通过 `from_cloud_model_config()` 消费 Story 1.17 的 `CloudModelConfig`

---

## 🤖 开发代理记录 Dev Agent Record

| 配置项 | 值 |
|--------|-----|
| **Model** | GLM-5.2 |
| **Version** | create-story workflow v2.9.0 |
| **Execution Date** | 2026-08-05 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `docs/architecture/architecture.md` |
| **前一个 Story (3-1b)** | `_bmad-output/implementation-artifacts/stories/3-1b-bm25-sparse-search-rrf-fusion.md` |
| **上游 Story (1.17)** | `_bmad-output/implementation-artifacts/stories/1-17-udmr-basic-routing.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |
| **异常设计文档** | `docs/architecture/sisys-uni-exception-design.md` |
| **EmbeddingAPIClient 参考** | `src/infrastructure/external_services/embedding/embedding_api_client.py` |
| **CircuitBreaker 参考** | `src/infrastructure/external_services/embedding/circuit_breaker.py` |
| **UDMR 配置参考** | `src/infrastructure/config/udmr.py` |

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/3-2a-llm-client-infrastructure.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/domain/ports/llm_client.py` — LLMClientPort + LLMConfig + LLMResponse
- `src/domain/exceptions/llm_exceptions.py` — LLMAPIError / LLMResponseError / LLMConfigError
- `src/infrastructure/external_services/llm/litellm_llm_client.py` — LitellmLLMClient
- `tests/unit/domain/ports/test_llm_config.py` — LLMConfig 测试
- `tests/unit/domain/exceptions/test_llm_exceptions.py` — LLM 异常测试
- `tests/unit/infrastructure/external_services/llm/test_litellm_llm_client.py` — LLM Client 测试
- `tests/unit/architecture/test_arch_llm_client.py` — 架构约束测试
- `tests/integration/test_integration_llm_client.py` — 集成测试
- `tests/contracts/test_port_contract_llm_client.py` — 端口契约测试
- `tests/acceptance/test_acceptance_llm_client.feature` — Gherkin 场景
- `tests/acceptance/test_acceptance_llm_client.py` — BDD 步骤实现

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 3.2a |
| **Story Key** | 3-2a-llm-client-infrastructure |
| **File** | `_bmad-output/implementation-artifacts/stories/3-2a-llm-client-infrastructure.md` |
| **Status** | `ready-for-dev` |
| **Epic** | Epic 3: 智能检索与知识发现 |
| **价值组** | 智能检索与溯源 |
| **优先级** | **P0-1c（公共基础设施）** |
| **覆盖 FR** | FR-SR-02（实体抽取）、FR-SR-06（契约化摘要）、FR-SR-07（检索相关性评估）— 共用 LLM 基础设施 |
| **前置依赖** | Story 1.17 (UDMR 基础路由 — CloudModelConfig / UDMRConfig / CircuitBreaker / API 兼容性调研) |
| **后续依赖** | Story 3-2b（实体抽取）、Story 3-6（契约化摘要）、Story 3-7（检索相关性评估）、Epic 5（Agent 推理） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0-5）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1 到 AC-6）
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Story 1.17 (UDMR) 衔接关系完整体现
5. [x] Previous story learnings integrated (Story 3-1b + Story 1.17)
6. [x] Sprint status synced to `ready-for-dev`

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查

**⚠️ 关键提示：** 本 Story 是 Epic 3 的关键基础设施，Story 3-2b（实体抽取）、3-6（契约化摘要）、3-7（检索相关性评估）及 Epic 5（Agent 推理）均依赖本 Story。建议优先实施。LLM Client 与 Story 1.17 (UDMR) 形成完整的 **路由→执行**链路。

---

**故事版本/Story Version:** v2.0.0
**创建日期/Created:** 2026-08-05
**最后更新/Last Updated:** 2026-08-05
**更新说明/Description:**
- v1.0.0: 创建故事文件（初版）
- v2.0.0: 补充 Story 1.17 (UDMR) 衔接关系 — LLMConfig 从 CloudModelConfig 转换、api_type 适配器设计、配置优先级、架构衔接图、上游依赖声明
