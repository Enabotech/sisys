# SISYS V2 战略传导链引擎架构设计

> **版本**: v1.0
> **目标**: V2 原型核心架构 -- 假设变更影响传播的全链路技术设计
> **状态**: Draft
> **作者**: Winston (System Architect)
> **日期**: 2026-06-11

---

## 目录

1. [设计总览与现有基础设施映射](#1-设计总览与现有基础设施映射)
2. [Neo4j 依赖图数据模型](#2-neo4j-依赖图数据模型)
3. [图遍历查询模式](#3-图遍历查询模式)
4. [Prefect 重计算 DAG](#4-prefect-重计算-dag)
5. [Ghost Preview 架构](#5-ghost-preview-架构)
6. [闭环反馈架构](#6-闭环反馈架构)
7. [事件系统设计](#7-事件系统设计)
8. [端口设计与组合根注册](#8-端口设计与组合根注册)
9. ["先做一件事"实现计划](#9-先做一件事实现计划)
10. [冷启动解决方案](#10-冷启动解决方案)

---

## 1. 设计总览与现有基础设施映射

### 1.1 策略：最大化复用现有基础设施

V2 原型不是从零开始 -- 它建立在现有六边形架构之上。下表列出哪些已有、哪些需要新增、哪些需要扩展：

| 组件 | 当前状态 | V2 需求 | 策略 |
|------|---------|--------|------|
| Neo4j 连接 (l5_graph) | 已注册端口 + Neo4jAdapter | 专用战略依赖图 | 新增 `StrategicGraphPort` (领域端口) + `StrategicGraphAdapter` (基础设施)，并行于现有 Memory 图存储 |
| Prefect 引擎 (workflow_engine) | PrefectEngine 已注册 | 重计算流定义 | 新增 Prefect flow 定义 + 复用已有引擎 |
| RabbitMQ 事件总线 (event_publisher) | DualChannelEventBus 完整实现 | 7 个新事件类型 | 新增领域事件类 + 通道配置 |
| LangGraph 引擎 (agent_engine) | LangGraphEngine 已注册 | 多 Agent 分析图 | 扩展已支持的多图类型 + 新增 Agent 图定义 |
| 领域异常体系 | 完整子域编码体系 | 战略领域异常 | 新增 `strategy` 子域 (271-279) |
| Qdrant 向量存储 (l3_vector) | 已注册端口 | 语义检索（AUD Agent 偏差分析） | 复用已有 |
| DomainEvent 基类 | 完整 AC-1 字段 | 战略事件家族 | 继承已有基类 |
| ChannelRouter | DEFAULT_MAPPINGS + YAML | 新事件通道路由 | 追加到两处 |

### 1.2 架构分层映射

```
┌─────────────────────────────────────────────────────────────┐
│ interfaces/v2/                                               │
│   api/v2/assumption_change.py   ← POST /v2/assumption/change│
│   api/v2/ghost_preview.py       ← GET  /v2/ghost/{session}  │
│   api/v2/feedback_ingest.py     ← POST /v2/execution/data   │
│   ws/v2/soc_stream.py           ← WS  /v2/soc/stream         │
├─────────────────────────────────────────────────────────────┤
│ application/v2/                                              │
│   services/consequence_chain_service.py                      │
│   services/ghost_preview_service.py                          │
│   services/feedback_deviation_service.py                     │
│   services/assumption_revision_service.py                    │
│   event_handlers/                                             │
│       ripple_computed_handler.py                             │
│       deviation_analyzed_handler.py                          │
│       ghost_preview_generated_handler.py                     │
├─────────────────────────────────────────────────────────────┤
│ domain/v2/                                                   │
│   entities/strategic_assumption.py                           │
│   entities/bp_initiative.py                                  │
│   entities/impact_path.py                                    │
│   value_objects/impact_magnitude.py                          │
│   value_objects/assumption_confidence.py                     │
│   ports/consequence_chain_port.py   (Protocol)               │
│   ports/ghost_preview_port.py       (Protocol)               │
│   ports/feedback_ingestion_port.py  (Protocol)               │
│   events/assumption_events.py                                │
│   events/ripple_events.py                                    │
│   events/feedback_events.py                                  │
│   exceptions/strategy_exceptions.py                          │
├─────────────────────────────────────────────────────────────┤
│ infrastructure/v2/                                           │
│   neo4j/strategic_graph_adapter.py    (StrategicGraphPort)   │
│   prefect/ripple_compute_flow.py                              │
│   prefect/ghost_preview_compute.py                            │
│   monitoring/cusum_drift_detector.py                          │
│   adapters/sap_data_ingestion_adapter.py                      │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 数据流全景

```
用户操作: 修改 market_growth_rate 15%→6%
    │
    ├─[200ms]── GhostPreviewService ──→ 前端渲染 Ghost UI
    │              │
    │              ├─ Neo4j 快速图遍历 (≤5ms)
    │              ├─ 确定性公式计算 (≤5ms)
    │              └─ Redis 缓存写入     (≤2ms)
    │
    ├─[4-7s]── ConsequenceChainService ──→ AI 分析管道
    │              │
    │              ├─ Step 1: Neo4j 完整图遍历 (apoc.path.expand)
    │              ├─ Step 2: Prefect 重计算 DAG 提交
    │              │    ├─ Phase A: 独立子图并行重算
    │              │    ├─ Phase B: 依赖链路串行重算
    │              │    └─ Phase C: LanGraph 多 Agent 分析
    │              ├─ Step 3: RabbitMQ 传播事件发布
    │              └─ Step 4: 前端 WebSocket 推送→替换 Ghost
    │
    └─[异步]── RipplePropagationEvents ──→ 下游系统
                   │
                   ├─ AlertService（预算超标→通知 CFO）
                   ├─ AuditLog（变更→WORM 归档）
                   └─ SOC Dashboard（承诺墙→更新状态）
```

---

## 2. Neo4j 依赖图数据模型

### 2.1 节点类型定义

所有节点共享基类属性 `{id: UUID, label: str, created_at: datetime, updated_at: datetime, version: int}`。

#### 2.1.1 StrategicAssumption（战略假设）

```cypher
CREATE (a:StrategicAssumption {
    id: "uuid-market-growth-2026",
    label: "中国新能源汽车市场年增长率",
    category: "market",           -- market|technology|regulatory|competitive|resource
    current_value: 0.15,          -- 当前假设值（15%）
    unit: "percentage",
    confidence: 0.78,             -- 假设置信度 0.0-1.0（AUD Agent 动态更新）
    owner: "CSO",                 -- 假设负责人角色
    blm_phase: "market_insight",  -- 所属 BLM 阶段
    source_document_id: "uuid-prd-v3",  -- 来源文档（可溯源）
    version: 3,                   -- 假设版本号（每次修订递增）
    last_revised_at: "2026-03-15T...",
    drift_status: "stable"        -- stable|warning|critical（CUSUM 检测）
})
```

#### 2.1.2 StrategicInitiative（战略举措 / BP 计划）

```cypher
CREATE (i:StrategicInitiative {
    id: "uuid-ev-battery-plant",
    label: "动力电池工厂产能扩建",
    category: "capacity_expansion",  -- capacity_expansion|product_launch|channel_dev|talent_build|tech_rd
    budget_total: 2.8e9,             -- 总预算 28亿
    budget_allocated: 8.5e8,         -- 已拨付 8.5亿
    time_window_start: "2026-Q1",
    time_window_end: "2028-Q4",
    current_phase: "construction",
    owner: "COO",
    priority: "P0",
    status: "in_progress",
    kpi_target: "年产能 50GWh",
    sp_plan_id: "uuid-sp-2026"       -- 关联 SP
})
```

#### 2.1.3 KPI（关键绩效指标）

```cypher
CREATE (k:KPI {
    id: "uuid-kpi-production-capacity",
    label: "年度电池产能",
    target_value: 50.0,
    unit: "GWh",
    measurement_frequency: "monthly",
    data_source: "SAP_PP",
    responsible_dept: "制造中心",
    current_actual: 12.3,            -- 实时执行数据
    last_updated: "2026-05-31T..."
})
```

#### 2.1.4 BudgetLine（预算科目）

```cypher
CREATE (b:BudgetLine {
    id: "uuid-budget-capex-2026",
    label: "2026 资本开支预算",
    category: "capex",               -- capex|opex|rd|marketing|hr
    amount_planned: 1.2e9,
    amount_committed: 4.5e8,         -- 已签约承诺
    amount_disbursed: 2.1e8,         -- 已支付
    fiscal_year: 2026,
    currency: "CNY",
    cost_center: "P-203-BATTERY",
    approval_chain: ["COO", "CFO", "CEO"]
})
```

#### 2.1.5 TalentNeed（人才需求）

```cypher
CREATE (t:TalentNeed {
    id: "uuid-talent-battery-engineers",
    label: "电池工艺工程师需求",
    role: "工艺工程师",
    headcount_required: 120,
    headcount_current: 34,
    avg_time_to_hire_days: 45,
    location: "合肥",
    criticality: "high",             -- critical|high|medium|low
    budget_per_head: 350000          -- 年薪 CNY
})
```

#### 2.1.6 Contract（合同/签约义务）

```cypher
CREATE (c:Contract {
    id: "uuid-training-contract-hfut",
    label: "合工大战略人才联合培养协议",
    contract_type: "training",       -- procurement|training|lease|loan|subsidy
    sign_date: "2025-11-01",
    value_amount: 1.2e8,
    penalty_clause: "单方终止赔偿 30% (3600万)",
    counterparty: "合肥工业大学",
    expiration_date: "2029-10-31",
    status: "active",
    immutability: "signed",          -- signed|pending|expired
    financial_viability_score: 0.91  -- 合同在当前假设下的财务可行性（关键！）
})
```

#### 2.1.7 CashFlowCycle（现金流周期）

```cypher
CREATE (cf:CashFlowCycle {
    id: "uuid-cashflow-battery-business",
    label: "电池业务现金流周期",
    receivables_days: 90,            -- 应收账款周转天数
    payables_days: 60,               -- 应付账款周转天数
    inventory_days: 45,              -- 库存周转天数
    cash_conversion_cycle: 75,       -- CCC = AR+INV-AP
    current_ratio: 1.8,
    debt_service_coverage: 2.3
})
```

#### 2.1.8 ChannelDealer（渠道经销商）

```cypher
CREATE (ch:ChannelDealer {
    id: "uuid-dealer-network-east",
    label: "华东区经销商网络",
    dealer_count: 350,
    subsidy_per_dealer: 5e5,         -- 已发放补贴/家
    total_subsidy_disbursed: 1.75e8,
    contract_term_months: 36,
    exit_penalty_per_dealer: 3e5
})
```

### 2.2 关系类型定义

| 关系类型 | 语义 | 方向 | 示例 |
|---------|------|------|------|
| `DRIVES` | 假设驱动战略举措 | Assumption → Initiative | 市场增长率→电池工厂 |
| `PRODUCES` | 举措产出 KPI 目标 | Initiative → KPI | 电池工厂→年产能 50GWh |
| `ALLOCATES` | 举措分配预算 | Initiative → BudgetLine | 电池工厂→2026 Capex |
| `REQUIRES` | 举措需要人才 | Initiative → TalentNeed | 电池工厂→工艺工程师 120人 |
| `HAS_METRIC` | KPI 下挂指标 | KPI → KPI | (层级 KPI 树) |
| `BINDS` | 合同约束举措 | Contract → Initiative | 培养协议→人才供给 |
| `AFFECTS` | 影响现金流周期 | Initiative → CashFlowCycle | 电池工厂→电池业务现金流 |
| `THROUGH` | 通过渠道销售 | Initiative → ChannelDealer | 渠道战略→华东经销商 |
| `DEPENDS_ON` | 跨举措依赖 | Initiative → Initiative | 电池产能→整车产能 |
| `HAS_ASSUMPTION` | SP 拥有假设 | StrategicPlan → Assumption | SP-2026→市场增长率 |

### 2.3 赵总6跳案例的 Neo4j 图建模

CSO 赵总的真实例子：市场增长率 15%→6%，通过 6 跳传导：

```
(StrategicAssumption: 市场增长率 15%)
    │
    └──[DRIVES]──→ (Initiative: 产能扩建)
                       │
                       ├──[PRODUCES]──→ (KPI: 年产能)
                       ├──[REQUIRES]──→ (TalentNeed: 工艺工程师 120人)
                       │                    │
                       │                    └──[BINDS]──→ (Contract: 合工大培养协议
                       │                                        penalty=30% 3600万)
                       ├──[ALLOCATES]──→ (BudgetLine: 2026 Capex)
                       │
                       ├──[THROUGH]──→ (ChannelDealer: 华东经销商
                       │                    subsidy=1.75亿 已发放)
                       │
                       └──[AFFECTS]──→ (CashFlowCycle: 电池业务 CCC=75天)
                                            │
                                            └──[AFFECTS]──→ (SupplierPaymentTerms)
```

**关键设计决策：直接依赖 vs 间接依赖的区别通过路径长度自然体现。**
- 直接依赖：`(a)-[:DRIVES]->(b)` -- 1 跳
- 间接依赖：`(a)-[:DRIVES]->(:Initiative)-[:REQUIRES]->(:TalentNeed)-[:BINDS]->(:Contract)` -- 3 跳
- 不需要在关系中编码"直接/间接"元数据 -- 查询时通过路径长度 + 权重衰减区分

每个关系都携带 `impact_weight` 属性（0.0-1.0），用于传导时的衰减计算：
```cypher
MERGE (a)-[r:DRIVES]->(i)
SET r.impact_weight = 0.85,
    r.description = "市场增长率每降低1pp，产能需求预期降低8%"
```

### 2.4 不可变合同的问题建模

当 `Contract.status = 'active' AND Contract.immutability = 'signed'`，合同的法律状态不变，但其**财务可达性**改变。通过以下方式建模：

1. **Contract 节点的 `financial_viability_score`** 在传导链重算时动态更新
2. **Contract 节点始终在图中** -- 不会因为假设变化而"删除"
3. **新增一个 Alert 节点** 当 `financial_viability_score < 0.6`：
```cypher
CREATE (alert:DerivedAlert {
    id: "uuid-alert-contract-risk-hfut",
    alert_type: "contract_financial_risk",
    severity: "high",
    message: "合工大培养协议在当前假设下财务可行性降至 0.52，触发违约金风险 3600万",
    triggered_by_assumption_id: "uuid-market-growth-2026"
})
MERGE (alert)-[:TRIGGERED_BY]->(c)
```

---

## 3. 图遍历查询模式

### 3.1 核心遍历查询：假设变更影响传导

当用户将 `market_growth_rate` 从 15% 改为 6%（变化率 = -60%），必须找出所有直接和间接受影响的节点。

#### 查询 1: 前向传导 -- 从假设向下游查找所有影响节点

```cypher
// 使用 APOC 路径扩展过程（需安装 apoc 插件）
// 最大深度 8 跳（覆盖赵总6跳示例 + 缓冲）
MATCH (start:StrategicAssumption {id: $assumption_id})
CALL apoc.path.expand(start, "DRIVES|PRODUCES|ALLOCATES|REQUIRES|AFFECTS|THROUGH|BINDS|DEPENDS_ON", null, 1, 8)
YIELD path
WITH path, nodes(path) AS path_nodes, relationships(path) AS path_rels
UNWIND path_nodes AS node
// 排除起始节点自身
WHERE node.id <> $assumption_id
WITH DISTINCT node,
     // 计算累积冲击权重（路径上所有权重的乘积）
     REDUCE(w = 1.0, r IN path_rels | w * COALESCE(r.impact_weight, 0.5)) AS cumulative_weight,
     // 路径深度
     LENGTH(path) AS hop_count,
     // 收集路径上所有节点标签以便前端展示传导链
     [n IN path_nodes | n.label] AS chain_labels
RETURN
    node.id AS node_id,
    LABELS(node) AS node_types,
    node.label AS node_label,
    cumulative_weight,
    hop_count,
    chain_labels,
    // 节点的当前属性快照
    PROPERTIES(node) AS current_properties
ORDER BY cumulative_weight DESC, hop_count ASC
```

#### 查询 2: 带冲击量级的注释遍历

```cypher
// 不仅返回被影响节点，还计算每个节点的预估冲击量级
MATCH (start:StrategicAssumption {id: $assumption_id})
CALL apoc.path.expand(start, "DRIVES|PRODUCES|ALLOCATES|REQUIRES|AFFECTS|THROUGH|BINDS|DEPENDS_ON", null, 1, 8)
YIELD path
WITH path, nodes(path) AS path_nodes, relationships(path) AS path_rels
WITH path_nodes, path_rels,
     // 累积冲击权重
     REDUCE(w = 1.0, r IN path_rels | w * COALESCE(r.impact_weight, 0.5)) AS cumulative_weight
UNWIND RANGE(1, SIZE(path_nodes) - 1) AS idx
WITH path_nodes[idx] AS node,
     cumulative_weight,
     SIZE(path_nodes) - 1 AS hop_count,
     // 对不同类型的节点计算不同的冲击
     CASE
         WHEN 'BudgetLine' IN LABELS(node) THEN
             cumulative_weight * ABS($change_ratio) * COALESCE(node.amount_planned, 0)
         WHEN 'TalentNeed' IN LABELS(node) THEN
             ROUND(cumulative_weight * ABS($change_ratio) * COALESCE(node.headcount_required, 0))
         WHEN 'Contract' IN LABELS(node) THEN
             cumulative_weight * ABS($change_ratio)
         WHEN 'KPI' IN LABELS(node) THEN
             cumulative_weight * ABS($change_ratio) * COALESCE(node.target_value, 0)
         ELSE
             cumulative_weight * ABS($change_ratio)
     END AS impact_magnitude
RETURN DISTINCT
    node.id AS node_id,
    LABELS(node)[0] AS node_type,
    node.label AS node_label,
    hop_count,
    cumulative_weight,
    impact_magnitude,
    CASE
        WHEN 'BudgetLine' IN LABELS(node) THEN node.amount_planned * (1 - cumulative_weight * ABS($change_ratio))
        WHEN 'TalentNeed' IN LABELS(node) THEN ROUND(node.headcount_required * (1 - cumulative_weight * ABS($change_ratio)))
        ELSE NULL
    END AS adjusted_value
ORDER BY impact_magnitude DESC
```

参数绑定示例：
```python
params = {
    "assumption_id": "uuid-market-growth-2026",
    "change_ratio": -0.60  # 从 15% 到 6%: (6-15)/15 = -0.60
}
```

#### 查询 3: 违约风险检测查询

```cypher
// 在遍历结果之后执行——检测哪些已签约合同面临财务可行性风险
MATCH (c:Contract {immutability: "signed", status: "active"})
WHERE c.financial_viability_score IS NOT NULL
  AND c.financial_viability_score < 0.7
OPTIONAL MATCH (t:TalentNeed)-[:BINDS]->(c)
OPTIONAL MATCH (i:StrategicInitiative)-[:REQUIRES]->(t)
OPTIONAL MATCH (a:StrategicAssumption)-[:DRIVES]->(i)
RETURN
    c.id AS contract_id,
    c.label AS contract_label,
    c.financial_viability_score AS viability_score,
    c.penalty_clause AS penalty,
    c.value_amount AS contract_value,
    i.label AS affected_initiative,
    a.label AS root_assumption,
    // 预算与合同价值的差距
    CASE
        WHEN c.value_amount IS NOT NULL
        THEN c.value_amount * (1 - c.financial_viability_score)
        ELSE 0
    END AS potential_loss
ORDER BY potential_loss DESC
```

### 3.2 遍历结果结构（Python 端消费）

图遍历结果由 `ConsequenceChainService` 消费后，转换为结构化响应：

```python
@dataclass(frozen=True)
class ImpactPath:
    """单条传导路径"""
    source_assumption_id: str
    target_node_id: str
    target_node_type: str           # "BudgetLine" | "Contract" | "TalentNeed" | ...
    target_node_label: str
    hop_count: int                  # 跳数（1 = 直接，6 = 赵总例子）
    cumulative_weight: float        # 累积冲击权重
    impact_magnitude: float         # 冲击量级（绝对值）
    adjusted_value: float | None    # 调整后的值（预算/人数等）
    chain_labels: list[str]         # 传导链的可读标签序列
    financial_consequence_cny: float | None  # 财务后果（CNY）
    responsible_person: str         # 责任人
    decision_window_days: int       # 决策时间窗口（天）
```

### 3.3 差异化传导：用户探索 vs 系统警报

最关键的设计区分：用户主动修改一个假设参数来探索"what-if"场景，与系统检测到现实数据背离后自动触发传导 -- 二者的处理路径相同（都是 Neo4j 遍历 + Prefect 重算），但以下几个维度不同：

| 维度 | 用户探索模式 (What-If) | 系统警报模式 (Deviation) |
|------|----------------------|--------------------------|
| 触发源 | `POST /v2/assumption/change` API | `CUSUMDriftDetected` 领域事件 |
| 假设变更持久化 | 否 -- 仅在会话内生效 | 是 -- 更新 Assumption.current_value + version++ |
| 审计要求 | 仅记录操作日志 | WORM 归档 + 审批链通知 |
| 响应时间期望 | 200ms Ghost + 4-7s AI | 1-5min 批处理（允许更深度分析） |
| 通知对象 | 操作者本人 | CEO + CSO + 受影响举措负责人 |
| GUI 标识 | "探索模式" 水印 | "系统检测到偏差" 红色横幅 |

---

## 4. Prefect 重计算 DAG

### 4.1 重计算阶段划分

图遍历返回受影响节点集合后，重计算分三个阶段进行：

```
Phase A: 独立子图并行重算
  ├─ Task A1: 独立 Initiative 重算  (并行)
  ├─ Task A2: 独立 Initiative 重算  (并行)
  └─ Task A3: 独立 Initiative 重算  (并行)
        │
        ▼
Phase B: 依赖链路串行重算
  ├─ Task B1: DEPENDS_ON 下游 Initiative 重算
  └─ Task B2: DEPENDS_ON 下游 Initiative 重算
        │
        ▼
Phase C: LangGraph 多 Agent 分析
  ├─ Task C1: CFO Agent -- 财务影响评估
  ├─ Task C2: COO Agent -- 运营影响评估
  ├─ Task C3: CHO Agent -- 人力影响评估
  ├─ Task C4: CMO Agent -- 市场影响评估
  └─ Task C5: CTO Agent -- 技术影响评估
        │
        ▼
  └─ Task C6: CEO Agent -- 综合研判 + 建议生成
```

### 4.2 Prefect Flow 定义

```python
# infrastructure/v2/prefect/ripple_compute_flow.py

from prefect import flow, task
from prefect.task_runners import ConcurrentTaskRunner
from typing import Any

@task(name="recompute_initiative")
async def recompute_initiative(
    initiative_id: str,
    change_context: dict[str, Any],
) -> dict[str, Any]:
    """重算单个战略举措的确定性指标（预算、时间线、人力需求）

    确定性计算——不涉及 AI，可在 Ghost Preview 中复用：
    - 预算调整 = 原预算 * cumulative_weight * change_ratio
    - 人力需求调整 = 原人力 * cumulative_weight * change_ratio
    - 时间线偏移 = 基于冲击量级的时间窗口滑动
    """
    ...

@task(name="financial_viability_check")
async def financial_viability_check(
    contract_ids: list[str],
    change_context: dict[str, Any],
) -> list[dict[str, Any]]:
    """合同财务可行性检查

    对已签约合同重新评估财务可行性得分
    当 score < 0.7 时生成预警
    """
    ...

@task(name="compute_aggregate_impacts")
async def compute_aggregate_impacts(
    all_initiative_results: list[dict[str, Any]],
    contract_alerts: list[dict[str, Any]],
) -> dict[str, Any]:
    """聚合所有影响计算结果

    生成：
    - 总预算冲击（CNY）
    - 时间线影响（最早/最晚完成时间变化）
    - 人力缺口汇总
    - 合同风险清单
    - 现金流周期变化
    """
    ...

@task(name="launch_agent_analysis")
async def launch_agent_analysis(
    aggregate_result: dict[str, Any],
    session_id: str,
) -> str:
    """启动 LangGraph 多 Agent 分析管道

    返回 graph_run_id 供后续状态查询
    """
    ...

@flow(
    name="RippleRecomputation",
    task_runner=ConcurrentTaskRunner(),
    log_prints=True,
)
async def ripple_recomputation_flow(
    assumption_id: str,
    change_ratio: float,
    impacted_nodes: list[dict[str, Any]],
    session_id: str,
) -> dict[str, Any]:
    """传导链重计算主流程

    Args:
        assumption_id: 被修改的战略假设 ID
        change_ratio: 变化比率（如 -0.60 表示降低 60%）
        impacted_nodes: Neo4j 图遍历返回的受影响节点列表
        session_id: 会话标识符
    """

    # Phase A: 独立节点并行重算
    independent_nodes = [n for n in impacted_nodes if n["node_type"] == "StrategicInitiative"]
    initiative_futures = [
        recompute_initiative.submit(n["node_id"], {"assumption_id": assumption_id, "change_ratio": change_ratio})
        for n in independent_nodes
    ]

    # Phase B: 依赖链串行重算（等待 Phase A 完成）
    dependent_nodes = [
        n for n in impacted_nodes
        if any(r["type"] == "DEPENDS_ON" for r in n.get("relationships", []))
    ]

    # Phase C: 合同财务可行性检查（可与 Phase B 并行）
    contract_nodes = [n for n in impacted_nodes if n["node_type"] == "Contract"]
    contract_future = financial_viability_check.submit(
        [n["node_id"] for n in contract_nodes],
        {"assumption_id": assumption_id, "change_ratio": change_ratio},
    )

    # 等待所有 Phase A 结果
    initiative_results = [f.result() for f in initiative_futures]
    contract_alerts = contract_future.result()

    # 聚合计算
    aggregate = await compute_aggregate_impacts(initiative_results, contract_alerts)

    # 启动 AI Agent 分析
    graph_run_id = await launch_agent_analysis(aggregate, session_id)

    return {
        "aggregate": aggregate,
        "graph_run_id": graph_run_id,
        "contract_alerts": contract_alerts,
    }
```

### 4.3 Prefect Flow 提交方式

```python
# application/v2/services/consequence_chain_service.py

from src.domain.ports.workflow_engine import WorkflowEnginePort

class ConsequenceChainService:
    def __init__(
        self,
        graph_port: StrategicGraphPort,
        workflow_engine: WorkflowEnginePort,
        agent_engine: AgentEnginePort,
        event_publisher: EventPublisher,
    ):
        self._graph = graph_port
        self._workflow = workflow_engine
        self._agent = agent_engine
        self._events = event_publisher

    async def execute_ripple_analysis(
        self,
        assumption_id: str,
        new_value: float,
        session_id: str,
    ) -> RippleAnalysisResult:
        # Step 1: Neo4j 图遍历
        impacted_nodes = await self._graph.traverse_impact_paths(
            assumption_id=assumption_id,
            max_depth=8,
        )

        # Step 2: 计算变化率
        old_value = await self._graph.get_assumption_value(assumption_id)
        change_ratio = (new_value - old_value) / old_value

        # Step 3: 提交 Prefect flow
        flow_run_id = await self._workflow.submit_flow(
            flow_name="RippleRecomputation/RippleRecomputation",
            parameters={
                "assumption_id": assumption_id,
                "change_ratio": change_ratio,
                "impacted_nodes": impacted_nodes,
                "session_id": session_id,
            },
        )

        # Step 4: 发布传播开始事件
        await self._events.publish(
            RippleComputationStarted(
                assumption_id=assumption_id,
                change_ratio=change_ratio,
                impacted_node_count=len(impacted_nodes),
                flow_run_id=flow_run_id,
                session_id=session_id,
            )
        )

        return RippleAnalysisResult(
            flow_run_id=flow_run_id,
            impacted_node_count=len(impacted_nodes),
            ghost_preview_id=None,  # 由 Ghost Preview 服务填充
        )
```

---

## 5. Ghost Preview 架构

### 5.1 设计决策：两阶段预览策略

| 阶段 | 时间目标 | 方法 | 精度 |
|------|---------|------|------|
| **Ghost Preview** | ≤200ms | 确定性公式（Neo4j 遍历 + 线性加权计算） | ±15% vs 最终 AI 结果 |
| **Resolved Preview** | 4-7s | LangGraph 多 Agent 分析 | 最终答案 |

**为什么不用学习模型做 Ghost？** 冷启动时没有训练数据。确定性公式立即可用、逻辑透明、错误可解释。学习模型（LightGBM/XGBoost regressor）在积累足够 (<assumption_value, agent_scores>) 样本后引入作为可选增强，但不作为 V2 原型的一部分。

### 5.2 确定性 Ghost 计算公式

```python
# domain/v2/value_objects/ghost_score.py

def compute_ghost_impact(
    assumption_change_ratio: float,
    hop_count: int,
    cumulative_weight: float,
    base_value: float,
    node_type: str,
) -> GhostImpact:
    """确定性 Ghost Impact 计算公式

    公式: adjusted_value = base_value * (1 + change_ratio * cumulative_weight^hop_count)
    衰减因子: cumulative_weight^hop_count（跳数越深衰减越强）

    Args:
        assumption_change_ratio: 假设变化比率（如 -0.60）
        hop_count: 传导跳数
        cumulative_weight: 累积路径权重
        base_value: 节点原始值（预算金额、人数等）
        node_type: 节点类型
    """
    decay_factor = cumulative_weight ** hop_count  # 跳数衰减
    impact_ratio = assumption_change_ratio * decay_factor
    adjusted_value = base_value * (1 + impact_ratio)

    # 不同类型节点的 Ghost Score 语义不同
    if node_type == "BudgetLine":
        score = adjusted_value / base_value  # 归一化到 1.0
    elif node_type == "Contract":
        # 合同财务可行性得分（高于0.9=安全，低于0.6=风险）
        score = 1.0 - abs(impact_ratio) * 1.5  # 放大合同风险敏感度
        score = max(0.0, min(1.0, score))
    else:
        score = 1.0 + impact_ratio  # 通用得分

    return GhostImpact(
        node_id="...",
        ghost_score=round(score, 3),
        adjusted_value=round(adjusted_value, 2),
        confidence_interval=(score * 0.90, score * 1.10),  # ±10% CI
        is_estimated=True,
    )
```

**Ghost → Resolved 的 UX 契约：**
- Ghost 展示时带半透明 UI + "估算中..."动画
- Ghost 得分显示为范围（如 "0.76-0.93" 而非 "0.85"）
- Resolved 结果到达时，元素过渡动画（opacity 0.5→1.0，score 数值平滑过渡）
- 如果 Ghost 误差 >20%（vs Resolved），显示黄色警示 "预估偏差较大，请以实际结果为准"

### 5.3 Ghost → Resolve 事件流

```
时间线  前端 UI 状态              事件流

T+0ms   假设参数修改框高亮        UserActionStarted (前端本地)
T+50ms
T+100ms Ghost UI 渲染             GhostPreviewGenerated (→WebSocket)
         - 半透明样式
         - 得分范围显示
         - 脉冲动画
T+200ms Ghost 渲染完成
T+500ms
T+1000ms "AI 分析中..." 状态     AIAnalysisStarted (→WebSocket)
T+2000ms Agent 1 结果             AgentDecided (CFO) (→WebSocket)
T+3000ms Agent 2 结果             AgentDecided (COO) (→WebSocket)
T+4000ms Agent 3 结果             AgentDecided (CHO) (→WebSocket)
T+5000ms Agent 4,5 结果           AgentDecided (CMO, CTO) (→WebSocket)
T+6500ms 综合研判完成             AISynthesisComplete (→WebSocket)
T+6700ms Score 过渡动画           ScoresResolved (→WebSocket)
T+7000ms 最终 UI 渲染（不透明）
```

### 5.4 WebSocket 事件订阅

```python
# interfaces/ws/v2/soc_stream.py

@router.websocket("/v2/soc/stream/{session_id}")
async def soc_stream(
    websocket: WebSocket,
    session_id: str,
    token: str = Depends(verify_token),
):
    await websocket.accept()

    # 订阅 Redis pub/sub 实时通道
    redis = await resolve("redis_client")
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"sisys:rt:soc:{session_id}")

    # 事件循环：Redis → WebSocket
    async for message in pubsub.listen():
        if message["type"] == "message":
            data = json.loads(message["data"])
            await websocket.send_json(data)
```

**事件通道设计：**

```yaml
# 在 configs/event_channels.yaml 中新增
  # =========================================================================
  # V2: Ghost Preview 事件
  # =========================================================================
  GhostPreviewGenerated:
    redis_channel: "sisys:rt:soc"          # 实时通道，低延迟
    delivery_mode: "realtime"
    description: "Ghost Preview 得分生成"

  AIAnalysisStarted:
    redis_channel: "sisys:rt:soc"
    delivery_mode: "realtime"
    description: "AI 分析管道启动"

  AISynthesisComplete:
    redis_channel: "sisys:rt:soc"
    delivery_mode: "realtime"
    description: "AI 综合研判完成"

  ScoresResolved:
    redis_channel: "sisys:rt:soc"
    delivery_mode: "realtime"
    description: "所有得分解析完成"
```

---

## 6. 闭环反馈架构

### 6.1 四阶段流水线

```
Stage 1: Execution Data Ingestion
  ┌──────────────────────────────────────────┐
  │ SAP/ERP Adapter → MilestoneAchieved      │
  │                  → BudgetActual           │
  │                  → TalentAttrition        │
  │                  → KPIReading             │
  └──────────┬───────────────────────────────┘
             │ (RabbitMQ: sisys.events.feedback.*)
             ▼
Stage 2: Deviation Analysis
  ┌──────────────────────────────────────────┐
  │ AUD Agent:                               │
  │  1. Neo4j 图遍历 → 将 KPI 映射到假设    │
  │  2. CUSUM 漂移检测 → 阈值: ±1.5σ        │
  │  3. 置信度重新校准（贝叶斯更新）         │
  │  4. 如果置信度 < 0.6 → 发布             │
  │     AssumptionConfidenceDecayed 事件     │
  └──────────┬───────────────────────────────┘
             │
             ▼
Stage 3: SP Assumption Revision Workflow
  ┌──────────────────────────────────────────┐
  │ Human-in-the-loop:                       │
  │  1. 通知 CEO/CSO（邮件+站内信）          │
  │  2. 提议修订值 + 证据链                  │
  │  3. 人类审批/拒绝/调整                   │
  │  4. 审批通过 → AssumptionRevised 事件    │
  │  5. 审批记录 → WORM 归档（审计）         │
  └──────────┬───────────────────────────────┘
             │
             ▼
Stage 4: Downstream Cascade
  ┌──────────────────────────────────────────┐
  │ 复用 ConsequenceChainEngine (Section 4)  │
  │ • 输入: AssumptionRevised 事件           │
  │ • traversal_mode = "system_deviation"    │
  │ • 与用户探索的区别: 持久化变更 + 通知链  │
  └──────────────────────────────────────────┘
```

### 6.2 数据契约：外部系统适配器

```python
# domain/v2/events/feedback_events.py

@dataclass(frozen=True)
class MilestoneAchieved(DomainEvent):
    """BP 举措里程碑达成"""
    event_type: str = field(default="MilestoneAchieved", init=False)
    initiative_id: str = ""
    milestone_name: str = ""
    achieved_date: str = ""  # ISO 8601
    data_source: str = ""    # "SAP_PS" | "manual" | "ERP"
    actual_value: float = 0.0
    unit: str = ""

@dataclass(frozen=True)
class BudgetActual(DomainEvent):
    """预算实际执行数据"""
    event_type: str = field(default="BudgetActual", init=False)
    budget_line_id: str = ""
    fiscal_period: str = ""  # "2026-05"
    planned_amount: float = 0.0
    actual_amount: float = 0.0
    variance_pct: float = 0.0
    data_source: str = ""

@dataclass(frozen=True)
class KPIReading(DomainEvent):
    """KPI 读数上报"""
    event_type: str = field(default="KPIReading", init=False)
    kpi_id: str = ""
    measured_value: float = 0.0
    measurement_date: str = ""
    data_source: str = ""    # "SAP_CO" | "IoT_sensor" | "manual"
    data_quality_score: float = 1.0  # 数据质量评分 0.0-1.0
```

**数据质量问题（CSO 的国产化率问题）：**

`KPIReading.data_quality_score` 字段是关键。当 KPI 自报为"绿色"但其他来源数据矛盾时：

```python
# infrastructure/v2/monitoring/data_quality_cross_validator.py

async def cross_validate_kpi(kpi_id: str, reported_value: float) -> DataQualityResult:
    """交叉验证 KPI 数据质量

    策略：
    1. Qdrant 语义检索：查找与 KPI 语义相关的其他指标
    2. Neo4j 图遍历：查找同一 Initiative 下的兄弟 KPI
    3. 相关性分析：如果兄弟 KPI 都指向负面趋势但此 KPI 为正，标记异常
    """
    related_kpis = await semantic_search_similar_kpis(kpi_id)
    related_kpis += await graph_traverse_sibling_kpis(kpi_id)

    if len(related_kpis) == 0:
        return DataQualityResult(score=1.0, anomaly=False)

    # Fisher 精确检验：此 KPI 与兄弟 KPI 方向是否一致
    direction_mismatch = sum(1 for k in related_kpis if k.trend != reported_value.trend)
    anomaly = direction_mismatch / len(related_kpis) > 0.7

    return DataQualityResult(
        score=1.0 - (direction_mismatch / len(related_kpis)),
        anomaly=anomaly,
    )
```

### 6.3 CUSUM 漂移检测

```python
# infrastructure/v2/monitoring/cusum_drift_detector.py

import math
from dataclasses import dataclass

@dataclass
class CUSUMConfig:
    """CUSUM 漂移检测配置

    校准方法：基于历史数据计算每个 KPI 的 μ 和 σ
    阈值 k = 0.5σ（检测 ±0.5σ 偏移）
    控制限 h = 4σ（对应 ARL0 ≈ 168 个数据点，即避免误报的平均运行长度）
    """
    target_mean: float         # 目标均值（来自 SP 假设）
    sigma: float               # 历史标准差
    k: float = 0.5             # 参考值（敏感性参数）
    h: float = 4.0             # 控制限（误报控制）
    window_size: int = 30      # 观测窗口大小

    @classmethod
    def calibrate(cls, historical_values: list[float]) -> "CUSUMConfig":
        """从历史数据校准 CUSUM 参数"""
        mu = sum(historical_values) / len(historical_values)
        sigma = math.sqrt(
            sum((v - mu) ** 2 for v in historical_values) / len(historical_values)
        )
        return cls(
            target_mean=mu,
            sigma=sigma,
            k=0.5 * sigma if sigma > 0 else 0.1,
            h=4.0 * sigma if sigma > 0 else 0.5,
        )


class CUSUMDetector:
    """CUSUM 累积和漂移检测器

    双侧检测：同时监控向上和向下漂移
    """

    def __init__(self, config: CUSUMConfig):
        self._cfg = config
        self._c_plus = 0.0   # 向上累积和
        self._c_minus = 0.0  # 向下累积和
        self._history: list[float] = []

    def update(self, value: float) -> CUSUMResult:
        """更新检测状态并返回漂移判定

        Returns:
            CUSUMResult: 包含漂移状态和累积统计量
        """
        self._history.append(value)
        standardized = (value - self._cfg.target_mean) / self._cfg.sigma if self._cfg.sigma > 0 else value

        # 双侧 CUSUM 更新
        self._c_plus = max(0, self._c_plus + standardized - self._cfg.k)
        self._c_minus = max(0, self._c_minus - standardized - self._cfg.k)

        # 漂移判定
        if self._c_plus > self._cfg.h:
            status = DriftStatus.UPWARD
        elif self._c_minus > self._cfg.h:
            status = DriftStatus.DOWNWARD
        else:
            status = DriftStatus.STABLE

        # 只保留窗口大小内的历史
        if len(self._history) > self._cfg.window_size * 2:
            self._history = self._history[-self._cfg.window_size:]

        return CUSUMResult(
            status=status,
            c_plus=self._c_plus,
            c_minus=self._c_minus,
            recent_mean=sum(self._history[-10:]) / min(len(self._history), 10),
        )
```

### 6.4 AUD Agent 偏差分析

```python
# application/v2/services/feedback_deviation_service.py

class FeedbackDeviationService:
    """阶段 2: 偏差分析服务

    AUD Agent 职责：
    1. 将执行的 KPI 映射到其战略假设（通过 Neo4j 图遍历）
    2. 运行 CUSUM 检测以识别实质偏差
    3. 重新校准假设置信度（贝叶斯更新）
    4. 发布 AssumptionConfidenceDecayed 事件（如果置信度降至临界值以下）
    """

    def __init__(
        self,
        graph_port: StrategicGraphPort,
        vector_port: L3VectorPort,
        event_publisher: EventPublisher,
    ):
        self._graph = graph_port
        self._vector = vector_port
        self._events = event_publisher

    async def analyze_deviation(
        self,
        kpi_event: KPIReading,
    ) -> DeviationAnalysisResult:
        # Step 1: Neo4j 反向遍历 KPI → Initiative → Assumption
        assumption_ids = await self._graph.traverse_upstream(
            start_node_id=kpi_event.kpi_id,
            start_label="KPI",
            target_labels={"StrategicAssumption"},
            max_depth=5,
        )

        if not assumption_ids:
            return DeviationAnalysisResult(linked_assumptions=[], drift_detected=False)

        # Step 2: 对每个关联的假设运行 CUSUM 检测
        results = []
        for asm_id in assumption_ids:
            # 获取次假设的历史 KPI 读数时间序列
            history = await self._get_kpi_history(asm_id)

            # 校准检测器并运行 CUSUM 更新
            detector = CUSUMDetector(CUSUMConfig.calibrate(history))
            cusum_result = detector.update(kpi_event.measured_value)

            if cusum_result.status != DriftStatus.STABLE:
                # Step 3: 贝叶斯置信度更新
                new_confidence = self._bayesian_confidence_update(
                    prior_confidence=await self._graph.get_assumption_confidence(asm_id),
                    evidence_strength=abs(cusum_result.c_plus + cusum_result.c_minus),
                    observation_count=len(history),
                )

                await self._graph.update_assumption_confidence(asm_id, new_confidence)

                results.append(
                    AssumptionDeviation(
                        assumption_id=asm_id,
                        cusum_status=cusum_result.status,
                        prior_confidence=await self._graph.get_assumption_confidence(asm_id),
                        new_confidence=new_confidence,
                        threshold_breach=new_confidence < 0.6,
                    )
                )

        # Step 4: 如果任何假设的置信度低于阈值，发布事件
        threshold_breaches = [r for r in results if r.threshold_breach]
        if threshold_breaches:
            await self._events.publish(
                AssumptionConfidenceDecayed(
                    deviations=threshold_breaches,
                    triggering_kpi_id=kpi_event.kpi_id,
                )
            )

        return DeviationAnalysisResult(
            linked_assumptions=results,
            drift_detected=any(r.cusum_status != DriftStatus.STABLE for r in results),
        )

    @staticmethod
    def _bayesian_confidence_update(
        prior_confidence: float,
        evidence_strength: float,
        observation_count: int,
    ) -> float:
        """贝叶斯置信度更新

        先验: 当前假设置信度 (0.0-1.0)
        似然: 证据强度（CUSUM 累积和的标准化值）
        权重: log(observation_count + 1) -- 观测越多，后验越强

        后验 = 先验 * (1 - 学习率 * 似然)
        """
        learning_rate = math.log(observation_count + 1) / math.log(100)  # 归一化到 [0,1]
        learning_rate = min(0.5, learning_rate)  # 上限 0.5，防止单次观测过度修正

        likelihood = min(1.0, evidence_strength / 10.0)  # 标准化为 [0,1]

        posterior = prior_confidence * (1 - learning_rate * likelihood)
        return round(max(0.1, posterior), 3)  # 下限 0.1，避免归零
```

### 6.5 人工审批工作流

```python
# application/v2/services/assumption_revision_service.py

class AssumptionRevisionService:
    """阶段 3: SP 假设修订工作流

    人工介入决策：系统提议修订，人来审批/拒绝/调整
    """

    async def propose_revision(
        self,
        deviation: AssumptionDeviation,
    ) -> AssumptionRevisionProposal:
        """基于检测到的偏差生成修订提案"""
        # 查询受影响的举措，计算建议的新值
        current_value = await self._graph.get_assumption_value(deviation.assumption_id)
        evidence_summary = await self._build_evidence_chain(deviation)

        proposed_value = self._compute_proposed_value(
            current_value=current_value,
            deviation=deviation,
        )

        proposal = AssumptionRevisionProposal(
            assumption_id=deviation.assumption_id,
            current_value=current_value,
            proposed_value=proposed_value,
            evidence_summary=evidence_summary,
            confidence_before=deviation.prior_confidence,
            confidence_after=deviation.new_confidence,
            proposed_by="AUD Agent (automated)",
            status="pending_review",
        )

        # 持久化提案
        await self._store_proposal(proposal)

        # 通知相关决策者
        await self._events.publish(
            AssumptionRevisionPending(
                proposal_id=proposal.id,
                assumption_id=deviation.assumption_id,
                notify_roles=["CEO", "CSO"],
            )
        )

        return proposal

    async def approve_revision(
        self,
        proposal_id: str,
        approver_id: str,
        adjusted_value: float | None = None,
    ) -> None:
        """审批人批准修订（可选择调整系统提议值）"""
        final_value = adjusted_value if adjusted_value is not None else proposal.proposed_value

        # 更新假设
        await self._graph.update_assumption(
            assumption_id=proposal.assumption_id,
            new_value=final_value,
            version_increment=True,
        )

        # 发布修订事件 → 触发阶段 4
        await self._events.publish(
            AssumptionRevised(
                assumption_id=proposal.assumption_id,
                old_value=proposal.current_value,
                new_value=final_value,
                revision_reason="deviation_detected",
                approved_by=approver_id,
                proposal_id=proposal_id,
            )
        )
```

### 6.6 阶段 4 -- 下游传导

阶段 4 完全复用 **ConsequenceChainEngine**（Section 3-4），区别仅在于调用参数：

```python
# AssumptionRevised 事件处理器
class AssumptionRevisedHandler:
    async def handle(self, event: AssumptionRevised) -> None:
        result = await self._ripple_service.execute_ripple_analysis(
            assumption_id=event.assumption_id,
            new_value=event.new_value,
            session_id=f"system-deviation-{event.assumption_id}",
            # 关键: 标记为系统偏差模式（非用户探索）
            mode="system_deviation",
        )
```

`mode="system_deviation"` 和 `mode="user_exploration"` 的区别：
- system_deviation: 变更持久化，通知链激活，审计级别 WORM
- user_exploration: 变更仅在会话内，仅通知操作者，审计级别 STANDARD

---

## 7. 事件系统设计

### 7.1 新增领域事件总览

| 事件类型 | 通道 | 触发时机 | 消费者 |
|---------|------|---------|--------|
| `AssumptionChanged` | RELIABLE | 用户修改假设参数 | GhostPreviewHandler, ConsequenceChainHandler |
| `GhostPreviewGenerated` | REALTIME | Ghost 计算完成 | WebSocket → 前端 SOC |
| `AIAnalysisStarted` | REALTIME | Prefect Flow 启动 | WebSocket → 前端 SOC |
| `AISynthesisComplete` | REALTIME | AI 综合研判完成 | WebSocket → 前端 SOC, ReportHandler |
| `ScoresResolved` | REALTIME | 所有得分解析完成 | WebSocket → 前端 SOC |
| `RippleComputationStarted` | RELIABLE | Prefect Flow 提交成功 | AuditHandler, NotificationHandler |
| `RippleComputationCompleted` | RELIABLE | Prefect Flow 完成 | AuditHandler, SOCDashboardHandler |
| `MilestoneAchieved` | RELIABLE | 外部系统数据上报 | FeedbackDeviationService |
| `BudgetActual` | RELIABLE | 外部系统数据上报 | FeedbackDeviationService |
| `KPIReading` | RELIABLE | 外部系统数据上报 | FeedbackDeviationService, DataQualityValidator |
| `AssumptionConfidenceDecayed` | RELIABLE | 置信度低于阈值 | AssumptionRevisionService, NotificationHandler |
| `AssumptionRevisionPending` | RELIABLE | 修订提案生成 | NotificationHandler (→邮件/站内信) |
| `AssumptionRevised` | RELIABLE | 人工审批通过 | ConsequenceChainHandler (→Stage 4), AuditHandler |
| `ContractFinancialRiskAlert` | RELIABLE | 合同可行性得分 < 0.6 | NotificationHandler, RiskDashboardHandler |

### 7.2 事件定义示例

```python
# domain/v2/events/ripple_events.py

from dataclasses import dataclass, field

from src.domain.events.base import DomainEvent


@dataclass(frozen=True)
class AssumptionChanged(DomainEvent):
    """用户修改假设参数"""
    event_type: str = field(default="AssumptionChanged", init=False)
    assumption_id: str = ""
    old_value: float = 0.0
    new_value: float = 0.0
    change_ratio: float = 0.0
    session_id: str = ""
    mode: str = "user_exploration"  # user_exploration | system_deviation

    def __post_init__(self) -> None:
        object.__setattr__(self, "aggregate_type", "StrategicAssumption")


@dataclass(frozen=True)
class ScoresResolved(DomainEvent):
    """所有得分解析完成 -- Ghost 替换信号"""
    event_type: str = field(default="ScoresResolved", init=False)
    session_id: str = ""
    assumption_id: str = ""
    resolved_scores: dict[str, float] = field(default_factory=dict)  # node_id → score
    analysis_duration_ms: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "aggregate_type", "AnalysisSession")
```

### 7.3 Event Channels 配置追加

在 `configs/event_channels.yaml` 中追加：

```yaml
  # =========================================================================
  # V2: Consequence Chain Events
  # =========================================================================
  AssumptionChanged:
    rabbitmq_routing_key: "sisys.events.reliable.assumption_changed"
    delivery_mode: "reliable"
    description: "用户修改战略假设参数"

  GhostPreviewGenerated:
    redis_channel: "sisys:rt:soc"
    delivery_mode: "realtime"
    description: "Ghost Preview 得分生成"

  AIAnalysisStarted:
    redis_channel: "sisys:rt:soc"
    delivery_mode: "realtime"
    description: "AI 分析管道启动"

  AISynthesisComplete:
    redis_channel: "sisys:rt:soc"
    delivery_mode: "realtime"
    description: "AI 综合研判完成"

  ScoresResolved:
    redis_channel: "sisys:rt:soc"
    delivery_mode: "realtime"
    description: "所有得分解析完成"

  RippleComputationStarted:
    rabbitmq_routing_key: "sisys.events.reliable.ripple_computation_started"
    delivery_mode: "reliable"
    description: "传导链重计算启动"

  RippleComputationCompleted:
    rabbitmq_routing_key: "sisys.events.reliable.ripple_computation_completed"
    delivery_mode: "reliable"
    description: "传导链重计算完成"

  MilestoneAchieved:
    rabbitmq_routing_key: "sisys.events.feedback.milestone_achieved"
    delivery_mode: "reliable"
    description: "BP 举措里程碑达成"

  BudgetActual:
    rabbitmq_routing_key: "sisys.events.feedback.budget_actual"
    delivery_mode: "reliable"
    description: "预算实际执行数据"

  KPIReading:
    rabbitmq_routing_key: "sisys.events.feedback.kpi_reading"
    delivery_mode: "reliable"
    description: "KPI 读数上报"

  AssumptionConfidenceDecayed:
    rabbitmq_routing_key: "sisys.events.reliable.assumption_confidence_decayed"
    delivery_mode: "reliable"
    description: "假设置信度衰减至临界值"

  AssumptionRevisionPending:
    rabbitmq_routing_key: "sisys.events.reliable.assumption_revision_pending"
    delivery_mode: "reliable"
    description: "假设修订提案等待审批"

  AssumptionRevised:
    rabbitmq_routing_key: "sisys.events.reliable.assumption_revised"
    delivery_mode: "reliable"
    description: "假设修订审批通过"

  ContractFinancialRiskAlert:
    rabbitmq_routing_key: "sisys.events.reliable.contract_financial_risk_alert"
    delivery_mode: "reliable"
    description: "合同财务风险预警"
```

同时在 `ChannelRouter.DEFAULT_MAPPINGS` 中同步追加。

---

## 8. 端口设计与组合根注册

### 8.1 新增领域端口

```python
# domain/v2/ports/consequence_chain_port.py

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class StrategicGraphPort(Protocol):
    """战略依赖图端口 —— 独立于记忆图（MemoryGraphPort）

    此端口定义战略依赖图的数据访问操作。
    与现有 L5GraphPort 的关系：
    - L5GraphPort: 通用记忆图操作（Memory 节点）
    - StrategicGraphPort: 战略领域专用图操作（StrategicAssumption, StrategicInitiative 等节点）
    二者共享 Neo4j 连接但使用不同的标签命名空间。
    """

    async def get_assumption_value(self, assumption_id: str) -> float:
        """获取假设当前值"""
        ...

    async def get_assumption_confidence(self, assumption_id: str) -> float:
        """获取假设置信度"""
        ...

    async def update_assumption_confidence(self, assumption_id: str, new_confidence: float) -> None:
        """更新假设置信度"""
        ...

    async def update_assumption(self, assumption_id: str, new_value: float, version_increment: bool) -> None:
        """更新假设值"""
        ...

    async def traverse_impact_paths(
        self,
        assumption_id: str,
        max_depth: int = 8,
    ) -> list[dict[str, Any]]:
        """前向传导 —— 从假设向下游查找所有受影响节点"""
        ...

    async def traverse_upstream(
        self,
        start_node_id: str,
        start_label: str,
        target_labels: set[str],
        max_depth: int = 5,
    ) -> list[str]:
        """反向传导 —— 从 KPI 向上游溯源到战略假设"""
        ...

    async def get_contract_viability_scores(self, initiative_ids: list[str]) -> dict[str, float]:
        """获取关联合同的财务可行性得分"""
        ...

    async def bootstrap_demo_graph(self) -> None:
        """初始化演示用依赖图（Week 1 硬编码数据）"""
        ...


@runtime_checkable
class GhostPreviewPort(Protocol):
    """Ghost Preview 端口

    提供假设变更的即时近似影响预估
    """

    async def compute_ghost_preview(
        self,
        assumption_id: str,
        old_value: float,
        new_value: float,
    ) -> dict[str, Any]:
        """计算 Ghost Preview 影响预估

        Returns:
            {
                "ghost_scores": {node_id: ghost_score, ...},
                "impacted_node_count": int,
                "estimated_duration_ms": int  # 总耗时
            }
        """
        ...


@runtime_checkable
class DriftDetectionPort(Protocol):
    """漂移检测端口

    CUSUM 统计过程控制
    """

    async def update_and_check(
        self,
        kpi_id: str,
        value: float,
        target_mean: float,
        sigma: float,
    ) -> dict[str, Any]:
        """更新 CUSUM 检测器并返回漂移状态"""
        ...
```

### 8.2 基础设施适配器

```python
# infrastructure/v2/neo4j/strategic_graph_adapter.py

class StrategicGraphAdapter(StrategicGraphPort):
    """StrategicGraphPort 的 Neo4j 基础设施实现

    使用与 L5GraphPort 相同的 Neo4j 连接（neo4j_driver 已注册端口），
    但操作不同的节点标签命名空间：
    - Memory 节点 → StrategicAssumption, StrategicInitiative, KPI, etc.
    """

    def __init__(self, neo4j_driver: AsyncDriver):
        self._driver = neo4j_driver

    async def traverse_impact_paths(
        self,
        assumption_id: str,
        max_depth: int = 8,
    ) -> list[dict[str, Any]]:
        """执行 APOC 路径扩展"""
        async with self._driver.session() as session:
            result = await session.run(
                """...""",  # 见 Section 3.1 的 Cypher 查询
                assumption_id=assumption_id,
                max_depth=max_depth,
            )
            return [record.data() for record in await result.fetch()]
```

### 8.3 组合根注册

在 `src/composition_root.py` 的 `bootstrap()` 函数中追加：

```python
# === V2: 战略传导链引擎 ===

from src.domain.v2.ports.consequence_chain_port import StrategicGraphPort, GhostPreviewPort
from src.infrastructure.v2.neo4j.strategic_graph_adapter import StrategicGraphAdapter
from src.infrastructure.v2.preview.ghost_preview_compute import GhostPreviewService
from src.infrastructure.v2.monitoring.cusum_drift_detector import CUSUMDetectorFactory

register_port(
    name="strategic_graph",
    version="v1.0.0",
    interface=StrategicGraphPort,
    impl=lambda resolver: StrategicGraphAdapter(
        neo4j_driver=resolver.resolve("neo4j_driver"),
    ),
    module="src.infrastructure.v2.neo4j.strategic_graph_adapter",
    lifetime=Lifetime.SCOPED,
    owner="strategy-team",
    tags=("neo4j", "strategy", "graph"),
)

register_port(
    name="ghost_preview",
    version="v1.0.0",
    interface=GhostPreviewPort,
    impl=lambda resolver: GhostPreviewService(
        graph_port=resolver.resolve("strategic_graph"),
    ),
    module="src.infrastructure.v2.preview.ghost_preview_compute",
    lifetime=Lifetime.SCOPED,
    owner="strategy-team",
    tags=("ghost", "preview"),
)

register_port(
    name="drift_detector",
    version="v1.0.0",
    interface=DriftDetectionPort,
    impl=lambda resolver: CUSUMDetectorFactory(),
    module="src.infrastructure.v2.monitoring.cusum_drift_detector",
    lifetime=Lifetime.SCOPED,
    owner="strategy-team",
    tags=("monitoring", "drift"),
)
```

### 8.4 异常体系追加

在 `src/domain/exceptions/_code_ranges.py` 的 `CODE_RANGES` 中追加：
```python
    # 战略子域（271-279）
    "strategy": (271, 279),
```

在 `_CLASS_TO_SUBDOMAIN` 中追加：
```python
    "AssumptionNotFoundError": "strategy",
    "ImpactTraversalError": "strategy",
    "GhostComputationError": "strategy",
    "FeedbackIngestionError": "strategy",
```

新异常文件：`src/domain/v2/exceptions/strategy_exceptions.py`
```python
"""领域层 V2 战略异常模块"""

from src.domain.exceptions.base_exceptions import BusinessException


class AssumptionNotFoundError(BusinessException):
    code = "EXCEPTION_271"
    message_template = "战略假设未找到: {assumption_id}"


class ImpactTraversalError(BusinessException):
    code = "EXCEPTION_272"
    message_template = "影响传导图遍历失败 [from={assumption_id}]: {detail}"


class GhostComputationError(BusinessException):
    code = "EXCEPTION_273"
    message_template = "Ghost 预览计算失败: {detail}"


class FeedbackIngestionError(BusinessException):
    code = "EXCEPTION_274"
    message_template = "执行数据回传失败 [source={data_source}]: {detail}"
```

---

## 9. "先做一件事" 实现计划

### 9.1 四周 Sprint 计划

```
Week 1: Neo4j 依赖图搭建 + 初始数据
  ├─ Day 1-2: Neo4j 模式设计（标签、关系、索引）
  ├─ Day 3-4: StrategicGraphAdapter 实现（traverse_impact_paths, bootstrap_demo_graph）
  ├─ Day 5: 硬编码 1 个演示场景依赖图数据（赵总 6 跳案例）
  └─ 验证: Cypher 查询返回正确 6 跳传导链

Week 2: 图遍历查询 + 确定性重计算 + Prefect Flow
  ├─ Day 1-2: APOC 遍历查询 + impact_weight 衰减算法
  ├─ Day 3-4: Prefect ripple_recomputation_flow 实现
  ├─ Day 5: 确定性 Ghost 公式实现
  └─ 验证: POST /v2/assumption/change → 返回受影响节点列表 + 预估得分

Week 3: Ghost Preview 端点 + 乐观 UI + Resolve 过渡
  ├─ Day 1-2: GhostPreviewService → /v2/ghost/preview 端点
  ├─ Day 3-4: GhostPreviewGenerated → WebSocket → 前端 Ghost UI 渲染
  ├─ Day 5: AI 分析启动 → AgentDecided → AISynthesisComplete → ScoresResolved 完整事件链路
  └─ 验证: 修改假设 → 200ms 半透明 UI → 7s 后平滑过渡到真实得分

Week 4: 集成测试 + 端到端演示
  ├─ Day 1-2: 集成测试（Neo4j + Prefect + RabbitMQ 联合）
  ├─ Day 3-4: 前端 SOC 界面（承诺墙 + 传导链可视化 + Ghost 效果）
  └─ Day 5: 端到端演示准备
```

### 9.2 Week 4 演示场景（精确规格）

**场景名称：** "赵总的噩梦：当市场增长率减半"

**具体数据（硬编码到 Neo4j 演示图）：**

```
战略假设 #1:
  market_growth_rate = 15% (confidence=0.78, owner=CSO)

依赖链：
  market_growth_rate
    └→ Initiative-A: 电池工厂产能扩建 (budget=28亿, owner=COO)
        ├→ KPI-A1: 年产能 50GWh
        ├→ BudgetLine-A: 2026 Capex 12亿 (committed 4.5亿)
        ├→ TalentNeed-A: 工艺工程师 120人 (current 34人)
        │   └→ Contract-A: 合工大培养协议 (value=1.2亿, penalty=30%)
        ├→ ChannelDealer-A: 华东经销商 (350家, subsidy=1.75亿已发放)
        └→ CashFlowCycle-A: 电池业务 (CCC=75天, DSCR=2.3)
            └→ SupplierPaymentTerms-A: 供应商 60天账期
```

**具体用户操作：**
1. CEO 登录 SOC 界面
2. 在"战略假设"面板中点击 `market_growth_rate`
3. 将滑块从 15% 拖到 6%
4. 点击"分析影响"

**具体系统响应（按时间线）：**

```
T+0ms:    滑块值变更 → AssumptionChanged 事件
T+50ms:   前端显示 "正在计算影响..."
T+150ms:  Ghost Preview 到达
          ┌─────────────────────────────────────┐
          │ 影响预估 (Ghost)                      │
          │                                      │
          │ 受影响节点: 8                        │
          │                                      │
          │ 🏭 电池工厂产能   得分: 0.52 [0.47-0.57]
          │ 📊 年产能 50GWh   目标: 20.0 GWh     │
          │ 💰 2026 Capex     调整: 7.2亿 (-40%) │
          │ 👥 工艺工程师      需求: 72人 (-40%)  │
          │ 📝 合工大协议      可行性: 0.52 ⚠️   │
          │ 🏪 华东经销商      ROI风险: 高       │
          │ 💵 电池业务CCC     CCC: 45天 (改善)  │
          │ 📋 供应商账期      风险: 延长至90天   │
          │                                      │
          │ ⏳ AI 详细分析中...                   │
          └─────────────────────────────────────┘
          (半透明样式 + 脉冲动画)

T+1000ms: AIAnalysisStarted → "AI 分析中..." 进度条
T+2000ms: AgentDecided (CFO) → 财务影响细节填充
T+3500ms: AgentDecided (COO) → 运营影响细节填充
T+5000ms: AgentDecided (CHO) → 人力影响细节填充
T+6500ms: AISynthesisComplete → 综合研判完整
T+6700ms: ScoresResolved → UI 过渡动画
T+7000ms: 最终视图
          ┌─────────────────────────────────────┐
          │ 影响分析 (已确认)                     │
          │                                      │
          │ 🏭 电池工厂产能   得分: 0.49          │
          │   - 产能目标下调至 18GWh              │
          │   - 建设周期延长 2 个季度             │
          │                                      │
          │ ⚠️ 📝 合工大协议  可行性: 0.48 红色   │
          │   - 潜在违约金: 3600万                │
          │   - 建议: 重新谈判培训规模降低50%     │
          │                                      │
          │ ⚠️ 🏪 华东经销商  已发放补贴回收风险  │
          │   - 1.75亿不可回收支出                │
          │   - 建议: 冻结新增经销商签约          │
          │                                      │
          │ CEO 综合研判:                         │
          │ "市场增长率减半情景下，电池业务线     │
          │  面临三大风险：产能过剩、合同违约、   │
          │  渠道补贴沉没。建议立即启动 Scenario   │
          │  Planning 并通知董事会。"             │
          └─────────────────────────────────────┘
```

**成功标准（证明 V2 原型可行）：**
1. Ghost Preview 在 200ms 内渲染
2. Ghost 得分与最终 AI 得分偏差不超过 20%
3. 6 跳传导链完整展示（从市场增长率到供应商账期）
4. 合同财务可行性风险自动检测并红色标注
5. 多 Agent 分析结果在 7s 内到达
6. Ghost → Resolved 过渡无闪烁

---

## 10. 冷启动解决方案

### 10.1 Neo4j 依赖图的冷启动

**策略：硬编码演示数据 + 从 PRD 中提取结构。**

```python
# infrastructure/v2/neo4j/strategic_graph_adapter.py

async def bootstrap_demo_graph(self) -> None:
    """V2 原型第 1 周：从 PRD 的 BLM/BEM 框架初始化演示数据

    硬编码 1 个完整的 6 跳传导链场景，足以演示系统能力。
    后续迭代中替换为：
    1. 从 BLM 阶段文档中自动提取假设（Qdrant RAG → Neo4j）
    2. 从 BP 计划文档中自动提取举措（文档解析 → 实体提取 → Neo4j）
    """
    # 创建演示假设
    await self._run("""
        CREATE (a:StrategicAssumption {
            id: "uuid-market-growth-2026",
            label: "中国新能源汽车市场年增长率",
            category: "market",
            current_value: 0.15,
            unit: "percentage",
            confidence: 0.78,
            owner: "CSO",
            blm_phase: "market_insight",
            source_document_id: "uuid-prd-v3",
            version: 3,
            drift_status: "stable"
        })
    """)

    # 创建 6 跳传导链数据
    await self._run("""
        // 创建举措节点
        CREATE (i:StrategicInitiative {
            id: "uuid-ev-battery-plant",
            label: "动力电池工厂产能扩建",
            category: "capacity_expansion",
            budget_total: 2.8e9,
            budget_allocated: 8.5e8,
            time_window_start: "2026-Q1",
            time_window_end: "2028-Q4",
            current_phase: "construction",
            owner: "COO",
            priority: "P0",
            status: "in_progress"
        })

        // 创建关联关系
        MATCH (a:StrategicAssumption {id: "uuid-market-growth-2026"})
        MATCH (i:StrategicInitiative {id: "uuid-ev-battery-plant"})
        CREATE (a)-[r:DRIVES {
            impact_weight: 0.85,
            description: "市场增长率每降低1pp，产能需求预期降低8%"
        }]->(i)
    """)

    # 创建 KPI、预算、人力、合同、渠道、现金流的完整链
    # ... (完整 Cypher 脚本省略，见 Section 2.3 的建模)
```

### 10.2 Ghost Preview 的冷启动

**策略：纯确定性公式，不依赖学习模型。**

V2 原型的 Ghost Preview 就是确定性模型（Section 5.2）。不需要训练数据。

当系统积累了足够的 (<assumption_change, deterministic_ghost_score, final_ai_score>) 三元组后（预计 50+ 个样本），可以训练一个轻量级回归器来改进 Ghost 精度。但这不在 V2 原型范围内。

**Cold start Ghost 公式的优势：**
- 逻辑完全透明（Excel 能验证）
- 立即可用（零训练时间）
- 错误方向可预测（确定性偏差可分析）
- Ghost 和 Resolved 之间的偏差本身就是价值信号（说明 AI 发现了确定性模型未捕获的因素）

### 10.3 AI Agent 质量的冷启动

**策略：结构化提示工程 + 领域知识注入。**

在多 Agent LangGraph 分析管道中，每个 Agent 接收的不只是裸数据，还包含：
1. **上下文窗口注入：** 当前 SP 文档片段（通过 Qdrant RAG 检索相关段）
2. **角色指令：** 每个 Agent 的系统提示对应其角色（CFO 看财务，COO 看运营）
3. **结构化模板：** 要求 Agent 输出结构化 JSON（得分 + 推理 + 证据）

```python
# infrastructure/v2/agent_orch/prompts/cfo_prompt.py

CFO_SYSTEM_PROMPT = """你是企业的首席财务官（CFO）。你的职责是评估战略假设变更的财务影响。

你需要分析：
1. 预算冲击：受影响的预算科目金额变化及百分比
2. 现金流影响：现金流周期的变化方向及幅度
3. 合同风险：已签约合同中触发财务风险的条款
4. 融资影响：是否需要调整融资计划

输出 JSON 格式：
{
  "budget_impacts": [{"budget_line": "...", "delta_cny": ..., "delta_pct": ...}],
  "cash_flow_change": {"ccc_before": ..., "ccc_after": ..., "direction": "..."},
  "contract_risks": [{"contract": "...", "risk_type": "...", "potential_loss_cny": ...}],
  "overall_financial_score": 0.0-1.0,
  "reasoning": "..."
}
"""
```

这种方法的局限性：对真正的新奇情景推理能力弱。改进路径是：
- 在积累足够的已审批修订案例后，对 Agent 进行微调
- 但 V2 原型不依赖微调

### 10.4 CEO 的 "历史预测 vs 实际" 要求的冷启动

**策略：反向生成"后见之明"对比。**

CEO 说："给我看系统过去的预测准确率。" 但系统在 V1 没有做过任何预测。

**冷启动方案：**
1. 选取 1-2 条去年的战略假设（手动从董事会材料中提取）
2. 人工回溯去年此时 BP 计划中的关键假设值
3. 用 SISYS V2 对去年的假设进行"回顾分析"（backtest）
4. 将 SISYS 的传导链预测与去年实际发生的情况进行对比
5. 生成一份 "SISYS 后见之明验证报告"

这是唯一有意义的"历史准确率"冷启动方式。它不是真实的运行数据，但它证明了系统的推理逻辑。

**具体示例：**
```
假设: 2024年Q1 市场增长率从 20% 下调到 12%
SISYS 回溯分析: 产能扩张计划应缩减 35%，人才需求应削减 40%
2024年实际:    产能扩张计划缩减了 30%，人才冻结到 Q3
准确率:        规划偏差 5pp（SISYS 略微保守）
```

---

## 附录 A: 关键设计决策记录

### ADR-V2-001: Ghost Preview 使用确定性模型而非学习模型

**状态：** 已接受
**上下文：** V2 原型需要在 200ms 内提供即时预览，但没有任何训练数据。
**决策：** 使用确定性线性加权公式（`impact_ratio * cumulative_weight^hop_count`），而非 ML 回归器。
**后果：**
- 优点：零冷启动延迟、完全透明的逻辑、错误方向可预测
- 缺点：精度上限约 85% vs AI 结果、无法捕获非线性交互效应
- 未来：积累 50+ 样本后引入 LightGBM 作为 Ghost 增强（可选）

### ADR-V2-002: StrategicGraphPort 与 L5GraphPort 分离

**状态：** 已接受
**上下文：** 已有的 L5GraphPort 专门用于记忆图（Memory 节点），V2 需要战略依赖图（StrategicAssumption 等节点）。
**决策：** 新增独立端口 StrategicGraphPort，共享同一 Neo4j 驱动，但使用不同标签命名空间。
**后果：**
- 优点：领域隔离清晰、独立演进、不影响已有记忆图功能
- 缺点：需要维护两个图端口（但代码量很小，StrategicGraphPort 约 15 个方法）

### ADR-V2-003: 闭环反馈使用季度批处理

**状态：** 已接受
**上下文：** 实时闭环反馈需要持续的数据流和实时 CUSUM 检测，但 V2 原型阶段外部系统集成不成熟。
**决策：** V2 原型中使用季度批处理模式（手动上传上个季度的执行数据 CSV），事件通道已就绪可切换为实时。
**后果：**
- 优点：降低原型复杂度、避免对外部系统的依赖、数据质量可控
- 缺点：不是真正的"实时"闭环（但架构已支持未来切换）

### ADR-V2-004: 硬编码演示依赖图

**状态：** 已接受
**上下文：** 第 1 周需要可用的 Neo4j 依赖图来演示系统功能，但没有自动从 PRD/BP 文档中提取假设的数据管道。
**决策：** 第 1 周硬编码 1 个完整的 6 跳传导场景数据。第 2 周开始建立自动提取管道。
**后果：**
- 优点：第 1 周即可运行端到端测试
- 缺点：演示场景覆盖范围窄（仅 1 个假设、1 条链）
- 缓解：6 跳案例足够展示完整的传导能力
