---
slug: vrio-framework
name: VRIO 框架
version: 1.0.0
tool_name: VRIO 框架
description: 资源/能力 VRIO 四维评估（价值/稀缺性/可模仿性/组织）
when_to_use:
  - 资源能力评估
  - 竞争优势识别
  - 战略资源审计
when_not_to_use:
  - 市场吸引力分析
capabilities:
  - resource_evaluation
  - competitive_advantage
status: active
rule_version: BLM-v3.2
reliability_score: 0.85
execution_count: 0
token_budget_l1: 12
token_budget_l2: 1800
depends_on: []
tags:
  - strategy
  - internal
---

# VRIO 框架

## 1. 适用场景
- 资源能力评估
- 竞争优势识别
- 战略资源审计

## 2. 负向触发
- 市场吸引力分析

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
