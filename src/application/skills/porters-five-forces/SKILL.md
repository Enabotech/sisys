---
slug: porters-five-forces
name: 波特五力
version: 1.0.0
tool_name: 波特五力
description: 行业竞争结构五力分析（供应商/买方/替代品/新进入者/现有竞争）
when_to_use:
  - 行业吸引力评估
  - 竞争结构分析
  - 进入新市场决策
when_not_to_use:
  - 企业内部诊断请用 value-chain-analysis
capabilities:
  - industry_analysis
  - competitive_structure
status: active
rule_version: BLM-v3.2
reliability_score: 0.85
execution_count: 0
token_budget_l1: 12
token_budget_l2: 1800
depends_on: []
tags:
  - strategy
  - external
---

# 波特五力

## 1. 适用场景
- 行业吸引力评估
- 竞争结构分析
- 进入新市场决策

## 2. 负向触发
- 企业内部诊断请用 value-chain-analysis

## 3. 输入字段
参见 Tool.input_schema（完整 JSON Schema 定义）。

## 4. 输出字段
参见 Tool.output_schema（完整 JSON Schema 定义）。

## 5. 执行步骤
1. 解析 ToolCall.arguments，校验 required 字段
2. 基于 SKILL.md 元数据（capabilities + tags）路由到本工具
3. 调用 ToolExecutionEngine 五阶段工作流（Think→Code→Execute→Observe→Validate）
4. 收集 EvidencePackage（9 字段：input_hash/rule_version/plan/code/result/observation/validation/confidence/citations）
5. 持久化 ToolExecution（含 tool_version 快照 + state_version 乐观锁）
6. 发布 ToolExecuted 事件（aggregate_id=execution_id，双通道 realtime+reliable）

## 6. input_examples
```json
{"placeholder": "请参考 Tool.input_schema 构造示例"}
```
