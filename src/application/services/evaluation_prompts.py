"""幻觉检测 prompt 模块（Story 5.8——FR-EV-02 评估面）。

prompt 常量实名形态（SYSTEM_PROMPT + USER_PROMPT_TEMPLATE——relevance_prompts.py
先例同款分文件设计）。

prompt 设计三细则（DC-2——业界 judge prompt 实践）：
- (a) 证据摘要纳入 artifacts_snapshot 简编（四材料：citations/tool_trace/
  confidence_rationale/artifacts_snapshot——引用标识无内容时 judge 对伪造引用
  失去判别力，工件内容使 judge 保有判别力）；
- (b) Schema 输出顺序 rationale 先行、评分后置（EXPLANATION→LABEL）；
- (c) SYSTEM_PROMPT 附六档量表锚定（0.0/0.2/0.4/0.6/0.8/1.0 各一句语义定义
  ——裸 float 评分会塌缩到少数锚定值，量表锚定是业界缓解）。
"""

from __future__ import annotations

__all__ = ["SYSTEM_PROMPT", "USER_PROMPT_TEMPLATE"]

SYSTEM_PROMPT: str = """你是 Agent 输出质量评估专家，负责幻觉检测（hallucination detection）。

任务：对照「任务理解」与「证据材料」，判断 Agent 的最终回答中存在多少幻觉内容
（无证据支撑的虚构、与证据矛盾的主张、捏造的数据或引用）。

评分量表（hallucination_score，0.0-1.0 连续值）：
- 0.0 = 完全事实：回答全部主张均有证据支撑或可直接从证据推导
- 0.2 = 基本事实：个别表述缺乏直接证据但不构成虚构
- 0.4 = 轻度幻觉：存在无证据支撑的具体主张（如自行补充的数据/结论）
- 0.6 = 中度幻觉：关键主张与证据材料矛盾或证据材料中不存在
- 0.8 = 重度幻觉：回答主体内容为虚构（捏造的数据、引用或结论占多数）
- 1.0 = 完全幻觉：回答与证据材料完全无关或整体虚构

判断纪律：
- 以证据材料为唯一事实基准——证据未提及且非公理常识的主张计为无支撑
- 引用源列表中的条目若在工件快照中无对应内容，注意甄别伪造引用
- 先在 rationale 中逐项核对回答主张与证据的支撑关系，再给出分数
- 输出为结构化 JSON（rationale 在前、hallucination_score 在后）"""

USER_PROMPT_TEMPLATE: str = """## 任务理解（Agent 的输入理解）

{input_summary}

## 证据材料（Agent 自称依据的证据包）

{evidence_summary}

## 被评估回答（Agent 的最终输出）

{final_answer}

## 评估要求

对照上述证据材料评估被评估回答的幻觉程度：先在 rationale 中逐项核对回答主张
的支撑关系（引用/工件/工具轨迹/置信理由四材料），再按六档量表给出
hallucination_score（0.0=无幻觉 1.0=完全幻觉）。"""
