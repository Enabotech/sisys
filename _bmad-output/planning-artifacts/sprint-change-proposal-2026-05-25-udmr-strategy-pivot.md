# Sprint Change Proposal: UDMR 路由策略调整——云端优先

**日期:** 2026-05-25
**状态:** ✅ Implemented
**触发原因:** 战略调整，将 UDMR 路由策略从"本地优先 80%，云端兜底"调整为"云端优先 80%，本地兜底"

---

## 1. Issue Summary

### 1.1 问题陈述

UDMR（统一动态模型路由框架）策略方向调整：

| 维度 | 旧策略 | 新策略 |
|------|--------|--------|
| 路由优先级 | 本地优先 80%，云端兜底 | 云端优先 80%，本地兜底 |
| 核心目标 | 成本优化 50%，本地路由占比≥80% | 云端模型质量优先，本地作为合规/降级兜底 |
| L3 默认决策 | 本地优先（成本节省） | 云端优先（本地兜底） |
| 成本指标 | 本地模型路由占比≥80% | 云端模型路由占比≥80% |

### 1.2 变更原因

- Story 1.17 实现时已采用"云端优先"策略（`UDMR_LOCAL_FIRST=false`）
- 云端模型质量更优，更适合 MVP 阶段快速验证
- 本地模型作为合规场景（PII/商业秘密/数据驻留）的强制路由
- 架构文档与实现长期存在不一致，需正式对齐

### 1.3 变更范围

**Minor scope** — 策略方向调整，不涉及代码变更（代码已实现云端优先），仅同步文档工件。

---

## 2. Impact Analysis

### 2.1 工件变更汇总

| 文件 | 变更点数 | 变更类型 |
|------|---------|---------|
| `docs/architecture/architecture.md` | 7 | 策略表、4.1 概述、4.4 L3 决策、FR-CP-05、ADR-005、成本指标表、CP 覆盖 |
| `_bmad-output/planning-artifacts/prd.md` | 8 | 指标、V1 功能表、核心创新目标、验证标准、里程碑 |
| `_bmad-output/planning-artifacts/epics_v1.0.md` | 8 | Epic 11 描述、Story 1.17 标题/描述、路由占比、Story 表 |
| `_bmad-output/planning-artifacts/or.md` | 1 | UDMR 系统概述 |
| `_bmad-output/planning-artifacts/roadmap.md` | 2 | V1 功能表、V1 技术指标 |
| `_bmad-output/project-context.md` | 2 | L3 目标、UDMR 指标表 |
| `docs/architecture/sisys-implementation-patterns.md` | 2 | 路由决策执行职责、测试命名 |
| `docs/architecture/arch-appendix.md` | 4 | CUSUM 指标、路由效率表、故障树 |
| `docs/developer/story-ac-consistency-check.md` | 8 | 策略校验规则（反向更新） |
| `_bmad-output/implementation-artifacts/stories/1-17-*.md` | 1 | 差异记录对齐 |
| `_bmad-output/implementation-artifacts/stories/1-19-*.md` | 1 | 成本指标引用 |

**总计: 44 处变更**

### 2.2 不受影响的范围

| 范围 | 原因 |
|------|------|
| 代码实现 | Story 1.17 已实现云端优先（`UDMR_LOCAL_FIRST=false`） |
| 数据主权隔离 (FR-SC-07) | "敏感数据本地优先处理"是独立的合规要求，不属于路由策略 |
| 三层决策架构 (L1/L2/L3) | 决策机制不变，仅 L3 默认决策方向调整 |
| L1 合规检查规则 | 合规强制本地路由不受影响 |
| L2 四因子评分权重 | 评分算法不变 |
| 路由延迟 P95<50ms | 性能约束不变 |

---

## 3. Detailed Change Proposals

### 3.1 architecture.md 关键变更

**Section: 架构风格特性表 (line 130)**

```
OLD: | **动态模型路由** | 本地优先 80%，云端兜底，成本优化 50% | UDMR 三层决策 |
NEW: | **动态模型路由** | 云端优先 80%，本地兜底，成本优化 50% | UDMR 三层决策 |
```

**Section: 4.1 架构概述 (line 563)**

```
OLD: 实现**本地路由占比 80%、成本节省 50%** 目标
NEW: 实现**云端路由占比 80%、本地兜底**目标
```

**Section: 4.4 L3 路由决策规则 (line 614)**

```
OLD: | **默认** | 其他情况 | 本地优先（成本节省） |
NEW: | **默认** | 其他情况 | 云端优先（本地兜底） |
```

**Section: ADR-005 (line 3222)**

```
OLD: 三层决策架构（L1 合规+L2 评估+L3 执行），本地路由占比 80%
NEW: 三层决策架构（L1 合规+L2 评估+L3 执行），云端路由占比 80%，本地兜底
```

### 3.2 prd.md 关键变更

- V1 功能表: "本地优先 80%" → "云端优先 80%"
- V1 技术指标: "本地模型路由占比≥80%" → "云端模型路由占比≥80%"
- 核心创新目标: "本地路由占比≥80%, 成本节省≥50%" → "云端路由占比≥80%, 本地兜底"
- 里程碑: "本地路由≥80%" → "云端路由≥80%"

### 3.3 epics_v1.0.md 关键变更

- Story 1.17 标题: "本地优先静态配置" → "云端优先静态配置"
- Epic 11 描述: "本地路由≥80%，成本节省≥50%" → "云端路由≥80%，本地兜底"
- 路由占比测试: "本地路由占比≥80%" → "云端路由占比≥80%"

### 3.4 arch-appendix.md 关键变更

- 路由效率指标表: `local_routing_ratio` 基线目标从 ≥80% 改为 ≤20%；`cloud_routing_ratio` 从 ≤20% 改为 ≥80%
- CUSUM 配置: `local_routing_ratio` → `cloud_routing_ratio`
- 故障树: "本地路由占比下降" → "云端路由占比下降"

### 3.5 story-ac-consistency-check.md 关键变更

反向更新校验规则：
- 策略维度表: "本地优先 80%，云端兜底" → "云端优先 80%，本地兜底"
- 错误示例: "写成'云端优先'" → "写成'本地优先'"
- 检查清单: 更新为校验云端优先

---

## 4. Implementation Handoff

**Scope:** Minor — Developer agent 直接实施

**已完成:** 全部 44 处工件变更已同步完成

**代码无变更:** Story 1.17 已实现云端优先策略

**成功标准:**
- ✅ 所有文档工件中"本地优先 80%，云端兜底"替换为"云端优先 80%，本地兜底"
- ✅ 所有指标表从"本地模型路由占比"更新为"云端模型路由占比"
- ✅ 数据主权相关"敏感数据本地优先"不受影响
- ✅ ADR-005 更新为云端优先策略
- ✅ 一致性检查规则反向更新
