# Story 1.14b: 自主调用循环 - route 实现

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 系统架构师,
**I want** 实现 session_id 哈希/语义路由机制,
**So that** 任务可以路由至目标 Agent 或工具。

### 业务价值

本 Story 是 Epic 1（企业级架构基础与合规）价值组 5（or.md 系统公理实现）的第二个故事，在 Story 1.14a（trigger 实现）完成后实现 route 机制。核心价值：

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **哈希路由** | 基于 session_id 哈希一致性路由，保证同 session 任务路由到同一处理节点 | 相同 session_id 始终路由到同一节点（一致性保证 100%） |
| **语义路由** | 基于任务语义相似度路由至最合适的 Agent 或工具 | 语义路由匹配度≥95%（基于人工标注测试集评估） |
| **路由决策日志** | 记录路由决策过程，支持审计和成本追踪 | 路由决策日志 WORM 归档 |
| **路由解耦** | route 机制与 trigger/execute 解耦，通过 Triggered 事件接收输入，通过 AutoRouted 事件输出 | 六边形架构合规，无循环依赖 |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 1: 企业级架构基础与合规，价值组 5: or.md 系统公理实现，Story 1.14b

**or.md 公理追溯:** 系统公理一（自主调用：trigger→route→execute），覆盖"route"阶段

**前置依赖:** Story 1.14a（trigger 实现）

**后续依赖:** Story 1.14c（execute 实现，待创建）、Story 1.17（UDMR 基础路由，日志后置依赖，待创建）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 哈希路由机制

**Given** Triggered 事件（包含 session_id 和任务上下文）
**When** AutoRouteService 接收 Triggered 事件
**Then** 基于 session_id 计算一致性哈希值
**And** 根据哈希值选择目标处理节点或 Agent 实例
**And** 发布 AutoRouted 事件至下游 execute 机制（Story 1.14c）

**验证标准/Validation Criteria:**
- [ ] AutoRouteService 事件监听器注册（`src/domain/services/auto_route_service.py`）
- [ ] session_id 一致性哈希算法实现（murmurhash3 或类似）
- [ ] 节点选择逻辑（哈希环/哈希槽）
- [ ] AutoRouted 事件定义与发布
- [ ] 相同 session_id 始终路由到同一节点（一致性保证 100%）
- [ ] 路由决策延迟 P95<50ms

### AC-2: 语义路由机制

**Given** Triggered 事件（包含 task_context 和任务类型）
**When** AutoRouteService 执行语义路由
**Then** 基于任务上下文计算语义嵌入向量
**And** 计算与候选 Agent/工具的相似度
**And** 选择相似度最高的候选者作为路由目标

**验证标准/Validation Criteria:**
- [ ] 语义嵌入向量计算（使用 bge-m3 模型，Story 1.6 已集成）
- [ ] 候选 Agent/工具相似度计算（余弦相似度）
- [ ] 语义路由选择逻辑
- [ ] 语义路由匹配度≥95%（相对于人工标注基准，随机路由基准约 30-40%，100+ 样本测试集）
- [ ] 语义路由延迟 P95<50ms（基准测试方法：1000 次连续请求，预热 100 次）

### AC-3: 路由决策日志

**Given** 路由决策完成
**When** AutoRouteService 发布 AutoRouted 事件
**Then** 记录路由决策日志至 PostgreSQL（Story 1.5 已实现）
**And** 日志包含：任务 ID、session_id、路由类型（hash/semantic）、路由目标、评分、时间戳、成本预估

**验证标准/Validation Criteria:**
- [ ] RoutingDecisionLog 数据模型（`src/domain/entities/routing_decision_log.py`）
- [ ] 路由决策日志存储至 PostgreSQL
- [ ] WORM 归档标识（RoutingDecisionLog 实体已有 worm_storage_ref 字段，Story 1.10 审计日志已实现）
- [ ] 日志字段完整性校验
- [ ] 路由决策日志可检索性（按 session_id/任务 ID/时间范围）

### AC-4: 路由与 trigger/execute 解耦

**Given** route 机制完成路由决策
**When** 发布 AutoRouted 事件
**Then** route 阶段不直接调用 execute 阶段，通过事件总线解耦
**And** 符合六边形架构依赖方向

**验证标准/Validation Criteria:**
- [ ] AutoRouted 事件定义（`src/domain/events/auto_route_events.py`）
- [ ] AutoRouteService 仅发布事件，不调用 execute
- [ ] 无循环依赖（六边形架构检测）
- [ ] AutoRouteService 位于领域层或应用层（不位于基础设施层直接调用）
- [ ] 依赖倒置：AutoRouteService 定义事件监听接口，基础设施层实现

### AC-5: 路由性能要求

**Given** Triggered 事件到达 AutoRouteService
**When** AutoRouteService 处理路由决策
**Then** 端到端路由决策延迟 P95<50ms
**And** 吞吐量支持 1000 decisions/second

**验证标准/Validation Criteria:**
- [ ] 路由决策延迟 P95<50ms（基准测试：1000 次连续请求，预热 100 次，统计 P95）
- [ ] 吞吐量 1000 decisions/second（负载测试：10 秒持续压力，稳定状态测量）
- [ ] 语义路由缓存（如语义相似度结果，使用 Redis mock）
- [ ] 路由决策幂等性（相同输入产生相同输出）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)
- [ ] AutoRouted 事件定义（`src/domain/events/auto_route_events.py`）
  - 字段: event_id, session_id, task_context, route_type, route_target, route_score, timestamp
  - 事件类型自动设置: `event_type = "AutoRouted"`
- [ ] Triggered 事件监听接口（接收来自 Story 1.14a 的 Triggered 事件）

#### 数据模型 (Data Models)
- [ ] AutoRouteService 服务类（`src/domain/services/auto_route_service.py`）
  - 方法: `on_triggered_event(event)`, `hash_route(session_id) -> RouteTarget`, `semantic_route(task_context) -> RouteTarget`
  - 职责: 接收 Triggered 事件、执行路由决策、发布 AutoRouted 事件
- [ ] RoutingDecisionLog 实体（`src/domain/entities/routing_decision_log.py`）
  - 字段: log_id, task_id, session_id, route_type, route_target, route_score, cost_estimate, latency_ms, timestamp
  - Story 1.10 审计日志已实现，可复用或扩展

#### 哈希路由算法 (Hash Routing)
- [ ] 一致性哈希实现（`src/infrastructure/routing/hash_router.py`）
  - 使用 murmurhash3 或类似算法
  - 支持哈希环/哈希槽数据结构
  - 支持节点动态添加/移除

#### 语义路由实现 (Semantic Routing)
- [ ] 语义嵌入向量计算（复用 Story 1.6 Qdrant 集成的 bge-m3 模型）
- [ ] 候选 Agent/工具相似度计算
- [ ] 语义路由缓存（如 Redis 缓存）

#### 配置模型 (Configuration Models)
- [ ] AutoRouteConfig 配置（`src/infrastructure/config/route.py`）
  - 环境变量: `ROUTE_ENABLED`, `ROUTE_TYPE`（hash/semantic/mixed）, `SEMANTIC_THRESHOLD`, `HASH_RING_SIZE`
  - 从环境变量读取（`from_env()` 方法，复用 OtelConfig 模式）

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_acceptance_autonomous-invocation-route.feature`（由 Dev agent 在 Task 0 创建）
- [ ] 覆盖场景:
  - 哈希路由 trigger → route（单一 hash 路由）
  - 语义路由 trigger → route（单一 semantic 路由）
  - 混合路由 trigger → route（hash + semantic 组合）
  - 路由决策日志记录
  - 路由与 execute 解耦
  - 路由延迟 P95<50ms

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
| **TDD 单元测试** | AutoRouteService | 哈希路由 | `test_auto_route_service.py` | Task 1 |
| **TDD 单元测试** | HashRouter | 一致性哈希 | `test_hash_router.py` | Task 1 |
| **TDD 单元测试** | SemanticRouter | 语义相似度 | `test_semantic_router.py` | Task 2 |
| **TDD 单元测试** | SemanticRouter | 语义路由缓存（Redis mock） | `test_semantic_router_cache.py` | Task 2 |
| **TDD 单元测试** | RoutingDecisionLog | 路由决策日志 | `test_routing_decision_log.py` | Task 2 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_autonomous-invocation-route.feature` | Task 0 |
| **SDD 架构验证** | 路由解耦 | 六边形架构约束 | `test_route_architecture.py` | Task 3 |
| **集成测试** | 事件总线 | 端到端路由流程 | `test_route_integration.py` | Task 3 |

---

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
| AC-1 | 哈希路由机制 | Task 1 | Subtask 1.1-1.3（HashRouter 红→绿→重构） | `test_hash_router.py` |
| AC-1 | AutoRouteService 事件监听 | Task 1 | Subtask 1.4-1.6（AutoRouteService 红→绿→重构） | `test_auto_route_service.py` |
| AC-2 | 语义路由机制 | Task 2 | Subtask 2.1-2.3（SemanticRouter 红→绿→重构） | `test_semantic_router.py` |
| AC-2 | 语义路由缓存 | Task 2 | Subtask 2.7-2.9（Redis mock 缓存测试） | `test_semantic_router_cache.py` |
| AC-3 | 路由决策日志 | Task 2 | Subtask 2.4-2.6（RoutingDecisionLog 红→绿→重构） | `test_routing_decision_log.py` |
| AC-4 | 路由与 execute 解耦 | Task 3 | Subtask 3.1-3.3（六边形架构验证 红→绿→重构） | `test_route_architecture.py` |
| AC-5 | 路由性能要求 | Task 3 | Subtask 3.4-3.6（性能基准测试 红→绿→重构） | `test_route_performance.py` |

---

## 📋 Tasks / Subtasks 任务分解

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5

> **目的：** 在进入代码实现前，明确 Schema、API 契约、验收标准。

- [ ] Subtask 0.1: 定义 AutoRouted 领域事件 Schema（`src/domain/events/auto_route_events.py`）
- [ ] Subtask 0.2: 定义 RoutingDecisionLog 实体（`src/domain/entities/routing_decision_log.py`）
- [ ] Subtask 0.3: 定义 AutoRouteService 服务接口（`src/domain/services/auto_route_service.py`）
- [ ] Subtask 0.4: 定义 HashRouter 路由算法（`src/infrastructure/routing/hash_router.py`）
- [ ] Subtask 0.5: 定义 SemanticRouter 路由（`src/infrastructure/routing/semantic_router.py`）
- [ ] Subtask 0.6: 定义 AutoRouteConfig 配置模型（`src/infrastructure/config/route.py`）
- [ ] Subtask 0.7: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_autonomous-invocation-route.feature`（Dev agent 创建）
- [ ] Subtask 0.8: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: 哈希路由与 AutoRouteService

**关联 AC:** AC-1

> **职责边界:** Task 1 负责 HashRouter（一致性哈希算法）和 AutoRouteService（事件监听、路由决策）

#### TDD 循环 [A]：HashRouter 一致性哈希

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/routing/test_hash_router.py`（验证一致性哈希） |
| 🟢 绿 | 实现 `src/infrastructure/routing/hash_router.py` - HashRouter 类 |
| 🔄 重构 | 添加类型注解和文档字符串 |

- [ ] Subtask 1.1: 🔴 红 — 编写 HashRouter 失败测试
- [ ] Subtask 1.2: 🟢 绿 — 实现 HashRouter（murmurhash3 哈希环）
- [ ] Subtask 1.3: 🔄 重构 — 优化哈希环节点管理

#### TDD 循环 [B]：AutoRouteService 事件监听

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/services/test_auto_route_service.py`（验证 Triggered 事件监听） |
| 🟢 绿 | 实现 `src/domain/services/auto_route_service.py` - AutoRouteService 类 |
| 🔄 重构 | 添加类型注解和文档字符串 |

- [ ] Subtask 1.4: 🔴 红 — 编写 AutoRouteService 失败测试
- [ ] Subtask 1.5: 🟢 绿 — 实现 AutoRouteService（监听 Triggered 事件，执行哈希路由）
- [ ] Subtask 1.6: 🔄 重构 — 优化事件处理逻辑

**完成标准/Definition of Done:**
- [ ] HashRouter 实现完成（一致性哈希环）
- [ ] AutoRouteService 实现完成
- [ ] 相同 session_id 始终路由到同一节点（一致性保证 100%）
- [ ] TDD 循环全部通过

---

### Task 2: 语义路由与路由决策日志

**关联 AC:** AC-2, AC-3

> **职责边界:** Task 2 负责 SemanticRouter（语义路由）和 RoutingDecisionLog（路由决策日志）
>
> **技术选型**: 语义嵌入使用 bge-m3（Story 1.6 已集成），Redis 缓存路由结果

#### TDD 循环 [A]：SemanticRouter 语义路由

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/routing/test_semantic_router.py`（验证语义路由） |
| 🟢 绿 | 实现 `src/infrastructure/routing/semantic_router.py` - SemanticRouter 类（复用 bge-m3） |
| 🔄 重构 | 添加类型注解和配置化支持 |

- [ ] Subtask 2.1: 🔴 红 — 编写 SemanticRouter 失败测试
- [ ] Subtask 2.2: 🟢 绿 — 实现 SemanticRouter（语义嵌入 + 余弦相似度）
- [ ] Subtask 2.3: 🔄 重构 — 优化语义缓存（Redis）

#### TDD 循环 [B]：RoutingDecisionLog 路由决策日志

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/entities/test_routing_decision_log.py`（验证日志记录） |
| 🟢 绿 | 实现 `src/domain/entities/routing_decision_log.py` - RoutingDecisionLog 实体 |
| 🔄 重构 | 优化日志字段和 WORM 归档标识 |

- [ ] Subtask 2.4: 🔴 红 — 编写 RoutingDecisionLog 失败测试
- [ ] Subtask 2.5: 🟢 绿 — 实现 RoutingDecisionLog 实体
- [ ] Subtask 2.6: 🔄 重构 — 验证 WORM 归档标识

#### TDD 循环 [C]：语义路由缓存（Redis mock）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/routing/test_semantic_router_cache.py`（验证缓存命中/未命中，使用 mock Redis） |
| 🟢 绿 | 实现缓存逻辑（Redis TTL=24h，缓存失效策略：TTL + 事件驱动 + 版本感知） |
| 🔄 重构 | 验证缓存失效策略 |

- [ ] Subtask 2.7: 🔴 红 — 编写 SemanticRouter 缓存失败测试（mock Redis）
- [ ] Subtask 2.8: 🟢 绿 — 实现语义路由缓存逻辑
- [ ] Subtask 2.9: 🔄 重构 — 验证缓存失效策略

> **测试隔离约束：** SemanticRouter 缓存测试使用 `pytest-mock` 或 `fakeredis` 模拟 Redis，遵循 sdd-tdd-checklist.md 外部服务隔离规则

**完成标准/Definition of Done:**
- [ ] SemanticRouter 实现完成（bge-m3 语义嵌入 + 余弦相似度）
- [ ] SemanticRouter 缓存测试完成（Redis mock，遵循测试隔离约束）
- [ ] RoutingDecisionLog 实现完成
- [ ] 语义路由匹配度≥95%（相对于人工标注基准，随机路由基准约 30-40%）
- [ ] TDD 循环全部通过

---

### Task 3: 架构验证与性能基准

**关联 AC:** AC-4, AC-5

> **职责边界:** Task 3 负责六边形架构验证（路由与 execute 解耦）和性能基准测试

#### TDD 循环 [A]：六边形架构验证

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/architecture/test_route_architecture.py`（验证架构约束） |
| 🟢 绿 | 实现架构验证逻辑（循环依赖检测、依赖方向检测） |
| 🔄 重构 | 优化架构验证器 |

- [ ] Subtask 3.1: 🔴 红 — 编写架构验证失败测试
- [ ] Subtask 3.2: 🟢 绿 — 实现架构验证逻辑
- [ ] Subtask 3.3: 🔄 重构 — 验证器优化

#### TDD 循环 [B]：性能基准测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/performance/test_route_performance.py`（验证性能要求） |
| 🟢 绿 | 实现性能优化（语义缓存、连接池复用） |
| 🔄 重构 | 性能调优 |

- [ ] Subtask 3.4: 🔴 红 — 编写性能基准失败测试
- [ ] Subtask 3.5: 🟢 绿 — 实现性能优化
- [ ] Subtask 3.6: 🔄 重构 — 性能调优

#### 集成测试

- [ ] Subtask 3.7: 创建 `tests/integration/test_route_integration.py`（端到端路由流程）

**完成标准/Definition of Done:**
- [ ] 六边形架构验证通过（无循环依赖）
- [ ] 路由决策延迟 P95<50ms
- [ ] 吞吐量 1000 decisions/second
- [ ] 集成测试通过

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（端口与适配器）、事件驱动架构
- **系统公理一:** trigger→route→execute 自主调用循环
  - trigger: 领域事件/心跳事件触发 → Story 1.14a
  - route: session_id 哈希/语义路由 → **本 Story**
  - execute: 会话命名空间执行与状态快照 → Story 1.14c
- **设计约束:**
  - 领域层零依赖外部框架
  - 依赖倒置：领域层定义接口，基础设施层实现
  - 事件总线双通道：Redis PubSub（实时）、RabbitMQ（持久化）
- **技术栈:**
  - Python 3.11+
  - 事件总线：Redis PubSub + RabbitMQ（Story 1.3 已实现）
  - 语义嵌入：bge-m3（Story 1.6 已集成）
  - 哈希算法：murmurhash3
  - 路由决策延迟目标：P95<50ms

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) - ADR 相关决策

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **AutoRouteService 位于领域层** | 符合六边形架构，领域逻辑与技术解耦 | 需要依赖倒置 | ✅ 9/10 |
| AutoRouteService 位于应用层 | 实现简单 | 领域逻辑泄漏 | 6/10 |
| AutoRouteService 位于基础设施层 | 实现最简单 | 违反六边形架构 | 3/10 |

### ADR: 路由类型选型决策

**问题**: 使用哈希路由还是语义路由，还是混合路由？

**评估维度** | 哈希路由 | 语义路由 | 混合路由
------------|---------|---------|----------
实现复杂度 | 低 | 中 | 高
路由匹配度 | 中（session 一致性保证） | 高（基于语义相似度） | 高
性能 | 高（O(1)） | 中（需要嵌入计算） | 中
**采用** | ❌ 单独使用不满足语义匹配要求 | ❌ 哈希仅保证 session 一致性 | **✅ 已选择**

**决策**: 采用 **混合路由**（hash + semantic），原因：
1. 哈希路由保证同 session 任务路由到同一节点（状态一致性）
2. 语义路由提高路由匹配度（匹配度≥95%）
3. 可配置优先级（先 hash 后 semantic 或 vice versa）

### 语义路由与 Story 1.6/1.17 的关系澄清

> ⚠️ **重要澄清**：语义路由（Story 1.14b）和 UDMR 路由（Story 1.17）是两个不同的路由机制！

| 路由类型 | 职责 | 位置 | 依赖 |
|---------|------|------|------|
| **语义路由（Story 1.14b）** | 基于任务语义将任务路由至目标 Agent/工具 | AutoRouteService | Story 1.6（bge-m3） |
| **UDMR 路由（Story 1.17）** | 基于 L1/L2/L3 三层决策选择本地/云端模型 | UDMR 框架 | Story 1.14b（路由日志） |

**数据流**:
```
Triggered 事件（Story 1.14a）
    ↓
AutoRouteService（语义路由）→ 选择目标 Agent/工具
    ↓ 发布 AutoRouted 事件
UDMR（Story 1.17）→ 选择本地/云端模型
    ↓
Execute（Story 1.14c）→ 执行任务
```

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── domain/
│   │   ├── events/
│   │   │   └── auto_route_events.py        # AutoRouted 事件（新实现）
│   │   ├── services/
│   │   │   └── auto_route_service.py       # AutoRouteService（核心逻辑）
│   │   └── entities/
│   │       └── routing_decision_log.py # RoutingDecisionLog（复用 Story 1.10）
│   ├── infrastructure/
│   │   ├── config/
│   │   │   └── route.py              # AutoRouteConfig 配置（新实现）
│   │   └── routing/
│   │       ├── hash_router.py         # HashRouter（一致性哈希）
│   │       └── semantic_router.py     # SemanticRouter（语义路由）
│   └── interfaces/
│       └── event_listeners/
│           └── auto_route_listener.py       # 事件监听适配器（复用 Story 1.3）
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   │   ├── services/
│   │   │   │   └── test_auto_route_service.py
│   │   │   └── entities/
│   │   │       └── test_routing_decision_log.py
│   │   ├── infrastructure/
│   │   │   └── routing/
│   │   │       ├── test_hash_router.py
│   │   │       └── test_semantic_router.py
│   │   ├── architecture/
│   │   │   └── test_route_architecture.py
│   │   └── performance/
│   │       └── test_route_performance.py
│   ├── integration/
│   │   └── test_route_integration.py
│   └── acceptance/
│       ├── test_acceptance_autonomous-invocation-route.feature
│       └── test_acceptance_autonomous-invocation-route.py
└── docs/
    └── developer/
        └── route_mechanism_guide.md    # 路由机制实施指南
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 1.14a: 自主调用循环 - trigger](./1-14a-autonomous-invocation-trigger.md)

**关键学习/Key Learnings:**
1. **配置模式复用** — OtelConfig.from_env() 模式应复用，AutoRouteConfig 采用相同 `from_env()` 类方法
2. **事件驱动解耦** — TriggerService 仅负责触发和上下文提取，不处理业务逻辑；AutoRouteService 应遵循相同模式
3. **六边形架构严格遵守** — Task 3 必须包含架构验证测试，确保无循环依赖
4. **性能基准测试** — trigger 性能要求 P95<10ms，route 性能要求 P95<50ms，需独立基准测试

**应用到本故事/Applied to This Story:**
- [ ] AutoRouteConfig 采用与 OtelConfig 相同的 `from_env()` 模式
- [ ] AutoRouteService 仅负责路由决策，不处理 execute 逻辑
- [ ] Task 3 包含架构验证测试（六边形架构约束检测）
- [ ] 性能基准测试验证 P95<50ms

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
| **Execution Date** | 2026-04-20 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|-----|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Instructions** | `_bmad/bmm/workflows/4-implementation/create-story/instructions.xml` |
| **Template** | `_bmad/bmm/workflows/4-implementation/create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/1-14a-autonomous-invocation-trigger.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [ ] 故事需求从 `epics_v1.0.md` 提取
- [ ] 架构约束从 `architecture.md` 提取
- [ ] or.md 系统公理一（route）追溯完成
- [ ] 状态设置为 `ready-for-dev`
- [ ] SDD+TDD 融合开发要求定义完成
- [ ] 项目结构对齐统一规范
- [ ] 前一个故事学习经验已整合
- [ ] 语义路由与 UDMR 路由关系澄清

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/1-14b-autonomous-invocation-route.md`
- `src/domain/events/auto_route_events.py` - AutoRouted 事件
- `src/domain/services/auto_route_service.py` - AutoRouteService
- `src/domain/entities/routing_decision_log.py` - RoutingDecisionLog（复用 Story 1.10 模式）
- `src/infrastructure/config/route.py` - AutoRouteConfig
- `src/infrastructure/routing/hash_router.py` - HashRouter（murmurhash3 哈希环）
- `src/infrastructure/routing/semantic_router.py` - SemanticRouter（bge-m3 语义嵌入）
- `tests/unit/domain/services/test_auto_route_service.py` - AutoRouteService 单元测试
- `tests/unit/domain/entities/test_routing_decision_log.py` - RoutingDecisionLog 单元测试
- `tests/unit/infrastructure/routing/test_hash_router.py` - HashRouter 单元测试
- `tests/unit/infrastructure/routing/test_semantic_router.py` - SemanticRouter 单元测试
- `tests/unit/infrastructure/routing/test_semantic_router_cache.py` - SemanticRouter 缓存测试（Redis mock）
- `tests/unit/architecture/test_route_architecture.py` - 架构验证测试
- `tests/unit/performance/test_route_performance.py` - 性能基准测试
- `tests/integration/test_route_integration.py` - 集成测试
- `tests/acceptance/test_acceptance_autonomous-invocation-route.feature` - Gherkin 验收测试（由 Dev agent 在 Task 0 创建）
- `tests/acceptance/test_acceptance_autonomous-invocation-route.py` - 验收测试步骤实现（由 Dev agent 在 Task 0 创建）
- `docs/developer/route_mechanism_guide.md` - 路由机制实施指南

**更新的文件/Updated Files:**
- `src/domain/events/__init__.py` - 添加 AutoRouted 事件导出
- `src/domain/services/__init__.py` - 添加 AutoRouteService 导出
- `src/domain/entities/__init__.py` - 添加 RoutingDecisionLog 导出
- `src/infrastructure/config/__init__.py` - 添加 AutoRouteConfig 导出
- `src/infrastructure/routing/__init__.py` - 添加 HashRouter, SemanticRouter 导出

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/interfaces/event_listeners/auto_route_listener.py` - 事件监听适配器（复用 Story 1.3 模式）

---

## 📚 Project Context Reference

> **来源:** [`project-context.md`](../../_bmad-output/project-context.md)

### 关键约束速查

| 约束类型 | 约束内容 | 来源 |
|---------|---------|------|
| **架构原则** | 六边形架构，领域层零依赖 | architecture.md §3.1 |
| **系统公理一** | trigger→route→execute 自主调用循环 | architecture.md §3.2 |
| **事件驱动** | 事务发件箱模式，事件处理幂等性 | architecture.md §3.3 |
| **测试覆盖率** | 架构层≥85%，集成测试≥75% | sdd-tdd-checklist.md §5 |
| **路由性能** | 路由决策延迟 P95<50ms | epics_v1.0.md Story 1.14b |

### 关键路径依赖

```
Story 1.14a (trigger) → Story 1.14b (route) → Story 1.14c (execute)
                                    ↓
                    Story 1.17 (UDMR 路由) → 模型选择（依赖路由日志）
```

### 路由决策体系（来自 architecture.md §3.5）

| 路由类型 | 触发条件 | 目标 | 性能要求 |
|---------|---------|------|---------|
| **语义路由** | 任务需要选择 Agent/工具 | 匹配度最高的 Agent/工具 | P95<50ms |
| **UDMR 路由** | 任务需要选择模型 | 本地/云端模型选择 | P95<50ms（Story 1.17） |

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 1.14b |
| **Story Key** | 1-14b-autonomous-invocation-route |
| **File** | `_bmad-output/implementation-artifacts/stories/1-14b-autonomous-invocation-route.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 1: 企业级架构基础与合规 |
| **价值组** | 价值组 5: or.md 系统公理实现 |
| **优先级** | P0-14b（or.md 系统公理一） |
| **覆盖 FR** | or.md 系统公理一（route 阶段）、FR-CP-01（路由决策日志） |
| **依赖 Story** | Story 1.14a（trigger 实现）、Story 1.6（bge-m3 嵌入） |
| **前置条件** | Triggered 事件已定义（Story 1.14a），bge-m3 已集成（Story 1.6） |
| **后续 Story** | Story 1.14c（execute，待创建）、Story 1.17（UDMR 基础路由，待创建） |
| **覆盖率要求** | 架构层≥85%（六边形架构验证），集成测试≥75% |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成
2. [x] All acceptance criteria specified 所有验收标准已定义
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 对抗性审查修复（Adversarial Review Fixes）

> 本次审查由 create-story skill 执行，聚焦科学性、合理性、正确性、一致性（三次审查）。

| # | 问题 | 严重度 | 修复方案 | 状态 |
|---|------|--------|----------|------|
| 1 | 语义路由与 UDMR 路由关系不清晰 | P1 | 添加"语义路由与 Story 1.6/1.17 的关系澄清"章节，明确两个路由机制的区别和联系 | ✅ 已修复 |
| 2 | 混合路由实现复杂度未评估 | P2 | 添加 ADR 路由类型选型决策，评估哈希/语义/混合路由的优缺点和评分 | ✅ 已修复 |
| 3 | Gherkin 验收测试文件未创建 | P2 | 标注文件由 Dev agent 在 Task 0 创建，更新"待创建的文件"列表 | ✅ 已修复 |
| 4 | Story 1.14c/1.17 链接不存在 | P2 | 更新为"待创建"标注，修复相关文档链接 | ✅ 已修复 |
| 5 | 测试分类与 Task 归属不一致 | P2 | 修正测试分类表，语义路由测试明确归属 Task 2 | ✅ 已修复 |
| 6 | "准确率 100%"表述不科学 | P1 | 改为"一致性保证 100%"，确定性算法不存在准确率概念 | ✅ 已修复 |
| 7 | "语义路由准确率≥95%"缺乏评估方法 | P2 | 补充"基于人工标注测试集：100+ 样本"评估方法定义 | ✅ 已修复 |
| 8 | ADR 表格"路由准确性"与正文"匹配度"不一致 | P2 | 统一为"匹配度"，修正语义路由采用理由 | ✅ 已修复 |
| 9 | Gherkin 未覆盖混合路由组合场景 | P2 | SDD Task 0 补充"混合路由 trigger → route"场景 | ✅ 已修复 |
| 10 | 语义匹配度基准不明确 | P2 | 明确 95% 相对于人工标注基准，随机路由基准约 30-40% | ✅ 本次修复 |
| 11 | 性能基准测试覆盖不完整 | P3 | 补充测试方法定义（1000 次请求预热 100 次，10 秒持续压力） | ✅ 本次修复 |
| 12 | Redis 缓存隔离未明确 | P3 | 新增 TDD 循环 [C] 语义路由缓存，使用 mock Redis，遵循测试隔离约束 | ✅ 本次修复 |

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查

- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

## 📚 相关文档 Related Documents

| 文档 | 说明 |
|------|------|
| [SDD+TDD 融合开发模式指南](./sdd-tdd-fusion-guide.md) | 开发模式详细说明与各层测试模板 |
| [SDD+TDD 实施检查清单](./sdd-tdd-checklist.md) | 实施步骤检查 |
| [or.md 系统公理一](../planning-artifacts/or.md) | 系统公理定义 |
| [Story 1.14a: 自主调用循环 - trigger](./1-14a-autonomous-invocation-trigger.md) | 前置 Story |
| Story 1.14c: 自主调用循环 - execute | 后续 Story（待创建） |
| Story 1.17: UDMR 基础路由 | 相关 Story（依赖本 Story 路由日志，待创建） |

---

**模板版本/Template Version:** 2.2.0
**创建日期/Created:** 2026-04-20
**最后更新/Last Updated:** 2026-04-21
**更新说明:** Story 1.14b 完整版本 - 实现 session_id 哈希/语义路由机制：(1) HashRouter 一致性哈希环; (2) SemanticRouter 语义路由; (3) SemanticRouter 缓存（Redis mock）；(4) RoutingDecisionLog 路由决策日志; (5) 六边形架构验证; (6) 性能基准测试 P95<50ms；本次更新：明确语义匹配度基准（人工标注基准 95% vs 随机基准 30-40%）、补充性能基准测试方法定义、新增 TDD 循环 [C] 语义路由缓存（遵循测试隔离约束）
