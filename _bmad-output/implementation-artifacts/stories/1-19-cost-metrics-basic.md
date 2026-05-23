# Story 1.19: 成本度量基础（Token 消耗与成本追踪）

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 运维工程师,
**I want** 追踪每个任务的 Token 消耗和成本，基于 UDMR 路由日志计算模型调用成本,
**So that** 验证 MVP 成本优化效果并衡量 ROI，支持"Token 成本节省 ≥50%"目标验证。

### 业务价值

本 Story 是 Epic 1（企业级架构基础与合规）价值组 6（MVP 关键机制增强）的成本度量 Story。在 Story 1.17 UDMR 基础路由（云端优先静态配置）完成后，首次实现成本追踪与 ROI 验证能力——从占位值 `cost_actual=0.0` 升级为基于定价表的估算成本。

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **模型定价配置** | CloudModelConfig 扩展定价字段，支持按模型配置单价 | 本地¥0.002/1K，云端¥0.02/1K |
| **成本计算服务** | CostCalculator 基于 route_type + token 估算计算实际成本 | 成本计算准确率 100% |
| **成本事件监听** | 消费 RoutingDecided 事件，填充 cost_actual 并持久化 | cost_actual 从 0.0 改为实际度量值 |
| **Prometheus 指标** | 扩展 MetricsPort，暴露 Token 消耗和成本 Gauge/Counter | Grafana 面板可查 |
| **聚合查询** | 支持按任务类型/Agent/时间范围聚合查询 | 查询延迟 P95<100ms |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 1: 企业级架构基础与合规，价值组 6: MVP 关键机制增强，Story 1.19

**or.md 公理追溯:** 系统公理一（自主调用），扩展"execute"阶段的成本追踪能力

**前置依赖:** Story 1.17（UDMR 基础路由 — RoutingDecided 事件 + RoutingDecisionLog 实体）

**后续依赖:** Epic 11 Story 11.3（三级成本熔断器）、Story 7.4（健康度仪表盘集成）

**覆盖 FR:** FR-CP-01（路由决策日志含成本）、FR-CP-03（健康度仪表盘 Token 消耗趋势）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 模型定价配置

**Given** 系统需要计算本地模型和云端模型的调用成本
**When** CostPricingConfig.from_env() 解析定价配置
**Then** CloudModelConfig 扩展 `price_per_input_1k_tokens` 和 `price_per_output_1k_tokens` 字段（元/1K tokens）
**And** 本地模型默认定价：input ¥0.002/1K，output ¥0.002/1K
**And** 云端模型定价从环境变量 `UDMR_CLOUD_*_PRICE_INPUT` 和 `UDMR_CLOUD_*_PRICE_OUTPUT` 读取
**And** 未配置定价时使用合理的默认值（本地 ¥0.002/1K，云端 ¥0.02/1K）
**And** 配置为 frozen dataclass，不可变

**验证标准/Validation Criteria:**
- [ ] CloudModelConfig 扩展 `price_per_input_1k_tokens: float` 和 `price_per_output_1k_tokens: float`
- [ ] `from_env()` 解析 `UDMR_CLOUD_*_PRICE_INPUT` 和 `UDMR_CLOUD_*_PRICE_OUTPUT`
- [ ] 默认值：本地 input/output ¥0.002/1K，云端 input/output ¥0.02/1K
- [ ] 定价配置非负校验

### AC-2: Token 消耗值对象与成本计算服务

**Given** 系统需要记录 Token 消耗并计算成本
**When** CostCalculator.calculate() 执行成本计算
**Then** TokenConsumption 值对象包含 `prompt_tokens: int`、`completion_tokens: int`、`total_tokens: int`
**And** CostCalculator 基于 `route_type` + `selected_model` + `pricing_config` 计算 cost_actual
**And** MVP 阶段 Token 消耗使用估算值（基于预设 prompt/completion token 比例）
**And** 成本计算公式：`cost = (prompt_tokens × input_price + completion_tokens × output_price) / 1000`

**验证标准/Validation Criteria:**
- [ ] TokenConsumption frozen dataclass 定义（`src/domain/value_objects/token_consumption.py`）
- [ ] CostCalculator 领域服务定义（`src/domain/services/cost_calculator.py`）
- [ ] CostCalculator 注入原始值（不依赖 CloudModelConfig 配置对象）
- [ ] MVP 估算策略：本地 256 prompt + 512 completion，云端 512 prompt + 1024 completion
- [ ] 成本计算准确率 100%

### AC-3: RoutingDecided 事件与 RoutingDecisionLog 实体扩展

**Given** Story 1.17 已定义 RoutingDecided 事件和 RoutingDecisionLog 实体
**When** 本 Story 扩展这些数据结构
**Then** RoutingDecided 新增 `prompt_tokens: int`、`completion_tokens: int`、`total_tokens: int`、`cost_actual: float` 字段
**And** RoutingDecisionLog 新增 `prompt_tokens: int`、`completion_tokens: int`、`total_tokens: int` 字段
**And** RoutingDecisionLog.validate() 新增 token 字段非负校验
**And** 向后兼容：所有新字段均有默认值 0，不影响现有事件消费

**验证标准/Validation Criteria:**
- [ ] RoutingDecided 事件扩展 4 个字段（均有默认值 0/0.0）
- [ ] RoutingDecisionLog 实体扩展 3 个字段（均有默认值 0）
- [ ] validate() 新增非负校验
- [ ] 已有测试不受影响（向后兼容）

### AC-4: CostMetricsListener 事件监听与 DI 注册

**Given** UDMR 路由决策产生 RoutingDecided 事件
**When** CostMetricsListener 消费 RoutingDecided 事件
**Then** 调用 CostCalculator 计算 cost_actual
**And** 构造 TokenConsumption 值对象
**And** 更新 RoutingDecisionLog 的 cost_actual/token 字段（通过 RoutingDecisionLogRepository）
**And** 记录 Prometheus 指标（Token 消耗 Counter + 成本 Gauge）
**And** 所有组件通过 composition_root.py DI 注册

**验证标准/Validation Criteria:**
- [ ] CostMetricsListener 应用层事件处理器（`src/application/event_handlers/cost_metrics_handler.py`）
- [ ] 订阅 RoutingDecided 事件（通过 DualChannelEventBus.subscribe_async()）
- [ ] 调用 CostCalculator.calculate() 计算成本
- [ ] 更新 RoutingDecisionLog 的 cost_actual 和 token 字段
- [ ] 记录 Prometheus 指标
- [ ] composition_root.py 注册新组件
- [ ] 六边形架构合规：无循环依赖、领域层零外部依赖

### AC-5: Prometheus 指标扩展与聚合查询

**Given** 系统需要暴露 Token 消耗和成本指标
**When** MetricsPort.collect() 收集指标
**Then** 新增 Prometheus Counter：`sisys_token_prompt_total`、`sisys_token_completion_total`
**And** 新增 Prometheus Gauge：`sisys_cost_total_cny`（累计成本/元）、`sisys_cost_by_model_cny`（按模型分）
**And** 支持按模型标签（model、route_type）区分指标
**And** MetricsPort 扩展 `record_token_usage(prompt: int, completion: int, model: str, route_type: str)` 和 `record_cost(cost: float, model: str, route_type: str)` 方法
**And** 聚合查询支持按任务类型/Agent/时间范围查询成本（通过 RoutingDecisionLogRepository 扩展）

**验证标准/Validation Criteria:**
- [ ] MetricsPort 接口扩展 2 个方法
- [ ] MetricsPortImpl 实现 2 个新方法
- [ ] BusinessMetricsCollector 新增 4 个 Prometheus 指标
- [ ] RoutingDecisionLogRepository 扩展聚合查询方法
- [ ] 查询延迟 P95<100ms

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](../../../docs/developer/sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](../../../docs/developer/sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

**扩展已有事件（向后兼容）：**
- [ ] `RoutingDecided` 事件（`src/domain/events/routing_events.py`）— 新增 4 个字段（均有默认值）
  - `prompt_tokens: int = 0` — prompt token 消耗
  - `completion_tokens: int = 0` — completion token 消耗
  - `total_tokens: int = 0` — 总 token 消耗
  - `cost_actual: float = 0.0` — 实际成本（元）

#### 数据模型 (Data Models)

**新建值对象：**
- [ ] TokenConsumption 值对象（`src/domain/value_objects/token_consumption.py`）
  - 字段: prompt_tokens(int), completion_tokens(int), total_tokens(int)
  - 不变量: total_tokens == prompt_tokens + completion_tokens
  - frozen dataclass

**扩展已有模型（向后兼容）：**
- [ ] RoutingDecisionLog 实体（`src/domain/entities/routing_decision_log.py`）— 新增 3 个字段
  - `prompt_tokens: int = 0`
  - `completion_tokens: int = 0`
  - `total_tokens: int = 0`
  - validate() 新增非负校验

**新建领域服务：**
- [ ] CostCalculator 领域服务（`src/domain/services/cost_calculator.py`）
  - 方法: calculate(token_consumption: TokenConsumption, route_type: str, model: str) -> float
  - 注入原始值（不依赖配置对象）：local_input_price, local_output_price, cloud_input_price, cloud_output_price, model_pricing_map
  - 成本公式: `(prompt_tokens × input_price + completion_tokens × output_price) / 1000`
  - MVP 估算策略: 本地 256+512，云端 512+1024

**扩展已有配置（向后兼容）：**
- [ ] CloudModelConfig（`src/infrastructure/config/udmr.py`）— 新增 2 个字段
  - `price_per_input_1k_tokens: float = 0.02` — 输入 token 单价（元/1K tokens）
  - `price_per_output_1k_tokens: float = 0.02` — 输出 token 单价（元/1K tokens）
  - from_env() 解析 `UDMR_CLOUD_*_PRICE_INPUT` 和 `UDMR_CLOUD_*_PRICE_OUTPUT`

#### 统一端口定义注册与管理 (Port Contract)

**复用已有端口（扩展）：**
- [ ] `MetricsPort`（`src/application/ports/metrics_port.py`）— 扩展 2 个方法
  - 新方法: `record_token_usage(prompt: int, completion: int, model: str, route_type: str) -> None`
  - 新方法: `record_cost(cost: float, model: str, route_type: str) -> None`
  - 版本: 1.0 → 1.1, owner: infrastructure-team, 向后兼容
- [ ] `RoutingDecisionLogRepository`（`src/domain/ports/routing_decision_log_repository.py`）— 扩展聚合查询
  - 新方法: `async def query_cost_summary(start_time: datetime, end_time: datetime, route_type: str | None = None) -> CostSummary`
  - 版本: 1.0 → 1.1, owner: auto-invocation-team

**新建端口：**
- [ ] `TokenEstimatorPort`（`src/domain/ports/token_estimator.py`）— Token 估算策略抽象（MVP）
  - 方法: `async def estimate(route_type: str, model: str) -> TokenConsumption`
  - 版本: 1.0, owner: cost-team
  - 端口契约测试: `tests/contracts/test_port_contract_token_estimator.py`

**端口契约清单（强制）：**

| 端口名称 | 版本 | Owner | 注册 | 解析 | 契约测试 | 状态 |
|---------|------|-------|------|------|---------|------|
| MetricsPort | 1.1 | infrastructure-team | ✅ | ✅ | ✅ | **扩展** |
| RoutingDecisionLogRepository | 1.1 | auto-invocation-team | ✅ | ✅ | ✅ | **扩展** |
| TokenEstimatorPort | 1.0 | cost-team | 新建 | 新建 | 新建 | **新建** |

#### 六边形架构约束（必须遵守）

**四层架构定义**

| 层次 | 目录 | 本 Story 职责 |
|------|------|-------------|
| domain | `src/domain/` | TokenConsumption + CostCalculator + TokenEstimatorPort + RoutingDecided/Log 扩展 |
| application | `src/application/` | CostMetricsListener 事件处理器 + MetricsPort 扩展 |
| infrastructure | `src/infrastructure/` | CloudModelConfig 扩展 + StaticTokenEstimator + MetricsPortImpl 扩展 + BusinessMetricsCollector 扩展 |
| interfaces | `src/interfaces/` | 无新增（通过事件总线和 /metrics 端点集成） |

**依赖方向矩阵**

| 起点 \ 终点 | domain | application | infrastructure |
|------------|--------|-------------|----------------|
| **domain (CostCalculator)** | — | ✗ 禁止 | ✗ 禁止 |
| **application (CostMetricsListener)** | ✓ 允许 | — | ✗ 禁止 |
| **infrastructure (Config/Estimator/Metrics)** | ✓ 允许 | ✓ 允许 | — |

**领域层零依赖原则** — CostCalculator 仅依赖：
- Python 标准库（dataclasses, uuid, logging）
- 领域值对象（TokenConsumption）
- 领域端口（TokenEstimatorPort）

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 功能测试文件：`tests/acceptance/test_acceptance_cost_metrics_basic.feature`
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_cost_metrics_basic.py`
- [ ] 覆盖场景:
  - 本地路由成本计算（本地模型定价 × Token 估算）
  - 云端路由成本计算（云端模型定价 × Token 估算）
  - 按时间范围聚合查询成本
  - Prometheus 指标记录
  - 成本计算准确率验证

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
| **TDD 单元测试** | TokenConsumption | 值对象不变量 | `test_token_consumption.py` | Task 1 |
| **TDD 单元测试** | CostCalculator | 成本计算 | `test_cost_calculator.py` | Task 2 |
| **TDD 单元测试** | CloudModelConfig 扩展 | 定价配置解析 | `test_udmr_config.py`（扩展） | Task 2 |
| **TDD 单元测试** | StaticTokenEstimator | Token 估算 | `test_static_token_estimator.py` | Task 3 |
| **TDD 单元测试** | CostMetricsListener | 事件处理器 | `test_cost_metrics_handler.py` | Task 4 |
| **TDD 单元测试** | MetricsPort 扩展 | Prometheus 指标 | `test_metrics_port_cost.py` | Task 3 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_acceptance_cost_metrics_basic.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现 | `test_acceptance_cost_metrics_basic.py` | Task 0 |
| **TDD 契约测试** | TokenEstimatorPort | 端口契约 | `test_port_contract_token_estimator.py` | Task 0 |
| **SDD 架构验证** | 成本度量六边形架构 | 依赖方向、零依赖 | `test_arch_cost_metrics.py` | Task 5 |
| **集成测试** | 成本度量管线 | 端到端成本追踪 | `test_integration_cost_metrics_basic.py` | Task 5 |

---

### 测试要求与质量门禁

#### 覆盖率要求

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**
- [ ] **架构层覆盖率 ≥85%**（`pytest --cov=src/domain/services/cost_calculator.py`）
- [ ] **基础设施层覆盖率 ≥75%**（`pytest --cov=src/infrastructure/config/udmr.py`）
- [ ] **集成测试覆盖率 ≥70%**

#### 代码质量门禁
- [ ] **Ruff 检查通过**（`ruff check src/`）
- [ ] **MyPy 类型检查通过**（`mypy src/`）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **外部服务隔离** | Prometheus 使用 mock 或内存 registry | 真实 Prometheus 依赖导致失败 |
| **配置隔离** | 每个测试使用独立的 CloudModelConfig 实例 | 配置污染 |
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
| AC-1 | CloudModelConfig 扩展定价字段 | Task 2 | Subtask 2.1-2.3 | `test_udmr_config.py` |
| AC-2 | TokenConsumption + CostCalculator | Task 1-2 | Subtask 1.1-1.3, 2.1-2.3 | `test_token_consumption.py`, `test_cost_calculator.py` |
| AC-3 | RoutingDecided/Log 扩展 | Task 1 | Subtask 1.4-1.6 | 扩展现有测试 |
| AC-4 | CostMetricsListener + DI 注册 | Task 4 | Subtask 4.1-4.3 | `test_cost_metrics_handler.py` |
| AC-5 | Prometheus 指标 + 聚合查询 | Task 3 | Subtask 3.1-3.6 | `test_metrics_port_cost.py` |
| AC-5 | 聚合查询 | Task 3 | Subtask 3.4-3.6 | 扩展 repository 测试 |
| AC-1~5 | 架构验证 + 集成测试 | Task 5 | Subtask 5.1-5.5 | `test_arch_cost_metrics.py` + `test_integration_cost_metrics_basic.py` |

---

## 📋 Tasks / Subtasks 任务分解

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5

> **目的：** 在进入代码实现前，明确 Schema、端口契约、验收标准与六边形架构边界。

- [ ] Subtask 0.1: 定义 TokenEstimatorPort 端口（`src/domain/ports/token_estimator.py`）
- [ ] Subtask 0.2: 定义端口契约测试（`tests/contracts/test_port_contract_token_estimator.py`）
- [ ] Subtask 0.3: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_cost_metrics_basic.feature`
- [ ] Subtask 0.4: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_cost_metrics_basic.py`
- [ ] Subtask 0.5: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 端口契约测试通过（验证 Protocol 结构）
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: Token 消耗值对象 + RoutingDecided/Log 扩展

**关联 AC:** AC-2, AC-3

#### TDD 循环 [A]：TokenConsumption 值对象

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/value_objects/test_token_consumption.py`（不变量验证） |
| 🟢 绿 | 实现 `src/domain/value_objects/token_consumption.py`（TokenConsumption frozen dataclass） |
| 🔄 重构 | 优化不变量校验，运行 `ruff` + `mypy` |

- [ ] Subtask 1.1: 🔴 红 — 编写 TokenConsumption 失败测试
  - total_tokens 必须等于 prompt_tokens + completion_tokens（不变量）
  - 所有字段非负
  - frozen 验证
- [ ] Subtask 1.2: 🟢 绿 — 实现 TokenConsumption frozen dataclass
- [ ] Subtask 1.3: 🔄 重构 — 优化不变量校验

#### TDD 循环 [B]：RoutingDecided/Log 扩展

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/domain/events/test_routing_events.py` 和 `tests/unit/domain/entities/test_routing_decision_log.py` |
| 🟢 绿 | 扩展 `src/domain/events/routing_events.py` 和 `src/domain/entities/routing_decision_log.py` |
| 🔄 重构 | 确保向后兼容，运行 `ruff` + `mypy` |

- [ ] Subtask 1.4: 🔴 红 — 编写 RoutingDecided 扩展字段测试
  - 新增 prompt_tokens/completion_tokens/total_tokens/cost_actual 字段
  - 默认值为 0/0.0（向后兼容）
- [ ] Subtask 1.5: 🔴 红 — 编写 RoutingDecisionLog 扩展字段测试
  - 新增 prompt_tokens/completion_tokens/total_tokens 字段
  - validate() 新增非负校验
- [ ] Subtask 1.6: 🟢 绿 — 扩展事件和实体字段
- [ ] Subtask 1.7: 🔄 重构 — 确保向后兼容

**完成标准/Definition of Done:**
- [ ] TokenConsumption frozen dataclass 实现完成
- [ ] RoutingDecided 新增 4 个字段（向后兼容）
- [ ] RoutingDecisionLog 新增 3 个字段（向后兼容）
- [ ] 已有测试不受影响
- [ ] TDD 循环全部通过

---

### Task 2: CostCalculator + CloudModelConfig 定价扩展

**关联 AC:** AC-1, AC-2

#### TDD 循环 [A]：CostCalculator 成本计算

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/services/test_cost_calculator.py`（成本计算验证） |
| 🟢 绿 | 实现 `src/domain/services/cost_calculator.py`（CostCalculator 领域服务） |
| 🔄 重构 | 优化计算逻辑，运行 `ruff` + `mypy` |

- [ ] Subtask 2.1: 🔴 红 — 编写 CostCalculator 失败测试
  - 本地路由成本：256 prompt × ¥0.002/1K + 512 completion × ¥0.002/1K = ¥0.001536
  - 云端路由成本：512 prompt × ¥0.02/1K + 1024 completion × ¥0.02/1K = ¥0.03072
  - 零 token 输入 → 成本为 0.0
  - 未匹配模型 → 使用默认定价
- [ ] Subtask 2.2: 🟢 绿 — 实现 CostCalculator
  - 构造器注入原始值：local_input_price, local_output_price, cloud_input_price, cloud_output_price, model_pricing_map
  - calculate(token_consumption, route_type, model) -> float
  - 成本公式: `(prompt × input_price + completion × output_price) / 1000`
- [ ] Subtask 2.3: 🔄 重构 — 优化计算逻辑

#### TDD 循环 [B]：CloudModelConfig 定价字段扩展

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/infrastructure/config/test_udmr_config.py`（定价解析） |
| 🟢 绿 | 扩展 `src/infrastructure/config/udmr.py`（CloudModelConfig 新增字段） |
| 🔄 重构 | 确保 from_env() 向后兼容 |

- [ ] Subtask 2.4: 🔴 红 — 编写 CloudModelConfig 定价解析失败测试
  - 解析 `UDMR_CLOUD_0_PRICE_INPUT` 和 `UDMR_CLOUD_0_PRICE_OUTPUT`
  - 默认值 ¥0.02/1K
  - 非负校验
- [ ] Subtask 2.5: 🟢 绿 — 扩展 CloudModelConfig
- [ ] Subtask 2.6: 🔄 重构 — 确保 from_env() 向后兼容

**完成标准/Definition of Done:**
- [ ] CostCalculator 实现完成
- [ ] CloudModelConfig 扩展 2 个定价字段（向后兼容）
- [ ] 成本计算准确率 100%
- [ ] TDD 循环全部通过

---

### Task 3: StaticTokenEstimator + Prometheus 指标扩展

**关联 AC:** AC-5

#### TDD 循环 [A]：StaticTokenEstimator

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/monitoring/test_static_token_estimator.py` |
| 🟢 绿 | 实现 `src/infrastructure/monitoring/static_token_estimator.py` |
| 🔄 重构 | 优化估算逻辑 |

- [ ] Subtask 3.1: 🔴 红 — 编写 StaticTokenEstimator 失败测试
  - 本地模型估算: prompt=256, completion=512
  - 云端模型估算: prompt=512, completion=1024
  - 实现 TokenEstimatorPort（check + close 可选）
- [ ] Subtask 3.2: 🟢 绿 — 实现 StaticTokenEstimator
- [ ] Subtask 3.3: 🔄 重构 — 优化估算逻辑

#### TDD 循环 [B]：MetricsPort 扩展 + Prometheus 指标

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/monitoring/test_metrics_port_cost.py`（成本指标） |
| 🟢 绿 | 扩展 `src/application/ports/metrics_port.py` + `src/infrastructure/monitoring/metrics_port_impl.py` + `src/infrastructure/monitoring/business_metrics.py` |
| 🔄 重构 | 优化指标收集 |

- [ ] Subtask 3.4: 🔴 红 — 编写 MetricsPort 扩展失败测试
  - record_token_usage(prompt, completion, model, route_type)
  - record_cost(cost, model, route_type)
  - Prometheus Counter: sisys_token_prompt_total, sisys_token_completion_total（按 model/route_type 标签）
  - Prometheus Gauge: sisys_cost_total_cny, sisys_cost_by_model_cny（按 model 标签）
- [ ] Subtask 3.5: 🟢 绿 — 扩展 MetricsPort 接口和实现
- [ ] Subtask 3.6: 🔄 重构 — 优化指标收集

#### TDD 循环 [C]：RoutingDecisionLogRepository 聚合查询扩展

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `tests/unit/domain/ports/test_routing_decision_log_repository.py`（聚合查询） |
| 🟢 绿 | 扩展 `src/domain/ports/routing_decision_log_repository.py` + `src/infrastructure/messaging/inmemory_routing_decision_log_repository.py` |
| 🔄 重构 | 优化聚合逻辑 |

- [ ] Subtask 3.7: 🔴 红 — 编写聚合查询失败测试
  - query_cost_summary(start_time, end_time, route_type=None) -> CostSummary
  - CostSummary 包含: total_cost, total_prompt_tokens, total_completion_tokens, record_count
- [ ] Subtask 3.8: 🟢 绿 — 扩展 Repository 端口和实现
- [ ] Subtask 3.9: 🔄 重构 — 优化聚合逻辑

**完成标准/Definition of Done:**
- [ ] StaticTokenEstimator 实现 TokenEstimatorPort
- [ ] MetricsPort 扩展 2 个新方法
- [ ] 4 个新 Prometheus 指标注册
- [ ] RoutingDecisionLogRepository 扩展聚合查询
- [ ] TDD 循环全部通过

---

### Task 4: CostMetricsListener + DI 注册

**关联 AC:** AC-4

#### TDD 循环 [A]：CostMetricsListener 事件处理器

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/application/event_handlers/test_cost_metrics_handler.py` |
| 🟢 绿 | 实现 `src/application/event_handlers/cost_metrics_handler.py` |
| 🔄 重构 | 优化事件处理逻辑 |

- [ ] Subtask 4.1: 🔴 红 — 编写 CostMetricsListener 失败测试
  - on_routing_decided() 接收 RoutingDecided → 调用 TokenEstimatorPort.estimate() → 构造 TokenConsumption → 调用 CostCalculator.calculate() → 更新 RoutingDecisionLog → 记录 Prometheus 指标
  - prompt_tokens/completion_tokens/total_tokens 为 0 时（MVP，从估算获取）
  - cost_actual 从 0.0 改为实际度量值
- [ ] Subtask 4.2: 🟢 绿 — 实现 CostMetricsListener
  - 订阅 RoutingDecided 事件（通过 DualChannelEventBus.subscribe_async()）
  - 事件处理流：估算 Token → 计算成本 → 更新日志 → 记录指标
  - **注意:** MVP 阶段 Token 数据来自估算而非实际 LLM 调用
- [ ] Subtask 4.3: 🔄 重构 — 优化处理器逻辑

#### DI 注册

- [ ] Subtask 4.4: 更新 `src/composition_root.py` 注册（遵循 lambda resolver: 内联 config 模式）
  - `token_estimator` → `lambda resolver:` StaticTokenEstimator()
  - `cost_calculator` → `lambda resolver:` CostCalculator(
    local_input_price=..., local_output_price=..., cloud_input_price=..., cloud_output_price=...,
    model_pricing_map=...（从 CloudModelConfig 提取）)
  - `cost_metrics_handler` → `lambda resolver:` CostMetricsListener(
    token_estimator=resolver.resolve("token_estimator"),
    cost_calculator=resolver.resolve("cost_calculator"),
    log_repo=resolver.resolve("routing_decision_log_repository"),
    metrics=resolver.resolve("metrics"),
    event_bus=resolver.resolve("event_publisher"))
  - **注意:** CostCalculator 注入原始值（从 UDMRConfig.from_env() 提取定价），不依赖 Config 对象
  - **注意:** Resolver._instantiate() 调用 `spec.impl(resolver=self)`，lambda 必须接收 resolver 参数

**完成标准/Definition of Done:**
- [ ] CostMetricsListener 实现完成
- [ ] composition_root.py 注册新组件
- [ ] TDD 循环全部通过

---

### Task 5: SDD 架构约束验证 + 集成测试

**关联 AC:** AC-4, AC-5

> **性质说明：** 本 Task 是 SDD 规范验证测试，验证代码是否符合六边形架构规则。

#### 架构验证测试实现

- [ ] Subtask 5.1: 创建 `tests/unit/architecture/test_arch_cost_metrics.py`
- [ ] Subtask 5.2: 验证 CostCalculator 仅依赖领域层（无外部依赖）
- [ ] Subtask 5.3: 验证 CostMetricsListener 位于应用层（不直接调用基础设施层）
- [ ] Subtask 5.4: 验证 StaticTokenEstimator 实现端口（依赖倒置）
- [ ] Subtask 5.5: 创建 `tests/integration/test_integration_cost_metrics_basic.py`
  - 端到端：RoutingDecided → CostMetricsListener → CostCalculator → Prometheus 指标

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
- **成本优化指标:** 本地模型路由占比≥60%(MVP)→≥80%(V1)→≥85%(V2)；Token 成本节省≥30%(MVP)→≥50%(V1)→≥60%(V2)
- **设计约束:**
  - 领域层零依赖外部框架
  - 依赖倒置：领域层定义 TokenEstimatorPort，基础设施层实现
  - 事件总线双通道：RoutingDecided 已注册 REALTIME 通道（sisys:rt:routing_decided）
- **技术栈:** Python 3.11+, prometheus_client（已集成）

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) - ADR-005 (UDMR 统一动态模型路由), FR-CP-01/03

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **估算定价 + Prometheus 指标** | MVP 够用、复用 RoutingDecided 事件、低成本实现 | 非实际 Token 数据 | ✅ 8/10 |
| 实际 Token 追踪 | 最准确 | 需修改 AutoExecuteService、LLM API 集成未就绪 | 5/10 |
| 仅 Prometheus 计数器 | 最简单 | 无持久化、无聚合查询、不满足审计需求 | 3/10 |

### 成本度量数据流

> **⚠️ MVP 限制：** MVP 阶段 Token 消耗使用估算值（本地 256+512，云端 512+1024），而非实际 LLM API 响应的 usage 数据。
> 后续 Story 将在 LLM API 集成完成后，替换估算为实际 Token 消耗数据。

```
RoutingDecided (1.17)
    ↓ cost_metrics_handler 订阅（REALTIME 通道 sisys:rt:routing_decided）
    ├── TokenEstimatorPort.estimate(route_type, model) → TokenConsumption
    ├── CostCalculator.calculate(consumption, route_type, model) → cost_actual (float)
    ├── RoutingDecisionLogRepository.update_cost(log_id, cost_actual, tokens)
    └── MetricsPort.record_token_usage() + record_cost() → Prometheus
```

### 成本计算模型

**定价表（MVP 默认值）：**

| 模型类型 | input_price (¥/1K tokens) | output_price (¥/1K tokens) | Token 估算 |
|---------|--------------------------|---------------------------|-----------|
| **本地模型** (qwen2.5:7b) | ¥0.002 | ¥0.002 | prompt=256, completion=512 |
| **云端模型** (MiniMax/DeepSeek/GLM) | ¥0.02 | ¥0.02 | prompt=512, completion=1024 |

**成本公式：**
```python
cost_actual = (prompt_tokens × input_price + completion_tokens × output_price) / 1000
```

**示例：**
- 本地: (256 × 0.002 + 512 × 0.002) / 1000 = ¥0.001536
- 云端: (512 × 0.02 + 1024 × 0.02) / 1000 = ¥0.03072

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── domain/
│   │   ├── value_objects/
│   │   │   └── token_consumption.py          # 新建：Token 消耗值对象
│   │   ├── services/
│   │   │   └── cost_calculator.py             # 新建：成本计算领域服务
│   │   ├── ports/
│   │   │   └── token_estimator.py             # 新建：Token 估算端口
│   │   ├── events/
│   │   │   └── routing_events.py              # 扩展：+4 字段
│   │   └── entities/
│   │       └── routing_decision_log.py        # 扩展：+3 字段
│   ├── application/
│   │   ├── event_handlers/
│   │   │   └── cost_metrics_handler.py        # 新建：成本事件处理器
│   │   └── ports/
│   │       └── metrics_port.py                # 扩展：+2 方法
│   ├── infrastructure/
│   │   ├── config/
│   │   │   └── udmr.py                        # 扩展：CloudModelConfig +2 字段
│   │   ├── monitoring/
│   │   │   ├── static_token_estimator.py      # 新建：静态 Token 估算器
│   │   │   ├── business_metrics.py            # 扩展：+4 Prometheus 指标
│   │   │   └── metrics_port_impl.py           # 扩展：+2 方法实现
│   │   └── messaging/
│   │       └── inmemory_routing_decision_log_repository.py  # 扩展：+聚合查询
│   └── composition_root.py                    # 更新：+4 个注册
├── tests/
│   ├── unit/
│   │   ├── domain/value_objects/test_token_consumption.py
│   │   ├── domain/services/test_cost_calculator.py
│   │   ├── infrastructure/monitoring/test_static_token_estimator.py
│   │   ├── infrastructure/monitoring/test_metrics_port_cost.py
│   │   ├── infrastructure/config/test_udmr_config.py         # 扩展
│   │   ├── application/event_handlers/test_cost_metrics_handler.py
│   │   └── architecture/test_arch_cost_metrics.py
│   ├── contracts/
│   │   └── test_port_contract_token_estimator.py
│   ├── integration/
│   │   └── test_integration_cost_metrics_basic.py
│   └── acceptance/
│       ├── test_acceptance_cost_metrics_basic.feature
│       └── test_acceptance_cost_metrics_basic.py
```

### 已有可复用组件（无需新建）

| 组件 | 文件路径 | 说明 |
|------|---------|------|
| RoutingDecided | `src/domain/events/routing_events.py` | 路由决策事件（需扩展 4 字段） |
| RoutingDecisionLog | `src/domain/entities/routing_decision_log.py` | 日志实体（需扩展 3 字段，cost_actual 已预留） |
| RoutingDecisionLogRepository | `src/domain/ports/routing_decision_log_repository.py` | 日志持久化端口（需扩展聚合查询） |
| InMemoryRoutingDecisionLogRepository | `src/infrastructure/messaging/inmemory_routing_decision_log_repository.py` | 内存实现 |
| MetricsPort | `src/application/ports/metrics_port.py` | 指标采集端口（需扩展 2 方法） |
| MetricsPortImpl | `src/infrastructure/monitoring/metrics_port_impl.py` | 指标实现（需扩展） |
| BusinessMetricsCollector | `src/infrastructure/monitoring/business_metrics.py` | Prometheus Gauge（需扩展 4 指标） |
| MetricsAggregator | `src/infrastructure/monitoring/aggregator.py` | 指标聚合器（可复用） |
| UDMRConfig / CloudModelConfig | `src/infrastructure/config/udmr.py` | 配置（需扩展 2 字段） |
| UDMRService | `src/domain/services/udmr_service.py` | 决策服务（_persist_decision_log 需传递 token） |
| DualChannelEventBus | `src/infrastructure/messaging/dual_channel_event_bus.py` | 事件总线（subscribe_async 复用） |
| ChannelRouter | `src/infrastructure/messaging/channel_router.py` | 频道路由（sisys:rt:routing_decided 已注册） |

### 环境变量扩展

```bash
# 云端模型定价（新增，可选）
export UDMR_CLOUD_0_PRICE_INPUT=0.02      # 输入 token 单价（元/1K tokens），默认 ¥0.02
export UDMR_CLOUD_0_PRICE_OUTPUT=0.02     # 输出 token 单价（元/1K tokens），默认 ¥0.02
export UDMR_CLOUD_1_PRICE_INPUT=0.02
export UDMR_CLOUD_1_PRICE_OUTPUT=0.02
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 1.17: UDMR 基础路由](./1-17-udmr-basic-routing.md)

**关键学习/Key Learnings:**
1. **frozen dataclass 配置约束** — UDMRConfig/CloudModelConfig 均为 frozen=True，扩展字段需有默认值
2. **向后兼容扩展** — RoutingDecided/Log 扩展字段必须有默认值（0/0.0），否则破坏事件反序列化
3. **构造器注入原始值** — CostCalculator 不依赖 CloudModelConfig 对象，注入原始浮点值（参考 UDMRService 模式）
4. **lambda resolver: DI 注册格式** — Resolver._instantiate() 调用 spec.impl(resolver=self)，所有 lambda 必须为 `lambda resolver:` 格式
5. **事件订阅统一方案** — 使用 DualChannelEventBus.subscribe_async()（非 subscribe()），InMemoryEventBus 仅用于测试 mock
6. **MVP 限制明确标注** — cost_actual 硬编码为 0.0 的审查记录（[Review][Defer]），本 Story 是其后续实现
7. **Prometheus 注册线程安全** — BusinessMetricsCollector 使用 threading.Lock 保证线程安全
8. **fire-and-forget 异步持久化** — UDMRService._persist_decision_log() 使用 create_task 异步保存

**应用到本故事/Applied to This Story:**
- [ ] CloudModelConfig 扩展字段为 frozen + 默认值
- [ ] RoutingDecided/Log 扩展字段均有默认值 0
- [ ] CostCalculator 注入原始浮点值（不依赖 Config 对象）
- [ ] 所有 lambda 使用 `lambda resolver:` 格式
- [ ] CostMetricsListener 使用 subscribe_async()
- [ ] 异步持久化使用 create_task 模式

### Git Intelligence Summary

**来源:** `git log` - 最近 UDMR 相关提交

| 提交 | 主题 | 关键模式 |
|------|------|---------|
| `1a1fd18d` | fix: resolve code review findings for Story 1.17 | health_check_latency_ms 测量、TTL 缓存、causation_id |
| `3626c613` | feat: implement Story 1.17 UDMR basic routing | 全流程实现 + Redis BUG 修复 |
| `f7433491` | fix(story-1.17): add missing cost_actual field | SDD Schema 补充 cost_actual |
| `bd42c02d` | fix(story-1.17): 修复第4轮审查问题 | 路由决策模型字段补充 |

**可应用模式:**
1. **frozen dataclass 配置** — CloudModelConfig 扩展遵循 frozen + 默认值
2. **Protocol 端口注册** — TokenEstimatorPort 新建注册
3. **事件处理器模式** — CostMetricsListener 遵循 UDMRHandler 的 on_routed → service 调用模式

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (create-story workflow) |
| **Version** | create-story workflow v1.0 |
| **Execution Date** | 2026-05-23 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|-----|
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/1-17-udmr-basic-routing.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取
- [x] 架构约束从 `architecture.md` §4 UDMR + §1.4 KPI + §10 事件驱动 提取
- [x] 前一个故事学习经验整合（Story 1.17 UDMR 基础路由）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范
- [x] 已有可复用组件清单明确
- [x] 成本计算模型与定价表设计完成
- [x] Metrics 现有基础设施（MetricsPort/BusinessMetricsCollector/Prometheus）分析完成
- [x] DI 注册模式（lambda resolver: 内联配置）对齐
- [x] FR-CP-01/03 覆盖关系明确

### 文件清单 File List

**待创建的文件/To Be Created:**
- `src/domain/value_objects/token_consumption.py` — Token 消耗值对象
- `src/domain/services/cost_calculator.py` — 成本计算领域服务
- `src/domain/ports/token_estimator.py` — Token 估算端口
- `src/application/event_handlers/cost_metrics_handler.py` — 成本事件处理器
- `src/infrastructure/monitoring/static_token_estimator.py` — 静态 Token 估算器
- `tests/unit/domain/value_objects/test_token_consumption.py` — 值对象测试
- `tests/unit/domain/services/test_cost_calculator.py` — 成本计算测试
- `tests/unit/infrastructure/monitoring/test_static_token_estimator.py` — 估算器测试
- `tests/unit/infrastructure/monitoring/test_metrics_port_cost.py` — 指标扩展测试
- `tests/unit/application/event_handlers/test_cost_metrics_handler.py` — 处理器测试
- `tests/unit/architecture/test_arch_cost_metrics.py` — 架构约束测试
- `tests/contracts/test_port_contract_token_estimator.py` — 端口契约测试
- `tests/integration/test_integration_cost_metrics_basic.py` — 集成测试
- `tests/acceptance/test_acceptance_cost_metrics_basic.feature` — Gherkin 验收测试
- `tests/acceptance/test_acceptance_cost_metrics_basic.py` — BDD 步骤实现

**待扩展的文件/To Be Extended:**
- `src/domain/events/routing_events.py` — +4 字段
- `src/domain/entities/routing_decision_log.py` — +3 字段 + validate()
- `src/infrastructure/config/udmr.py` — CloudModelConfig +2 字段 + from_env()
- `src/application/ports/metrics_port.py` — +2 方法
- `src/infrastructure/monitoring/metrics_port_impl.py` — +2 方法实现
- `src/infrastructure/monitoring/business_metrics.py` — +4 Prometheus 指标
- `src/domain/ports/routing_decision_log_repository.py` — +聚合查询方法
- `src/infrastructure/messaging/inmemory_routing_decision_log_repository.py` — +聚合查询实现
- `src/composition_root.py` — +4 个 DI 注册
- `src/domain/services/udmr_service.py` — _persist_decision_log 传递 token 字段

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 1.19 |
| **Story Key** | 1-19-cost-metrics-basic |
| **File** | `_bmad-output/implementation-artifacts/stories/1-19-cost-metrics-basic.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 1: 企业级架构基础与合规 |
| **价值组** | 价值组 6: MVP 关键机制增强 |
| **优先级** | P0-19（MVP，CFO ROI 验证） |
| **覆盖 FR** | FR-CP-01（路由决策日志含成本）、FR-CP-03（健康度仪表盘 Token 消耗趋势） |

### 完成总结 Completion Summary

1. [ ] All tasks defined 所有任务定义完成
2. [x] All acceptance criteria specified 所有验收标准已定义
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合
5. [ ] Sprint status synced to `ready-for-dev`

### 下一步 Next Steps

- [ ] Story created with `ready-for-dev` status
- [ ] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查
- [ ] 运行 `/bmad:tea:automate` 生成测试（可选）

---

**故事版本/Story Version:** v1.0.0
**创建日期/Created:** 2026-05-23
**最后更新/Last Updated:** 2026-05-23
**更新说明/Description:**
- v1.0.0: 创建故事文件（基于 Story 1.17 UDMR 基础路由学习经验 + 4 个并行 Agent 全量调研）
