"""Story AC 与 architecture.md 一致性校验流程文档

SISYS 项目在 Epic 1 中发现 Story AC（验收标准）与 architecture.md 存在多处技术参数不一致问题，
包括默认值、性能阈值、命名、路由策略等维度。本文档定义在 Story 创建阶段进行一致性校验的标准流程，
确保 Story AC 始终以 architecture.md 为唯一事实源（Single Source of Truth）。

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.
"""

# Story AC 与 architecture.md 一致性校验流程

**版本:** 1.0.0
**日期:** 2026-05-25
**用途:** Story 创建阶段（create-story 工作流）中 AC 与架构文档技术参数的一致性校验
**关联文档:** `docs/architecture/architecture.md`、`docs/developer/story-template.md`

---

## 1. 问题描述

SISYS 项目在 Epic 1 开发过程中发现，Story AC（验收标准）中的技术参数与 `architecture.md`
定义的架构决策存在多处不一致。这些不一致导致开发阶段反复修正，增加审查迭代轮次。

### 1.1 Epic 1 典型不一致案例

| Story | 不一致项 | Story AC 值 | architecture.md 值 | 影响 |
|-------|---------|------------|-------------------|------|
| 1.17 | 路由策略 | 云端优先 | 云端优先 80%，本地兜底 | ~~架构方向偏离~~ 已对齐 |
| 1.17 | 路由延迟 P95 | <100ms | MVP <100ms / V1 <50ms（公理一明确 <50ms） | 验收阈值不精确 |
| 1.17 | 路由方式 | 静态路由 | UDMR 动态三层决策 | 核心机制缺失 |
| 1.18b | api_url 默认端口 | 8123 | 8000（FastAPI 标准端口） | 配置错误 |
| 1.18b | graph_timeout_seconds | 3600 | 1800 | 超时配置偏离 |
| 1.18b | 节点命名 | analysis | analyze（与 API 路由 /financial/analyze 一致） | 命名不统一 |

### 1.2 根因分析

不一致的根因是 Story 创建阶段缺少对 architecture.md 的系统性参数校验。create-story 工作流
依赖人工记忆提取技术参数，而 architecture.md 作为 ~3300 行的综合架构文档，技术参数散布在
多个章节（公理定义、NFR 指标表、UDMR 设计、存储架构等），人工提取容易遗漏或记忆偏差。

### 1.3 目标

在 Story 创建阶段增加自动化/半自动化的一致性校验步骤，确保：
- Story AC 中的技术参数与 architecture.md 保持一致
- 不一致项在 Story 进入 `ready-for-dev` 之前被发现并修正
- 减少 review 阶段因参数不一致导致的审查迭代

---

## 2. 校验时机

一致性校验嵌入 **create-story 工作流**中，位于 Story 文件生成之后、状态设置为 `ready-for-dev`
之前。

### 2.1 在 create-story 流程中的位置

```
create-story 工作流:
    Step 1: 从 epics_v1.0.md 提取 Story 需求
    Step 2: 从 architecture.md 提取架构约束
    Step 3: 生成 Story 文件（AC / Tasks / 测试规划）
    Step 4: ★ AC 一致性校验（本文档定义）★    ← 在此步骤执行
    Step 5: 修正不一致项
    Step 6: 设置状态为 ready-for-dev
```

### 2.2 校验触发条件

- **必须校验**：每个新 Story 创建时
- **必须校验**：Story AC 发生变更时（含 review 修正后的更新）
- **建议校验**：architecture.md 技术参数更新后，对 affected 的已创建 Story 进行回溯校验

---

## 3. 校验维度

校验覆盖以下五个维度，每个维度列举需要关注的典型参数类型。

### 3.1 默认值校验

确保 Story AC 中引用的配置默认值与 architecture.md 定义的值完全一致。

**典型校验项：**

| 参数类别 | 校验要点 | architecture.md 参考章节 |
|---------|---------|------------------------|
| 端口号 | FastAPI 默认端口 8000（非 8123） | 技术栈选型 |
| 超时值 | 单轮超时 30 秒、graph_timeout 与架构定义一致 | Agent 标准工作流、存储架构 |
| 重试次数 | 事件发布重试、存储操作重试与架构定义一致 | 事件驱动架构设计 |
| TTL 值 | Redis 状态快照 TTL 24h-30d、事件去重 TTL 7 天 | 存储架构设计 |
| 并发数 | 并发 Agent 会话 MVP 10 / V1 50 / V2 200 | 关键架构指标 |

### 3.2 性能阈值校验

确保 Story AC 中的性能指标与 architecture.md 的 NFR（非功能需求）指标表一致，
且需明确 MVP / V1 / V2 版本对应的阈值。

**architecture.md 关键性能指标参考（1.4 节）：**

| 指标 | MVP 目标 | V1 目标 | V2 目标 |
|------|---------|--------|--------|
| 检索延迟 P95 | <800ms | <500ms | <300ms |
| 路由决策延迟 P95 | <100ms | <50ms | <30ms |
| 图遍历查询 P95（简单） | <200ms | <150ms | <100ms |
| 图遍历查询 P95（复杂） | <800ms | <600ms | <400ms |
| CLI 命令响应延迟 P95 | <1s | <500ms | <200ms |
| SAP 消息传递延迟 P95 | <500ms | <200ms | <100ms |

**校验要点：**
- Story AC 必须明确引用哪个版本（MVP/V1/V2）的阈值
- 公理级别的硬性指标（如系统公理一要求 P95<50ms）优先于 NFR 表格中的分版本值
- 检索延迟 P95<800ms 为 MVP 阶段目标，公理一要求路由决策延迟 P95<50ms 为系统公理硬约束

### 3.3 命名一致性校验

确保 Story AC 中使用的命名（节点名、参数名、文件路径、API 路径）与 architecture.md
定义的命名规范一致。

**典型校验项：**

| 命名类型 | 校验要点 | 不一致案例 |
|---------|---------|-----------|
| LangGraph 节点名 | 与 architecture.md 目录树和代码示例一致 | analysis vs analyze（应为 analyze，与 /financial/analyze 一致） |
| Config 字段名 | 与架构定义的字段名完全匹配 | graph_timeout_seconds 默认值 3600 vs 1800 |
| API 路径 | 与 architecture.md API 路由表一致 | /analysis vs /analyze |
| 文件路径 | 与 architecture.md 目录结构参考一致 | 错误的模块放置位置 |
| 存储层端口名 | l0_storage / l1_cache / l2_rdb / l3_vector / l4_object / l5_graph | 端口命名从 0 开始而非 1 |

### 3.4 路由策略校验

确保 Story AC 中的路由策略与 architecture.md 的 UDMR（统一动态模型路由框架）设计一致。

**architecture.md 路由策略定义：**

| 策略维度 | architecture.md 定义 | 常见错误 |
|---------|---------------------|---------|
| 路由优先级 | 云端优先 80%，本地兜底 | 写成"本地优先" |
| 路由方式 | UDMR 三层动态决策（L1 合规→L2 评估→L3 执行） | 写成"静态路由" |
| 路由延迟 | P95<50ms（系统公理一硬约束） | 写成 P95<100ms |
| 成本目标 | Token 成本追踪与度量（MVP） | 缺失成本维度 |
| 本地模型路由占比 | MVP 本地兜底 / V1 云端路由≥80% | 引用错误版本值 |

### 3.5 配置字段校验

确保 Story AC 中引用的所有 Config 类（如 PrefectConfig、LiteLLMConfig、Neo4jConfig 等）
的字段名和默认值与 architecture.md 中的定义一致。

**校验要点：**
- 每个 Config 字段的默认值必须与 architecture.md 定义匹配
- 新增 Config 字段必须在 architecture.md 中有对应定义或记录为架构扩展
- Config 字段的类型标注必须与 architecture.md 一致（int vs float、str vs Optional[str]）

---

## 4. 校验步骤

### Step 1: 从 architecture.md 提取相关技术参数

**操作：** 根据新建 Story 的功能范围，从 architecture.md 中提取所有相关的技术参数。

**提取范围按 Story 类型划分：**

| Story 类型 | 必查章节 |
|-----------|---------|
| 路由/模型相关 | 1.2 系统公理一、1.4 关键架构指标、4 UDMR 框架 |
| 存储/检索相关 | 11 存储架构设计、1.4 检索延迟指标 |
| Agent/编排相关 | 1.2 系统公理、8 Checkpoint 机制、17 核心领域架构 |
| 事件/消息相关 | 10 事件驱动架构设计、config/event_channels.yaml |
| 安全相关 | 15 风险缓解、附录 K Agent 沙箱安全策略 |
| API/接口相关 | 1.5 CLI+Skills 原则、1.6 四层映射架构、13 完整目录结构 |

**输出：** 技术参数清单（含章节号、参数名、architecture.md 值、版本标注）。

### Step 2: 逐项对照 Story AC 中的技术参数

**操作：** 将 Step 1 提取的参数清单与 Story AC 逐项对照。

**对照表格模板：**

| # | 参数名 | architecture.md 值 | Story AC 值 | 一致性 | 差异说明 |
|---|--------|-------------------|------------|--------|---------|
| 1 | 路由决策延迟 P95 | <100ms（MVP）/ <50ms（公理一） | — | — | — |
| 2 | 路由策略 | 云端优先 80%，本地兜底 | — | — | — |
| 3 | api_url 默认端口 | 8000 | — | — | — |
| 4 | ... | ... | ... | ... | ... |

**对照规则：**
- 数值型参数：完全匹配（允许精度差异，如 8000 vs 8123 不允许）
- 枚举型参数：值完全一致（如 analysis vs analyze 视为不一致）
- 策略型参数：语义一致（如"本地优先"与"云端优先"为语义冲突）
- 版本型参数：需标注 MVP/V1/V2，Story AC 引用错误的版本阈值视为不一致

### Step 3: 不一致项标记并修正

**操作：** 对 Step 2 发现的不一致项进行标记，并确定修正方案。

**修正原则：**
- **architecture.md 为唯一事实源**：不一致时以 architecture.md 为准修正 Story AC
- **公理级硬约束优先**：系统公理（如 P95<50ms）的约束力高于 NFR 表格的分版本值
- **架构扩展需评审**：如确需修改 architecture.md 的参数，必须经架构评审通过后方可修改

**不一致项标记格式：**

```
[不一致] #N: [参数名]
  - architecture.md 值: [值]（章节 [X.X]）
  - Story AC 值: [值]（AC-N）
  - 修正方案: [以 architecture.md 为准 / 需架构评审修改 architecture.md]
  - 修正状态: [待修正 / 已修正]
```

---

## 5. 常见不一致模式

基于 Epic 1（23 个 Story）的实际经验，总结以下高频不一致模式，供校验时重点关注。

### 模式 1: 版本阈值混用

**表现：** Story AC 引用了错误版本（如 V1）的性能阈值，但当前开发阶段为 MVP。

**案例：** Story 1.17 中路由延迟 P95 写成 <50ms（V1 目标），实际 MVP 应为 <100ms。

**防范：** 校验时必须确认 Story 所在 Epic/Sprint 的版本阶段，引用对应版本的 NFR 阈值。

### 模式 2: 端口号/超时值凭记忆填写

**表现：** 开发者凭记忆填写默认端口号或超时值，与 architecture.md 定义不符。

**案例：** Story 1.18b 中 api_url 默认端口写成 8123，实际应为 8000；graph_timeout_seconds
写成 3600，实际应为 1800。

**防范：** 所有涉及端口号、超时值、重试次数的默认值，必须从 architecture.md 原文提取，
禁止凭记忆填写。

### 模式 3: 节点命名不一致

**表现：** LangGraph 节点名、API 路径中的动词/名词与 architecture.md 定义不匹配。

**案例：** Story 1.18b 中节点命名为 analysis，architecture.md 中 API 路由为
/financial/analyze，节点命名应为 analyze 以保持一致。

**防范：** 校验时将 Story AC 中的所有命名与 architecture.md 的 API 路由表、目录结构
参考中的命名逐项比对。

### 模式 4: 路由策略方向偏离

**表现：** Story AC 中的路由策略与 architecture.md 的核心设计方向不一致。

**案例：** Story 中写成"本地优先"，architecture.md 明确为"云端优先 80%，本地兜底"；
写成"静态路由"，实际应为 UDMR 动态三层决策。

**防范：** 涉及路由、模型选择、成本优化的 Story，必须校验 UDMR 章节（architecture.md
第 4 章）的策略定义。

### 模式 5: Config 字段名或默认值偏离

**表现：** Story AC 中 Config 类的字段名、类型或默认值与 architecture.md 定义不一致。

**案例：** 新增 Config 字段时，字段名使用了不同的命名风格（如 snake_case vs camelCase），
或默认值与架构定义不同。

**防范：** 新增或修改 Config 类时，必须对照 architecture.md 中对应章节的字段定义，
确保字段名、类型、默认值完全一致。

### 模式 6: 存储层端口编号错误

**表现：** 存储层端口命名使用了错误的起始编号。

**案例：** 将存储层端口从 l1 开始编号，实际应为 l0_storage（文件系统）→ l1_cache（Redis）
→ l2_rdb（PostgreSQL）→ l3_vector（Qdrant）→ l4_object（MinIO）→ l5_graph（Neo4j）。

**防范：** 涉及存储层的 Story，校验端口命名必须从 L0 开始，参照 architecture.md
存储架构设计章节。

---

## 6. 检查清单

以下检查清单在每次 create-story 工作流执行时逐项勾选。

### 6.1 默认值检查

- [ ] 所有端口号默认值已与 architecture.md 技术栈章节对照（如 FastAPI 端口 8000）
- [ ] 所有超时值默认值已与 architecture.md 对应章节对照（如单轮超时 30 秒）
- [ ] 所有重试次数默认值已与 architecture.md 事件/存储架构章节对照
- [ ] 所有 TTL 值已与 architecture.md 存储架构章节对照（如 Redis TTL 24h-30d）
- [ ] 所有并发数阈值已与 architecture.md 关键架构指标表（1.4 节）对照

### 6.2 性能阈值检查

- [ ] Story AC 中每个性能指标已明确标注版本（MVP/V1/V2）
- [ ] P95 延迟阈值已与 architecture.md 1.4 节 NFR 指标表逐项对照
- [ ] 系统公理级硬约束（如路由决策延迟 P95<50ms）优先于 NFR 表格分版本值
- [ ] QPS / 吞吐量指标已与 architecture.md 对应章节对照
- [ ] 可用性指标（99%/99.5%/99.9%）已按版本正确引用

### 6.3 命名一致性检查

- [ ] LangGraph 节点名与 architecture.md 目录树和代码示例一致（如 analyze 而非 analysis）
- [ ] API 路径与 architecture.md API 路由表一致（如 /financial/analyze）
- [ ] Config 字段名与 architecture.md 定义完全匹配（包括命名风格和拼写）
- [ ] 文件路径与 architecture.md 13 章目录结构参考一致
- [ ] 存储层端口命名正确（l0_storage → l5_graph，从 0 开始）

### 6.4 路由策略检查

- [ ] 路由优先级为"云端优先 80%，本地兜底"（非"本地优先"）
- [ ] 路由方式为"UDMR 三层动态决策"（非"静态路由"）
- [ ] 路由延迟引用正确的版本阈值（公理一硬约束 P95<50ms）
- [ ] 云端路由占比引用正确（≥80% V1）

### 6.5 配置字段检查

- [ ] 所有 Config 类字段名已与 architecture.md 对应章节逐一比对
- [ ] 所有 Config 字段默认值已与 architecture.md 定义完全一致
- [ ] 所有 Config 字段类型标注已与 architecture.md 一致（int/float/str/Optional）
- [ ] 新增 Config 字段已在 architecture.md 中有对应定义或记录为架构扩展
- [ ] Config 字段注入方式正确（原始值注入 domain 层，Config 对象仅在 infrastructure 层）

### 6.6 校验完成确认

- [ ] Step 1-3 已全部执行完毕（参数提取 → 逐项对照 → 不一致修正）
- [ ] 不一致项修正后已二次校验确认一致
- [ ] 校验结果已记录在 Story 文件的"完成清单"中
- [ ] 如有 architecture.md 参数变更需求，已提交架构评审

---

## 附录：参考信息

### A. architecture.md 关键参数速查索引

| 参数类型 | 章节 | 关键参数 |
|---------|------|---------|
| 系统公理 | 1.2 | P95<50ms 路由延迟、P95<800ms 检索延迟 |
| NFR 指标表 | 1.4 | 全部性能/可用性/质量/成本/接口指标 |
| UDMR 框架 | 4 | 云端优先 80%、三层决策、本地兜底 |
| 事件架构 | 10 | 双通道总线、事件类型、TTL |
| 存储架构 | 11 | L0-L5 存储层、同步延迟 |
| 技术栈 | 12 | 端口号、版本号、驱动版本 |
| 目录结构 | 13 | 文件路径、模块命名 |
| 核心领域 | 17 | Agent 工作流、节点命名、Config 定义 |

### B. 相关文档

| 文档 | 说明 |
|------|------|
| `docs/architecture/architecture.md` | 架构设计主文档（唯一事实源） |
| `docs/developer/story-template.md` | Story 创建模板 |
| `docs/developer/review-feedback-checklist.md` | 代码审查反馈检查清单 |
| `docs/developer/sdd-tdd-fusion-guide.md` | SDD+TDD 融合开发模式指南 |
| `_bmad-output/planning-artifacts/epics_v1.0.md` | Epic 需求定义 |

---

**文档版本:** 1.0.0
**创建日期:** 2026-05-25
**最后更新:** 2026-05-25
**更新说明:**
- v1.0.0: 创建 Story AC 一致性校验流程文档
