"""幻觉检测 Schema（Story 5.8——FR-EV-02 评估面）。

定义在应用层（src/application/services/），允许依赖 pydantic（领域层零外部
依赖约束不适用于应用层 Schema——relevance_schemas.py 同款先例）。

设计决策：
- 扁平零嵌套（anthropic 通道约束——嵌套 Schema 触发 GLM-5.3 anthropic 端点
  服务端 500 StackOverflowError，litellm_llm_client.py L630-637 注记）；
- 字段声明序 rationale 先行、hallucination_score 后置（CoT-then-score——
  G-Eval/Phoenix 模板均 EXPLANATION→LABEL 序，评分受先行理由约束更稳——
  DC-2 细则(b)）；
- 与既有五 Schema（agent_workflow_schemas.py）类对象两两不同——Fake LLM
  response_schema 身份分派的前提（L9-10 设计决策保持）；
- rationale max_length=3000 与「逐项概括核对（每主张一行短语）」指令配套
  （CR1-F3——原 1000 上限对主张密集的战略规划回答系统性硬拒丢评估覆盖：
  超限→pydantic 校验失败→LLMResponseError→450→降级，选择偏差使最长、最需
  幻觉检测的回答丢覆盖；OpenAI structured outputs 严格模式不支持 maxLength
  ——拒断只发生在客户端校验侧）。max_tokens 耦合知悉：max_tokens<~2048 的
  运维配置下极端 rationale（3000 字≈1700-3000 tokens）会 finish_reason=length
  截断 JSON→331→450→降级（与 prompt 概括指令共同把典型 rationale 压至
  200-800 字，概率性损失面）。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = ["HallucinationEvaluationSchema"]


class HallucinationEvaluationSchema(BaseModel):
    """幻觉检测结构化输出 Schema（OD-5 字面语义：0.0=无幻觉 1.0=完全幻觉）。

    评分方向注记：hallucination_score 越高越坏（与 context_relevance/
    confidence_accuracy 越高越好方向相反——overall 反转加权归一，见
    agent_evaluation.py 权重常量注记）。
    """

    rationale: str = Field(
        ...,
        min_length=1,
        max_length=3000,
        description="幻觉判断理由（先给理由后给分——CoT-then-score 序约束评分稳定性）",
    )
    hallucination_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="幻觉程度评分：0.0=无幻觉（完全事实）、1.0=完全幻觉（越高越坏）",
    )
