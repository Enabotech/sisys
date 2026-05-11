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

本 Story 是 Epic 1（企业级架构基础与合规）价值组 6（MVP 关键机制增强）的第一个故事，在 Story 1.14b（route 路由机制）完成后实现 UDMR（统一动态模型路由）基础路由。核心价值：

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **本地优先路由** | 降低成本，本地模型成本显著低于云端 | 本地路由占比≥80%（业务目标，基于本地模型可用率>95%假设） |
| **故障自动切换** | 本地模型不可用或超时时自动切换云端 | 故障切换时间<30秒 |
| **路由决策日志** | 记录路由决策过程，支持审计和成本追踪 | WORM 归档 |
| **路由性能要求** | 路由决策延迟满足性能要求 | P95<100ms（MVP） |

> ⚠️ **MVP 范围澄清**：本 Story 实现 **简化的 L3 功能（本地优先静态配置）**，属于 MVP 降级实现（不等同于 L3 动态阈值）
> - **L3 动态阈值**（基于 L2 评分的自适应决策）→ Story 11.2 范围
> - **本 Story 实现**：本地优先 + 超时>30s 切换云端（简化版本，无 L2 评分依赖）

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 1: 企业级架构基础与合规，价值组 6: MVP 关键机制增强，Story 1.17

**or.md 公理追溯:** 系统公理一（自主调用：trigger→route→execute），覆盖"route"阶段的**模型路由决策子阶段**（两-tier 路由：语义路由→UDMR 模型路由）

---

## 🔗 前置依赖与现有代码继承

### 依赖故事

| 故事 | 组件 | 用途 |
|------|------|------|
| Story 1.3 | Event Bus | 事件发布基础设施 |
| Story 1.14a | AutoTriggerService + AutoTriggered | 触发机制 |
| Story 1.14b | AutoRouteService + AutoRouted + RoutingDecisionLog | 路由机制 + 决策日志 |
| Story 1.14c | AutoExecuteService + AutoExecuted | 执行机制 |

### 现有代码继承（必须复用，禁止重复定义）

| 现有组件 | 文件路径 | 复用方式 |
|---------|---------|---------|
| `EventPublisher` (Protocol) | `src/domain/ports/event_publisher.py` | 事件发布接口 |
| `RedisEventPublisher` | `src/infrastructure/messaging/redis_publisher.py` | 事件发布实现 |
| `RoutingDecided` 事件 | `src/domain/events/routing_events.py` | 发布 UDMR 决策事件 |
| `RoutingDecisionLog` 实体 | `src/domain/entities/routing_decision_log.py` | UDMR 扩展字段已存在 |
| `HealthCheckPort` | `src/domain/ports/health_check.py` | 健康检查接口 |
| `AutoRouted` 事件 | `src/domain/events/auto_route_events.py` | 接收路由事件 |

### 架构位置

```
AutoTriggered (1.14a)
       ↓
AutoRouteService (1.14b) → 一级路由 (hash/semantic/mixed)
       ↓
  [UDMRouter 1.17] → 二级路由 (local/cloud) ← HERE
       ↓
RoutingDecided 事件 (更新 selected_model, fallback_reason)
       ↓
AutoExecuteService (1.14c)
       ↓
AutoExecuted
```

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 本地优先静态路由配置

**Given** 系统配置了本地模型（Ollama+Qwen2.5）和云端模型（Qwen/Claude）
**When** 执行 LLM 任务
**Then** 根据静态配置路由（本地优先）
**And** 记录路由决策日志（任务 ID、时间戳、选定路由、选定模型、成本预估、延迟）

**验证标准/Validation Criteria:**
- [ ] UDMRouter 类实现（`src/domain/services/udmr_router.py`）
- [ ] 静态路由配置（`src/infrastructure/config/udmr.py`）
- [ ] 本地模型健康检查（Ollama 连接检测）
- [ ] 路由决策日志记录（RoutingDecisionLog）
- [ ] 本地路由占比≥80%

### AC-2: 故障切换机制

**Given** 本地模型不可用或响应超时（>30秒）
**When** UDMRouter 执行路由决策
**Then** 自动切换至云端模型
**And** 记录切换原因和切换时间

> 🔄 **故障切换时序**：
> 1. **路由决策前** → LocalModelHealth 执行快速 ping 检测（健康检查）
> 2. **本地可用** → 直接路由至本地模型
> 3. **本地不可用/超时** → 触发故障切换，路由至云端模型
> 4. **调用过程中** → 如果实际调用超时（>30秒），中断并切换云端

**验证标准/Validation Criteria:**
- [ ] 本地模型健康检查（Ollama ping，路由决策前执行）
- [ ] 超时检测（30秒阈值，调用过程中执行）
- [ ] 自动故障切换逻辑（健康检查失败 OR 调用超时 → 切换云端）
- [ ] 切换日志记录（fallback_reason: "timeout" | "unavailable" | "health_check_failed"）
- [ ] 故障切换时间<30秒

### AC-3: 路由决策日志

**Given** 路由决策完成
**When** UDMRouter 发布路由决策事件
**Then** 记录路由决策日志至 PostgreSQL（Story 1.14b 已实现）
**And** 日志包含：任务 ID、路由类型（route_type）、选定模型（selected_model）、成本预估（cost_estimate）、成本实际（cost_actual）、延迟、切换原因（fallback_reason）

> 📝 **RoutingDecisionLog 扩展字段说明**：
> Story 1.14b 已实现以下 UDMR 扩展字段，本 Story **验证**这些字段符合 AC-3 要求：
> - `route_type: Literal["local", "cloud"]` — 路由类型（Story 1.14b 已实现，本 Story 验证）
> - `selected_model: str` — 选定的模型名称（Story 1.14b 已实现，本 Story 验证）
> - `fallback_reason: Optional[str]` — 切换原因（Story 1.14b 已实现，本 Story 验证）

**验证标准/Validation Criteria:**
- [ ] RoutingDecisionLog 数据模型验证（`src/domain/entities/routing_decision_log.py`）
  - 验证 `route_type: Literal["local", "cloud"]` 字段存在且有效
  - 验证 `selected_model: str` 字段存在且非空（当 route_type=cloud 时）
  - 验证 `fallback_reason: Optional[str]` 字段存在且有效
- [ ] 路由决策日志存储至 PostgreSQL
- [ ] WORM 归档标识（RoutingDecisionLog 实体已有 worm_storage_ref 字段）
- [ ] 日志字段完整性校验
- [ ] 路由决策日志可检索性（按 session_id/任务 ID/时间范围）

### AC-4: 路由性能要求

**Given** UDMRouter 接收路由请求
**When** 执行路由决策
**Then** 路由决策延迟 P95<100ms

**验证标准/Validation Criteria:**
- [ ] 路由决策延迟 P95<100ms（基准测试：1000 次连续请求，预热 100 次）
- [ ] 本地路由占比≥80%
- [ ] 路由决策幂等性（相同输入产生相同输出）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域服务 Schema (Domain Services)
- [ ] UDMRouter 服务类（`src/domain/services/udmr_router.py`）
  - 方法: `async route(task_context) -> RoutingDecision`, `async check_local_health() -> bool`
  - 职责: 接收任务上下文、执行本地优先路由决策、发布路由决策事件

#### 端口接口 Schema (Domain Ports)
- [ ] HealthCheckPort 端口接口（`src/domain/ports/health_check.py`）
  - 方法: `async check() -> bool`, `async close() -> None`
  - 职责: 定义健康检查的统一接口契约（异步，零外部依赖）
- [ ] HealthCheckerFactory 工厂接口（`src/domain/ports/health_check_factory.py`）
  - 方法: `async create() -> HealthCheckPort`
  - 职责: 定义创建 HealthCheckPort 实例的工厂接口（零外部依赖）

#### 配置模型 (Configuration Models)
- [ ] UDMRConfig 配置（`src/infrastructure/config/udmr.py`）
  - 环境变量: `UDMR_ENABLED`, `UDMR_LOCAL_FIRST`, `UDMR_LOCAL_TIMEOUT`（秒，30秒默认）, `UDMR_LOCAL_MODEL`, `UDMR_CLOUD_{n}_API_TYPE`, `UDMR_CLOUD_{n}_ENDPOINT`, `UDMR_CLOUD_{n}_API_KEY`, `UDMR_CLOUD_{n}_MODEL`, `UDMR_CLOUD_{n}_ENABLED`（其中 n=0,1,2，最多3个云端配置）
  - 从环境变量读取（`from_env()` 方法，复用 OtelConfig 模式）

#### 应用层入口 Schema (Application Facade)
- [ ] LocalModelHealthFacade 门面（`src/application/services/local_model_health_facade.py`）
  - 方法: `async check() -> bool`, `async close() -> None`
  - 职责: 根据配置选择具体 Adapter（Ollama/Gemini/vLLM），统一暴露给 UDMRouter

#### 路由决策模型 (Routing Decision Model)
- [ ] RoutingDecision 值对象（`src/domain/value_objects/routing_decision.py`）
  - 字段:
    - `route_type: Literal["local", "cloud"]` — 路由类型
    - `selected_model: str` — 选定的模型名称（非空）
    - `cost_estimate: float` — 预估成本（USD）
    - `cost_actual: float` — 实际成本（USD）
    - `latency_ms: float` — 延迟（毫秒）
    - `fallback_reason: Optional[Literal["timeout", "unavailable", "health_check_failed"]]` — 切换原因

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_story_1.17.feature`（由 Dev agent 在 Task 0 创建）
- [ ] 覆盖场景:
  - 本地优先路由（local 模型可用）
  - 故障切换路由（local 模型不可用）
  - 超时切换路由（local 模型超时>30秒）
  - 路由决策日志记录
  - 路由性能 P95<100ms

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
| **TDD 单元测试** | UDMRouter | 本地优先路由 | `test_udmr_router.py` | Task 1 |
| **TDD 单元测试** | LocalModelHealth | 健康检查 | `test_local_model_health.py` | Task 1 |
| **TDD 单元测试** | FallbackRouter | 故障切换 | `test_fallback_router.py` | Task 2 |
| **TDD 单元测试** | RoutingDecisionLog | 路由决策日志 | `test_routing_decision_log.py` | Task 2 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_story_1.17.feature` | Task 0 |
| **SDD 架构验证** | 路由解耦 | 六边形架构约束 | `test_udmr_architecture.py` | Task 3 |
| **集成测试** | 事件总线 | 端到端路由流程 | `test_udmr_integration.py` | Task 3 |

---

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
| **BDD async 协调** | BDD 步骤使用 `asyncio.get_event_loop()` 而非 `loop` fixture | 事件循环冲突 |
| **asyncio.run** | 测试中避免使用 `asyncio.run()`，使用 `await` 或 `asyncio.get_event_loop().run_until_complete()` | 事件循环重复创建 |
| **并发测试方法** | 并发测试使用 `threading` 而非 `multiprocessing`（进程隔离问题） | 资源泄漏 |
| **语义缓存隔离** | 语义缓存基于向量相似度，多测试用相同 embedding 会互相覆盖缓存，需要用 unique_cache_key 生成不同 embedding | 缓存互相覆盖 |

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
| AC-1 | 本地优先静态路由配置 | Task 1 | Subtask 1.1-1.3（UDMRouter 红→绿→重构） | `test_udmr_router.py` |
| AC-1 | 本地模型健康检查 | Task 1 | Subtask 1.4-1.6（LocalModelHealthFacade 红→绿→重构） | `test_local_model_health_facade.py` |
| AC-2 | 故障切换机制 | Task 2 | Subtask 2.1-2.3（FallbackRouter 红→绿→重构） | `test_fallback_router.py` |
| AC-3 | 路由决策日志 | Task 2 | Subtask 2.4-2.6（RoutingDecisionLog 红→绿→重构） | `test_routing_decision_log.py` |
| AC-4 | 路由性能要求 | Task 3 | Subtask 3.4-3.6（性能基准测试 红→绿→重构） | `test_udmr_performance.py` |
| AC-1 | HealthCheckPort 端口接口 | Task 0 | Subtask 0.4（SDD 规范定义） | - |

---

## 📋 Tasks / Subtasks 任务分解

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4

> **目的：** 在进入代码实现前，明确 Schema、API 契约、验收标准。

- [ ] Subtask 0.1: 定义 UDMRouter 服务类（`src/domain/services/udmr_router.py`）
- [ ] Subtask 0.2: 定义 RoutingDecision 值对象（`src/domain/value_objects/routing_decision.py`）
- [ ] Subtask 0.3: 定义 UDMRConfig 配置模型（`src/infrastructure/config/udmr.py`）
- [ ] Subtask 0.4: 定义 HealthCheckPort 端口接口（`src/domain/ports/health_check.py`）
- [ ] Subtask 0.5: 定义 HealthCheckerFactory 工厂接口（`src/domain/ports/health_check_factory.py`）
- [ ] Subtask 0.6: 定义 LocalModelHealthFacade 应用层入口（`src/application/services/local_model_health_facade.py`）
- [ ] Subtask 0.7: 定义 FallbackRouter 故障切换（`src/infrastructure/routing/fallback_router.py`）
- [ ] Subtask 0.8: 验证 RoutingDecisionLog UDMR 扩展字段Schema（Story 1.14b 已实现的 route_type/selected_model/fallback_reason 符合本 Story AC-3 要求）
- [ ] Subtask 0.9: 编写 Gherkin 验收测试 `tests/acceptance/test_story_1.17.feature`（Dev agent 创建）
- [ ] Subtask 0.10: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕（Subtask 0.1-0.8）
- [ ] Gherkin 验收测试已编写（Subtask 0.8）
- [ ] 验收测试运行失败（Subtask 0.9，🔴 红阶段验证）

> **📝 Task 0 特殊性说明**：
> - Task 0 是 SDD 规范定义阶段，不是 TDD 实现阶段，因此**不执行绿→重构阶段**
> - Task 0 的"红"= Gherkin 验收测试失败（BDD 层面），而 Task 1-3 的"红"= TDD 单元测试失败（代码层面）
> - Task 0 定义的 Schema 是后续 Task 1-3 TDD 测试的契约输入

---

### Task 1: 本地优先路由与健康检查

**关联 AC:** AC-1

> **职责边界:** Task 1 负责 UDMRouter（本地优先路由）和 LocalModelHealth（健康检查）

#### TDD 循环 [A]：UDMRouter 本地优先路由

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/services/test_udmr_router.py`（验证本地优先路由） |
| 🟢 绿 | 实现 `src/domain/services/udmr_router.py` - UDMRouter 类 |
| 🔄 重构 | 添加类型注解和文档字符串 |

- [ ] Subtask 1.1: 🔴 红 — 编写 UDMRouter 失败测试
- [ ] Subtask 1.2: 🟢 绿 — 实现 UDMRouter（本地优先路由）
- [ ] Subtask 1.3: 🔄 重构 — 优化路由决策逻辑

#### TDD 循环 [B]：LocalModelHealthFacade 应用层入口

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/services/test_local_model_health_facade.py`（验证多模型路由） |
| 🟢 绿 | 实现 `src/application/services/local_model_health_facade.py` - LocalModelHealthFacade 类 |
| 🔄 重构 | 添加类型注解和文档字符串 |

- [ ] Subtask 1.4: 🔴 红 — 编写 LocalModelHealthFacade 失败测试
- [ ] Subtask 1.5: 🟢 绿 — 实现 LocalModelHealthFacade（多模型工厂，根据配置返回 OllamaHealthAdapter）
- [ ] Subtask 1.6: 🔄 重构 — 优化健康检查逻辑

**完成标准/Definition of Done:**
- [ ] UDMRouter 实现完成（本地优先路由）
- [ ] LocalModelHealth 实现完成（Ollama 连接检测）
- [ ] 本地路由占比≥80%
- [ ] TDD 循环全部通过

---

### Task 2: 故障切换与路由决策日志

**关联 AC:** AC-2, AC-3

> **职责边界:** Task 2 负责 FallbackRouter（故障切换）和 RoutingDecisionLog（路由决策日志）

#### TDD 循环 [A]：FallbackRouter 故障切换

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/routing/test_fallback_router.py`（验证故障切换） |
| 🟢 绿 | 实现 `src/infrastructure/routing/fallback_router.py` - FallbackRouter 类 |
| 🔄 重构 | 优化切换逻辑 |

- [ ] Subtask 2.1: 🔴 红 — 编写 FallbackRouter 失败测试
- [ ] Subtask 2.2: 🟢 绿 — 实现 FallbackRouter（超时检测 + 云端切换）
- [ ] Subtask 2.3: 🔄 重构 — 验证切换日志

#### TDD 循环 [B]：RoutingDecisionLog 路由决策日志验证

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/entities/test_routing_decision_log.py`（验证 UDMR 扩展字段符合 AC-3） |
| 🟢 绿 | 验证 `src/domain/entities/routing_decision_log.py` - UDMR 扩展字段符合 AC-3 要求（route_type/selected_model/fallback_reason） |
| 🔄 重构 | 验证 WORM 归档标识 |

- [ ] Subtask 2.4: 🔴 红 — 编写 RoutingDecisionLog 失败测试
- [ ] Subtask 2.5: 🟢 绿 — 验证 RoutingDecisionLog 实体（验证 UDMR 扩展字段 route_type/selected_model/fallback_reason 符合 AC-3 要求）
- [ ] Subtask 2.6: 🔄 重构 — 验证 WORM 归档标识

**完成标准/Definition of Done:**
- [ ] FallbackRouter 实现完成（超时>30秒切换云端）
- [ ] RoutingDecisionLog 验证完成（UDMR 扩展字段符合 AC-3）
- [ ] 故障切换时间<30秒
- [ ] TDD 循环全部通过

---

### Task 3: 架构验证与性能基准

**关联 AC:** AC-3, AC-4

> **职责边界:** Task 3 负责六边形架构验证和性能基准测试

#### TDD 循环 [A]：六边形架构验证

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/architecture/test_udmr_architecture.py`（验证架构约束） |
| 🟢 绿 | 实现架构验证逻辑（循环依赖检测、依赖方向检测） |
| 🔄 重构 | 优化架构验证器 |

- [ ] Subtask 3.1: 🔴 红 — 编写架构验证失败测试
- [ ] Subtask 3.2: 🟢 绿 — 实现架构验证逻辑
- [ ] Subtask 3.3: 🔄 重构 — 验证器优化

#### TDD 循环 [B]：性能基准测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/performance/test_udmr_performance.py`（验证性能要求） |
| 🟢 绿 | 实现性能优化（缓存路由结果） |
| 🔄 重构 | 性能调优 |

- [ ] Subtask 3.4: 🔴 红 — 编写性能基准失败测试
- [ ] Subtask 3.5: 🟢 绿 — 实现性能优化
- [ ] Subtask 3.6: 🔄 重构 — 性能调优

#### TDD 循环 [C]：集成测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/integration/test_udmr_integration.py`（端到端路由流程） |
| 🟢 绿 | 实现集成测试（事件总线端到端路由流程） |
| 🔄 重构 | 优化测试覆盖 |

- [ ] Subtask 3.7: 🔴 红 — 编写集成测试失败测试
- [ ] Subtask 3.8: 🟢 绿 — 实现端到端路由流程
- [ ] Subtask 3.9: 🔄 重构 — 优化测试覆盖

**完成标准/Definition of Done:**
- [ ] 六边形架构验证通过（无循环依赖）
- [ ] 路由决策延迟 P95<100ms
- [ ] 本地路由占比≥80%
- [ ] 集成测试通过

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（端口与适配器）、事件驱动架构
- **系统公理一:** trigger→route→execute 自主调用循环
  - trigger: 领域事件/心跳事件触发 → Story 1.14a
  - route: session_id 哈希/语义路由 + UDMR 模型路由 → Story 1.14b + Story 1.17
  - execute: 会话命名空间执行与状态快照 → Story 1.14c
- **UDMR MVP 静态路由（本 Story 范围）：**
  - 本地优先：本地模型优先路由
  - 超时切换：本地响应超时>30秒时自动切换云端
  - 静态配置：无动态评分，纯 if-else 规则
- **UDMR 完整架构（Story 11.x 范围）：**
  - L1 合规性网关: 敏感数据检查、数据驻留限制、白名单校验 → Story 11.1
  - L2 四因子评分: 语义匹配度35% + 历史成功率30% + 成本效率20% + 任务复杂度15% → Story 11.2
  - L3 动态阈值: 基于 L2 评分的自适应决策（云模型优势阈值0.15, 本地质量阈值0.70）→ Story 11.2
    - 注意：本 Story 实现的是 **L3 静态阈值**（本地优先，超时切换），与 Story 11.2 的动态阈值不冲突
- **设计约束:**
  - 领域层零依赖外部框架
  - 依赖倒置：领域层定义接口，基础设施层实现
  - 本地优先：本地模型优先，本地不可用或超时>30秒时切换云端
- **技术栈:**
  - 本地模型: Ollama+Qwen2.5
  - 云端模型: Qwen/Claude
  - 路由决策延迟目标: P95<100ms（MVP 静态配置）

### LocalModelHealth 六边形架构设计

> ⚠️ **重要澄清：** UDMRouter 需要健康检查能力，但不应该直接依赖具体实现（Ollama）。

```
Domain Layer（端口 — 零外部依赖）
└── ports/
    └── health_check.py          # HealthCheckPort（异步接口，ABC）

Application Layer（门面 — 业务编排）
└── services/
    └── local_modelhealth_facade.py   # LocalModelHealthFacade（多模型统一入口）

Infrastructure Layer（适配器 — 具体实现）
└── routing/
    ├── ollama_health.py          # OllamaHealthAdapter（实现 HealthCheckPort）
    ├── gemini_health.py           # Future: Gemini 实现
    └── vllm_health.py             # Future: vLLM 实现
```

#### 核心设计原则

1. **依赖倒置**：Domain 层定义 `HealthCheckPort` 接口，Infrastructure 层实现
2. **Application 层门面**：`LocalModelHealthFacade` 隐藏具体 Adapter 细节
3. **UDMRouter 依赖**：使用 `HealthCheckPort`（异步）而非同步实现

### UDMR 与 Story 1.14b 语义路由的关系澄清

> ⚠️ **重要澄清**：Story 1.14b 语义路由和 Story 1.17 UDMR 路由是两个不同的路由机制！

| 路由类型 | 职责 | 位置 | 依赖 |
|---------|------|------|------|
| **语义路由（Story 1.14b）** | 基于任务语义将任务路由至目标 Agent/工具 | RouteService | Story 1.6（bge-m3） |
| **UDMR 路由（Story 1.17）** | 基于本地优先静态配置选择本地/云端模型（L3 静态版本） | UDMRouter | Story 1.14b（路由日志） |

**数据流**:
```
Triggered 事件（Story 1.14a）
    ↓
AutoRouteService（语义路由）→ 选择目标 Agent/工具
    ↓ 发布 AutoRouted 事件
UDMRouter（UDMR 路由）→ 接收 AutoRouted 事件，选择本地/云端模型 ← 本 Story
    ↓
Execute（Story 1.14c）→ 执行任务
```

> **UDMRouter 输入说明**：UDMRouter 接收 `Routed` 事件（两-tier 路由模式：语义路由→模型路由）。MVP 可选优化：支持直接调用 UDMRouter 进行单次路由决策（绕过事件驱动），适用于批量场景或极致性能要求。

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── domain/
│   │   ├── ports/
│   │   │   ├── health_check.py        # HealthCheckPort（Domain Port，异步接口）
│   │   │   └── health_check_factory.py # HealthCheckerFactory（Domain 工厂接口）
│   │   ├── services/
│   │   │   └── udmr_router.py         # UDMRouter（Domain Service，核心逻辑）
│   │   ├── value_objects/
│   │   │   └── routing_decision.py    # RoutingDecision 值对象
│   │   └── entities/
│   │       └── routing_decision_log.py # RoutingDecisionLog（已存在，本 Story 扩展）
│   ├── application/
│   │   └── services/
│   │       └── local_model_health_facade.py  # LocalModelHealthFacade（Application Facade）
│   └── infrastructure/
│       ├── config/
│       │   └── udmr.py                # UDMRConfig 配置
│       └── routing/
│           ├── ollama_health.py       # OllamaHealthAdapter + OllamaHealthCheckerFactory（配对）
│           ├── local_model_health.py   # LocalModelHealth + create_local_model_health_facade（入口）
│           └── fallback_router.py      # FallbackRouter（故障切换）
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   │   ├── services/
│   │   │   │   └── test_udmr_router.py
│   │   │   └── value_objects/
│   │   │       └── test_routing_decision.py
│   │   └── infrastructure/
│   │       └── routing/
│   │           ├── test_local_model_health.py
│   │           └── test_fallback_router.py
│   ├── integration/
│   │   └── test_udmr_integration.py
│   └── acceptance/
│       ├── test_story_1.17.feature
│       └── test_story_1.17_steps.py
└── docs/
    └── developer/
        └── udmr_guide.md              # UDMR 实施指南
```

### 六边形架构分层说明

| 层级 | 目录 | 组件 | 职责 |
|------|------|------|------|
| **Domain（领域层）** | `domain/` | `HealthCheckPort`, `HealthCheckerFactory`, `UDMRouter`, `RoutingDecision` | 定义接口契约和核心业务逻辑，零外部依赖 |
| **Application（应用层）** | `application/services/` | `LocalModelHealthFacade` | 业务编排，接受 factory 注入，不直接创建 Infrastructure 对象 |
| **Infrastructure（基础设施层）** | `infrastructure/routing/` | `OllamaHealthAdapter`, `OllamaHealthCheckerFactory`, `FallbackRouter` | 具体技术实现，依赖外部库（httpx） |

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 1.14b: 自主调用循环 - route](./1-14b-autonomous-invocation-route.md)

**关键学习/Key Learnings:**
1. **配置模式复用** — OtelConfig.from_env() 模式应复用，UDMRConfig 采用相同 `from_env()` 类方法
2. **事件驱动解耦** — RouteService 仅负责触发和上下文提取，不处理业务逻辑；UDMRouter 应遵循相同模式
3. **六边形架构严格遵守** — Task 3 必须包含架构验证测试，确保无循环依赖
4. **性能基准测试** — 路由性能要求 P95<100ms，需独立基准测试
5. **AutoRouteService 命名** — 本故事正确使用 AutoRouteService，避免与 RouteService（语义路由）混淆

**应用到本故事/Applied to This Story:**
- [ ] UDMRConfig 采用与 OtelConfig 相同的 `from_env()` 模式
- [ ] UDMRouter 仅负责模型路由决策，不处理 execute 逻辑
- [ ] Task 3 包含架构验证测试（六边形架构约束检测）
- [ ] 性能基准测试验证 P95<100ms

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (create-story workflow) |
| **Version** | create-story workflow v1.0 |
| **Execution Date** | 2026-05-11 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Instructions** | `_bmad/bmm/workflows/4-implementation/create-story/instructions.xml` |
| **Template** | `_bmad/bmm/workflows/4-implementation/create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/1-14b-autonomous-invocation-route.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |
| **项目上下文** | `_bmad-output/project-context.md` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取
- [x] 架构约束从 `architecture.md` 提取
- [x] or.md 系统公理一（route）追溯完成
- [x] UDMR 三层决策架构分析完成（明确 MVP 仅实现 L3 静态版本）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] 前一个故事学习经验已整合
- [x] UDMR 与语义路由关系澄清

### 文件清单 File List

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/domain/services/udmr_router.py` - UDMRouter 服务类
- `src/domain/value_objects/routing_decision.py` - RoutingDecision 值对象
- `src/infrastructure/config/udmr.py` - UDMRConfig 配置模型
- `src/application/services/local_model_health_facade.py` - LocalModelHealthFacade（多模型工厂门面）
- `src/infrastructure/routing/ollama_health.py` - OllamaHealthAdapter + OllamaHealthCheckerFactory（配对实现）
- `src/infrastructure/routing/local_model_health.py` - LocalModelHealth + create_local_model_health_facade（入口）
- `src/infrastructure/routing/fallback_router.py` - FallbackRouter 故障切换
- `src/domain/entities/routing_decision_log.py` - RoutingDecisionLog 扩展（添加本地/云端路由字段）
- `tests/unit/domain/services/test_udmr_router.py` - UDMRouter 单元测试
- `tests/unit/domain/value_objects/test_routing_decision.py` - RoutingDecision 值对象测试
- `tests/unit/infrastructure/routing/test_local_model_health.py` - LocalModelHealth 单元测试
- `tests/unit/infrastructure/routing/test_fallback_router.py` - FallbackRouter 单元测试
- `tests/unit/domain/entities/test_routing_decision_log.py` - RoutingDecisionLog 单元测试
- `tests/unit/architecture/test_udmr_architecture.py` - 架构验证测试
- `tests/unit/performance/test_udmr_performance.py` - 性能基准测试
- `tests/integration/test_udmr_integration.py` - 集成测试
- `tests/acceptance/test_story_1.17.feature` - Gherkin 验收测试（由 Dev agent 在 Task 0 创建）
- `tests/acceptance/test_story_1.17_steps.py` - 验收测试步骤实现（由 Dev agent 在 Task 0 创建）
- `docs/developer/udmr_guide.md` - UDMR 实施指南
- `src/application/event_listeners/` or `src/infrastructure/event_listeners/` - 事件监听适配器（复用 Story 1.3 模式）

**更新的文件/Updated Files:**
- `src/domain/ports/__init__.py` - 添加 HealthCheckPort, HealthCheckerFactory 导出
- `src/domain/services/__init__.py` - 添加 UDMRouter 导出
- `src/domain/value_objects/__init__.py` - 添加 RoutingDecision 导出
- `src/domain/entities/__init__.py` - 添加 RoutingDecisionLog 导出
- `src/application/services/__init__.py` - 添加 LocalModelHealthFacade 导出
- `src/infrastructure/config/__init__.py` - 添加 UDMRConfig 导出
- `src/infrastructure/routing/__init__.py` - 添加 OllamaHealthAdapter, OllamaHealthCheckerFactory, LocalModelHealth, FallbackRouter 导出

---

## 📚 Project Context Reference

> **来源:** [`project-context.md`](../../_bmad-output/project-context.md)

### 关键约束速查

| 约束类型 | 约束内容 | 来源 |
|---------|---------|------|
| **架构原则** | 六边形架构，领域层零依赖 | architecture.md §3.1 |
| **系统公理一** | trigger→route→execute 自主调用循环 | architecture.md §3.2 |
| **UDMR 三层决策** | L1 合规→L2 四因子评分→L3 路由阈值 | architecture.md §3.5 |
| **测试覆盖率** | 架构层≥85%，集成测试≥75% | sdd-tdd-checklist.md §5 |
| **路由性能** | 路由决策延迟 P95<100ms（MVP） | epics_v1.0.md Story 1.17 |

### 关键路径依赖

```
Story 1.14a (trigger) → Story 1.14b (route 语义路由) → Story 1.17 (UDMR 模型路由)
                                                                          ↓
                                                        Story 1.19 (CFO ROI 成本验证)
```

### UDMR 路由决策体系（来自 architecture.md §3.5）

| 层次 | 决策内容 | 输入 | 输出 | 归属 |
|------|---------|------|------|------|
| **L1 合规性网关** | 敏感数据检查、数据驻留限制、白名单校验 | 任务上下文 | 合规/不合规 | Story 11.1 |
| **L2 四因子评分** | 语义匹配度35% + 历史成功率30% + 成本效率20% + 任务复杂度15% | 合规通过 | 路由评分 | Story 11.2 |
| **L3 路由阈值（静态）** | 本地优先，超时>30s 切换云端 | — | 本地/云端 | **本 Story** |

> ⚠️ **本 Story 仅实现 L3 静态版本**（本地优先，超时切换），不涉及 L1/L2 动态决策

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
| **优先级** | P0-17（MVP，ARCH UDMR 基础） |
| **覆盖 FR** | or.md 系统公理一（route 阶段）、FR-CP-01（路由决策日志）、FR-CP-05（UDMR L3 静态路由，完整三层架构→Story 11.1/11.2）、FR-CP-06（四因子评分→Story 11.2） |
| **依赖 Story** | Story 1.14a（trigger 实现）、Story 1.14b（语义路由 + 路由日志） |
| **前置条件** | Triggered/Routed 事件已定义（Story 1.14a/b），路由决策日志基础设施（Story 1.14b） |
| **后续 Story** | Story 1.19（CFO ROI 验证，Token 消耗追踪、成本统计） |
| **覆盖率要求** | 架构层≥85%，集成测试≥75% |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0-3）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1 至 AC-4）
3. [x] Architecture constraints extracted 架构约束已提取（UDMR 三层决策、静态路由配置）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（Story 1.14b 配置模式、事件驱动解耦）
5. [x] Sprint status synced to `ready-for-dev`
6. [x] UDMR 与语义路由关系澄清（Story 1.14b vs Story 1.17）
7. [x] UDMR 三层架构与 MVP 范围澄清（MVP 仅 L3 静态，L1/L2 归 Story 11.x）

### 🔍 审查自查清单（Self-Verification Checklist）

> **创建 story 后必填，确保符合规范**

| # | 检查项 | 状态 | 说明 |
|---|--------|------|------|
| 1 | Story ID 和 Story Key 一致 | ✅ | 1-17-udmr-basic-routing |
| 2 | Story 描述包含 As a/I want/So that | ✅ | 运维工程师，配置本地/云端路由策略 |
| 3 | Acceptance Criteria 完整（AC-1~AC-4） | ✅ | 本地优先路由、故障切换、日志、性能 |
| 4 | Task 0 (SDD) 定义完整 | ✅ | 7 个 Schema 定义项 |
| 5 | Task 1-3 TDD 循环约束明确 | ✅ | 红→绿→重构 循环 |
| 6 | 测试分类与 Task 归属一致 | ✅ | 7 种测试类型对应 3 个 Task |
| 7 | 测试隔离约束已说明 | ✅ | 10 条约束规则 |
| 8 | 架构模式与约束已提取 | ✅ | 六边形架构、UDMR MVP 静态路由 |
| 9 | 前一个故事学习经验整合 | ✅ | Story 1.14b 配置模式复用 |
| 10 | 项目结构与统一规范一致 | ✅ | domain/infrastructure/interfaces |
| 11 | Git Intelligence 已分析 | ✅ | 5 个提交关键模式 |
| 12 | Sprint status 状态正确 | ✅ | ready-for-dev |
| 13 | 后续 Story 依赖已标注 | ✅ | Story 1.19 CFO ROI |
| 14 | UDMR 与语义路由关系已澄清 | ✅ | 两个不同路由机制 |
| 15 | UDMR 三层架构与 MVP 范围澄清 | ✅ | MVP 仅 L3 静态，L1/L2 归 Story 11.x |

---

## 📚 相关文档 Related Documents

| 文档 | 说明 |
|------|------|
| [SDD+TDD 融合开发模式指南](./sdd-tdd-fusion-guide.md) | 开发模式详细说明与各层测试模板 |
| [SDD+TDD 实施检查清单](./sdd-tdd-checklist.md) | 实施步骤检查 |
| [or.md 系统公理一](../planning-artifacts/or.md) | 系统公理定义 |
| [Story 1.14a: 自主调用循环 - trigger](./1-14a-autonomous-invocation-trigger.md) | 前置 Story |
| [Story 1.14b: 自主调用循环 - route](./1-14b-autonomous-invocation-route.md) | 前置 Story（语义路由） |
| [Story 1.19: CFO ROI 验证](./1-19-cfo-roi-verification.md) | 后续 Story（依赖本 Story 路由日志） |

---

**模板版本/Template Version:** 2.2.0
**创建日期/Created:** 2026-04-26
**最后更新/Last Updated:** 2026-05-11
**更新说明:**
- v2.2.0: Story 1.17 完整版本（重新创建）- 实现 UDMR 基础路由（本地优先静态配置）：(1) UDMRouter 本地优先路由; (2) LocalModelHealth Ollama 健康检查; (3) FallbackRouter 故障切换（超时>30秒）; (4) RoutingDecisionLog 扩展; (5) 六边形架构验证; (6) 性能基准测试 P95<100ms
- 明确 MVP 范围（L3 静态路由），澄清 L1/L2/L3 与 Story 11.x 的关系
