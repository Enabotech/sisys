# Story 1.17: UDMR 基础路由（云端优先静态配置）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 运维工程师,
**I want** 配置本地/云端路由策略（云端优先静态配置，云端不可用时回退本地）,
**So that** MVP 阶段支持基础路由决策日志和成本追踪，验证路由决策完整性≥95%、路由决策延迟 P95<100ms。

### 业务价值

本 Story 是 Epic 1（企业级架构基础与合规）价值组 6（MVP 关键机制增强）的 UDMR 路由 Story。在 Story 1.14a/b/c 自主调用三阶段管线（trigger→route→execute）和四阶段重构完成后，首次扩展管线能力——从 Agent/工具路由扩展到本地/云模型选择。

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **L1 合规检查** | 复用 ComplianceGatewayPort，敏感数据强制本地处理 | 含 PII/商业秘密时强制 local |
| **静态路由策略** | 云端优先；云端所有模型不可用或超时时切换本地 | 云端不可用→本地回退<30 秒 |
| **健康检查** | 定期检测云端可用性，恢复后自动切回云端 | 每 300 秒健康检查 |
| **路由决策日志** | 记录路由决策过程，支持审计和成本追踪 | WORM 归档，selected_model/cost_actual/fallback_reason |
| **事件集成** | 消费 AutoRouted 事件，产出 RoutingDecided 事件（带外模式） | 与自主调用管线并行集成 |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 1: 企业级架构基础与合规，价值组 6: MVP 关键机制增强，Story 1.17

**or.md 公理追溯:** 系统公理一（自主调用：trigger→route→execute），扩展"route"阶段至模型选择层

**前置依赖:** Story 1.14b（路由决策日志）、Story 1.14c（执行层 AutoExecuted 事件）

**后续依赖:** Story 1.19（成本度量，依赖 UDMR 路由日志）、Epic 11（UDMR 三层动态决策，L2 四因子评分）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: UDMR 配置模型

**Given** 系统需要配置本地模型（Ollama+Qwen2.5）和多云端模型（MiniMax/DeepSeek/GLM 等）
**When** UDMRConfig.from_env() 解析环境变量
**Then** 支持 UDMR_ENABLED、UDMR_LOCAL_FIRST、UDMR_LOCAL_MODEL 等公共配置
**And** 支持 UDMR_CLOUD_0_* 到 UDMR_CLOUD_9_* 多云端模型配置
**And** api_type 支持业界主流格式：`openai`（OpenAI Chat Completions）、`anthropic`（Anthropic Messages API）、`openai_responses`（OpenAI Responses API 新一代）
**And** Anthropic 类型必须提供 max_tokens 参数（Anthropic API 必需）
**And** 配置为 frozen dataclass，不可变

**验证标准/Validation Criteria:**
- [ ] UDMRConfig frozen dataclass 定义（`src/infrastructure/config/udmr.py`）
- [ ] CloudModelConfig frozen dataclass 定义，api_type 使用 `Literal["openai", "anthropic", "openai_responses"]`
- [ ] CloudModelConfig 包含 max_tokens 字段（Anthropic 必需）
- [ ] from_env() 解析所有 UDMR_* 环境变量
- [ ] from_env() 对 api_type=="anthropic" 且 max_tokens 缺失时抛出 ValueError
- [ ] 默认值合理：enabled=True, local_first=False, llm_timeout=600, healthcheck_interval=300, max_tokens=4096

### AC-2: UDMR 静态路由决策

**Given** 系统配置了本地模型和云端模型（AutoRouted 事件包含任务上下文）
**When** UDMRService 执行路由决策
**Then** 根据 L1 合规检查结果和静态配置决定路由类型（local/cloud）
**And** L1 合规检查通过 ComplianceGatewayPort（已实现 ComplianceGatewayImpl）
**And** 云端优先策略：默认选择第一个 enabled 的云端模型
**And** 云端不可用（超时>600 秒或所有云端模型 disabled）时回退本地
**And** 记录路由决策日志（selected_model、cost_actual、fallback_reason）

**验证标准/Validation Criteria:**
- [ ] UDMRService 领域服务定义（`src/domain/services/udmr_service.py`）
- [ ] L1 合规检查复用 ComplianceGatewayPort（已实现）
- [ ] 静态路由策略：云端优先 → 云端不可用切换本地 → 健康检查恢复后切回云端
- [ ] RoutingDecided 事件发布（事件已存在于 `src/domain/events/routing_events.py`）
- [ ] RoutingDecisionLog 持久化（selected_model、cost_actual、fallback_reason 字段填充）

### AC-3: 云端健康检查

**Given** 系统当前使用本地模型（云端曾不可用）
**When** 定期健康检查间隔到达（默认 300 秒）
**Then** 检测云端模型可用性
**And** 云端恢复健康后，下次路由决策切回云端
**And** 记录健康检查结果到 RoutingDecided 事件

**验证标准/Validation Criteria:**
- [ ] CloudHealthChecker 实现 HealthCheckPort（`src/infrastructure/external_services/llm/cloud_health_checker.py`）— 需实现 check() 和 close() 两个方法
- [ ] CloudHealthChecker 构造时绑定 cloud_configs 列表，check() 检查第一个 enabled 的云端模型
- [ ] 健康检查结果缓存（避免每次路由都检查）
- [ ] 健康检查超时处理
- [ ] health_check_passed 和 health_check_latency_ms 字段填充（基于被选中的云端模型）

### AC-4: 事件集成与 DI 注册

**Given** 自主调用管线已完成（AutoTriggered → AutoRouted → AutoExecuted）
**When** AutoRouted 事件发布后
**Then** UDMRHandler 并行消费 AutoRouted 事件（带外模式，不阻塞 AutoExecuteService）
**And** 从 AutoRouted.task_context 提取字段构造 UDMRTask
**And** 调用 UDMRService.decide() 获取路由决策
**And** 发布 RoutingDecided 事件（已注册于 ChannelRouter REALTIME 通道）
**And** 从 AutoTriggerHandler._registered_event_types 中排除 "RoutingDecided" 防止循环触发
**And** 所有组件通过 composition_root.py DI 注册

**验证标准/Validation Criteria:**
- [ ] UDMRHandler 应用层事件处理器（`src/application/event_handlers/udmr_handler.py`）
- [ ] composition_root.py 注册：udmr_policy、cloud_health_checker、udmr_service、udmr_handler（遵循 lambda 内联 config 模式）
- [ ] RoutingDecided 事件已在 ChannelRouter 中注册（sisys:rt:routing_decided）
- [ ] 六边形架构合规：无循环依赖、领域层零外部依赖
- [ ] 带外模式：AutoExecuteService 不等待 RoutingDecided，UDMR 独立并行处理
- [ ] 循环防护：从 AutoTriggerHandler._registered_event_types 中排除 "RoutingDecided"
- [ ] 事件订阅统一使用 DualChannelEventBus（InMemoryEventListener 仅用于测试 mock）

### AC-5: 路由性能与决策质量要求

> **⚠️ MVP 限制：** 本 Story 为带外模式，RoutingDecided 事件仅用于审计日志和成本追踪，不影响 AutoExecuteService 实际执行。
> 后续 Story 将修改 AutoExecuteService 消费 RoutingDecided 实现真正的模型选择控制。

**Given** AutoRouted 事件到达 UDMRHandler
**When** UDMRService 执行路由决策
**Then** 路由决策延迟 P95<100ms（MVP 静态配置，无 LLM 调用）
**And** 路由决策日志完整性≥95%（所有 AutoRouted 事件均产生 RoutingDecided 日志）
**And** 云端模型可用性检测响应<30 秒（单个云端模型健康检查超时）

**验证标准/Validation Criteria:**
- [ ] 路由决策延迟 P95<100ms 基准测试
- [ ] 路由决策幂等性（相同输入产生相同输出）
- [ ] 路由决策日志完整性≥95%（AutoRouted→RoutingDecided 转化率）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](../../../docs/developer/sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](../../../docs/developer/sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

**复用已有事件（无需新建）：**
- [ ] `RoutingDecided` 事件（`src/domain/events/routing_events.py`）— 已定义，含 L1/L2/L3 完整字段
  - route_type: Literal["local", "cloud"]
  - selected_model: str
  - estimated_cost: float
  - fallback_reason: Literal["timeout", "unavailable", "health_check_failed"] | None
  - health_check_passed: bool
  - health_check_latency_ms: float

#### 数据模型 (Data Models)

**复用已有模型（无需新建）：**
- [ ] `RoutingDecisionLog` 实体（`src/domain/entities/routing_decision_log.py`）— 已定义，含 UDMR 扩展字段
  - selected_model: str = ""
  - cost_actual: float = 0.0
  - fallback_reason: str | None = None
- [ ] `UDMRTask` 值对象（`src/domain/value_objects/udmr_task.py`）— 已定义
- [ ] `ComplianceResult` 值对象（`src/domain/value_objects/compliance_result.py`）— 已定义

**新建模型：**
- [ ] UDMRConfig 配置（`src/infrastructure/config/udmr.py`）
  - 字段: enabled(bool), local_first(bool), local_model(str), llm_timeout(int), healthcheck_interval(int), cloud_configs(list[CloudModelConfig])
  - from_env() 类方法
- [ ] CloudModelConfig 配置（同文件）
  - 字段: api_type(Literal["openai","anthropic","openai_responses"]), endpoint(str), api_key(str), model(str), enabled(bool), max_tokens(int|None), temperature(float)
  - api_type 值说明:
    - `openai` — OpenAI Chat Completions 格式（覆盖 DeepSeek/Zhipu/Qwen/Baidu V2/Ollama）
    - `anthropic` — Anthropic Messages API 格式（覆盖 Anthropic/MiniMax 推荐）
    - `openai_responses` — OpenAI Responses API 新一代格式
  - max_tokens: Anthropic 必需，其他可选
- [ ] UDMRService 领域服务（`src/domain/services/udmr_service.py`）
  - 方法: async decide(task: UDMRTask) -> RoutingDecided
  - 构造器注入原始值（不依赖 UDMRConfig）：local_first: bool, local_model: str, llm_timeout: int
  - 职责: L1 合规检查 + 静态路由策略 + 日志持久化（含 selected_model/cost_actual/fallback_reason）+ 事件发布

#### 统一端口定义注册与管理 (Port Contract)

**复用已有端口（无需新建）：**
- [ ] `ComplianceGatewayPort`（`src/domain/ports/compliance_gateway.py`）— L1 合规网关
  - 版本: 1.0, owner: compliance-team, 已在 registry 注册
  - 注意: ComplianceGatewayImpl 子服务（pipl_service/cross_border_service）未在 DI 中注入，forced_local 仅基于 data_residency 基本检查
- [ ] `RoutingDecisionLogRepository`（`src/domain/ports/routing_decision_log_repository.py`）— 路由日志持久化
  - 版本: 1.0, owner: auto-invocation-team, 已在 registry 注册
- [ ] `EventPublisher`（`src/domain/ports/event_publisher.py`）— 事件发布
  - 版本: 1.0, owner: auto-invocation-team, 已在 registry 注册

**需新建实现注册的端口（端口已定义）：**
- [ ] `HealthCheckPort`（`src/domain/ports/health_check.py`）— 健康检查
  - 版本: 1.0, owner: infrastructure-team, 端口已定义但需新建 CloudHealthChecker 实现并注册到 composition_root.py
  - 注意: HealthCheckPort.check() 为无参数方法返回 bool，另有 close() -> None 方法用于释放资源；CloudHealthChecker 需在构造时绑定 cloud_configs，check() 检查第一个 enabled 云端模型，close() 清理连接

**新建端口：**
- [ ] `UdmrPolicyPort`（`src/domain/ports/udmr_policy.py`）— UDMR 策略抽象（MVP 静态路由）
  - 方法: async route(task: UDMRTask, compliance_result: ComplianceResult) -> tuple[str, str, str | None]
  - 返回: (route_type, selected_model, fallback_reason)
  - 版本: 1.0, owner: routing-team
  - 端口契约测试: `tests/contracts/test_port_contract_udmr_policy.py`

**端口契约清单（强制）：**

| 端口名称 | 版本 | Owner | 注册 | 解析 | 契约测试 | 状态 |
|---------|------|-------|------|------|---------|------|
| ComplianceGatewayPort | 1.0 | compliance-team | ✅ | ✅ | ✅ | 复用 |
| HealthCheckPort | 1.0 | infrastructure-team | 新建 | 新建 | 新建 | **新建** |
| RoutingDecisionLogRepository | 1.0 | auto-invocation-team | ✅ | ✅ | ✅ | 复用 |
| EventPublisher | 1.0 | auto-invocation-team | ✅ | ✅ | ✅ | 复用 |
| UdmrPolicyPort | 1.0 | routing-team | 新建 | 新建 | 新建 | **新建** |

#### 六边形架构约束（必须遵守）

**四层架构定义**

| 层次 | 目录 | 本 Story 职责 |
|------|------|-------------|
| domain | `src/domain/` | UDMRService 服务 + UdmrPolicyPort 端口 |
| application | `src/application/` | UDMRHandler 事件处理器 |
| infrastructure | `src/infrastructure/` | UDMRConfig + CloudHealthChecker + StaticUdmrPolicy |
| interfaces | `src/interfaces/` | 无新增（通过事件总线集成） |

**依赖方向矩阵**

| 起点 \ 终点 | domain | application | infrastructure |
|------------|--------|-------------|----------------|
| **domain (UDMRService)** | — | ✗ 禁止 | ✗ 禁止 |
| **application (UDMRHandler)** | ✓ 允许 | — | ✗ 禁止 |
| **infrastructure (Config/HealthChecker/Policy)** | ✓ 允许 | ✓ 允许 | — |

**领域层零依赖原则** — UDMRService 仅依赖：
- Python 标准库（dataclasses, uuid, datetime, logging, asyncio）
- 领域端口（ComplianceGatewayPort, UdmrPolicyPort, HealthCheckPort, RoutingDecisionLogRepository, EventPublisher）
- 领域值对象（UDMRTask, ComplianceResult）
- 领域事件（RoutingDecided）
- 领域实体（RoutingDecisionLog）

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 功能测试文件：`tests/acceptance/test_acceptance_udmr_basic_routing.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_udmr_basic_routing.py`
- [ ] 覆盖场景:
  - 云端优先路由（云端可用时选择云端模型）
  - 云端不可用回退本地（所有云端模型 disabled 或超时）
  - L1 合规检查强制本地（敏感数据）
  - 健康检查恢复后切回云端
  - 路由决策日志记录
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
| **TDD 单元测试** | UDMRConfig + CloudModelConfig | 配置解析 | `test_udmr_config.py` | Task 1 |
| **TDD 单元测试** | StaticUdmrPolicy | 静态路由策略 | `test_udmr_policy.py` | Task 2 |
| **TDD 单元测试** | UDMRService | 三层决策编排 | `test_udmr_service.py` | Task 3 |
| **TDD 单元测试** | CloudHealthChecker | 云端健康检查 | `test_cloud_health_checker.py` | Task 3 |
| **TDD 单元测试** | UDMRHandler | 事件处理器 | `test_udmr_handler.py` | Task 4 |
| **TDD 单元测试** | RedisEventBus.subscribe() BUG修复 | 事件订阅消费机制 | `test_redis_event_bus_subscribe_fix.py` | Task 4 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_udmr_basic_routing.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_udmr_basic_routing.py` | Task 0 |
| **TDD 契约测试** | UdmrPolicyPort | 端口契约 | `test_port_contract_udmr_policy.py` | Task 0 |
| **SDD 架构验证** | UDMR 六边形架构 | 依赖方向、零依赖 | `test_arch_udmr.py` | Task 5 |
| **集成测试** | UDMR 管线 | 端到端路由流程 | `test_integration_udmr_basic_routing.py` | Task 5 |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）
- [ ] **架构层覆盖率 ≥85%**（`pytest --cov=src/domain/services/udmr_service.py`）
- [ ] **基础设施层覆盖率 ≥75%**（`pytest --cov=src/infrastructure/config/udmr.py`）
- [ ] **集成测试覆盖率 ≥70%**

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **外部服务隔离** | 云端 API 使用 AsyncMock，健康检查使用 mock | 真实 API 调用导致失败 |
| **配置隔离** | 每个测试使用独立的 UDMRConfig 实例 | 配置污染 |
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
| AC-1 | UDMRConfig + CloudModelConfig + from_env() | Task 1 | Subtask 1.1-1.3 | `test_udmr_config.py` |
| AC-2 | StaticUdmrPolicy 静态路由 | Task 2 | Subtask 2.1-2.3 | `test_udmr_policy.py` |
| AC-2 | UDMRService 三层决策编排 | Task 3 | Subtask 3.1-3.3 | `test_udmr_service.py` |
| AC-3 | CloudHealthChecker 健康检查 | Task 3 | Subtask 3.4-3.6 | `test_cloud_health_checker.py` |
| AC-4 | UDMRHandler 事件处理器 | Task 4 | Subtask 4.1-4.3 | `test_udmr_handler.py` |
| AC-4 | RedisEventBus.subscribe() BUG 修复 | Task 4 | Subtask 4.4-4.6 | `test_redis_event_bus_subscribe_fix.py` |
| AC-4 | DI 注册 | Task 4 | Subtask 4.7 | `test_integration_udmr_basic_routing.py` |
| AC-5 | 路由性能 + 架构验证 + 集成测试 | Task 5 | Subtask 5.1-5.5 | `test_arch_udmr.py` + `test_integration_udmr_basic_routing.py` |

---

## 📋 Tasks / Subtasks 任务分解

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5

> **目的：** 在进入代码实现前，明确 Schema、API 契约、端口契约、验收标准与六边形架构边界。

- [ ] Subtask 0.0: 清理陈旧 `.pyc` 缓存（之前 UDMR 原型制品）：`find src tests -name '__pycache__/udmr_*.pyc' -delete && find tests -name '__pycache__/test_*udmr*.pyc' -delete`
- [ ] Subtask 0.1: 定义 UdmrPolicyPort 端口（`src/domain/ports/udmr_policy.py`）
- [ ] Subtask 0.2: 定义端口契约测试（`tests/contracts/test_port_contract_udmr_policy.py`）
- [ ] Subtask 0.3: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_udmr_basic_routing.feature`
- [ ] Subtask 0.4: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_udmr_basic_routing.py`
- [ ] Subtask 0.5: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 端口契约测试通过（验证 Protocol 结构）
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: UDMR 配置模型

**关联 AC:** AC-1

#### TDD 循环 [A]：UDMRConfig + CloudModelConfig

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/config/test_udmr_config.py`（配置解析 + frozen 验证） |
| 🟢 绿 | 实现 `src/infrastructure/config/udmr.py`（UDMRConfig + CloudModelConfig） |
| 🔄 重构 | 优化 from_env() 解析逻辑，运行 `ruff` + `mypy` |

- [ ] Subtask 1.1: 🔴 红 — 编写 UDMRConfig 失败测试（默认值、frozen、from_env 解析）
- [ ] Subtask 1.2: 🟢 绿 — 实现 UDMRConfig + CloudModelConfig frozen dataclass
- [ ] Subtask 1.3: 🔄 重构 — 优化环境变量解析，更新 `src/infrastructure/config/__init__.py` 导出

**完成标准/Definition of Done:**
- [ ] UDMRConfig + CloudModelConfig frozen dataclass 实现
- [ ] from_env() 支持解析所有 UDMR_* 环境变量（循环解析 UDMR_CLOUD_0_* 到 UDMR_CLOUD_9_*，最多10组）
- [ ] from_env() 对 api_type=="anthropic" 且 max_tokens 缺失时抛出 ValueError
- [ ] TDD 循环全部通过

---

### Task 2: 静态路由策略实现

**关联 AC:** AC-2

#### TDD 循环 [A]：StaticUdmrPolicy

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/routing/test_udmr_policy.py`（路由策略验证） |
| 🟢 绿 | 实现 `src/infrastructure/routing/udmr_policy.py` |
| 🔄 重构 | 优化路由逻辑，运行 `ruff` + `mypy` |

- [ ] Subtask 2.1: 🔴 红 — 编写 StaticUdmrPolicy 失败测试
  - 云端优先：云端可用时返回 cloud + 第一个 enabled 模型
  - 云端不可用：所有云端 disabled 时返回 local + 本地模型
  - L1 合规强制本地：forced_local=True 时返回 local + 本地模型
  - local_first=True 时优先本地
- [ ] Subtask 2.2: 🟢 绿 — 实现 StaticUdmrPolicy
- [ ] Subtask 2.3: 🔄 重构 — 优化策略逻辑

**完成标准/Definition of Done:**
- [ ] StaticUdmrPolicy 实现 UdmrPolicyPort
- [ ] 云端优先/本地优先/合规强制三种策略正确
- [ ] TDD 循环全部通过

---

### Task 3: UDMRService + CloudHealthChecker

**关联 AC:** AC-2, AC-3

#### TDD 循环 [A]：UDMRService 三层决策编排

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/services/test_udmr_service.py`（决策编排验证） |
| 🟢 绿 | 实现 `src/domain/services/udmr_service.py` |
| 🔄 重构 | 优化决策流程，运行 `ruff` + `mypy` |

- [ ] Subtask 3.1: 🔴 红 — 编写 UDMRService 失败测试
  - decide() 接收 UDMRTask → L1 合规检查 → 静态路由 → 发布 RoutingDecided
  - L1 合规通过 + 云端可用 → route_type="cloud"
  - L1 合规不通过 → route_type="local", forced_local
  - 云端不可用 → route_type="local", fallback_reason="unavailable"
  - 日志持久化 selected_model/cost_actual/fallback_reason
- [ ] Subtask 3.2: 🟢 绿 — 实现 UDMRService
- [ ] Subtask 3.3: 🔄 重构 — 优化服务逻辑

#### TDD 循环 [B]：CloudHealthChecker

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/external_services/llm/test_cloud_health_checker.py` |
| 🟢 绿 | 实现 `src/infrastructure/external_services/llm/cloud_health_checker.py` |
| 🔄 重构 | 优化健康检查逻辑 |

- [ ] Subtask 3.4: 🔴 红 — 编写 CloudHealthChecker 失败测试
  - check() 返回 bool（mock 云端 API 调用）
  - close() 释放资源（无异常）
  - 超时处理
  - 缓存结果（避免频繁检查）
- [ ] Subtask 3.5: 🟢 绿 — 实现 CloudHealthChecker（实现 HealthCheckPort）
- [ ] Subtask 3.6: 🔄 重构 — 优化健康检查

**完成标准/Definition of Done:**
- [ ] UDMRService 实现完成（L1 合规 → 静态路由 → 日志持久化 → 事件发布）
- [ ] CloudHealthChecker 实现 HealthCheckPort
- [ ] TDD 循环全部通过

---

### Task 4: UDMRHandler + DI 注册

**关联 AC:** AC-4

#### TDD 循环 [A]：UDMRHandler 事件处理器

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/event_handlers/test_udmr_handler.py` |
| 🟢 绿 | 实现 `src/application/event_handlers/udmr_handler.py` |
| 🔄 重构 | 优化事件处理逻辑 |

- [ ] Subtask 4.1: 🔴 红 — 编写 UDMRHandler 失败测试
  - on_routed() 接收 AutoRouted → 从 task_context 提取字段构造 UDMRTask → 调用 UDMRService.decide() → 发布 RoutingDecided
  - UDMRTask 构造映射：task_id=uuid4(), input=task_context.get("input",""), data_residency=task_context.get("data_residency","CHINA_DOMESTIC"), preferred_model=task_context.get("preferred_model",""), allowed_models=task_context.get("allowed_models",[])
  - **注意:** AutoTriggerContext.ALLOWED_CONTEXT_KEYS 当前不含 input/data_residency/preferred_model/allowed_models，MVP 阶段 UDMRTask 将使用默认值，后续 Story 扩展上游事件字段
  - UDMR_ENABLED=false 时 on_routed() 应直接返回不处理
  - 非法事件类型过滤
- [ ] Subtask 4.2: 🟢 绿 — 实现 UDMRHandler
  - 事件订阅机制：UDMRHandler.subscribe() 订阅 DualChannelEventBus 的 REALTIME 通道 `sisys:rt:auto_routed`
  - DualChannelEventBus.subscribe() 在本 Story 中实现（当前仅有 publish() 能力，需新增 subscribe() 消费机制）
  - 测试环境可使用 InMemoryEventBus + InMemoryEventListener 作为 mock
- [ ] Subtask 4.3: 🔄 重构 — 优化处理器逻辑

#### TDD 循环 [B]：RedisEventBus.subscribe() BUG 修复

> **前置说明：** DualChannelEventBus 已实现 subscribe()/subscribe_async()/start()/close()，
> 委托给 RedisEventBus。但 RedisEventBus 存在 3 个已知 BUG（sisys-port-impl-refactor P0-29/30/31）：
> 1. subscribe() 传递 event_type 而非 Redis channel 名给 RedisEventSubscriber（频道名不匹配）
> 2. subscribe_async() 调用 RedisEventSubscriber 上不存在的 subscribe_async() 方法（AttributeError）
> 3. handler 收到 dict 而非 DomainEvent（缺少 from_dict 反序列化）
>
> 本 TDD 循环修复这 3 个 BUG，使 UDMRHandler 可正确订阅 AutoRouted 事件。
> 参考：`docs/architecture/sisys-port-impl-refactor.md` P0-29/30/31

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/messaging/test_redis_event_bus_subscribe_fix.py` |
| 🟢 绿 | 修复 `src/infrastructure/messaging/redis_event_bus.py` subscribe() 频道名转换 + DomainEvent 反序列化 |
| 🔄 重构 | 优化订阅机制，运行 `ruff` + `mypy` |

- [ ] Subtask 4.4: 🔴 红 — 编写 RedisEventBus.subscribe() BUG 修复失败测试
  - 频道名转换：subscribe("AutoRouted", handler) 应订阅 Redis channel `sisys:rt:auto_routed`（通过 ChannelRouter 解析）
  - DomainEvent 反序列化：handler 收到 DomainEvent 对象而非 dict（通过 DomainEvent.from_dict 包裹）
  - subscribe_async() 存在或降级：确保 subscribe_async() 路径可用
- [ ] Subtask 4.5: 🟢 绿 — 修复 RedisEventBus.subscribe() 3 个 BUG
  - redis_event_bus.py subscribe()：调用 `self._router.get_redis_channel(event_type)` 转换频道名
  - redis_event_bus.py subscribe()：用 DomainEvent.from_dict 包裹 handler 使 subscriber 收到 DomainEvent
  - redis_event_bus.py subscribe_async() 或 redis_subscriber.py：确保异步 handler 路径可用
- [ ] Subtask 4.6: 🔄 重构 — 优化订阅机制

#### DI 注册

> **六边形架构约束：** UDMRService 构造器注入原始值（local_first, local_model, llm_timeout），不依赖 UDMRConfig 配置对象。
> 参考 AutoRouteService 模式：`AutoRouteService(..., semantic_threshold=AutoRouteConfig.from_env().semantic_threshold, ...)`。

- [ ] Subtask 4.7: 更新 `src/composition_root.py` 注册（遵循 lambda resolver: 内联 config 模式）
  - `udmr_policy` → `lambda resolver:` StaticUdmrPolicy(cloud_configs=UDMRConfig.from_env().cloud_configs, local_model=UDMRConfig.from_env().local_model)
  - `cloud_health_checker` → `lambda resolver:` CloudHealthChecker(cloud_configs=UDMRConfig.from_env().cloud_configs, timeout=UDMRConfig.from_env().llm_timeout)
  - `udmr_service` → `lambda resolver:` UDMRService(compliance_gateway=resolver.resolve("compliance_gateway"), policy=resolver.resolve("udmr_policy"), health_checker=resolver.resolve("cloud_health_checker"), log_repo=resolver.resolve("routing_decision_log_repository"), publisher=resolver.resolve("event_publisher"), local_first=UDMRConfig.from_env().local_first, local_model=UDMRConfig.from_env().local_model, llm_timeout=UDMRConfig.from_env().llm_timeout)
  - `udmr_handler` → `lambda resolver:` UDMRHandler(udmr_service=resolver.resolve("udmr_service"), event_bus=resolver.resolve("event_publisher"))
  - **注意:** Resolver._instantiate() 调用 `spec.impl(resolver=self)`，lambda 必须接收 resolver 参数
  - **注意:** UDMRHandler 使用 DualChannelEventBus 订阅事件（非 InMemoryEventListener），event_bus 参数即为已注册的 DualChannelEventBus 实例

**完成标准/Definition of Done:**
- [ ] UDMRHandler 实现完成
- [ ] DualChannelEventBus.subscribe() 消费机制实现完成
- [ ] composition_root.py 注册 5 个新组件
- [ ] TDD 循环全部通过

---

### Task 5: SDD 架构约束验证 + 集成测试

**关联 AC:** AC-4, AC-5

> **性质说明：** 本 Task 是 SDD 规范验证测试，验证代码是否符合六边形架构规则。

#### 架构验证测试实现

- [ ] Subtask 5.1: 创建 `tests/unit/architecture/test_arch_udmr.py`
- [ ] Subtask 5.2: 验证 UDMRService 仅依赖领域层端口（无外部依赖）
- [ ] Subtask 5.3: 验证 UDMRHandler 位于应用层（不直接调用基础设施层）
- [ ] Subtask 5.4: 验证 StaticUdmrPolicy 实现端口（依赖倒置）
- [ ] Subtask 5.5: 创建 `tests/integration/test_integration_udmr_basic_routing.py`
  - 端到端：AutoRouted → UDMRHandler → UDMRService → RoutingDecided

**完成标准/Definition of Done:**
- [ ] 所有架构约束测试通过
- [ ] 集成测试通过
- [ ] 无循环依赖
- [ ] 领域层零外部依赖

---

### Task 6: 开发结束验收测试

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5

> **性质说明：** 对 Story 收尾阶段的交付物与完成清单进行最终验收。

- [ ] Subtask 6.1: 场景 1 — 验证 `src` 完成清单的逐项确认
- [ ] Subtask 6.2: 场景 2 — 验证 `tests/unit`、`tests/contracts`、`tests/acceptance` 完成清单
- [ ] Subtask 6.3: 运行开发结束验收测试并确认通过
- [ ] Subtask 6.4: 运行 `poetry run pytest --tb=short -q`、`poetry run ruff check`、`poetry run mypy`

**完成标准/Definition of Done:**
- [ ] `src` 完成清单已逐项验证确认
- [ ] `tests` 完成清单已逐项验证确认
- [ ] 开发结束验收测试通过
- [ ] Story 可进入 `done`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（端口与适配器）、事件驱动架构
- **系统公理一:** trigger→route→execute 自主调用循环，UDMR 在 Phase 2.5 扩展模型选择层
- **UDMR 三层决策:** L1 合规性网关 → L2 任务复杂度评估 → L3 路由决策执行
  - **本 Story 仅实现 L1 + L3 静态路由**（MVP）
  - **L2 四因子评分由 Epic 11 Story 11.1 实现**
- **设计约束:**
  - 领域层零依赖外部框架
  - 依赖倒置：领域层定义 UdmrPolicyPort，基础设施层实现
  - 事件总线双通道：RoutingDecided 已注册 REALTIME 通道（sisys:rt:routing_decided）
- **技术栈:**
  - Python 3.11+
  - LiteLLM ^1.28.0（pyproject.toml 已声明，MVP 阶段不直接调用）
  - Ollama（本地模型运行时，不在依赖中）

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) - ADR-005 (UDMR 统一动态模型路由)

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **云端优先静态配置 + L1 合规** | 实现简单、MVP 够用、复用 ComplianceGatewayPort | 无动态评分、无 L2 | ✅ 8/10 |
| 完整三层动态决策 | 最优路由质量 | 实现复杂度高、需 L2 数据积累 | 5/10 |
| 仅本地路由 | 最简单 | 无法利用云端模型能力 | 3/10 |

### UDMR 路由 vs 自主路由澄清

> ⚠️ **重要澄清**：自主路由（Story 1.14b）和 UDMR 路由（本 Story）是两个不同层次的路由。

| 维度 | 自主路由 (Story 1.14b) | UDMR 路由 (Story 1.17) |
|------|----------------------|----------------------|
| 路由对象 | Agent/工具（目标选择） | 本地/云模型（模型选择） |
| 输入事件 | AutoTriggered | AutoRouted |
| 输出事件 | AutoRouted | RoutingDecided |
| 决策算法 | hash + semantic | L1 合规 → L3 静态路由 |
| 触发时机 | Phase 2 | Phase 2.5 |

**数据流（MVP 带外模式）：**
```
AutoTriggered (1.14a)
    ↓
AutoRouteService (1.14b) → 选择目标 Agent/工具
    ↓ 发布 AutoRouted 事件
    ├── AutoExecuteService (1.14c) → 执行任务（不等待 UDMR）
    │
    └── [并行/带外] UDMRService (1.17) → 选择本地/云端模型
        ↓ 发布 RoutingDecided 事件
        └→ 审计/日志/成本追踪（不影响现有管线）
```

> **⚠️ 架构说明：** MVP 阶段 UDMR 为**带外（out-of-band）处理器**，与 AutoExecuteService 并行消费 AutoRouted 事件。
> RoutingDecided 事件用于审计日志和成本追踪，**不阻塞 AutoExecuteService 执行**。
> 后续 Story 将修改 AutoExecuteService 消费 RoutingDecided 实现真正的模型选择。
>
> **⚠️ 事件订阅统一方案：** 系统统一使用 DualChannelEventBus 作为事件分发机制（Redis REALTIME 通道 + RabbitMQ BATCH 通道）。
> DualChannelEventBus 已实现 EventSubscriber Protocol（subscribe/subscribe_async/start/close），
> 委托给 RedisEventBus。但 RedisEventBus 存在 3 个已知 BUG 需在本 Story 中修复（P0-29/30/31）：
> - subscribe() 传递 event_type 而非 Redis channel 名 → 频道名不匹配
> - subscribe_async() 调用不存在的方法 → AttributeError
> - handler 收到 dict 而非 DomainEvent → 缺少 from_dict 反序列化
> - composition_root.py 已注册 `event_subscriber` 解析为 `event_publisher`（同一 DualChannelEventBus 实例）
> - InMemoryEventListener 仅用于单元测试和集成测试环境（mock 场景）
>
> **⚠️ 循环防护（必须实施）：** AutoTriggerHandler._registered_event_types 已包含 "RoutingDecided"，
> 但其 _process_event() 不检查 causation_id，无条件调用 on_domain_event()，因此 causation_id 方案**不能**防止循环。
> **必须**从 AutoTriggerHandler._registered_event_types 中排除 "RoutingDecided"（auto_trigger_handler.py 第75行）。
> 设置 causation_id 仅作为辅助追踪手段，不能作为防护措施。

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── domain/
│   │   ├── ports/
│   │   │   └── udmr_policy.py  # 新建：UDMR 策略端口
│   │   └── services/
│   │       └── udmr_service.py             # 新建：UDMR 三层决策服务
│   ├── application/
│   │   └── event_handlers/
│   │       └── udmr_handler.py             # 新建：UDMR 事件处理器
│   ├── infrastructure/
│   │   ├── config/
│   │   │   └── udmr.py                     # 新建：UDMRConfig + CloudModelConfig
│   │   ├── messaging/
│   │   │   └── dual_channel_event_bus.py   # 更新：新增 subscribe() 消费机制
│   │   ├── routing/
│   │   │   └── udmr_policy.py  # 新建：UDMR 策略实现（MVP 静态路由）
│   │   └── external_services/
│   │       └── llm/
│   │           └── cloud_health_checker.py # 新建：云端健康检查
│   └── composition_root.py                 # 更新：新增 5 个注册
├── tests/
│   ├── unit/
│   │   ├── infrastructure/config/test_udmr_config.py
│   │   ├── infrastructure/routing/test_udmr_policy.py
│   │   ├── infrastructure/external_services/llm/test_cloud_health_checker.py
│   │   ├── domain/services/test_udmr_service.py
│   │   ├── application/event_handlers/test_udmr_handler.py
│   │   └── architecture/test_arch_udmr.py
│   ├── contracts/
│   │   └── test_port_contract_udmr_policy.py
│   ├── integration/
│   │   └── test_integration_udmr_basic_routing.py
│   └── acceptance/
│       ├── test_acceptance_udmr_basic_routing.feature
│       └── test_acceptance_udmr_basic_routing.py
```

### 已有可复用组件（无需新建）

| 组件 | 文件路径 | 说明 |
|------|---------|------|
| ComplianceGatewayPort | `src/domain/ports/compliance_gateway.py` | L1 合规网关端口 |
| ComplianceGatewayImpl | `src/infrastructure/security/compliance_gateway_impl.py` | L1 合规网关实现 |
| HealthCheckPort | `src/domain/ports/health_check.py` | 健康检查端口（端口已定义，需新建实现注册） |
| RoutingDecisionLog | `src/domain/entities/routing_decision_log.py` | 含 UDMR 扩展字段 |
| RoutingDecisionLogRepository | `src/domain/ports/routing_decision_log_repository.py` | 日志持久化端口 |
| InMemoryRoutingDecisionLogRepository | `src/infrastructure/messaging/inmemory_routing_decision_log_repository.py` | 内存实现 |
| UDMRTask | `src/domain/value_objects/udmr_task.py` | UDMR 任务值对象 |
| ComplianceResult | `src/domain/value_objects/compliance_result.py` | 合规结果值对象 |
| RoutingDecided | `src/domain/events/routing_events.py` | UDMR 路由决策事件（已含完整 L1/L2/L3 字段） |
| AutoRouted | `src/domain/events/auto_route_events.py` | 自主路由事件（UDMR 输入） |
| ChannelRouter | `src/infrastructure/messaging/channel_router.py` | RoutingDecided 已注册 REALTIME 通道 |

### 环境变量设计

> **业界调研基础：** api_type 支持 3 种主流格式，覆盖 95%+ 国内外大模型提供商。
> 详细调研参见 [LLM API 调研报告](#llm-api-兼容性调研)。
>
> **参数合理性说明：**
> - `UDMR_LLM_TIMEOUT=600` — 10 分钟超时适用于长文档处理场景（如 PDF 分析、代码审查）。短对话场景由应用层设置更短超时
> - `UDMR_HEALTHCHECK_INTERVAL=300` — 5 分钟健康检查间隔平衡资源消耗和恢复检测速度
> - `UDMR_LOCAL_FIRST=false` — 默认云端优先，通过健康检查自动回退本地

```bash
# UDMR 公共配置
export UDMR_ENABLED=true
export UDMR_LOCAL_FIRST=false
export UDMR_LOCAL_MODEL=qwen2.5:7b
export UDMR_LLM_TIMEOUT=600
export UDMR_HEALTHCHECK_INTERVAL=300

# 云端模型 0 — MiniMax (Anthropic 模式，官方推荐，支持 thinking block)
export UDMR_CLOUD_0_ENABLED=true
export UDMR_CLOUD_0_API_TYPE=anthropic
export UDMR_CLOUD_0_ENDPOINT=https://api.minimax.chat/anthropic
export UDMR_CLOUD_0_API_KEY=""
export UDMR_CLOUD_0_MODEL=MiniMax-M2.7
export UDMR_CLOUD_0_MAX_TOKENS=4096

# 云端模型 1 — DeepSeek (OpenAI 兼容格式)
export UDMR_CLOUD_1_ENABLED=true
export UDMR_CLOUD_1_API_TYPE=openai
export UDMR_CLOUD_1_ENDPOINT=https://api.deepseek.com
export UDMR_CLOUD_1_API_KEY=""
export UDMR_CLOUD_1_MODEL=deepseek-v4-flash

# 云端模型 2 — 智谱 GLM (OpenAI 兼容格式，可选扩展)
# export UDMR_CLOUD_2_ENABLED=true
# export UDMR_CLOUD_2_API_TYPE=openai
# export UDMR_CLOUD_2_ENDPOINT=https://open.bigmodel.cn/api/paas/v4
# export UDMR_CLOUD_2_API_KEY=""
# export UDMR_CLOUD_2_MODEL=glm-5.1
```

#### api_type 与业界模型兼容性映射

| api_type | 兼容提供商 | Endpoint 示例 | 认证方式 |
|----------|-----------|--------------|---------|
| `openai` | OpenAI, DeepSeek, Zhipu GLM, Qwen/DashScope, Baidu ERNIE V2, Ollama | `https://api.deepseek.com` | Bearer Token |
| `anthropic` | Anthropic, MiniMax(推荐) | `https://api.minimax.chat/anthropic` | x-api-key header |
| `openai_responses` | OpenAI(新), Ollama(新) | `https://api.openai.com/v1` | Bearer Token |

#### Anthropic 格式关键差异（开发时必须处理）

| 维度 | OpenAI 格式 | Anthropic 格式 | UDMR 处理要求 |
|------|-----------|---------------|-------------|
| 认证头 | `Authorization: Bearer xxx` | `x-api-key: xxx` + `anthropic-version: 2023-06-01` | 适配器切换认证方式 |
| system 消息 | messages 中 role=system | top-level `system` 参数 | Anthropic 调用时提取 system |
| max_tokens | 可选（默认 inf） | **必需** | CloudModelConfig.max_tokens 提供默认值 |
| content 格式 | `"string"` 或 array | 必须是 array | Anthropic 调用时转换格式 |
| 响应 usage | prompt/completion/total | input_tokens/output_tokens | 响应统一层转换 |

### LLM API 兼容性调研

> **调研日期:** 2026-05-22
> **调研范围:** OpenAI, Anthropic, DeepSeek, Zhipu GLM, MiniMax, Qwen/DashScope, Baidu ERNIE, Ollama, LiteLLM

#### API 格式统一性分析

| 提供商 | 兼容 OpenAI | 兼容 Anthropic | Base URL | 备注 |
|--------|:---------:|:-----------:|----------|------|
| **OpenAI** | ✅ 原生 | — | `https://api.openai.com/v1` | 行业标准 |
| **Anthropic** | — | ✅ 原生 | `https://api.anthropic.com` | 独立格式 |
| **DeepSeek** | ✅ 完全 | — | `https://api.deepseek.com` | 直接兼容 |
| **Zhipu GLM** | ✅ 完全 | — | `https://open.bigmodel.cn/api/paas/v4` | 直接兼容 |
| **MiniMax** | ✅ | ✅ **推荐** | `https://api.minimax.chat/anthropic` | Anthropic 模式支持 thinking |
| **Qwen** | ✅ 完全 | — | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 兼容模式 endpoint |
| **Baidu ERNIE** | ✅ V2 | — | `https://qianfan.baidubce.com/v2` | V2 兼容，V1 遗留 OAuth 不支持 |
| **Ollama** | ✅ 完全 | — | `http://localhost:11434` | 无认证，本地推理 |

#### 统一抽象层架构

```
UDMRClient (统一接口)
    ├── OpenAIAdapter (api_type=openai)
    │   └── 直接传递（行业标准格式，无需转换）
    │
    ├── AnthropicAdapter (api_type=anthropic)
    │   ├── 请求转换: system 提取 + content 数组化 + max_tokens 注入
    │   ├── 认证适配: x-api-key header + anthropic-version
    │   └── 响应转换: content[0].text → message.content
    │
    └── OpenAIResponsesAdapter (api_type=openai_responses)
        └── 增量流式处理 + 状态管理（V2+ 扩展）
```

#### 故障切换策略（参考 LiteLLM 最佳实践）

| 参数 | 建议值 | 说明 |
|------|--------|------|
| cooldown_time | 30s | 云端模型失败后冷却期 |
| retries | 3 | 单次请求最大重试次数 |
| allowed_fails | 3 | 连续失败阈值，触发冷却 |
| healthcheck_interval | 300s | 健康检查周期 |
| retry_after | 0.5s | 重试间隔（指数退避可选） |

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 1.14b: 自主调用循环 - route](./1-14b-autonomous-invocation-route.md), [Story 1.14c: execute](./1-14c-autonomous-invocation-execute.md), [重构文档](../../docs/architecture/sisys-auto-invocation-refactor.md)

**关键学习/Key Learnings:**
1. **配置 frozen 约束** — 重构 Phase 3 统一所有 auto-invocation 配置为 frozen=True，UDMRConfig 必须遵循
2. **路由决策日志必须实例化并填充扩展字段** — 重构 P2-3 修复了 RoutingDecisionLog 从未实例化的问题；AutoRouteService._persist_decision_log() 仅填充基础字段（source_agent/target_agent），UDMR 扩展字段（selected_model/cost_actual/fallback_reason）留空。本 Story UDMRService._persist_decision_log() 必须正确填充：
   - selected_model: 从 UdmrPolicyPort.route() 返回值获取
   - cost_actual: MVP 阶段使用估算值（基于云端模型定价或默认 0.0）
   - fallback_reason: 从 route() 返回值获取（Literal["timeout","unavailable","health_check_failed"]）
3. **事件处理器解耦 + 带外模式** — AutoRouteHandler 仅调用 AutoRouteService，不自行发布事件（P0-2 修复），UDMRHandler 应遵循相同模式。此外 UDMR 为带外处理器，与 AutoExecuteService 并行消费 AutoRouted，不阻塞执行管线。循环防护必须从 AutoTriggerHandler._registered_event_types 中排除 "RoutingDecided"（causation_id 不能防止循环）。**事件订阅统一使用 DualChannelEventBus**（生产环境 Redis REALTIME 通道），InMemoryEventListener 仅用于单元测试 mock
4. **DockerSandboxAdapter 实例变量** — 重构 P2-7 修复了类级别状态共享问题
5. **composition_root 注册模式** — 使用 `register_port()` 统一注册，lambda 工厂函数注入依赖

**应用到本故事/Applied to This Story:**
- [ ] UDMRConfig 和 CloudModelConfig 均为 frozen=True
- [ ] UDMRService._persist_decision_log() 填充 selected_model/cost_actual/fallback_reason
- [ ] UDMRHandler 仅调用 UDMRService，不自行发布事件
- [ ] 所有新组件通过 composition_root.py DI 注册

### Git Intelligence Summary

**来源:** `git log` - 最近提交

| 提交 | 主题 | 关键模式 |
|------|------|---------|
| `b85bb83f` | refactor: Phase 3+4 auto-invocation code quality | frozen config, LRU cache, instance state |
| `31a51ab5` | docs: R6 final review fixes | 文档同步 |
| `e1e49d21` | refactor: Phase 1+2 auto-invocation critical bug fixes | DI path, cosine similarity, PublishResult |

**可应用模式:**
1. **frozen dataclass 配置** — AutoTriggerConfig/AutoRouteConfig 均为 frozen=True
2. **Protocol 端口注册** — ComplianceGatewayPort 在 registry 中注册
3. **事件处理器模式** — AutoRouteHandler 的 on_triggered → service 调用模式

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (create-story workflow) |
| **Version** | create-story workflow v1.0 |
| **Execution Date** | 2026-05-22 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|-----|
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/1-14c-autonomous-invocation-execute.md` |
| **设计文档** | `docs/architecture/sisys-auto-invocation-design.md` |
| **重构文档** | `docs/architecture/sisys-auto-invocation-refactor.md` |
| **Sprint 变更提案** | `_bmad-output/planning-artifacts/sprint-change-proposal-2026-05-11-udmr-cloud-models.md` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取
- [x] 架构约束从 `architecture.md` §4 UDMR 章节提取
- [x] 前一个故事学习经验整合（1.14b/c + 重构经验）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] 已有可复用组件清单明确
- [x] 环境变量设计与业界主流 LLM API 调研对齐
- [x] UDMR 路由 vs 自主路由关系澄清
- [x] 端口契约清单（3 个复用 + 1 个新建实现 + 1 个新建端口）

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/1-17-udmr-basic-routing.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/domain/ports/udmr_policy.py` - UDMR 策略端口
- `src/domain/services/udmr_service.py` - UDMR 三层决策服务
- `src/infrastructure/config/udmr.py` - UDMRConfig + CloudModelConfig
- `src/infrastructure/routing/udmr_policy.py` - UDMR 策略实现（MVP 静态路由）
- `src/infrastructure/external_services/llm/cloud_health_checker.py` - 云端健康检查
- `src/application/event_handlers/udmr_handler.py` - UDMR 事件处理器
- `tests/unit/infrastructure/config/test_udmr_config.py` - 配置单元测试
- `tests/unit/infrastructure/routing/test_udmr_policy.py` - 策略单元测试
- `tests/unit/infrastructure/external_services/llm/test_cloud_health_checker.py` - 健康检查测试
- `tests/unit/domain/services/test_udmr_service.py` - UDMRService 单元测试
- `tests/unit/application/event_handlers/test_udmr_handler.py` - UDMRHandler 单元测试
- `tests/unit/infrastructure/messaging/test_redis_event_bus_subscribe_fix.py` - RedisEventBus.subscribe() BUG修复测试
- `tests/unit/architecture/test_arch_udmr.py` - 架构约束测试
- `tests/contracts/test_port_contract_udmr_policy.py` - 端口契约测试
- `tests/integration/test_integration_udmr_basic_routing.py` - 集成测试
- `tests/acceptance/test_acceptance_udmr_basic_routing.feature` - Gherkin 验收测试
- `tests/acceptance/test_acceptance_udmr_basic_routing.py` - BDD 步骤实现

**更新的文件/Updated Files:**
- `src/infrastructure/messaging/dual_channel_event_bus.py` - 无需修改（subscribe 已实现）
- `src/infrastructure/messaging/redis_event_bus.py` - 修复 subscribe() 3个BUG（频道名/DomainEvent/subscribe_async）
- `src/infrastructure/config/__init__.py` - 添加 UDMRConfig 导出
- `src/domain/ports/__init__.py` - 添加 UdmrPolicyPort 导出
- `src/domain/services/__init__.py` - 添加 UDMRService 导出（如需要）
- `src/infrastructure/external_services/llm/__init__.py` - 新建目录及包初始化
- `src/composition_root.py` - 新增 5 个 DI 注册

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
| **覆盖 FR** | FR-CP-05 |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成
2. [x] All acceptance criteria specified 所有验收标准已定义
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [ ] Sprint status synced to `ready-for-dev`

### 🔧 对抗性审查修复（Adversarial Review Fixes）

> **Round 1 (2026-05-22):** 基于3个并行Agent调研实际代码实现，发现并修复4个P0问题
> - P0-1: UDMRService 构造器从依赖 UDMRConfig 改为注入原始值（local_first/local_model/llm_timeout），遵循六边形架构
> - P0-2: 扩展 Lessons Learned 明确 UDMRService._persist_decision_log() 必须填充 selected_model/cost_actual/fallback_reason
> - P0-3: 文件清单添加 src/domain/ports/__init__.py 导出 UdmrPolicyPort
> - P0-4: HealthCheckPort 状态从"复用"修正为"新建"（composition_root.py 未注册，需新建实现注册）
>
> **Round 2 (2026-05-22):** 基于3个并行Agent调研，发现并修复3个P0问题+6个P1问题
> - P0-1: 事件流架构矛盾 — 数据流从顺序改为带外并行模式（AutoExecuteService不等待RoutingDecided）
> - P0-2: AutoRouted.task_context→UDMRTask映射补充完整字段映射规范
> - P0-3: RoutingDecided循环风险 — 补充event_id因果链防循环机制
> - P0-4: UdmrPolicyPort.route()返回类型修正 float|None → str|None
> - P1: 移除"向后兼容UDMR_CLOUD_MODELS"（无代码依据）
> - P1: DI注册改为lambda内联UDMRConfig.from_env()模式（遵循现有惯例）
> - P1: 零依赖原则列表补充HealthCheckPort
> - P1: 文件清单添加external_services/llm/__init__.py
> - P1: AC-1补充api_type=="anthropic"时max_tokens必需验证
> - P1: AC-4补充带外模式验证标准
>
> **Round 3 (2026-05-22):** 科学性与合理性审查，修复2个P0问题+3个P1问题
> - P0: Story标题从"本地优先"修正为"云端优先静态配置"（与策略和配置一致）
> - P0: AC-5指标从"本地路由占比≥80%"改为"路由决策日志完整性≥95%"（带外模式下决策不影响执行）
> - P0: 明确MVP限制说明（RoutingDecided仅用于审计，不影响AutoExecuteService）
> - P1: 添加参数合理性说明（llm_timeout/healthcheck_interval/local_first）
> - P1: AC-5补充健康检查超时性能指标
> - P1: 补充ComplianceGatewayImpl子服务注入说明（pipl_service/cross_border_service参数名不匹配为已知问题）
>
> **Round 4 (2026-05-22):** 跨文档一致性+实现可行性+内部一致性审查，修复4个P0问题+8个P1问题
> - P0: 追溯矩阵Subtask 1.4-1.6不存在，合并到1.1-1.3
> - P0: 循环防护从"event_id因果链"改为具体实现指导（排除AutoTriggerHandler中的RoutingDecided）
> - P0: CloudHealthChecker多模型策略明确（构造时绑定cloud_configs，check()检查第一个enabled模型）
> - P0: 添加陈旧.pyc缓存清理步骤到Task 0
> - P1: 价值组归属修正（5→6:MVP关键机制增强）
> - P1: EventPublisher添加到端口契约清单表格
> - P1: AC-1字段名修正（timeout→llm_timeout）
> - P1: TDD标题拼写修正（UDR→UDMR）
> - P1: HealthCheckPort分类修正（从"复用"移至"需新建实现注册")
> - P1: test_cloud_model_config合并到test_udmr_config
> - P1: 补充UDMR_ENABLED=false行为和UDMRHandler订阅机制
> - 用户反馈: static_routing_strategy重命名为udmr_policy（UdmrPolicyPort/StaticUdmrPolicy）
>
> **Round 5 (2026-05-22):** 最终质量确认，无P0问题，修复4个P1+2个P2
> - P1: DI参数名strategy→policy同步重命名（第480行）
> - P1: 价值组归属第19行和第866行从"5"更新为"6"（Round 4遗漏）
> - P1: UDMRHandler DI注册补充event_listener参数注入
> - P1: 依赖方向矩阵标签Strategy→Policy
> - P2: AC-1默认值false→False（Python布尔值大写）
> - P2: 中英文间距修正
>
> **--- 第二批审查 ---**
>
> **第二批 Round 1 (2026-05-22):** 3个并行Agent管线集成/数据模型/DI架构深度验证，修复3个P0+2个P1
> - P0: causation_id循环防护无效—AutoTriggerHandler不检查causation_id无条件调用on_domain_event()，必须从_registered_event_types排除RoutingDecided
> - P0: DualChannelEventBus.publish()不调用InMemoryEventListener.dispatch()，event_listener.on_event()模式仅MVP/测试环境有效，生产环境需单独订阅机制
> - P0: AutoRouted事件当前无InMemoryEventListener消费者（AutoRouteHandler无register_handlers()），UDMRHandler将是第一个
> - P1: data_residency默认值"default"→"CHINA_DOMESTIC"（与UDMRTask默认值对齐）
> - P1: Lessons Learned循环防护描述修正（移除causation_id有效性暗示）
>
> **第二批 Round 2 (2026-05-22):** 3个并行Agent端口契约/事件数据模型/DI模式深度验证，修复2个P0
> - P0: DI注册lambda无参写法错误—Resolver._instantiate()调用spec.impl(resolver=self)，所有lambda必须为`lambda resolver:`格式而非`lambda:`
> - P0: HealthCheckPort遗漏close()方法—端口实际定义check()+close()两个方法，CloudHealthChecker必须同时实现close()释放资源
>
> **第二批 Round 3-4 (2026-05-22):** 跨文档一致性+DI完整性+数据流验证，修复3个P0
> - P0: 事件订阅统一改为DualChannelEventBus（用户决策），InMemoryEventListener仅用于测试mock；UDMRHandler.subscribe()订阅Redis REALTIME通道
> - P0: 上游AutoTriggerContext.ALLOWED_CONTEXT_KEYS缺失UDMR字段（input/data_residency/preferred_model/allowed_models），MVP阶段使用默认值
> - P0: UDMRHandler DI注册从event_listener改为event_bus（DualChannelEventBus实例）
>
> **第二批 Round 5 (2026-05-22):** 最终质量确认，3个并行Agent设计规则+测试策略+文档质量全量验证，无P0问题
> - 设计规则验证：8项全部合规（六边形架构/frozen/DI模式/事件订阅统一/循环防护/端口契约/数据流/MVP限制）
> - 测试策略验证：6项全部通过（文件清单/覆盖率/TDD循环/隔离约束/契约测试/Gherkin场景）
> - 文档质量验证：6项全部通过（模板合规/章节完整/内部一致/审查记录/概念澄清/格式规范）
>
> **用户补充决策 (2026-05-22):**
> - 事件订阅统一使用 DualChannelEventBus，InMemoryEventListener 仅供备用或测试需要时使用
> - DualChannelEventBus 当前仅有 publish() 能力，subscribe() 消费机制需在本 Story 中实现（新增 Subtask 4.4-4.6、测试文件、更新文件清单）
>
> **第三批 Round 1 (2026-05-22):** 3个并行Agent基于事件总线设计文档深度验证，发现3个P0问题
> - P0: Story声称"DualChannelEventBus仅有publish()能力"是错误的—subscribe()/subscribe_async()/start()/close()均已实现
> - P0: RedisEventBus.subscribe()存在3个已知BUG（P0-29/30/31）：频道名不匹配、subscribe_async()调用不存在方法、handler收到dict非DomainEvent
> - P0: Subtask 4.4-4.6从"从零实现subscribe()"改为"修复RedisEventBus现有BUG"；测试文件重命名为test_redis_event_bus_subscribe_fix.py

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v3.0.0
**创建日期/Created:** 2026-05-22
**最后更新/Last Updated:** 2026-05-22
**更新说明/Description:**
- v1.0.0: 创建故事文件
- v1.1.0: 融入业界 LLM API 调研成果（OpenAI/Anthropic/DeepSeek/Zhipu/MiniMax/Qwen/Baidu/Ollama/LiteLLM）；api_type 从 str 改为 Literal["openai","anthropic","openai_responses"]；CloudModelConfig 新增 max_tokens 字段；新增 API 兼容性映射表和统一抽象层架构；新增故障切换策略参考 LiteLLM 最佳实践
- v1.2.0: Round 1 审查修复 — P0-1:UDMRService构造器改原始值注入；P0-2:明确_persist_decision_log填充UDMR扩展字段；P0-3:添加ports/__init__.py导出；P0-4:HealthCheckPort状态修正为"新建"
- v1.3.0: Round 2 审查修复 — P0:事件流从顺序改为带外并行模式；P0:补充AutoRouted→UDMRTask字段映射；P0:补充RoutingDecided因果链防循环；P0:修正route()返回类型float→str；P1:移除UDMR_CLOUD_MODELS兼容；P1:DI改lambda内联模式；P1:补充HealthCheckPort到零依赖列表；P1:添加llm/__init__.py到文件清单
- v1.4.0: Round 3 审查修复 — P0:标题改为"云端优先静态配置"（与策略一致）；P0:AC-5指标改为"路由决策日志完整性≥95%"（带外模式）；P1:参数合理性说明；P1:健康检查性能指标；P1:ComplianceGatewayImpl已知问题标注
- v1.5.0: Round 4 审查修复 — P0:追溯矩阵合并虚构Subtask；P0:循环防护改为具体实现指导；P0:CloudHealthChecker多模型策略明确；P0:.pyc清理步骤；P1:价值组5→6；P1:EventPublisher入端口表；P1:字段名/拼写修正；P1:UDMR_ENABLED行为；用户反馈:重命名udmr_policy
- v1.6.0: Round 5 最终审查修复 — P1:strategy→policy参数名同步重命名；P1:价值组归属2处遗漏修正；P1:UDMRHandler DI补充event_listener注入；P1:依赖矩阵Strategy→Policy标签；P2:false→False；P2:中英文间距
- v2.0.0: 第二批审查 Round 1 — P0:循环防护causation_id无效改为必须排除RoutingDecided；P0:标注事件订阅MVP限制（InMemoryEventBus vs DualChannelEventBus）；P0:标注AutoRouted当前无InMemoryEventListener消费者；P1:data_residency默认值default→CHINA_DOMESTIC；P1:修正Lessons Learned循环防护描述
- v2.1.0: 第二批审查 Round 2 — P0:DI注册lambda无参写法改为lambda resolver:格式；P0:HealthCheckPort补充close()方法
- v2.2.0: 第二批审查 Round 3-4 — P0:事件订阅统一DualChannelEventBus（用户决策）；P0:上游task_context字段缺失标注MVP默认值；P0:UDMRHandler DI从event_listener改event_bus
- v2.3.0: 用户补充决策 — DualChannelEventBus.subscribe()在本Story实现；新增Subtask 4.4-4.6 TDD循环；添加test_dual_channel_subscribe.py；更新dual_channel_event_bus.py文件清单
- v3.0.0: 第三批审查 Round 1 — P0:纠正"DualChannelEventBus仅有publish()"错误声明（subscribe已实现）；P0:Subtask 4.4-4.6改为修复RedisEventBus 3个BUG（P0-29/30/31频道名/DomainEvent/subscribe_async）；P0:测试文件重命名
