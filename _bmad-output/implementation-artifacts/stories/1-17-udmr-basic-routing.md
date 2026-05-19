# Story 1.17: UDMR 基础路由（本地优先静态配置）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 运维工程师,
**I want** 配置本地/云端路由策略（本地优先静态配置）,
**So that** MVP 阶段支持基础成本优化，验证本地路由占比≥80%。

### 业务价值

本 Story 是 Epic 1（企业级架构基础与合规）价值组 6（MVP 关键机制增强）的第一个故事。在 Story 1.14a/b/c（自主调用循环 trigger→route→execute）完成后，实现 UDMR（统一动态模型路由）L3 静态路由层——本地模型优先，本地不可用时切换云端。

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **本地优先路由** | 本地模型成本显著低于云端，MVP 验证成本优化假设 | 本地路由占比≥80%（基于本地可用率>95%假设） |
| **健康检查故障切换** | 本地模型不可用时自动切换云端，保证服务连续 | 健康检查失败→切换云端，决策延迟<1s |
| **路由决策事件** | 路由决策通过 RoutingDecided 事件持久化，支持审计 | 事件字段完整，Outbox 自动归档 |
| **路由性能** | 路由决策延迟满足 MVP 要求 | P95<100ms |

> ⚠️ **MVP 范围澄清**：本 Story 仅实现 **L3 静态路由**（本地优先 + 健康检查切换）。
> - L1 合规性网关 → Story 11.1（`ComplianceGatewayPort` 端口已就绪）
> - L2 四因子评分 → Story 11.2（`ComplexityAssessor` 未实现）
> - L3 动态阈值（基于 L2 评分的自适应决策）→ Story 11.2

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 1, 价值组 6, Story 1.17

**or.md 公理追溯:** 系统公理一（trigger→route→execute），覆盖 route 阶段的**模型路由决策子阶段**

**前置依赖:** Story 1.14b（AutoRouted 事件 + AutoRouteService 已实现）

**后续依赖:** Story 1.19（CFO ROI 成本验证，依赖本 Story 路由决策事件）

---

## 🔗 前置依赖与现有代码继承

### 依赖故事

| 故事 | 组件 | 用途 |
|------|------|------|
| Story 1.14a | AutoTriggerService + AutoTriggered | 触发机制（已完成） |
| Story 1.14b | AutoRouteService + AutoRouted + RoutingDecisionLog | 一级路由 + 决策日志（代码已实现） |
| Story 1.14c | AutoExecuteService + AutoExecuted | 执行机制 |

### 现有代码继承（必须复用，禁止重复定义）

| 现有组件 | 文件路径 | 复用方式 |
|---------|---------|---------|
| `RoutingDecided` 事件 | `src/domain/events/routing_events.py` | 直接复用——L3 字段（route_type/selected_model/estimated_cost/fallback_reason）和健康检查字段（health_check_passed/health_check_latency_ms）已完整 |
| `RoutingDecisionLog` 实体 | `src/domain/entities/routing_decision_log.py` | 直接复用——UDMR 扩展字段（selected_model/cost_actual/fallback_reason）已存在 |
| `HealthCheckPort` 端口 | `src/domain/ports/health_check.py` | 直接复用——Protocol 接口 check()/close() 已定义 |
| `UDMRTask` 值对象 | `src/domain/value_objects/udmr_task.py` | 直接复用——任务上下文 data_residency/preferred_model |
| `AutoRouted` 事件 | `src/domain/events/auto_route_events.py` | 直接复用——UDMRouter 接收此事件作为输入 |
| `EventPublisher` 端口 | `src/domain/ports/event_publisher.py` | 直接复用——发布 RoutingDecided 事件 |
| `AutoRouteHandler` | `src/application/event_handlers/auto_route_handler.py` | 参考模式——UDMRHandler 遵循相同桥接模式 |

### 架构位置

```
AutoTriggered (1.14a)
       ↓
AutoRouteService (1.14b) → 一级路由 (hash/semantic/mixed) → 发布 AutoRouted
       ↓
  [UDMRouter 1.17] → 二级路由 (local/cloud) → 发布 RoutingDecided ← 本 Story
       ↓
AutoExecuteService (1.14c)
```

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 本地优先静态路由

**Given** 系统配置了 UDMR（UDMR_ENABLED=true），本地模型（UDMR_LOCAL_MODEL）和至少一个启用云端模型（UDMR_CLOUD_{N}_ENABLED=true）
**When** UDMRouter 接收 AutoRouted 事件并执行路由决策
**Then** UDMR_LOCAL_FIRST=true 且健康检查通过 → route_type="local"，selected_model=UDMR_LOCAL_MODEL
**And** UDMR_LOCAL_FIRST=true 且健康检查失败 → route_type="cloud"，selected_model=第一启用云端模型，fallback_reason="health_check_failed"
**And** UDMR_LOCAL_FIRST=false → route_type="cloud"，selected_model=第一启用云端模型，fallback_reason=None
**And** 发布 RoutingDecided 事件（包含完整的 L3 字段和健康检查字段）

**验证标准/Validation Criteria:**
- [ ] UDMRouter 类实现（`src/domain/services/udmr_router.py`）
- [ ] RoutingDecision 值对象（`src/domain/value_objects/routing_decision.py`）
- [ ] UDMRConfig 配置（`src/infrastructure/config/udmr.py`，from_env() 模式，支持多云端索引配置）
- [ ] CloudModelConfig 配置（`src/infrastructure/config/udmr.py`，单云端模型配置）
- [ ] 本地路由占比≥80%（UDMR_LOCAL_FIRST=true 且本地可用时）

### AC-2: 健康检查与故障切换

**Given** UDMRouter 在路由决策前执行本地模型健康检查
**When** HealthCheckPort.check() 返回 True
**Then** route_type="local"，fallback_reason=None
**When** HealthCheckPort.check() 返回 False（Ollama 不可达或响应异常）
**Then** route_type="cloud"，fallback_reason="health_check_failed"
**When** Ollama 连接超时或网络异常
**Then** route_type="cloud"，fallback_reason="unavailable"

> ⚠️ **职责边界**：UDMRouter 仅负责**路由决策前的健康检查**。LLM 调用过程中的超时监控属于执行层（Story 1.14c）职责。如需 LLM 调用超时后切换模型，由执行层重新发布路由请求触发二次路由。

**验证标准/Validation Criteria:**
- [ ] OllamaHealthAdapter 实现 HealthCheckPort（GET /api/tags，使用 OLLAMA_BASE_URL）
- [ ] HealthCheckerFactory 端口（`src/domain/ports/health_check_factory.py`）
- [ ] OllamaHealthCheckerFactory 实现 HealthCheckerFactory
- [ ] LocalModelHealthFacade 应用层门面（`src/application/services/local_model_health_facade.py`）
- [ ] FallbackRouter 基础设施组件（`src/infrastructure/routing/fallback_router.py`，选择第一启用云端模型）
- [ ] health_check_passed/health_check_latency_ms 记录于 RoutingDecided 事件

### AC-3: 路由决策事件与日志

**Given** 路由决策完成
**When** UDMRouter 发布 RoutingDecided 事件
**Then** 事件包含完整字段：task_id, route_type, selected_model, estimated_cost, fallback_reason, health_check_passed, health_check_latency_ms
**And** RoutingDecided 事件通过 EventPublisher → Outbox 机制自动持久化
**And** RoutingDecisionLog 实体 UDMR 扩展字段（selected_model, fallback_reason）可被下游消费者写入

> 📝 **字段分布说明**：health_check_passed 和 health_check_latency_ms 仅存在于 **RoutingDecided 事件**中（瞬时决策数据）。**RoutingDecisionLog 实体**不包含这两个字段——Log 是通用审计实体，健康检查是 L3 路由的瞬时数据，不需要持久化到日志实体。

**验证标准/Validation Criteria:**
- [ ] RoutingDecided 事件 L3 字段完整性验证（已有测试 `test_new_events.py`，验证扩展）
- [ ] RoutingDecisionLog 实体 UDMR 字段验证（已有测试 `test_routing_decision_log.py`，验证扩展）
- [ ] 事件字段分布文档化（健康检查字段仅存在于事件，不存于实体）
- [ ] UDMRHandler 事件桥接（AutoRouted → UDMRouter → RoutingDecided）

### AC-4: 路由性能

**Given** UDMRouter 接收 AutoRouted 事件
**When** 执行路由决策（含健康检查）
**Then** 路由决策延迟 P95<100ms（MVP 静态配置）
**And** 路由决策幂等性（相同输入→相同输出）

**验证标准/Validation Criteria:**
- [ ] 路由决策延迟 P95<100ms（基准测试：1000 次请求，预热 100 次。**注意**：使用 mock 健康检查（瞬时返回），仅测量路由决策逻辑延迟。真实 Ollama 健康检查延迟取决于网络/硬件，不纳入 MVP 基准测试）
- [ ] 路由决策幂等性（相同 AutoRouted 输入产生相同 RoutingDecided 输出）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域服务 Schema (Domain Services)
- [ ] UDMRouter 服务（`src/domain/services/udmr_router.py`）
  - `async on_routed_event(event: AutoRouted) -> RoutingDecision` — 接收 AutoRouted，执行本地/云端二级路由
    - **task_id 映射**：`task_id = event.event_id`（保持事件链聚合标识一致性）
    - **发布职责**：UDMRouter 仅返回 RoutingDecision 值对象，不发布事件；由 UDMRHandler 创建 RoutingDecided 事件并发布
  - `async check_local_health() -> tuple[bool, float]` — 检查本地模型健康状态，返回 (passed, latency_ms)。**实现方式**：包装 `HealthCheckPort.check()` 调用，使用 `time.monotonic()` 测量耗时（端口接口仅返回 bool，latency 由 UDMRouter 外部测量）
  - 构造函数注入：`HealthCheckPort`, **原始值类型**（local_model: str, first_cloud_model: str, local_first: bool = True, local_timeout: int = 30）
    - > **六边形架构约束**：UDMRouter（领域层）不导入 UDMRConfig（基础设施层）。构造函数接受原始值类型，由 composition_root.py 解析 UDMRConfig 后传入。参考 AutoRouteService 模式（不导入 AutoRouteConfig）。
    - > **first_cloud_model 说明**：composition_root 从 UDMRConfig.cloud_models 中预选第一个 enabled=True 的模型名称传入。选择逻辑在配置层完成，领域层仅接收已筛选的值。

#### 值对象 Schema (Value Objects)
- [ ] RoutingDecision 值对象（`src/domain/value_objects/routing_decision.py`）
  - route_type: Literal["local", "cloud"]
  - selected_model: str
  - estimated_cost: float = 0.0（MVP 静态路由不计算成本，固定为 0.0。成本计算由 Story 11.2 实现。对齐 RoutingDecided 事件字段命名）
  - health_check_passed: bool
  - health_check_latency_ms: float
  - fallback_reason: Literal["health_check_failed", "unavailable"] | None
  - > **枚举子集说明**：RoutingDecision 的 fallback_reason 是 RoutingDecided 事件枚举的 MVP 子集。事件允许 `"timeout"`（执行层 Story 1.14c 使用），值对象仅限健康检查相关值（`"health_check_failed"`, `"unavailable"`），符合 MVP 范围。

#### 端口接口 Schema (Domain Ports)
- [ ] HealthCheckerFactory 端口（`src/domain/ports/health_check_factory.py`）
  - `async create() -> HealthCheckPort` — 创建健康检查实例
  - Protocol + runtime_checkable

#### 配置模型 (Configuration Models)
- [ ] UDMRConfig 配置（`src/infrastructure/config/udmr.py`）
  - `@dataclass(frozen=True)` — 不可变配置，对齐 sprint-change-proposal（不同于 AutoRouteConfig 的可变模式）
  - enabled: bool（UDMR_ENABLED，默认 false。注意：不同于其他 auto-config 的 true 默认值，UDMR 作为新特性默认关闭）
  - local_first: bool（UDMR_LOCAL_FIRST，默认 false）
  - local_timeout: int（UDMR_LOCAL_TIMEOUT，默认 30，单位秒，健康检查超时）
  - local_model: str（UDMR_LOCAL_MODEL，默认 "qwen2.5:7b"。如未设置，回退至 LOCAL_MODEL_NAME）
  - cloud_models: list[CloudModelConfig] = field(default_factory=list)（从 UDMR_CLOUD_{N}_* 解析）
  - from_env() 类方法，扫描 os.environ 中 UDMR_CLOUD_{N}_* 前缀变量
  - > 向后兼容：from_env() 检测旧 ENABLE_UDMR 变量并映射至 UDMR_ENABLED（打印 deprecation warning）
- [ ] CloudModelConfig 配置（`src/infrastructure/config/udmr.py`）
  - `@dataclass(frozen=True)` — 不可变配置，对齐 sprint-change-proposal
  - api_type: str（UDMR_CLOUD_{N}_API_TYPE，"openai" | "anthropic" | "custom"）
  - endpoint: str（UDMR_CLOUD_{N}_ENDPOINT）
  - api_key: str（UDMR_CLOUD_{N}_API_KEY）
  - model: str（UDMR_CLOUD_{N}_MODEL）
  - enabled: bool（UDMR_CLOUD_{N}_ENABLED，默认 true）
  - > 索引由列表位置决定，不设 index 字段。对齐 sprint-change-proposal-2026-05-11-udmr-cloud-models.md

**环境变量模板：**
```bash
# UDMR 本地模型配置
export UDMR_ENABLED=true
export UDMR_LOCAL_FIRST=true
export UDMR_LOCAL_TIMEOUT=30
export UDMR_LOCAL_MODEL=qwen2.5:7b

# UDMR 云端模型配置 - Provider 0
export UDMR_CLOUD_0_API_TYPE=anthropic
export UDMR_CLOUD_0_ENDPOINT=https://api.example.com/anthropic
export UDMR_CLOUD_0_API_KEY=your_api_key_here
export UDMR_CLOUD_0_MODEL=Model-Name
export UDMR_CLOUD_0_ENABLED=true

# UDMR 云端模型配置 - Provider 1（可选，支持多云端）
export UDMR_CLOUD_1_API_TYPE=openai
export UDMR_CLOUD_1_ENDPOINT=https://api.example.com
export UDMR_CLOUD_1_API_KEY=your_api_key_here
export UDMR_CLOUD_1_MODEL=Model-Name
export UDMR_CLOUD_1_ENABLED=true
```

#### 基础设施适配器 Schema (Infrastructure Adapters)
- [ ] OllamaHealthAdapter + OllamaHealthCheckerFactory（`src/infrastructure/routing/ollama_health.py`）
  - OllamaHealthAdapter 实现 HealthCheckPort：check() 调用 GET {OLLAMA_BASE_URL}/api/tags
  - OllamaHealthCheckerFactory 实现 HealthCheckerFactory：create() 返回 OllamaHealthAdapter 实例
- [ ] FallbackRouter（`src/infrastructure/routing/fallback_router.py`）
  - `async route_with_fallback(health_checker: HealthCheckPort, local_model: str, first_cloud_model: str, local_first: bool) -> RoutingDecision`
  - 健康检查通过 + local_first → local
  - 健康检查失败 + local_first → cloud + fallback_reason="health_check_failed"
  - local_first=false → cloud + fallback_reason=None

#### 应用层 Schema (Application Services)
- [ ] LocalModelHealthFacade（`src/application/services/local_model_health_facade.py`）
  - 接受 HealthCheckerFactory 注入
  - `async check() -> bool`, `async close() -> None`
  - 委托具体 Adapter（MVP 仅 Ollama）

#### 应用层事件处理器 Schema
- [ ] UDMRHandler（`src/application/event_handlers/udmr_handler.py`）
  - 参考 AutoRouteHandler 模式
  - `async on_routed(self, event: DomainEvent) -> RoutingDecided | None`
  - 类型守卫：isinstance(event, AutoRouted)
  - 委托 UDMRouter.on_routed_event() → 获取 RoutingDecision 值对象 → **UDMRHandler 创建 RoutingDecided 事件并发布**
  - 参考 AutoRouteHandler 模式（AutoRouteHandler 也接收领域服务返回值后发布事件）

#### 统一端口注册与接口治理
- [ ] 端口注册：composition_root.py 注册 health_checker_factory
- [ ] 契约测试：tests/contracts/test_port_contract_health_checker_factory.py
- [ ] 端口版本：v1.0.0，owner=routing-team

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_story_1_17.feature`（由 Dev agent 在 Task 0 创建）
- [ ] 步骤实现文件：`tests/acceptance/test_story_1_17_steps.py`（BDD 步骤实现）
- [ ] 覆盖场景：
  - UDMR_LOCAL_FIRST=true 且本地模型可用 → 路由至本地
  - UDMR_LOCAL_FIRST=true 且本地模型不可用 → 切换至第一启用云端模型
  - UDMR_LOCAL_FIRST=false → 直接路由至第一启用云端模型
  - Ollama 连接异常 → fallback_reason="unavailable"
  - 多云端配置解析（UDMR_CLOUD_0_*, UDMR_CLOUD_1_*）
  - 路由决策事件字段完整性
  - 路由决策延迟 P95<100ms

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
| **TDD 单元测试** | UDMRouter | 本地优先路由决策 | `test_udmr_router.py` | Task 1 |
| **TDD 单元测试** | RoutingDecision | 值对象不变量 | `test_routing_decision.py` | Task 1 |
| **TDD 单元测试** | OllamaHealthAdapter | Ollama 健康检查 | `test_ollama_health.py` | Task 2 |
| **TDD 单元测试** | FallbackRouter | 故障切换逻辑 | `test_fallback_router.py` | Task 2 |
| **TDD 单元测试** | LocalModelHealthFacade | 门面编排 | `test_local_model_health_facade.py` | Task 2 |
| **TDD 单元测试** | UDMRConfig + CloudModelConfig | 配置 from_env() + 多云端索引 | `test_udmr_config.py` | Task 2 |
| **TDD 单元测试** | UDMRHandler | 事件桥接 | `test_udmr_handler.py` | Task 1 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_story_1_17.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_story_1_17_steps.py` | Task 0 |
| **TDD 契约测试** | HealthCheckerFactory | 端口契约 | `test_port_contract_health_checker_factory.py` | Task 1 |
| **已有测试扩展** | RoutingDecided L3 字段 | 事件字段完整性 | `test_new_events.py` | Task 1 |
| **已有测试扩展** | RoutingDecisionLog UDMR | 实体 UDMR 字段 | `test_routing_decision_log.py` | Task 1 |
| **SDD 架构验证** | 六边形约束 | 依赖方向/零依赖 | `test_udmr_architecture.py` | Task 3 |
| **集成测试** | 事件总线 | AutoRouted→RoutingDecided 端到端 | `test_story_1_17_integration.py` | Task 3 |
| **性能基准** | UDMRouter | P95<100ms | `test_udmr_performance.py` | Task 3 |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）
- [ ] **架构层覆盖率 ≥85%**（架构层 Story，含核心路由机制）
- [ ] **集成测试覆盖率 ≥70%**

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **外部服务隔离** | Ollama 健康检查使用 mock（unittest.mock.AsyncMock） | 真实 Ollama 不可用时测试失败 |
| **并行隔离** | 并行测试使用 UUID 前缀隔离资源 | 资源冲突导致并行失败 |
| **BDD async 配合** | BDD 步骤函数使用 `event_loop.run_until_complete()`，不使用 `@pytest.mark.asyncio` | context 数据丢失 |
| **asyncio.run 使用** | pytest-xdist 并行测试中 BDD 步骤函数用 event_loop fixture | asyncio.run() 创建新循环导致冲突 |
| **并发测试方法** | 真正并发测试在 async 函数内用 `asyncio.gather()` | 场景选择错误否则失败 |

**验证要求：**
- [ ] 并行测试 `pytest tests/ -n 8` 通过
- [ ] 连续5次运行无随机失败
- [ ] `poetry run ruff check` 通过
- [ ] `poetry run mypy` 通过

---

## 📊 AC → Task → Subtask 追溯矩阵

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | UDMRouter 本地优先路由 | Task 1 | 1.1-1.3（UDMRouter 红→绿→重构） | `test_udmr_router.py` |
| AC-1 | RoutingDecision 值对象 | Task 1 | 1.4-1.6（RoutingDecision 红→绿→重构） | `test_routing_decision.py` |
| AC-1 | UDMRHandler 事件桥接 | Task 1 | 1.7-1.9（UDMRHandler 红→绿→重构） | `test_udmr_handler.py` |
| AC-2 | OllamaHealthAdapter | Task 2 | 2.1-2.3（OllamaHealthAdapter 红→绿→重构） | `test_ollama_health.py` |
| AC-2 | FallbackRouter | Task 2 | 2.4-2.6（FallbackRouter 红→绿→重构） | `test_fallback_router.py` |
| AC-2 | UDMRConfig + CloudModelConfig | Task 2 | 2.7-2.9（UDMRConfig 红→绿→重构） | `test_udmr_config.py` |
| AC-2 | LocalModelHealthFacade | Task 2 | 2.10-2.12（Facade 红→绿→重构） | `test_local_model_health_facade.py` |
| AC-3 | RoutingDecided 事件验证 | Task 1 | 1.10（事件 L3 字段完整性验证，扩展已有 test_new_events.py） | `test_new_events.py`（已有，扩展） |
| AC-3 | RoutingDecisionLog 验证 | Task 1 | 1.11（实体 UDMR 字段验证） | `test_routing_decision_log.py`（已有） |
| AC-4 | 性能基准 | Task 3 | 3.5-3.7（P95<100ms 基准） | `test_udmr_performance.py` |
| 全部 | 架构验证 | Task 3 | 3.1-3.3（六边形约束） | `test_udmr_architecture.py` |
| 全部 | 集成测试 | Task 3 | 3.8-3.10（端到端流程） | `test_story_1_17_integration.py` |

---

## 📋 Tasks / Subtasks 任务分解

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4

> **目的：** 在进入代码实现前，明确 Schema、API 契约、验收标准。

- [ ] Subtask 0.1: 定义 UDMRouter 服务 Schema（`src/domain/services/udmr_router.py`）
- [ ] Subtask 0.2: 定义 RoutingDecision 值对象（`src/domain/value_objects/routing_decision.py`）
- [ ] Subtask 0.3: 定义 HealthCheckerFactory 端口（`src/domain/ports/health_check_factory.py`）
- [ ] Subtask 0.4: 定义 UDMRConfig + CloudModelConfig 配置（`src/infrastructure/config/udmr.py`，UDMR_CLOUD_{N}_* 索引解析）
- [ ] Subtask 0.5: 定义 OllamaHealthAdapter + OllamaHealthCheckerFactory Schema
- [ ] Subtask 0.6: 定义 FallbackRouter Schema
- [ ] Subtask 0.7: 定义 LocalModelHealthFacade Schema
- [ ] Subtask 0.8: 定义 UDMRHandler Schema
- [ ] Subtask 0.9: 验证已有组件（RoutingDecided 事件 / RoutingDecisionLog 实体 / HealthCheckPort / AutoRouted）
- [ ] Subtask 0.10: 编写 Gherkin 验收测试 `tests/acceptance/test_story_1_17.feature`
- [ ] Subtask 0.11: 编写 BDD 步骤实现 `tests/acceptance/test_story_1_17_steps.py`
- [ ] Subtask 0.12: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] Gherkin 验收测试运行失败（红阶段确认）
- [ ] 端口契约清单完整（registry/composition_root/contract test）

---

### Task 1: UDMRouter 领域服务 + RoutingDecision 值对象 + UDMRHandler

**关联 AC:** AC-1, AC-3

#### TDD 循环 [A]：RoutingDecision 值对象

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/value_objects/test_routing_decision.py`（验证 route_type/selected_model/fallback_reason 不变量） |
| 🟢 绿 | 实现 `src/domain/value_objects/routing_decision.py` — frozen dataclass |
| 🔄 重构 | 优化验证逻辑 |

- [ ] Subtask 1.1: 🔴 红 — 编写 RoutingDecision 失败测试
- [ ] Subtask 1.2: 🟢 绿 — 实现 RoutingDecision 值对象
- [ ] Subtask 1.3: 🔄 重构 — 优化不变量验证

#### TDD 循环 [B]：UDMRouter 领域服务

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/services/test_udmr_router.py`（验证本地优先路由、健康检查切换） |
| 🟢 绿 | 实现 `src/domain/services/udmr_router.py` — UDMRouter 类 |
| 🔄 重构 | 优化路由决策逻辑 |

- [ ] Subtask 1.4: 🔴 红 — 编写 UDMRouter 失败测试
- [ ] Subtask 1.5: 🟢 绿 — 实现 UDMRouter（注入 HealthCheckPort + 原始值类型：local_model, first_cloud_model, local_first, local_timeout）
- [ ] Subtask 1.6: 🔄 重构 — 优化决策逻辑

#### TDD 循环 [C]：UDMRHandler 事件桥接

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/event_handlers/test_udmr_handler.py`（验证 AutoRouted → RoutingDecided 桥接） |
| 🟢 绿 | 实现 `src/application/event_handlers/udmr_handler.py` — UDMRHandler 类 |
| 🔄 重构 | 优化事件处理 |

- [ ] Subtask 1.7: 🔴 红 — 编写 UDMRHandler 失败测试
- [ ] Subtask 1.8: 🟢 绿 — 实现 UDMRHandler（参考 AutoRouteHandler 模式）
- [ ] Subtask 1.9: 🔄 重构 — 优化桥接逻辑

#### 契约测试

- [ ] Subtask 1.10: 编写 `tests/contracts/test_port_contract_health_checker_factory.py`（端口注册/解析/兼容性）

#### 已有组件验证

- [ ] Subtask 1.11: 验证 RoutingDecided 事件 L3 字段完整性（扩展 `test_new_events.py`）
- [ ] Subtask 1.12: 验证 RoutingDecisionLog UDMR 字段（确认已有测试覆盖）

**完成标准/Definition of Done:**
- [ ] UDMRouter / RoutingDecision / UDMRHandler 全部实现
- [ ] HealthCheckerFactory 契约测试通过
- [ ] TDD 循环全部通过

---

### Task 2: 健康检查适配器 + 故障切换 + 配置

**关联 AC:** AC-2

#### TDD 循环 [A]：OllamaHealthAdapter

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/routing/test_ollama_health.py`（mock httpx，验证 check()/close()） |
| 🟢 绿 | 实现 `src/infrastructure/routing/ollama_health.py` — OllamaHealthAdapter + OllamaHealthCheckerFactory |
| 🔄 重构 | 优化错误处理 |

- [ ] Subtask 2.1: 🔴 红 — 编写 OllamaHealthAdapter 失败测试
- [ ] Subtask 2.2: 🟢 绿 — 实现 OllamaHealthAdapter（GET /api/tags，httpx AsyncClient）
- [ ] Subtask 2.3: 🔄 重构 — 优化超时和错误处理

#### TDD 循环 [B]：FallbackRouter

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/routing/test_fallback_router.py`（验证 local_first=true/false + 健康检查通过/失败 + 多云端选择逻辑） |
| 🟢 绿 | 实现 `src/infrastructure/routing/fallback_router.py` — FallbackRouter |
| 🔄 重构 | 优化切换逻辑 |

- [ ] Subtask 2.4: 🔴 红 — 编写 FallbackRouter 失败测试
- [ ] Subtask 2.5: 🟢 绿 — 实现 FallbackRouter（local_first + health_check → local/cloud 切换，选择第一启用云端模型）
- [ ] Subtask 2.6: 🔄 重构 — 验证 fallback_reason 字段

#### TDD 循环 [C]：UDMRConfig + CloudModelConfig

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/config/test_udmr_config.py`（验证 from_env() 解析 UDMR_* 变量、CloudModelConfig 多云端索引解析、默认值） |
| 🟢 绿 | 实现 `src/infrastructure/config/udmr.py` — UDMRConfig + CloudModelConfig |
| 🔄 重构 | 对齐 AutoRouteConfig 模式

- [ ] Subtask 2.7: 🔴 红 — 编写 UDMRConfig + CloudModelConfig 失败测试
- [ ] Subtask 2.8: 🟢 绿 — 实现 UDMRConfig（from_env，扫描 UDMR_CLOUD_{N}_* 变量）+ CloudModelConfig
- [ ] Subtask 2.9: 🔄 重构 — 对齐配置模式

#### TDD 循环 [D]：LocalModelHealthFacade

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_local_model_health_facade.py` |
| 🟢 绿 | 实现 `src/application/services/local_model_health_facade.py` |
| 🔄 重构 | 优化门面逻辑 |

- [ ] Subtask 2.10: 🔴 红 — 编写 LocalModelHealthFacade 失败测试
- [ ] Subtask 2.11: 🟢 绿 — 实现 LocalModelHealthFacade（注入 HealthCheckerFactory）
- [ ] Subtask 2.12: 🔄 重构 — 优化门面编排

**完成标准/Definition of Done:**
- [ ] OllamaHealthAdapter + OllamaHealthCheckerFactory 实现完成
- [ ] FallbackRouter 实现完成
- [ ] UDMRConfig 实现完成
- [ ] LocalModelHealthFacade 实现完成
- [ ] TDD 循环全部通过

---

### Task 3: SDD 架构验证 + DI 注册 + 集成测试

**关联 AC:** AC-1, AC-2, AC-3, AC-4

#### SDD 架构约束验证测试

- [ ] Subtask 3.1: 创建 `tests/unit/architecture/test_udmr_architecture.py`
- [ ] Subtask 3.2: 验证六边形架构约束（domain 零外部依赖、依赖方向、无循环依赖）
- [ ] Subtask 3.3: 验证端口注册完整性（registry/composition_root/contract test 三位一体）

#### DI 注册 + 事件订阅

- [ ] Subtask 3.4: 更新 `src/composition_root.py`
  - 注册 health_checker_factory 端口（SINGLETON, owner="story-1.17"）
  - 注册 udmr_handler 相关端口（参考 AutoRouteHandler 模式）
  - 注册 UDMRHandler 为 AutoRouted 事件订阅者（event_bus.subscribe）
  - > **注意**：当前 AutoRouteHandler/UDMRHandler 均未在 composition_root.py 中订阅事件总线。本 Subtask 需同时完成 UDMRHandler 的端口注册和事件订阅接线

#### 性能基准测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/performance/test_udmr_performance.py`（验证 P95<100ms） |
| 🟢 绿 | 实现性能优化（健康检查结果缓存） |
| 🔄 重构 | 性能调优 |

- [ ] Subtask 3.5: 🔴 红 — 编写性能基准失败测试
- [ ] Subtask 3.6: 🟢 绿 — 实现性能优化
- [ ] Subtask 3.7: 🔄 重构 — 性能调优

#### 集成测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/integration/test_story_1_17_integration.py`（AutoRouted → UDMRouter → RoutingDecided） |
| 🟢 绿 | 实现集成测试 |
| 🔄 重构 | 优化测试覆盖 |

- [ ] Subtask 3.8: 🔴 红 — 编写集成测试失败测试
- [ ] Subtask 3.9: 🟢 绿 — 实现端到端路由流程
- [ ] Subtask 3.10: 🔄 重构 — 优化测试覆盖

**完成标准/Definition of Done:**
- [ ] 六边形架构验证通过（无循环依赖，domain 零外部依赖）
- [ ] composition_root.py 端口注册完成
- [ ] 路由决策延迟 P95<100ms
- [ ] 集成测试通过
- [ ] `pytest tests/ -n 8` 并行测试通过

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) §4

- **架构模式:** 六边形架构（端口与适配器）、事件驱动架构
- **UDMR 三层决策架构（architecture.md §4.1）:**
  - L1 合规性网关 → Story 11.1（`ComplianceGatewayPort` 已就绪）
  - L2 四因子评分 → Story 11.2（未实现）
  - **L3 路由决策 → 本 Story（静态版本：本地优先 + 健康检查切换）**
- **L3 完整版（architecture.md §4.4）:** RouterExecutor 含 CLOUD_ADVANTAGE_THRESHOLD=0.15, LOCAL_QUALITY_THRESHOLD=0.70
  - 本 Story 实现**简化版**：if-else 规则（本地可用→local，否则→cloud），无评分逻辑
  - 完整版由 Story 11.2 补充
- **性能目标（architecture.md §1.5 NFR 表）:**
  - MVP: P95<100ms → 本 Story
  - V1: P95<50ms → Story 11.x
  - V2: P95<30ms → 远期

### 关键架构决策

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **UDMRouter 位于 domain/services/** | 符合六边形架构，依赖 HealthCheckPort 端口 | 需依赖倒置 | ✅ 9/10 |
| UDMRouter 位于 application/services/ | 实现简单 | 领域路由逻辑泄漏到应用层 | 6/10 |

### HealthCheckPort 延迟测量方案

**问题**：HealthCheckPort.check() 仅返回 bool，但 RoutingDecided 事件需要 health_check_latency_ms 字段。

**方案**：UDMRouter.check_local_health() 包装 HealthCheckPort.check() 调用，使用 `time.monotonic()` 测量耗时。不修改 HealthCheckPort 接口（遵循端口稳定性原则）。

### fallback_reason 枚举子集说明

**问题**：RoutingDecided 事件的 fallback_reason 允许 `"timeout"`（执行层 Story 1.14c 使用），但 Story 1.17 的 RoutingDecision 值对象仅限健康检查相关值。

**方案**：值对象 fallback_reason 是事件枚举的 MVP 子集。Story 1.17 仅产生 `"health_check_failed"` 和 `"unavailable"`，`"timeout"` 由执行层产生。类型兼容：子集赋值安全。

### 多云端配置对齐

**来源:** [`sprint-change-proposal-2026-05-11-udmr-cloud-models.md`](../../planning-artifacts/sprint-change-proposal-2026-05-11-udmr-cloud-models.md)

- CloudModelConfig 不设 index 字段（索引由列表位置决定）
- api_type 支持 "openai" | "anthropic" | "custom"
- UDMR_CLOUD_{N}_* 索引解析：from_env() 扫描 os.environ 中匹配 `UDMR_CLOUD_(\d+)_API_TYPE` 的键
- `@dataclass(frozen=True)` — UDMRConfig 和 CloudModelConfig 均为不可变配置
- 向后兼容：from_env() 检测旧 ENABLE_UDMR 变量并映射至 UDMR_ENABLED（打印 deprecation warning）
- 字段命名：`cloud_models`（Story 使用），sprint proposal 使用 `cloud_configs`，本 Story 统一为 `cloud_models`（语义更准确：列表元素是模型配置而非云端配置）

### OLLAMA_BASE_URL 依赖说明

OllamaHealthAdapter 需要 OLLAMA_BASE_URL 构造 Ollama API 地址。此变量**不纳入 UDMRConfig**（它是系统级配置，被多个组件共享）。注入路径：
1. OllamaHealthCheckerFactory.create() 从 os.getenv("OLLAMA_BASE_URL", "http://localhost:11434") 读取
2. 传入 OllamaHealthAdapter 构造函数

### 事件订阅接线说明

UDMRHandler 需订阅 AutoRouted 事件。当前 AutoRouteHandler 也未在 composition_root.py 中显式订阅事件总线（可能通过其他机制）。本 Story 在 Task 3 Subtask 3.4 中明确要求完成事件订阅接线，包括：
- composition_root.py 中注册 UDMRHandler 端口
- event_bus.subscribe(AutoRouted, udmr_handler.on_routed)

### UDMR 路由 vs AutoRoute 语义路由（澄清）

| 路由类型 | 职责 | 输入事件 | 输出事件 | 位置 |
|---------|------|---------|---------|------|
| **AutoRoute（1.14b）** | 选择目标 Agent/工具 | AutoTriggered | AutoRouted | AutoRouteService |
| **UDMR（1.17）** | 选择本地/云端模型 | AutoRouted | RoutingDecided | UDMRouter |

**数据流:**
```
AutoTriggered (1.14a)
    ↓
AutoRouteService (1.14b) → 一级路由 (hash/semantic/mixed)
    ↓ 发布 AutoRouted
UDMRouter (1.17) → 二级路由 (local/cloud)
    ↓ 发布 RoutingDecided
AutoExecuteService (1.14c) → 执行任务
```

### 项目结构说明

```
sisys/
├── src/
│   ├── domain/
│   │   ├── services/
│   │   │   └── udmr_router.py              # UDMRouter（新建）
│   │   ├── value_objects/
│   │   │   └── routing_decision.py         # RoutingDecision（新建）
│   │   ├── ports/
│   │   │   ├── health_check.py             # HealthCheckPort（已有）
│   │   │   └── health_check_factory.py     # HealthCheckerFactory（新建）
│   │   ├── events/
│   │   │   └── routing_events.py           # RoutingDecided（已有，复用）
│   │   └── entities/
│   │       └── routing_decision_log.py     # RoutingDecisionLog（已有，复用）
│   ├── application/
│   │   ├── services/
│   │   │   └── local_model_health_facade.py # LocalModelHealthFacade（新建）
│   │   └── event_handlers/
│   │       └── udmr_handler.py             # UDMRHandler（新建）
│   └── infrastructure/
│       ├── config/
│       │   └── udmr.py                     # UDMRConfig（新建）
│       └── routing/
│           ├── ollama_health.py            # OllamaHealthAdapter + Factory（新建）
│           └── fallback_router.py          # FallbackRouter（新建）
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   │   ├── services/test_udmr_router.py
│   │   │   └── value_objects/test_routing_decision.py
│   │   ├── application/
│   │   │   ├── services/test_local_model_health_facade.py
│   │   │   └── event_handlers/test_udmr_handler.py
│   │   ├── infrastructure/
│   │   │   ├── routing/test_ollama_health.py
│   │   │   ├── routing/test_fallback_router.py
│   │   │   └── config/test_udmr_config.py
│   │   ├── architecture/test_udmr_architecture.py
│   │   └── performance/test_udmr_performance.py
│   ├── integration/test_story_1_17_integration.py
│   ├── contracts/test_port_contract_health_checker_factory.py
│   └── acceptance/
│       ├── test_story_1_17.feature
│       └── test_story_1_17_steps.py
```

### 六边形架构分层说明

| 层级 | 目录 | 组件 | 职责 |
|------|------|------|------|
| **Domain** | `domain/` | UDMRouter, RoutingDecision, HealthCheckPort, HealthCheckerFactory | 核心路由逻辑和端口接口，零外部依赖 |
| **Application** | `application/` | LocalModelHealthFacade, UDMRHandler | 业务编排和事件桥接，接受端口注入 |
| **Infrastructure** | `infrastructure/` | OllamaHealthAdapter, FallbackRouter, UDMRConfig, CloudModelConfig | 技术实现，依赖 httpx |

### 前一个故事学习经验

**来源:** [Story 1.14a](./1-14a-autonomous-invocation-trigger.md) + [Story 1.14b](./1-14b-autonomous-invocation-route.md)

1. **配置模式复用** — UDMRConfig 采用与 AutoRouteConfig 相同的 `@dataclass` + `from_env()` 模式；CloudModelConfig 使用 UDMR_CLOUD_{N}_* 索引解析（支持多云端）
2. **事件驱动解耦** — UDMRouter 仅发布 RoutingDecided 事件，不调用 execute 逻辑
3. **Handler 桥接模式** — UDMRHandler 参考AutoRouteHandler 的 isinstance 类型守卫 + 委托服务 + 发布事件模式
4. **测试隔离** — BDD 步骤使用 `event_loop.run_until_complete()`，不用 `@pytest.mark.asyncio`
5. **Ollama mock 策略** — 健康检查测试 mock httpx.AsyncClient，不依赖真实 Ollama 实例
6. **多云端配置** — UDMR_CLOUD_{N}_* 索引模式支持多云端配置，MVP 选择第一启用云端作为 fallback 目标

**应用到本故事:**
- [ ] UDMRConfig 采用 AutoRouteConfig 的 from_env() 模式，增加 CloudModelConfig 多云端解析
- [ ] UDMRHandler 参考 AutoRouteHandler 桥接模式
- [ ] 健康检查测试使用 mock，不依赖真实 Ollama
- [ ] FallbackRouter 从 UDMRConfig.cloud_models 选择第一启用云端模型

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (create-story workflow) |
| **Version** | create-story workflow v1.0 |
| **Execution Date** | 2026-05-19 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|-----|
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `docs/architecture/architecture.md` §4 UDMR |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/1-14b-autonomous-invocation-route.md` |
| **Story 模板** | `docs/developer/story-template.md` v2.7.0 |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取
- [x] 架构约束从 `architecture.md` §4 提取
- [x] 现有代码继承已确认（RoutingDecided/RoutingDecisionLog/HealthCheckPort/AutoRouted）
- [x] 前一个故事学习经验已整合
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] UDMR vs AutoRoute 路由关系澄清
- [x] MVP 范围澄清（L3 静态路由，非 L1/L2）
- [x] 超时职责边界明确（仅健康检查，非 LLM 调用）
- [x] 健康检查字段分布文档化（事件有，实体无）

### 文件清单 File List

**待创建的文件/To Be Created (Dev Story 实施):**

领域层（Domain）:
- `src/domain/services/udmr_router.py` — UDMRouter 领域服务
- `src/domain/value_objects/routing_decision.py` — RoutingDecision 值对象
- `src/domain/ports/health_check_factory.py` — HealthCheckerFactory 端口

应用层（Application）:
- `src/application/services/local_model_health_facade.py` — LocalModelHealthFacade 门面
- `src/application/event_handlers/udmr_handler.py` — UDMRHandler 事件桥接

基础设施层（Infrastructure）:
- `src/infrastructure/config/udmr.py` — UDMRConfig 配置（含 CloudModelConfig 多云端索引解析）
- `src/infrastructure/routing/ollama_health.py` — OllamaHealthAdapter + OllamaHealthCheckerFactory
- `src/infrastructure/routing/fallback_router.py` — FallbackRouter

测试文件:
- `tests/unit/domain/services/test_udmr_router.py`
- `tests/unit/domain/value_objects/test_routing_decision.py`
- `tests/unit/application/services/test_local_model_health_facade.py`
- `tests/unit/application/event_handlers/test_udmr_handler.py`
- `tests/unit/infrastructure/routing/test_ollama_health.py`
- `tests/unit/infrastructure/routing/test_fallback_router.py`
- `tests/unit/infrastructure/config/test_udmr_config.py`
- `tests/unit/architecture/test_udmr_architecture.py`
- `tests/unit/performance/test_udmr_performance.py`
- `tests/integration/test_story_1_17_integration.py`
- `tests/contracts/test_port_contract_health_checker_factory.py`
- `tests/acceptance/test_story_1_17.feature`
- `tests/acceptance/test_story_1_17_steps.py`

**更新的文件/Updated Files:**
- `.env.example` — 替换 ENABLE_UDMR 为 UDMR_* 系列变量（UDMR_ENABLED/UDMR_LOCAL_FIRST/UDMR_LOCAL_TIMEOUT/UDMR_LOCAL_MODEL/UDMR_CLOUD_{N}_*）
- `src/composition_root.py` — 注册 health_checker_factory 端口
- `src/domain/ports/__init__.py` — 导出 HealthCheckerFactory
- `src/domain/services/__init__.py` — 导出 UDMRouter
- `src/domain/value_objects/__init__.py` — 导出 RoutingDecision
- `src/infrastructure/routing/__init__.py` — 导出 OllamaHealthAdapter, FallbackRouter
- `src/infrastructure/config/__init__.py` — 导出 UDMRConfig, CloudModelConfig
- `src/application/services/__init__.py` — 导出 LocalModelHealthFacade
- `src/application/event_handlers/__init__.py` — 导出 UDMRHandler

**已有文件（复用，禁止修改）:**
- `src/domain/events/routing_events.py` — RoutingDecided 事件（L3 字段已完整）
- `src/domain/entities/routing_decision_log.py` — RoutingDecisionLog 实体（UDMR 字段已存在）
- `src/domain/ports/health_check.py` — HealthCheckPort 端口
- `src/domain/events/auto_route_events.py` — AutoRouted 事件

---

## 📚 Project Context Reference

### 关键约束速查

| 约束类型 | 约束内容 | 来源 |
|---------|---------|------|
| **架构原则** | 六边形架构，领域层零依赖 | architecture.md §3.1 |
| **系统公理一** | trigger→route→execute 自主调用循环 | architecture.md §3.2 |
| **UDMR 三层决策** | L1 合规→L2 评分→L3 路由 | architecture.md §4 |
| **MVP 范围** | 仅 L3 静态路由（本地优先 + 健康检查切换） | epics_v1.0.md |
| **测试覆盖率** | 架构层≥85%，集成测试≥75% | story-template.md |

### 关键路径依赖

```
Story 1.14a (trigger) → Story 1.14b (语义路由) → Story 1.17 (UDMR 模型路由)
                                                                ↓
                                              Story 1.19 (CFO ROI 成本验证)
```

### UDMR 路由决策体系

| 层次 | 决策内容 | 输入 | 输出 | 归属 |
|------|---------|------|------|------|
| L1 合规性网关 | 敏感数据/数据驻留/白名单 | UDMRTask | ComplianceResult | Story 11.1 |
| L2 四因子评分 | 语义35%+成功30%+成本20%+复杂度15% | 合规通过 | 路由评分 | Story 11.2 |
| **L3 静态路由** | **本地优先，健康检查失败→云端** | **—** | **local/cloud** | **本 Story** |

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 1.17 |
| **Story Key** | 1-17-udmr-basic-routing |
| **File** | `_bmad-output/implementation-artifacts/stories/1-17-udmr-basic-routing.md` |
| **Status** | `ready-for-dev` |
| **Epic** | Epic 1: 企业级架构基础与合规 |
| **价值组** | 价值组 6: MVP 关键机制增强 |
| **优先级** | P0-17（ARCH UDMR 基础） |
| **覆盖 FR** | FR-CP-05（UDMR L3 静态路由）、or.md 系统公理一（route 模型路由子阶段） |
| **依赖 Story** | Story 1.14a（trigger）、Story 1.14b（语义路由 + 路由日志） |
| **前置条件** | AutoRouted 事件已定义（1.14b）、RoutingDecided 事件 L3 字段已定义、HealthCheckPort 已定义 |
| **后续 Story** | Story 1.19（CFO ROI 验证） |
| **覆盖率要求** | 架构层≥85%，集成测试≥75% |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成
2. [x] All acceptance criteria specified 所有验收标准已定义
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [x] Sprint status synced to `ready-for-dev`
6. [x] UDMR vs AutoRoute 路由关系澄清
7. [x] MVP 范围澄清（L3 静态路由，L1/L2 归 Story 11.x）
8. [x] 超时职责边界明确（仅健康检查，非 LLM 调用）
9. [x] 健康检查字段分布文档化（事件有，实体无）
10. [x] 端口契约治理完整（registry/composition_root/contract test）
11. [x] 环境变量模板对齐 UDMR_* 前缀 + 多云端索引（UDMR_CLOUD_{N}_*）
12. [x] 文件命名符合 story-template.md 规范（契约测试 test_port_contract_*、集成测试 test_story_x_y_*）

### 🔧 对抗性审查修复（Adversarial Review Fixes）

| # | 问题 | 严重度 | 修复方案 | 状态 |
|---|------|--------|----------|------|
| 1 | RoutingDecisionLog 实体无 health_check_passed/health_check_latency_ms 字段 | P0 | 明确字段分布：健康检查字段仅存在于 RoutingDecided 事件，不存在于实体。AC-3 添加字段分布说明 | ✅ |
| 2 | AC-2 "调用过程中超时" 职责越界 | P0 | UDMRouter 仅负责路由决策前的健康检查，不监控 LLM 调用超时。fallback_reason 仅保留 health_check_failed/unavailable | ✅ |
| 3 | 缺少 RoutingDecisionLog Repository | P0 | 日志通过 RoutingDecided 事件 + Outbox 机制自动持久化，不新增 Repository | ✅ |
| 4 | 缺少 composition_root.py DI 注册 | P1 | Task 3 包含 composition_root.py 端口注册 Subtask | ✅ |
| 5 | AutoRouted → UDMRouter 映射链缺失 | P1 | Task 1 包含 UDMRHandler 事件桥接 TDD 循环 | ✅ |
| 6 | 架构.md P95<50ms vs Story P95<100ms 不一致 | P1 | Dev Notes 明确 MVP/V1/V2 分级目标（100ms/50ms/30ms） | ✅ |
| 7 | HealthCheckPort.check() 仅返回 bool，无法获取 latency_ms | P0 | UDMRouter.check_local_health() 包装调用 + time.monotonic() 测量耗时，不修改端口接口 | ✅ R1 |
| 8 | RoutingDecided 事件 fallback_reason 含 "timeout"，值对象不含 | P0 | 值对象是事件枚举的 MVP 子集，类型兼容，Dev Notes 文档化 | ✅ R1 |
| 9 | CloudModelConfig.index 字段冗余 | P1 | 移除 index 字段，索引由列表位置决定，对齐 sprint-change-proposal | ✅ R1 |
| 10 | UDMRHandler 事件订阅缺失 | P0 | Task 3 Subtask 3.4 明确要求 event_bus.subscribe(AutoRouted, udmr_handler.on_routed) | ✅ R2 |
| 11 | OLLAMA_BASE_URL 依赖未文档化 | P0 | Dev Notes 添加 OLLAMA_BASE_URL 依赖说明，OllamaHealthCheckerFactory.create() 注入 | ✅ R2 |
| 12 | cloud_models vs cloud_configs 命名不一致 | P1 | 统一为 cloud_models（语义更准确），Dev Notes 文档化决策 | ✅ R2 |
| 13 | frozen=True vs mutable 不一致 | P0 | UDMRConfig 和 CloudModelConfig 均使用 frozen=True，对齐 sprint-change-proposal | ✅ R2 |
| 14 | ENABLE_UDMR → UDMR_ENABLED 向后兼容未提及 | P1 | from_env() 检测旧变量并映射，打印 deprecation warning | ✅ R2 |
| 15 | AutoRouted 无 task_id，RoutingDecided 需要 task_id | P0 | task_id = event.event_id，保持事件链聚合标识一致性 | ✅ R3 |
| 16 | UDMRouter vs UDMRHandler 双重发布歧义 | P0 | UDMRouter 仅返回 RoutingDecided，UDMRHandler 负责发布 | ✅ R3 |
| 17 | UDMRConfig（infrastructure）导入到 domain 层违规 | P0 | UDMRouter 构造函数改为原始值类型（str/bool/int/list），composition_root 传入 | ✅ R3 |
| 18 | 追溯矩阵 Task 3 编号偏移一位 | P1 | 3.4-3.6→3.5-3.7，3.7-3.9→3.8-3.10 | ✅ R3 |
| 19 | test_routing_events_udmr.py 命名与 subtask 不一致 | P1 | 统一为扩展已有 test_new_events.py | ✅ R3 |
| 20 | "第一启用云端模型"选择算法未定义 | P1 | next(m for m in cloud_models if m.enabled)，按 N 升序 | ✅ R3 |
| 21 | AC-4 P95<100ms 未区分 mock vs 真实健康检查 | P1 | 明确 MVP 基准使用 mock 健康检查 | ✅ R3 |
| 22 | UDMRouter 返回 RoutingDecided（事件）而非 RoutingDecision（值对象） | P0 | 修正返回类型为 RoutingDecision 值对象 | ✅ R4 |
| 23 | EventPublisher 注入冗余（UDMRouter 不发布） | P0 | 移除 EventPublisher，构造函数仅注入 HealthCheckPort + 原始值 | ✅ R4 |
| 24 | cloud_models 类型矛盾（list[str] vs list[CloudModelConfig]） | P0 | 改为 first_cloud_model: str，composition_root 预筛选 | ✅ R4 |
| 25 | cost_estimate vs estimated_cost 命名不一致 | P1 | 统一为 estimated_cost，对齐 RoutingDecided 事件 | ✅ R4 |
| 26 | RoutingDecision.latency_ms 冗余字段未定义用途 | P2 | 移除，仅保留 health_check_latency_ms | ✅ R4 |
| 27 | Subtask 1.5 仍引用 UDMRConfig | P0 | 更新为原始值类型描述 | ✅ R4 |

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查

---

## 📚 相关文档 Related Documents

| 文档 | 说明 |
|------|------|
| [SDD+TDD 融合开发模式指南](./sdd-tdd-fusion-guide.md) | 开发模式详细说明与各层测试模板 |
| [SDD+TDD 实施检查清单](./sdd-tdd-checklist.md) | 实施步骤检查 |
| [or.md 系统公理一](../planning-artifacts/or.md) | 系统公理定义 |
| [Story 1.14a: 自主调用循环 - trigger](./1-14a-autonomous-invocation-trigger.md) | 前置 Story（已完成） |
| [Story 1.14b: 自主调用循环 - route](./1-14b-autonomous-invocation-route.md) | 前置 Story |
| [Story 1.19: CFO ROI 验证](./1-19-cfo-roi-verification.md) | 后续 Story（依赖本 Story） |

---

**模板版本/Template Version:** 2.7.0
**创建日期/Created:** 2026-05-19
**最后更新/Last Updated:** 2026-05-19
**更新说明:** Story 1.17 完整重写（v2.7.0 模板）- 实现 UDMR 基础路由（本地优先静态配置）。修复旧版 7 个问题：职责边界明确（仅健康检查）、字段分布文档化（事件 vs 实体）、DI 注册纳入 Task、事件桥接 Handler 纳入 TDD、MVP 性能目标分级说明。审查完善：环境变量统一 UDMR_* 前缀 + UDMR_CLOUD_{N}_* 多云端索引配置、CloudModelConfig 新增、文件命名对齐 story-template.md 规范。
