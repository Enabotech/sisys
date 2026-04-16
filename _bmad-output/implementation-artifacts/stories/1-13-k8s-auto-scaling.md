# Story 1.13: K8s 动态扩缩容

**Status:** `ready-for-dev`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行 `validate-create-story` 进行质量检查后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 运维工程师,
**I want** 系统暴露 Prometheus `/metrics` HTTP 端点，支持基于负载的自动扩缩容，
**So that** K8s HPA 可以根据应用自定义指标实现动态扩缩容，响应时间<5 分钟。

### 业务价值

本 Story 是 Epic 1（企业级架构基础与合规）价值组 3（五层存储架构）的最后一个故事，在 Story 1.4/1.5（Redis/PostgreSQL 层）完成后实现 K8s 动态扩缩容能力。核心价值：

| 职责 | 业务价值 | 验收标准 |
|------|---------|---------|
| **Prometheus `/metrics` 端点** | 应用指标暴露给 Prometheus 采集 | 端点响应<100ms，兼容 Prometheus 格式 |
| **自定义指标暴露** | 支持 HPA 基于业务指标扩缩容 | 暴露 Agent 会话数、任务队列长度等 |
| **扩缩容响应时间** | 流量高峰时快速扩容 | 响应时间<5 分钟（K8s HPA 指标采集+决策+执行） |
| **HPA 资源指标** | 补充 CPU/内存利用率监控 | 指标与 K8s metrics-server 协同 |

**来源:** [`epics_v1.0.md`](../../_bmad-output/planning-artifacts/epics_v1.0.md) - Epic 1: 企业级架构基础与合规，价值组 3: 五层存储架构，Story 1.13

**NFR 追溯:** NFR-SCALE-03（Agent 动态扩缩容，基于负载自动伸缩，响应时间<5 分钟）

**前置依赖:** Story 1.4（Redis 缓存层）、Story 1.5（PostgreSQL 关系层）

---

## ✅ Acceptance Criteria 验收标准

### AC-1: Prometheus `/metrics` HTTP 端点

**Given** EventMetricsCollector 已实现（Story 1.3），BusinessMetricsCollector 将实现
**When** 访问 `/metrics` 端点
**Then** 返回 Prometheus 文本格式指标
**And** 聚合 EventMetricsCollector（事件处理计数、处理耗时）+ BusinessMetricsCollector（Agent 会话数、队列长度）指标

> **📌 架构说明:** EventMetricsCollector（Story 1.3）是**纯内存计数器**，不暴露 HTTP 端点。本 Story 负责：
> 1. 实现 `/metrics` HTTP 端点（FastAPI 路由）
> 2. 实现 BusinessMetricsCollector（新组件）
> 3. 通过 MetricsAggregator 聚合两个收集器的指标统一暴露

**验证标准/Validation Criteria:**
- [ ] FastAPI 路由 `/metrics` 定义（`src/interfaces/api/monitoring.py`）
- [ ] MetricsAggregator 聚合 EventMetricsCollector + BusinessMetricsCollector
- [ ] Prometheus 文本格式输出（`# HELP` / `# TYPE` / 指标值）
- [ ] 指标类型支持：Counter、 Gauge、Histogram、Summary
- [ ] 端点响应时间 P95<100ms
- [ ] 多进程模式支持（使用 `generate_latest()` 而非 HTTP 服务器）
- [ ] 单元测试覆盖端点响应格式、指标内容

### AC-2: 自定义业务指标暴露

**Given** Prometheus 端点已实现
**When** HPA 需要扩缩容决策
**Then** 暴露以下自定义业务指标供 Prometheus 采集：
- `sisys_agent_sessions_active`：当前活跃 Agent 会话数（**Gauge**）
- `sisys_task_queue_length`：任务队列长度（**Gauge**）
- `sisys_events_processing_rate`：事件处理速率（**Gauge**，每秒处理事件数）
- `sisys_cache_hit_rate`：缓存命中率（**Gauge**，0.0-1.0）

**指标类型说明:**
- **Gauge**: 用于瞬时值（会话数、队列长度、命中率）
- **events_processing_rate**: 每秒事件处理数，通过定时采样 `events_processed_total` 增量计算得出

**验证标准/Validation Criteria:**
- [ ] AgentSessionGauge 指标定义（活跃会话数，类型 Gauge）
- [ ] TaskQueueGauge 指标定义（队列长度，类型 Gauge）
- [ ] EventProcessingRateGauge 指标定义（处理速率，类型 Gauge）
- [ ] CacheHitRateGauge 指标定义（缓存命中率，类型 Gauge）
- [ ] 指标更新机制（定时更新，支持配置间隔）
- [ ] 单元测试覆盖指标注册、更新、输出

### AC-3: K8s HPA 集成

**Given** Prometheus 端点暴露自定义业务指标
**When** K8s HPA 基于自定义指标配置
**Then** 支持基于业务指标的扩缩容决策

> **📌 架构说明:** K8s HPA **不能直接使用 Prometheus 自定义指标**，需要 Prometheus Adapter（如 `prometheus-adapter`）将 Prometheus 指标转换为 K8s External Metrics API。本 Story 提供：
> 1. Prometheus 抓取配置（ServiceMonitor/PodMonitor + Prometheus Annotation）
> 2. HPA 自定义指标配置（基于 CPU/内存）
> 3. **不包含** Prometheus Adapter 部署（属于 K8s 基础设施，由 Story 0.4 或运维团队负责）

**验证标准/Validation Criteria:**
- [ ] K8s ServiceMonitor 配置示例（`deploy/kubernetes/apps/sisys/base/prometheus-servicemonitor.yaml`）
- [ ] Prometheus 抓取注解（`prometheus.io/scrape`，`prometheus.io/port`，`prometheus.io/path`）
- [ ] HPA 资源指标配置（CPU/内存，基于 `deploy/kubernetes/apps/sisys/base/hpa.yaml` 已有）
- [ ] Prometheus Adapter 部署说明（README 或部署注释）
- [ ] 扩缩容阈值配置化（通过 ConfigMap 环境变量注入）
- [ ] 集成测试覆盖 HPA 扩缩容场景（Mock K8s API）

### AC-4: 扩缩容性能要求

**Given** K8s HPA 已配置
**When** 系统负载变化触发扩缩容
**Then** 扩缩容完成时间<5 分钟（端到端总时间）

> **📌 性能分解:**
> - 指标采集: ≤15 秒（Prometheus scrape_interval）
> - HPA 决策: <60 秒（K8s HPA 默认同步检查周期）
> - Pod 启动: <180 秒（ ReadinessProbe initialDelaySeconds=30 + 启动时间）
> - **总计**: ≤255 秒（约 4.25 分钟），留有 45 秒余量

**验证标准/Validation Criteria:**
- [ ] Prometheus 指标采集间隔≤15 秒（配置 `scrape_interval`）
- [ ] HPA 检查周期≤60 秒（默认 15 秒，可配置）
- [ ] Pod 启动时间<180 秒（基于 ReadinessProbe 配置）
- [ ] 扩容准确率 100%（新 Pod 进入 Ready 状态）
- [ ] 缩容准确率 100%（缩容不中断正在处理的任务）
- [ ] 端到端扩缩容时间验证（总时间<5 分钟）

### AC-5: 指标可观测性

**Given** 所有指标已暴露
**When** 监控面板需要展示系统状态
**Then** Grafana 可视化面板展示关键指标

**验证标准/Validation Criteria:**
- [ ] Grafana Dashboard JSON 配置（`deploy/kubernetes/apps/sisys/base/grafana-dashboard.json`）
- [ ] 展示面板：Agent 会话数、任务队列长度、事件处理速率、缓存命中率
- [ ] 扩缩容事件时间线面板
- [ ] 单元测试覆盖指标正确性

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。
> 参考 [`sdd-tdd-fusion-guide.md`](./sdd-tdd-fusion-guide.md) 和 [`sdd-tdd-checklist.md`](./sdd-tdd-checklist.md)。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 数据模型 (Data Models)
- [ ] MetricsConfig 配置模型（`src/infrastructure/config/metrics.py`）
  - 字段: `enabled: bool`, `path: str`
  - **复用 Story 1.3 OtelConfig 模式**: `from_env()` 类方法
- [ ] BusinessMetricsCollector 指标收集器（`src/infrastructure/monitoring/business_metrics.py`）
  - **独立组件**: 不是 EventMetricsCollector 的扩展
  - 指标: AgentSessionGauge, TaskQueueGauge, EventProcessingRateGauge, CacheHitRateGauge
  - 方法: `record_sessions(n)`, `record_queue_length(n)`, `update_processing_rate()`, `record_cache_hit()`, `record_cache_miss()`
- [ ] MetricsAggregator 聚合器（`src/infrastructure/monitoring/aggregator.py`）
  - **聚合职责**: 统一收集 EventMetricsCollector + BusinessMetricsCollector 指标
  - 方法: `collect() -> Dict[str, MetricFamily]`
  - **复用 Story 1.3 EventMetricsCollector**: 通过注入获取，不修改原组件

#### 领域事件 Schema (Domain Events)
> **📌 架构说明:** 本 Story 不定义新领域事件，复用 Story 1.2/1.3 已定义的领域事件

#### 配置模型 (Configuration Models)
- [ ] MetricsConfig 定义（`src/infrastructure/config/metrics.py`）
  - 环境变量: `METRICS_ENABLED`, `METRICS_PORT`, `METRICS_PATH`, `METRICS_AUTH_ENABLED`
  - 从环境变量读取（`from_env()` 方法）

#### K8s 资源配置
- [ ] ServiceMonitor 配置（`deploy/kubernetes/apps/sisys/base/prometheus-servicemonitor.yaml`）
- [ ] Prometheus Adapter 配置说明（`deploy/kubernetes/apps/sisys/base/README.md`）
  - 说明 K8s HPA 需要 prometheus-adapter 将 Prometheus 指标转换为 External Metrics
- [ ] 更新 `deploy/kubernetes/apps/sisys/base/service.yaml` - 添加 Prometheus 注解
- [ ] Grafana Dashboard 配置（`deploy/kubernetes/apps/sisys/base/grafana-dashboard.json`）
- [ ] Grafana Dashboard provision 配置（`deploy/kubernetes/apps/sisys/base/grafana-dashboard-configmap.yaml`）

#### 验收标准 Gherkin (Acceptance Tests)
- [ ] 功能测试文件：`tests/acceptance/test_story_1.13.feature`
- [ ] 覆盖场景:
  - `/metrics` 端点返回 Prometheus 格式
  - 自定义业务指标正确暴露
  - K8s HPA 基于自定义指标扩缩容
  - 扩缩容响应时间<5 分钟

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕
- [ ] Gherkin 验收测试已编写，运行确认失败（红阶段验证）
- [ ] K8s 资源配置已定义

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
| **TDD 单元测试** | MetricsEndpoint | 端点响应格式 | `test_metrics_endpoint.py` | Task 1 |
| **TDD 单元测试** | BusinessMetricsCollector | 指标注册更新 | `test_business_metrics.py` | Task 2 |
| **TDD 单元测试** | MetricsAggregator | 指标聚合 | `test_metrics_aggregator.py` | Task 2 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收 | `test_story_1.13.feature` | Task 0 |
| **集成测试** | K8s HPA | 扩缩容场景 | `test_k8s_hpa_integration.py` | Task 3 |
| **SDD 架构验证** | 指标格式 | Prometheus 兼容性 | `test_prometheus_format.py` | Task 1 |

---

## 📊 AC → Task → Subtask 追溯矩阵

> **目的：** 确保每个 AC 都有明确的 Task 和 Subtask 对应，避免遗漏或重复。

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | Prometheus `/metrics` HTTP 端点 | Task 1 | Subtask 1.1-1.3（MetricsEndpoint 红→绿→重构） | `test_metrics_endpoint.py` |
| AC-1 | Prometheus 格式兼容 | Task 1 | Subtask 1.4-1.6（Prometheus 格式验证 红→绿→重构） | `test_prometheus_format.py` |
| AC-2 | BusinessMetricsCollector | Task 2 | Subtask 2.1-2.3（BusinessMetricsCollector 红→绿→重构） | `test_business_metrics.py` |
| AC-2 | MetricsAggregator（聚合器） | Task 2 | Subtask 2.4-2.6（MetricsAggregator 红→绿→重构） | `test_metrics_aggregator.py` |
| AC-3 | K8s HPA 集成 | Task 3 | Subtask 3.1-3.3（K8s 配置验证 红→绿→重构）, Subtask 3.7-3.9（资源配置） | `test_k8s_config.py` |
| AC-4 | 扩缩容性能要求 | Task 3 | Subtask 3.4-3.6（HPA 扩缩容测试 红→绿→重构） | `test_k8s_hpa_integration.py` |
| AC-5 | Grafana 可观测性 | Task 3 | Subtask 3.10（Grafana Dashboard 配置） | `test_grafana_dashboard.py` |

---

## 🌐 Latest Technical Information

> **来源:** Web Research - prometheus_client 库官方文档

### prometheus_client 库关键信息

| 项目 | 详情 |
|------|------|
| **项目内版本** | `^0.21.1`（已在 pyproject.toml 中定义） |
| **Python 版本** | 3.8+ |
| **安装方式** | `pip install prometheus_client` |
| **指标类型** | Counter, Gauge, Histogram, Summary, Info, Enum |
| **导出格式** | Prometheus 文本格式 0.0.4（自动生成 `# HELP` / `# TYPE`） |
| **多进程模式** | `prometheus_client.multiprocess` 支持 Gunicorn/uWSGI 多进程（**FastAPI 多 worker 必须使用**） |
| **REGISTRY** | 线程安全，推荐使用 `CollectorRegistry()` 或 `REGISTRY`（默认全局） |

### prometheus_client 核心 API

```python
from prometheus_client import Counter, Gauge, Histogram, Summary, generate_latest

# Counter（只增计数器）
c = Counter('requests_total', 'Total requests', ['method', 'endpoint'])
c.labels(method='GET', endpoint='/metrics').inc()

# Gauge（可增可减）
g = Gauge('active_sessions', 'Active sessions')
g.set(42)
g.inc()
g.dec()

# Histogram（分布统计）
h = Histogram('request_latency', 'Request latency', ['endpoint'],
              buckets=(.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10))
h.labels(endpoint='/api').observe(0.123)

# Summary（分位统计）
s = Summary('request_size', 'Request size', ['endpoint'])
s.labels(endpoint='/upload').observe(1024)

# 导出指标
output = generate_latest()
```

### 关键注意事项

1. **多进程问题**: 使用 Gunicorn 时需要 `prometheus_client.multiprocess` 模式，否则指标不准确
2. **标签基数**: 避免高基数标签（如 user_id），会导致 Prometheus 内存问题
3. **Histogram 分位数**: 分位数计算在客户端完成，默认分位数 [0.5, 0.9, 0.99]
4. **线程安全**: `CollectorRegistry` 线程安全，但单进程推荐使用默认 Registry

---

## 📋 Tasks / Subtasks 任务分解

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1, AC-2, AC-3, AC-4, AC-5

> **目的：** 在进入代码实现前，明确 Schema、API 契约、验收标准。

- [ ] Subtask 0.1: 定义 MetricsConfig 配置模型（`src/infrastructure/config/metrics.py`）
- [ ] Subtask 0.2: 定义 BusinessMetrics 数据类（`src/infrastructure/monitoring/business_metrics.py`）
- [ ] Subtask 0.3: 创建/更新 `docs/api/openapi.yaml` - `GET /metrics` 端点
- [ ] Subtask 0.4: 创建 K8s ServiceMonitor 配置
- [ ] Subtask 0.5: 创建 HPA 自定义指标配置
- [ ] Subtask 0.6: 创建 Grafana Dashboard 配置
- [ ] Subtask 0.7: 编写 Gherkin 验收测试 `tests/acceptance/test_story_1.13.feature`
- [ ] Subtask 0.8: 运行验收测试，确认失败（🔴 红阶段验证）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕
- [ ] 验收测试运行失败（预期行为，红阶段确认）

---

### Task 1: Prometheus `/metrics` HTTP 端点

**关联 AC:** AC-1

> **职责边界:** Task 1 负责 `/metrics` 端点本身，Task 2 负责业务指标定义和聚合

#### TDD 循环 [A]：MetricsEndpoint 端点

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/api/test_metrics_endpoint.py`（验证 `/metrics` 返回 Prometheus 格式） |
| 🟢 绿 | 实现 `src/interfaces/api/monitoring.py` - FastAPI 路由 `/metrics` |
| 🔄 重构 | 使用 `generate_latest()` 替代手动格式化，支持多进程 |

- [ ] Subtask 1.1: 🔴 红 — 编写 MetricsEndpoint 失败测试
- [ ] Subtask 1.2: 🟢 绿 — 实现 `/metrics` 端点
- [ ] Subtask 1.3: 🔄 重构 — 使用 `generate_latest()` 格式化

#### TDD 循环 [B]：Prometheus 格式验证

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/interfaces/api/test_prometheus_format.py`（验证 HELP/TYPE/指标值格式） |
| 🟢 绿 | 验证 Prometheus 文本格式标准合规 |
| 🔄 重构 | 优化格式生成性能 |

- [ ] Subtask 1.4: 🔴 红 — 编写 Prometheus 格式验证失败测试
- [ ] Subtask 1.5: 🟢 绿 — 验证格式合规性
- [ ] Subtask 1.6: 🔄 重构 — 优化验证逻辑

**完成标准/Definition of Done:**
- [ ] `/metrics` 端点实现完成
- [ ] Prometheus 格式兼容（HELP/TYPE/指标值）
- [ ] 端点响应时间 P95<100ms
- [ ] TDD 循环全部通过

---

### Task 2: 自定义业务指标与聚合

**关联 AC:** AC-2

> **职责边界:** Task 2 负责 BusinessMetricsCollector（业务指标定义）和 MetricsAggregator（指标聚合）

#### TDD 循环 [A]：BusinessMetricsCollector 指标注册

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/monitoring/test_business_metrics.py`（验证指标注册和更新） |
| 🟢 绿 | 实现 `src/infrastructure/monitoring/business_metrics.py` - BusinessMetricsCollector 类 |
| 🔄 重构 | 添加类型注解和文档字符串 |

- [ ] Subtask 2.1: 🔴 红 — 编写 BusinessMetricsCollector 失败测试
- [ ] Subtask 2.2: 🟢 绿 — 实现 BusinessMetricsCollector（Agent 会话数、队列长度、处理速率、缓存命中率）
- [ ] Subtask 2.3: 🔄 重构 — 优化指标更新性能

#### TDD 循环 [B]：MetricsAggregator 聚合器

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/monitoring/test_metrics_aggregator.py`（验证 EventMetricsCollector + BusinessMetricsCollector 聚合） |
| 🟢 绿 | 实现 `src/infrastructure/monitoring/aggregator.py` - MetricsAggregator 类 |
| 🔄 重构 | 统一收集和输出 |

- [ ] Subtask 2.4: 🔴 红 — 编写 MetricsAggregator 失败测试
- [ ] Subtask 2.5: 🟢 绿 — 实现 MetricsAggregator（聚合两个收集器）
- [ ] Subtask 2.6: 🔄 重构 — 统一管理所有指标采集器

**完成标准/Definition of Done:**
- [ ] BusinessMetricsCollector 实现完成
- [ ] MetricsAggregator 实现完成
- [ ] 自定义业务指标正确暴露
- [ ] TDD 循环全部通过

---

### Task 3: K8s HPA 集成

**关联 AC:** AC-3, AC-4, AC-5

#### TDD 循环 [A]：K8s 配置验证

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/test_k8s_config.py`（验证 K8s 配置正确性） |
| 🟢 绿 | 实现 K8s 配置验证逻辑 |
| 🔄 重构 | 配置验证器优化 |

- [ ] Subtask 3.1: 🔴 红 — 编写 K8s 配置验证失败测试
- [ ] Subtask 3.2: 🟢 绿 — 实现配置验证逻辑
- [ ] Subtask 3.3: 🔄 重构 — 优化验证器

#### TDD 循环 [B]：HPA 扩缩容测试

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/integration/test_k8s_hpa_integration.py`（验证 HPA 扩缩容行为） |
| 🟢 绿 | 实现 HPA 扩缩容触发逻辑（Mock K8s API） |
| 🔄 重构 | 集成测试优化 |

- [ ] Subtask 3.4: 🔴 红 — 编写 HPA 集成失败测试
- [ ] Subtask 3.5: 🟢 绿 — 实现 HPA 扩缩容测试逻辑（Mock K8s API）
- [ ] Subtask 3.6: 🔄 重构 — 完善测试覆盖率

#### K8s 资源配置

- [ ] Subtask 3.7: 创建 `deploy/kubernetes/apps/sisys/base/prometheus-servicemonitor.yaml`
- [ ] Subtask 3.8: 更新 `deploy/kubernetes/apps/sisys/base/service.yaml` - 添加 Prometheus 注解
- [ ] Subtask 3.9: 创建 Prometheus Adapter 部署说明（`deploy/kubernetes/apps/sisys/base/README.md`）
- [ ] Subtask 3.10: 创建 Grafana Dashboard 配置

**完成标准/Definition of Done:**
- [ ] K8s ServiceMonitor 配置完成
- [ ] Prometheus 抓取配置正确
- [ ] Prometheus Adapter 部署说明完成
- [ ] Grafana Dashboard 配置完成
- [ ] 扩缩容响应时间<5 分钟（性能基准测试）

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md)

- **架构模式:** 六边形架构（端口与适配器）
- **设计约束:**
  - 指标端点位于接口层（`src/interfaces/api/`）
  - 指标收集器位于基础设施层（`src/infrastructure/monitoring/`）
  - 领域层零依赖外部框架
- **技术栈:**
  - Python 3.11+
  - FastAPI 0.104+
  - prometheus_client `^0.21.1`（项目内已安装，指标暴露）
  - K8s HPA（自动扩缩容，依赖 prometheus-adapter）
  - K3S v1.34.5（K8s 运行时）
  - **多进程注意**: FastAPI + Uvicorn 多 worker 时使用 `generate_latest()` 聚合

### 关键架构决策

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) - ADR 相关决策

| 方案 | 优点 | 缺点 | 评分 |
|------|------|------|------|
| **使用 prometheus_client 库** | 标准库，Prometheus 原生支持 | 引入额外依赖 | ✅ 9/10 |
| 自定义 Prometheus 格式 | 无额外依赖 | 格式兼容风险 | 6/10 |

### 项目结构说明 Project Structure

```
sisys/
├── src/
│   ├── infrastructure/
│   │   ├── config/
│   │   │   └── metrics.py              # MetricsConfig 配置（复用 OtelConfig 模式）
│   │   └── monitoring/
│   │       ├── __init__.py
│   │       ├── event_metrics.py         # EventMetricsCollector（Story 1.3 已实现）
│   │       ├── business_metrics.py      # BusinessMetricsCollector（新实现）
│   │       └── aggregator.py            # MetricsAggregator 聚合器（新实现）
│   └── interfaces/
│       └── api/
│           └── monitoring.py            # /metrics 端点
├── deploy/kubernetes/apps/sisys/base/
│   ├── service.yaml                     # 更新：添加 Prometheus 注解
│   ├── prometheus-servicemonitor.yaml   # ServiceMonitor 配置
│   ├── grafana-dashboard.json           # Grafana Dashboard 配置
│   └── grafana-dashboard-configmap.yaml # Grafana Dashboard Provisioning
└── tests/
    ├── unit/
    │   ├── infrastructure/monitoring/
    │   │   ├── test_business_metrics.py
    │   │   └── test_metrics_aggregator.py
    │   └── interfaces/api/
    │       ├── test_metrics_endpoint.py
    │       └── test_prometheus_format.py
    ├── integration/
    │   └── test_k8s_hpa_integration.py
    └── acceptance/
        └── test_story_1.13.feature
```

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 1.3: Event Bus Implementation](./1-3-event-bus-implementation.md)

**关键学习/Key Learnings:**
1. **EventMetricsCollector 是纯内存计数器** — `src/infrastructure/monitoring/event_metrics.py` 仅有 `record_*()` 方法，**不暴露 HTTP 端点**，端点实现移至本 Story
2. **prometheus_client 已安装** — 项目内版本 `^0.21.1`，Story 1.3 用于注册 Counter/Histogram（Mock Registry）
3. **配置模式复用** — `OtelConfig.from_env()` 模式应复用，MetricsConfig 采用相同 `from_env()` 类方法
4. **Task 5.3 明确移至本 Story** — Story 1.3 注释明确："Prometheus `/metrics` HTTP 端点 → 移至 Story 1.13"

**应用到本故事/Applied to This Story:**
- [x] EventMetricsCollector **不修改**，仅通过 MetricsAggregator 聚合其指标
- [x] MetricsConfig 采用与 OtelConfig 相同的 `from_env()` 模式
- [x] 使用 `prometheus_client.generate_latest()` 暴露指标
- [x] 不重复实现 EventMetricsCollector 的指标定义

### Git Intelligence Summary

**来源:** `git log` - 最近 5 个提交

| 提交 | 主题 | 关键模式 |
|------|------|---------|
| `1ce59d7` | refactor: mv deploy/alembic to deploy/postgresql/alembic | 部署配置重组 |
| `a2e5138` | refactor: mv deploy/alembic to deploy/postgresql/alembic | 部署配置重组 |
| `1b73bed` | refactor: mv deployments to deploy/kubernetes | K8s 目录结构统一 |
| `94c8f59` | refactor: mv deployments to deploy/kubernetes | K8s 目录结构统一 |
| `1916ae9` | refactor: mv deployments to deploy/kubernetes | K8s 目录结构统一 |

**可应用模式:**
1. **K8s 配置集中管理** — `deploy/kubernetes/apps/sisys/base/` 下集中管理所有 K8s 资源配置（Service/Deployment/HPA）
2. **配置与实现分离** — YAML 配置与 Python 代码分离，Story 1.13 遵循此模式
3. **渐进式依赖** — 先有 K8s 基础设施（Story 0.4），后有应用层扩缩容（Story 1.13）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code (create-story workflow) |
| **Version** | create-story workflow v1.0 |
| **Execution Date** | 2026-04-16 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `_bmad/bmm/workflows/4-implementation/create-story/workflow.yaml` |
| **Instructions** | `_bmad/bmm/workflows/4-implementation/create-story/instructions.xml` |
| **Template** | `_bmad/bmm/workflows/4-implementation/create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md` |
| **架构文档** | `_bmad-output/planning-artifacts/architecture.md` |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/1-3-event-bus-implementation.md` |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` 提取
- [x] 架构约束从 `architecture.md` 提取
- [x] NFR-SCALE-03 追溯完成
- [x] K8s HPA 配置分析完成
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成
- [x] 项目结构对齐统一规范

### 文件清单 File List

**创建的文件/Created Files:**
- `_bmad-output/implementation-artifacts/stories/1-13-k8s-auto-scaling.md`

**待创建的文件/To Be Created (Dev Story 实施):**
- `src/infrastructure/config/metrics.py` - MetricsConfig 配置（复用 from_env 模式）
- `src/infrastructure/monitoring/business_metrics.py` - BusinessMetricsCollector
- `src/infrastructure/monitoring/aggregator.py` - MetricsAggregator（聚合 EventMetricsCollector + BusinessMetricsCollector）
- `src/interfaces/api/monitoring.py` - /metrics 端点
- `deploy/kubernetes/apps/sisys/base/prometheus-servicemonitor.yaml` - ServiceMonitor
- `deploy/kubernetes/apps/sisys/base/README.md` - Prometheus Adapter 部署说明
- `deploy/kubernetes/apps/sisys/base/grafana-dashboard.json` - Grafana Dashboard
- `tests/unit/infrastructure/monitoring/test_business_metrics.py` - BusinessMetricsCollector 单元测试
- `tests/unit/infrastructure/monitoring/test_metrics_aggregator.py` - MetricsAggregator 单元测试
- `tests/unit/interfaces/api/test_metrics_endpoint.py` - 端点单元测试
- `tests/integration/test_k8s_hpa_integration.py` - K8s HPA 集成测试
- `tests/acceptance/test_story_1.13.feature` - 验收测试

---

## 📚 Project Context Reference

> **来源:** [`project-context.md`](../../_bmad-output/project-context.md)

### 关键约束速查

| 约束类型 | 约束内容 | 来源 |
|---------|---------|------|
| **架构原则** | 六边形架构，领域层零依赖 | architecture.md §3.1 |
| **事件驱动** | 事务发件箱模式，事件处理幂等性 | architecture.md §3.3 |
| **CLI+Skills** | CLI 是 LLM 母语，Skills 渐进式披露 | architecture.md §3.4 |
| **测试覆盖率** | 整体≥80%，基础设施层≥75% | sdd-tdd-checklist.md §5 |
| **K8s 部署** | K3S v1.34.5，ArgoCD 持续部署 | project-context.md §2.7 |

### 关键路径依赖

```
Story 0.4 (K3S 集群) → Story 1.13 (K8s 扩缩容)
                            ↓
                    依赖 Story 1.4/1.5
                            ↓
                    Epic 1 存储层完成
```

### 监控指标体系（来自 project-context.md §14.9）

| 指标类别 | 指标 | 告警阈值 |
|---------|------|---------|
| **性能** | CLI 命令响应延迟 | P95 > 1s |
| **性能** | Skill 加载延迟 | P95 > 500ms |
| **质量** | Skill 触发准确率 | < 85% |
| **事件** | 事件处理成功率 | < 99% |
| **事件** | 事件处理延迟 | P95 > 5s |

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 1.13 |
| **Story Key** | 1-13-k8s-auto-scaling |
| **File** | `_bmad-output/implementation-artifacts/stories/1-13-k8s-auto-scaling.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 1: 企业级架构基础与合规 |
| **价值组** | 价值组 3: 五层存储架构 |
| **优先级** | P1-13（NFR-SCALE-03） |
| **覆盖 FR** | NFR-SCALE-03（Agent 动态扩缩容，响应时间<5 分钟） |
| **依赖 Story** | Story 1.3（EventMetricsCollector），Story 1.4（Redis 缓存层） |
| **前置条件** | EventMetricsCollector 已实现（Story 1.3） |
| **覆盖率要求** | 基础设施层≥75%（接口层≥85%，复用已有测试框架） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成
2. [x] All acceptance criteria specified 所有验收标准已定义
3. [x] Architecture constraints extracted 架构约束已提取
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（无直接前驱）
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 对抗性审查修复（Adversarial Review Fixes）

> 本次审查由 create-story skill 执行，聚焦 Story 1.3 一致性。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | prometheus_client 版本错误（0.19+ → ^0.21.1） | P1 | 更正为项目内已安装版本 |
| 2 | OpenAPI 定义（Prometheus 端点不是 REST API） | P1 | 移除 `/metrics` 的 OpenAPI 定义 |
| 3 | EventMetricsCollector 关系描述模糊 | P1 | 明确是独立组件，非扩展；新增 MetricsAggregator 聚合 |
| 4 | 缺少 K8s prometheus-adapter 说明 | P2 | 添加部署说明，明确 HPA 不能直接使用 Prometheus 指标 |
| 5 | AC-4 性能分解不清晰 | P2 | 明确端到端 5 分钟 = 指标采集 + HPA 决策 + Pod 启动 |
| 6 | events_processing_rate 类型不明确 | P2 | 明确为 Gauge 类型（每秒事件数） |
| 7 | 多进程模式未说明 | P2 | 添加使用 `generate_latest()` 而非 HTTP 服务器 |

### 下一步 Next Steps

- [ ] Story created with `ready-for-dev` status
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
| [K8s HPA 官方文档](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/) | HPA 配置参考 |
| [Prometheus 指标类型](https://prometheus.io/docs/concepts/metric_types/) | Counter/Gauge/Histogram/Summary |
| [prometheus_client 库](https://github.com/prometheus/client_python) | Python Prometheus 客户端 |

---

**模板版本/Template Version:** 2.0.0
**创建日期/Created:** 2026-04-16
**最后更新/Last Updated:** 2026-04-16
**更新说明:** 审查修复版本 - 修正与 Story 1.3 的一致性：(1) prometheus_client 版本更正为 ^0.21.1; (2) 移除 OpenAPI 定义（Prometheus 端点非 REST API）; (3) 明确 MetricsAggregator 聚合职责; (4) 添加 K8s prometheus-adapter 说明; (5) 修正 AC-4 性能分解; (6) 明确 events_processing_rate 为 Gauge
