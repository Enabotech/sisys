# Story 1.17: UDMR 基础路由（本地优先静态配置）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 运维工程师，
**I want** 配置本地/云端路由策略（本地优先静态配置），
**So that** MVP 阶段支持基础成本优化，验证本地路由占比≥80%。

### 业务价值

本 Story 是 Epic 1（企业级架构基础与合规）价值组 6（MVP 关键机制增强）的第一个故事，在 Story 1.14b（route 实现）完成后实现 UDMR 基础路由。核心价值：

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **本地优先路由** | 降低云端 API 调用成本，验证本地路由占比≥80% | 本地路由占比≥80%（基于 1000 次任务采样） |
| **故障切换机制** | 本地模型不可用或超时>30 秒时自动切换云端 | 故障切换时间<30 秒（从检测到切换完成），切换成功率≥95% |
| **路由决策日志** | 记录路由决策过程，支持成本追踪和审计 | 路由决策日志 WORM 归档，字段完整性 100% |
| **路由延迟要求** | MVP 阶段本地优先静态路由，端到端 P95<200ms | 端到端延迟 P95<200ms（含健康检查开销，1000 次采样） |

> **⚠️ MVP vs V1 阶段说明**：本 Story 实现 MVP 阶段简化版 UDMR（本地优先静态配置 + 故障切换），**不含 L1/L2/L3 三层决策**。完整 UDMR 三层决策（L1 合规性网关 → L2 四因子评分 → L3 路由执行）在 Epic 11（V1 阶段）实现。本 Story 性能目标 P95<200ms 是端到端（含健康检查），V1 阶段目标 P95<50ms 是纯路由计算。

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 1: 企业级架构基础与合规，价值组 6: MVP 关键机制增强，Story 1.17

**or.md 公理追溯:** 系统公理一（自主调用：trigger→route→execute），覆盖"route"阶段的后续模型路由决策

**架构文档追溯:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) - 第 4 章 统一动态模型路由框架 UDMR

**前置依赖:** Story 1.14b（route 实现，提供 session_id 哈希/语义路由）

**后续依赖:** Story 1.19（成本度量基础，依赖本 Story 路由日志）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 本地优先静态路由配置

**Given** 系统配置了本地模型（Ollama+Qwen2.5）和云端模型（Qwen/Claude）
**When** 执行 LLM 任务
**Then** 根据静态配置路由（本地优先）
**And** 本地路由占比≥80%（基于 1000 次任务采样统计）
**And** 发布 RoutingDecided 事件至下游 execute 机制

> **职责说明**：StaticRouter 仅负责静态路由选择（本地优先），**不负责故障切换**。故障切换由 FallbackRouter 独立处理。

**验证标准/Validation Criteria:**
- [ ] StaticRouter 类实现（`src/infrastructure/routing/static_router.py`）
- [ ] 本地优先配置（`ROUTE_STRATEGY=local_first`）
- [ ] 路由决策延迟<10ms（纯静态选择，无计算开销）
- [ ] 发布 RoutingDecided 事件（携带 route_type=local/cloud）
- [ ] 本地路由占比≥80%（1000 次任务采样）

### AC-2: 故障切换机制

**Given** FallbackRouter 收到 RoutingDecided 事件（route_type=local）
**When** FallbackRouter 执行健康检查（按需检测，非心跳）
**Then** 如果本地模型不可用或响应超时>30 秒，自动切换至云端模型（Qwen/Claude）
**And** 切换时间<30 秒（从检测到切换完成）
**And** 切换成功后发布 FallbackTriggered 事件

> **健康检查机制说明**：采用**按需检测**模式（请求时检查），非心跳模式。原因：MVP 阶段模型实例少，健康检查频率低，按需检测减少不必要的网络开销。超时阈值 30 秒指单次请求超时，非检查周期。

**验证标准/Validation Criteria:**
- [ ] FallbackRouter 类实现（`src/infrastructure/routing/fallback_router.py`）
- [ ] 按需健康检查机制（请求时检查，非心跳）
- [ ] 超时检测与计时器（`LOCAL_TIMEOUT_SECONDS=30`）
- [ ] 自动切换逻辑（本地→云端）
- [ ] 切换时间<30 秒（性能测试）
- [ ] 切换成功率≥95%（100 次切换测试）
- [ ] 切换日志记录（切换原因、切换前后模型）

### AC-3: 路由决策日志

**Given** 路由决策完成（本地或云端）
**When** StaticRouter 返回路由结果
**Then** 记录路由决策日志至 PostgreSQL（Story 1.5 已实现）
**And** 日志包含：任务 ID、session_id、路由类型（local/cloud）、选定模型、成本预估、实际成本、延迟、状态

**验证标准/Validation Criteria:**
- [ ] RoutingDecisionLog 数据模型（`src/domain/entities/routing_decision_log.py`）
  - 字段：log_id, task_id, session_id, route_type, selected_model, cost_estimate, actual_cost, latency_ms, status, timestamp
- [ ] 路由决策日志存储至 PostgreSQL
- [ ] WORM 归档标识（worm_storage_ref 字段）
- [ ] 日志字段完整性校验
- [ ] 路由决策日志可检索性（按 session_id/任务 ID/时间范围）

### AC-4: 路由性能要求

**Given** UDMR 组件处理路由决策
**When** 端到端路由决策执行（含 StaticRouter + FallbackRouter）
**Then** 端到端路由决策延迟 P95<200ms（含健康检查开销）
**And** 支持 500 decisions/second 吞吐量

> **性能要求说明**：MVP 阶段 P95<200ms 是端到端（含按需健康检查），V1 阶段 P95<50ms 是纯路由计算（Epic 11 优化目标）。吞吐量 500 decisions/s 低于 V1 目标 1000 decisions/s，因为 MVP 仅支持单模型实例。

**验证标准/Validation Criteria:**
- [ ] 端到端路由决策延迟 P95<200ms（基准测试：1000 次请求，预热 100 次）
- [ ] 吞吐量 500 decisions/second（负载测试：10 秒持续压力）
- [ ] 路由决策幂等性（相同输入产生相同输出）

### AC-5: 六边形架构合规

**Given** UDMR 基础路由实现
**When** 执行路由决策
**Then** 符合六边形架构依赖方向（领域层定义接口，基础设施层实现）
**And** 无循环依赖
**And** 与 Story 1.14b 的语义路由解耦（UDMR 处理模型选择，Story 1.14b 处理 Agent/工具选择）

> **架构位置说明**：UDMRService 位于**领域层**（`src/domain/services/udmr_service.py`），作为核心领域逻辑。应用层仅作为协调者（`src/application/services/udmr_coordinator.py`）编排领域服务。

**验证标准/Validation Criteria:**
- [ ] UDMRService 位于领域层（`src/domain/services/udmr_service.py`）
- [ ] 依赖倒置：领域层定义路由决策接口，基础设施层实现（StaticRouter/FallbackRouter）
- [ ] 无循环依赖（六边形架构检测）
- [ ] UDMR 与语义路由解耦（通过事件总线通信：Routed → UDMR → RoutingDecided → execute）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] RoutingDecided 事件定义（`src/domain/events/routing_events.py`）
  - 字段：event_id, task_id, session_id, route_type, selected_model, estimated_cost, actual_cost, latency_ms, status, timestamp
  - 事件类型自动设置：event_type = "RoutingDecided"
- [ ] ModelHealthCheckResult 事件（内部事件，用于健康检查）

#### 数据模型 (Data Models)
- [ ] UDMRService 服务类（`src/application/services/udmr_service.py`）
  - 方法：route_to_model(task_context) -> ModelSelection，check_local_health() -> bool，fallback_to_cloud() -> ModelSelection
  - 职责：接收任务上下文、执行本地优先路由决策、发布 RoutingDecided 事件
- [ ] ModelHealthChecker 健康检查类（`src/infrastructure/routing/model_health_checker.py`）
  - 方法：check_ollama_health() -> bool，check_qwen_health() -> bool
- [ ] RoutingDecisionLog 实体（`src/domain/entities/routing_decision_log.py`）
  - 字段：log_id, task_id, session_id, route_type, selected_model, cost_estimate, actual_cost, latency_ms, status, timestamp, worm_storage_ref
  - Story 1.14b 已实现 RoutingDecisionLog，需扩展字段

#### 静态路由配置 (Static Routing Configuration)
- [ ] StaticRouteConfig 配置类（`src/infrastructure/config/udmr.py`）
  - 环境变量：`ROUTE_STRATEGY`（local_first/cloud_only），`LOCAL_TIMEOUT_SECONDS`，`LOCAL_MODEL_NAME`，`CLOUD_MODEL_NAME`
  - 从环境变量读取（`from_env()` 方法，复用 Story 1.14b RouteConfig 模式）

#### API 契约 (API Contract)
- [ ] OpenAPI 定义更新 `docs/api/openapi.yaml`
  - 端点：`POST /api/v1/routing/decide` - 路由决策
  - 端点：`GET /api/v1/routing/health` - 模型健康检查

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_story_1.17.feature`（由 Dev agent 在 Task 0 创建）
- [ ] 覆盖场景：
  - 本地优先路由 trigger → route（本地模型可用）
  - 故障切换 trigger → route（本地超时切换云端）
  - 路由决策日志记录
  - 路由延迟 P95<100ms
  - 六边形架构合规验证

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
| **TDD 单元测试** | UDMRService | 本地优先路由 | `test_udmr_service.py` | Task 1 |
| **TDD 单元测试** | ModelHealthChecker | 健康检查 | `test_model_health_checker.py` | Task 1 |
| **TDD 单元测试** | StaticRouteConfig | 静态配置 | `test_static_route_config.py` | Task 1 |
| **TDD 单元测试** | FallbackRouter | 故障切换 | `test_fallback_router.py` | Task 2 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_story_1.17.feature` | Task 0 |
| **SDD 架构验证** | 路由解耦 | 六边形架构约束 | `test_udmr_architecture.py` | Task 3 |
| **集成测试** | 事件总线 | 端到端路由流程 | `test_udmr_integration.py` | Task 3 |

---

### 测试隔离约束（必须遵守）

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**
> 参考 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md) §5.5 测试隔离约束。

**约束规则：**

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
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
|----|-------------|-----------|-------------|---------|
| AC-1 | 本地优先静态路由配置 | Task 1 | Subtask 1.1-1.3（StaticRouter 红→绿→重构） | `test_static_router.py` |
| AC-1 | 模型健康检查 | Task 1 | Subtask 1.4-1.6（ModelHealthChecker 红→绿→重构） | `test_model_health_checker.py` |
| AC-2 | 故障切换机制 | Task 2 | Subtask 2.1-2.3（FallbackRouter 红→绿→重构） | `test_fallback_router.py` |
| AC-3 | 路由决策日志 | Task 1 | Subtask 1.7-1.9（RoutingDecisionLog 扩展 红→绿→重构） | `test_routing_decision_log.py` |
| AC-4 | 路由性能要求 | Task 2 | Subtask 2.4-2.6（性能基准测试 红→绿→重构） | `test_udmr_performance.py` |
| AC-5 | 六边形架构合规 | Task 3 | Subtask 3.1-3.3（六边形架构验证 红→绿→重构） | `test_udmr_architecture.py` |

---

## 📋 Tasks / Subtasks 任务分解

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5

> **目的：** 在进入代码实现前，明确 Schema、API 契约、验收标准。

- [ ] Subtask 0.1: 定义 RoutingDecided 领域事件 Schema（`src/domain/events/routing_events.py`）
- [ ] Subtask 0.2: 定义 ModelHealthChecker 接口（`src/infrastructure/routing/model_health_checker.py`）
- [ ] Subtask 0.3: 定义 UDMRService 服务接口（`src/application/services/udmr_service.py`）
- [ ] Subtask 0.4: 定义 StaticRouteConfig 配置模型（`src/infrastructure/config/udmr.py`）
- [ ] Subtask 0.5: 更新 RoutingDecisionLog 实体（扩展字段，Story 1.14b 已实现）
- [ ] Subtask 0.6: 更新 OpenAPI 定义 `docs/api/openapi.yaml`
- [ ] Subtask 0.7: 编写 Gherkin 验收测试 `tests/acceptance/test_story_1.17.feature`（Dev agent 创建）
- [ ] Subtask 0.8: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: 本地优先路由与健康检查

**关联 AC:** AC-1, AC-3

> **职责边界：** Task 1 负责 StaticRouter（本地优先路由）、ModelHealthChecker（健康检查）、RoutingDecisionLog（扩展）

#### TDD 循环 [A]：StaticRouter 本地优先路由

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/routing/test_static_router.py`（验证本地优先路由） |
| 🟢 绿 | 实现 `src/infrastructure/routing/static_router.py` - StaticRouter 类 |
| 🔄 重构 | 添加类型注解和文档字符串 |

- [ ] Subtask 1.1: 🔴 红 — 编写 StaticRouter 失败测试
- [ ] Subtask 1.2: 🟢 绿 — 实现 StaticRouter（本地优先 + 超时检测）
- [ ] Subtask 1.3: 🔄 重构 — 优化路由策略配置

#### TDD 循环 [B]：ModelHealthChecker 健康检查

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/routing/test_model_health_checker.py`（验证健康检查） |
| 🟢 绿 | 实现 `src/infrastructure/routing/model_health_checker.py` - ModelHealthChecker 类 |
| 🔄 重构 | 添加异步健康检查优化 |

- [ ] Subtask 1.4: 🔴 红 — 编写 ModelHealthChecker 失败测试
- [ ] Subtask 1.5: 🟢 绿 — 实现 ModelHealthChecker（Ollama/Qwen 健康检测）
- [ ] Subtask 1.6: 🔄 重构 — 优化健康检查缓存

#### TDD 循环 [C]：RoutingDecisionLog 扩展

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/entities/test_routing_decision_log.py`（验证扩展字段） |
| 🟢 绿 | 扩展 `src/domain/entities/routing_decision_log.py`（添加 route_type, selected_model, actual_cost 字段） |
| 🔄 重构 | 验证 WORM 归档标识 |

- [ ] Subtask 1.7: 🔴 红 — 编写 RoutingDecisionLog 扩展字段测试
- [ ] Subtask 1.8: 🟢 绿 — 扩展 RoutingDecisionLog 实体
- [ ] Subtask 1.9: 🔄 重构 — 验证 WORM 归档标识

**完成标准/Definition of Done:**
- [ ] StaticRouter 实现完成（本地优先路由策略）
- [ ] ModelHealthChecker 实现完成（Ollama/Qwen 健康检测）
- [ ] RoutingDecisionLog 扩展完成
- [ ] 本地路由占比≥80%（1000 次任务采样）
- [ ] TDD 循环全部通过

---

### Task 2: 故障切换与性能基准

**关联 AC:** AC-2, AC-4

> **职责边界：** Task 2 负责 FallbackRouter（故障切换）和性能基准测试

#### TDD 循环 [A]：FallbackRouter 故障切换

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/routing/test_fallback_router.py`（验证故障切换） |
| 🟢 绿 | 实现 `src/infrastructure/routing/fallback_router.py` - FallbackRouter 类 |
| 🔄 重构 | 添加切换日志和状态管理 |

- [ ] Subtask 2.1: 🔴 红 — 编写 FallbackRouter 失败测试
- [ ] Subtask 2.2: 🟢 绿 — 实现 FallbackRouter（超时切换 + 重试逻辑）
- [ ] Subtask 2.3: 🔄 重构 — 优化切换状态机

#### TDD 循环 [B]：性能基准测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/performance/test_udmr_performance.py`（验证性能要求） |
| 🟢 绿 | 实现性能优化（缓存、连接池复用） |
| 🔄 重构 | 性能调优 |

- [ ] Subtask 2.4: 🔴 红 — 编写性能基准失败测试（P95<100ms）
- [ ] Subtask 2.5: 🟢 绿 — 实现性能优化
- [ ] Subtask 2.6: 🔄 重构 — 性能调优

**完成标准/Definition of Done:**
- [ ] FallbackRouter 实现完成
- [ ] 切换时间<30 秒（性能测试）
- [ ] 切换成功率 100%（100 次切换测试）
- [ ] 路由决策延迟 P95<100ms
- [ ] TDD 循环全部通过

---

### Task 3: 架构验证与集成测试

**关联 AC:** AC-4, AC-5

> **职责边界：** Task 3 负责六边形架构验证（路由与语义路由解耦）和集成测试

#### TDD 循环 [A]：六边形架构验证

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/architecture/test_udmr_architecture.py`（验证架构约束） |
| 🟢 绿 | 实现架构验证逻辑（循环依赖检测、依赖方向检测） |
| 🔄 重构 | 优化架构验证器 |

- [ ] Subtask 3.1: 🔴 红 — 编写架构验证失败测试
- [ ] Subtask 3.2: 🟢 绿 — 实现架构验证逻辑
- [ ] Subtask 3.3: 🔄 重构 — 验证器优化

#### 集成测试

- [ ] Subtask 3.4: 创建 `tests/integration/test_udmr_integration.py`（端到端路由流程）

**完成标准/Definition of Done:**
- [ ] 六边形架构验证通过（无循环依赖）
- [ ] UDMR 与语义路由解耦（通过事件总线通信）
- [ ] 集成测试通过

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（端口与适配器）、事件驱动架构
- **系统公理一:** trigger→route→execute 自主调用循环
  - trigger: 领域事件/心跳事件触发 → Story 1.14a
  - route: session_id 哈希/语义路由（Agent/工具选择）→ Story 1.14b
  - execute: 会话命名空间执行与状态快照 → Story 1.14c
  - UDMR: 模型路由（本地/云端选择）→ **本 Story**
- **设计约束:**
  - 领域层零依赖外部框架
  - 依赖倒置：领域层定义接口，基础设施层实现
  - 路由决策延迟目标：P95<100ms（MVP）
- **技术栈:**
  - Python 3.11+
  - 本地模型：Ollama（Qwen2.5）
  - 云端模型：Qwen/Claude API
  - 路由决策延迟目标：P95<100ms（MVP 静态配置）

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) - 第 4 章 UDMR

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **UDMRService 位于领域层** | 符合六边形架构，领域逻辑与技术解耦 | 需要依赖倒置，MVP 实现复杂度略高 | 9/10 |
| **UDMRService 位于应用层** | 实现简单，与用例服务集成方便 | 领域逻辑泄漏到应用层，违反架构原则 | 6/10 |
| **UDMRService 位于基础设施层** | 实现最简单 | 违反六边形架构，领域逻辑完全泄漏 | 3/10 |

**决策**：选择 **UDMRService 位于领域层**，原因：
1. 路由决策是核心领域逻辑（模型选择策略），属于"做什么"而非"怎么做"
2. 六边形架构要求核心领域逻辑位于领域层，技术细节位于基础设施层
3. V1 阶段扩展为 L1/L2/L3 三层决策时，领域层位置无需重构
4. 应用层仅作为协调者（`UDMRCoordinator`）编排领域服务

### ADR: 路由策略选型决策

**问题**: MVP 阶段使用本地优先路由还是动态路由（基于 L1/L2/L3 三层决策）？

**评估维度** | 本地优先静态配置（MVP） | 动态路由（L1/L2/L3，V1）
------------|------------------------|--------------------------
实现复杂度 | 低 | 高
路由准确性 | 中（静态优先，无 L1 合规/L2 评分） | 高（四因子评分）
L1 合规检查 | ❌ MVP 跳过（简化实现） | ✅ V1 实现
性能 | 高（无计算开销） | 中（需计算评分）
MVP 适用性 | ✅ MVP 阶段必须 | ❌ V1 阶段
**采用** | **✅ 已选择（MVP）** | ❌ V1 阶段

**决策**: MVP 阶段采用 **本地优先静态配置**，原因：
1. MVP 阶段需要快速验证"本地优先"策略的可行性
2. L1 合规检查（敏感数据/数据驻留/白名单）属于 V1 需求
3. V1 阶段升级为 L1/L2/L3 三层决策架构（Epic 11）

> **⚠️ 合规性说明**：MVP 阶段跳过 L1 合规检查不代表系统不安全。本地模型（Ollama+Qwen2.5）默认处理非敏感数据，云端模型（Qwen/Claude）已内置合规过滤。正式合规检查在 V1 阶段（Epic 11）实现。

### UDMR 与 Story 1.14b 语义路由的关系澄清

> ⚠️ **重要澄清**：UDMR 路由（Story 1.17）和 Story 1.14b 语义路由是两个不同的路由机制！

| 路由类型 | 职责 | 位置 | 依赖 |
|---------|------|------|------|
| **语义路由（Story 1.14b）** | 基于任务语义将任务路由至目标 Agent/工具 | RouteService | Story 1.6（bge-m3） |
| **UDMR 路由（Story 1.17）** | 基于本地优先策略选择本地/云端模型 | UDMRService | Story 1.14b（路由日志） |

**数据流**:
```
Triggered 事件（Story 1.14a）
    ↓
RouteService（语义路由）→ 选择目标 Agent/工具
    ↓ 发布 Routed 事件
UDMR（Story 1.17）→ 选择本地/云端模型（本地优先静态配置）
    ↓
Execute（Story 1.14c）→ 执行任务
```

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── application/
│   │   └── services/
│   │       └── udmr_service.py       # UDMRService（核心逻辑）
│   ├── domain/
│   │   ├── events/
│   │   │   └── routing_events.py     # RoutingDecided 事件（新实现）
│   │   └── entities/
│   │       └── routing_decision_log.py # RoutingDecisionLog（扩展，Story 1.14b 已实现）
│   ├── infrastructure/
│   │   ├── config/
│   │   │   └── udmr.py               # StaticRouteConfig 配置（新实现）
│   │   └── routing/
│   │       ├── static_router.py       # StaticRouter（本地优先路由）
│   │       ├── model_health_checker.py # ModelHealthChecker（健康检查）
│   │       └── fallback_router.py     # FallbackRouter（故障切换）
│   └── interfaces/
│       └── event_listeners/
│           └── udmr_listener.py       # UDMR 事件监听适配器
├── tests/
│   ├── unit/
│   │   ├── application/
│   │   │   └── services/
│   │   │       └── test_udmr_service.py
│   │   ├── infrastructure/
│   │   │   └── routing/
│   │   │       ├── test_static_router.py
│   │   │       ├── test_model_health_checker.py
│   │   │       └── test_fallback_router.py
│   │   ├── architecture/
│   │   │   └── test_udmr_architecture.py
│   │   └── performance/
│   │       └── test_udmr_performance.py
│   ├── integration/
│   │   └── test_udmr_integration.py
│   └── acceptance/
│       ├── test_story_1.17.feature
│       └── test_story_1.17_steps.py
└── docs/
    └── developer/
        └── udmr_routing_guide.md     # UDMR 路由实施指南
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 1.14b: 自主调用循环 - route](./1-14b-autonomous-invocation-route.md)

**关键学习/Key Learnings:**
1. **配置模式复用** — RouteConfig.from_env() 模式应复用，StaticRouteConfig 采用相同 `from_env()` 类方法
2. **路由解耦原则** — UDMR 路由和语义路由必须通过事件总线解耦，禁止直接调用
3. **六边形架构严格遵守** — Task 3 必须包含架构验证测试，确保无循环依赖
4. **性能基准测试** — 语义路由 P95<50ms，UDMR 路由 P95<100ms，需独立基准测试

**应用到本故事/Applied to This Story:**
- [ ] StaticRouteConfig 采用与 RouteConfig 相同的 `from_env()` 模式
- [ ] UDMRService 仅负责模型选择，不处理语义路由逻辑
- [ ] Task 3 包含架构验证测试（六边形架构约束检测）
- [ ] 性能基准测试验证 P95<100ms

### Git Intelligence Summary

**来源:** `git log` - 最近 5 个提交

| 提交 | 主题 | 关键模式 |
|------|------|---------|
| `5bdfc3c` | update | - |
| `3ec9a9d` | update | - |
| `d962424` | update | - |
| `995ad30` | update | - |
| `d1e1fde` | fix(test): setup_schema 先删除再创建，确保干净状态 | 测试框架改进 |

**可应用模式:**
1. **六边形架构严格分层** — domain/infrastructure/application 层严格分离
2. **配置与实现分离** — Config 类与实现类分离
3. **测试数据隔离** — UUID 前缀隔离资源，transaction rollback 清理

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
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/1-14b-autonomous-invocation-route.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [ ] 故事需求从 `epics_v1.0.md` 提取
- [ ] 架构约束从 `architecture.md` 提取
- [ ] or.md 系统公理一（route → UDMR）追溯完成
- [ ] 状态设置为 `ready-for-dev`
- [ ] SDD+TDD 融合开发要求定义完成
- [ ] 项目结构对齐统一规范
- [ ] 前一个故事学习经验已整合
- [ ] UDMR 与语义路由关系澄清

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/1-17-udmr-basic-routing.md`
- `src/application/services/udmr_service.py` - UDMRService
- `src/domain/events/routing_events.py` - RoutingDecided 事件
- `src/infrastructure/config/udmr.py` - StaticRouteConfig
- `src/infrastructure/routing/static_router.py` - StaticRouter
- `src/infrastructure/routing/model_health_checker.py` - ModelHealthChecker
- `src/infrastructure/routing/fallback_router.py` - FallbackRouter
- `src/interfaces/event_listeners/udmr_listener.py` - UDMR 事件监听适配器
- `tests/unit/application/services/test_udmr_service.py` - UDMRService 单元测试
- `tests/unit/infrastructure/routing/test_static_router.py` - StaticRouter 单元测试
- `tests/unit/infrastructure/routing/test_model_health_checker.py` - ModelHealthChecker 单元测试
- `tests/unit/infrastructure/routing/test_fallback_router.py` - FallbackRouter 单元测试
- `tests/unit/architecture/test_udmr_architecture.py` - 架构验证测试
- `tests/unit/performance/test_udmr_performance.py` - 性能基准测试
- `tests/integration/test_udmr_integration.py` - 集成测试
- `tests/acceptance/test_story_1.17.feature` - Gherkin 验收测试（由 Dev agent 在 Task 0 创建）
- `tests/acceptance/test_story_1.17_steps.py` - 验收测试步骤实现（由 Dev agent 在 Task 0 创建）
- `docs/developer/udmr_routing_guide.md` - UDMR 路由实施指南

**更新的文件/Updated Files:**
- `src/domain/entities/routing_decision_log.py` - 扩展字段（route_type, selected_model, actual_cost）
- `src/domain/events/__init__.py` - 添加 RoutingDecided 事件导出
- `src/application/services/__init__.py` - 添加 UDMRService 导出
- `src/infrastructure/config/__init__.py` - 添加 StaticRouteConfig 导出
- `src/infrastructure/routing/__init__.py` - 添加 StaticRouter, ModelHealthChecker, FallbackRouter 导出

**待创建的文件/To Be Created (Dev Story 实施):**
- `docs/api/openapi.yaml` - 更新路由决策 API 端点

---

## 📚 Project Context Reference

> **来源:** [`project-context.md`](../../_bmad-output/project-context.md)

### 关键约束速查

| 约束类型 | 约束内容 | 来源 |
|---------|---------|------|
| **架构原则** | 六边形架构，领域层零依赖 | architecture.md §3.1 |
| **系统公理一** | trigger→route→execute 自主调用循环 | architecture.md §3.2 |
| **UDMR 三层决策** | L1 合规→L2 评估→L3 执行（V1 阶段） | architecture.md §3.5 |
| **本地优先路由** | MVP 阶段本地路由占比≥80% | epics_v1.0.md Story 1.17 |
| **路由性能** | P95<100ms（MVP 静态配置） | epics_v1.0.md Story 1.17 |

### 关键路径依赖

```
Story 1.14b (route) → Story 1.17 (UDMR) → Story 1.14c (execute)
                                    ↓
                    Story 1.19 (成本度量基础，依赖路由日志)
```

### 路由决策体系（来自 architecture.md §3.5）

| 路由类型 | 触发条件 | 目标 | 性能要求 |
|---------|---------|------|---------|
| **语义路由（Story 1.14b）** | 任务需要选择 Agent/工具 | 匹配度最高的 Agent/工具 | P95<50ms |
| **UDMR 路由（Story 1.17）** | 任务需要选择模型（本地/云端） | 本地优先，成本优化 | P95<100ms（MVP） |
| **UDMR 动态路由（Epic 11）** | V1 阶段需要四因子评分 | 本地占比≥80%，成本节省≥50% | P95<50ms（V1） |

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 1.17 |
| **Story Key** | 1-17-udmr-basic-routing |
| **File** | `_bmad-output/implementation-artifacts/stories/1-17-udmr-basic-routing.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 1: 企业级架构基础与合规 |
| **价值组** | 价值组 6: MVP 关键机制增强 |
| **优先级** | P0-17（MVP，ARCH UDMR 基础） |
| **覆盖 FR** | FR-CP-01（路由决策日志）、FR-CP-05（UDMR 三层决策基础） |
| **依赖 Story** | Story 1.14b（route 实现，提供路由日志） |
| **前置条件** | Triggered 事件已定义（Story 1.14a），RoutingDecisionLog 已存在（Story 1.14b） |
| **后续 Story** | Story 1.14c（execute，待创建）、Story 1.19（成本度量基础，待创建） |
| **覆盖率要求** | 架构层≥85%（六边形架构验证），集成测试≥75% |

### 完成总结 Completion Summary

1. [ ] All tasks defined 所有任务定义完成
2. [ ] All acceptance criteria specified 所有验收标准已定义
3. [ ] Architecture constraints extracted 架构约束已提取
4. [ ] Previous story learnings integrated 前一个故事学习经验已整合
5. [ ] Sprint status synced to `ready-for-dev`

### 🔧 对抗性审查修复（Adversarial Review Fixes）

> 本次审查由 create-story skill 执行，聚焦科学性、合理性、正确性、一致性。

| # | 问题 | 严重度 | 修复方案 | 状态 |
|---|------|--------|----------|------|
| 1 | UDMR 与语义路由关系不清晰 | P1 | 添加"UDMR 与 Story 1.14b 语义路由的关系澄清"章节 | ✅ 已修复 |
| 2 | MVP 静态配置与 V1 动态路由未区分 | P1 | 添加 ADR 路由策略选型决策，明确 MVP/V1 阶段差异 | ✅ 已修复 |
| 3 | 路由决策日志字段不完整 | P2 | 明确 RoutingDecisionLog 扩展字段（route_type, selected_model, actual_cost） | ✅ 已修复 |
| 4 | 健康检查与故障切换逻辑未分离 | P2 | 分离为 ModelHealthChecker 和 FallbackRouter 两个独立组件 | ✅ 已修复 |
| 5 | 性能基准测试方法未定义 | P2 | 补充测试方法（1000 次请求预热 100 次，10 秒持续压力） | ✅ 已修复 |

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
| [or.md 系统公理一](../planning-artifacts/or.md) | 系统公理定义 |
| [architecture.md - 第 4 章 UDMR](../../_bmad-output/planning-artifacts/architecture.md#4-统一动态模型路由框架-udmr) | UDMR 三层决策架构 |
| [Story 1.14b: 自主调用循环 - route](./1-14b-autonomous-invocation-route.md) | 前置 Story |
| [Story 1.14c: 自主调用循环 - execute](./1-14c-autonomous-invocation-execute.md) | 后续 Story（待创建） |
| [Story 1.19: 成本度量基础](./1-19-cost-metrics-basic.md) | 相关 Story（依赖本 Story 路由日志，待创建） |

---

**模板版本/Template Version:** 2.5.0
**创建日期/Created:** 2026-04-24
**最后更新/Last Updated:** 2026-04-24
**更新说明:**
- v2.5.0: 初始版本 - Story 1.17 UDMR 基础路由（本地优先静态配置）：(1) StaticRouter 本地优先路由；(2) ModelHealthChecker 健康检查；(3) FallbackRouter 故障切换；(4) RoutingDecisionLog 扩展；(5) 六边形架构验证；(6) 性能基准测试 P95<100ms
