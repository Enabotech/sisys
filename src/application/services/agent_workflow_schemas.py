"""应用层单 Agent 工作流 LLM 结构化输出 Schema 模块（Story 5-3）

六阶段工作流各 LLM 阶段的结构化 Schema（structured_generate 的
response_schema 契约）：PerceptionSchema / PlanSchema（含 PlanStep）/
VerificationSchema / ReflectionSchema / ChainOfThoughtSchema（终局合成）。

设计决策（debate_schemas.py 先例同构）：
- 定义在应用层（src/application/），允许依赖 Pydantic（领域零依赖红线）
- 五 Schema 两两不同——Fake LLM response_schema 身份分派的前提（测试隔离
  约束；若任两处共用 Schema 需补次级分派键）
- NonEmptyStr 条目级非空校验（strip_whitespace + min_length=1——pydantic v2
  的 Annotated+StringConstraints 是唯一正确机制，Field(strip_whitespace=True)
  是 deprecated no-op 且泄漏脏键进 JSON Schema）
- PlanStep 含 tool_name/arguments（DC-10：规划阶段 LLM 自主选择工具并给出
  参数；零工具步 tool_name 空串合法）
- to_domain() 承担 list→tuple 转换（VO 字段全 tuple，Schema 全 list）
- Pydantic 校验 + 领域 VO 双重不变量（VO __post_init__ 兜底——异常契约
  三层次序②的 242 抛点）
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, Field, StringConstraints

from src.domain.value_objects.chain_of_thought import ChainOfThought

#: 条目级非空字符串约束（strip 后非空——debate_schemas 同款单一事实源）
NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class PerceptionSchema(BaseModel):
    """感知阶段 Schema（任务上下文摘要）"""

    summary: NonEmptyStr = Field(..., description="任务上下文摘要（目标/领域/约束/预期产出）")


class PlanStep(BaseModel):
    """规划步骤 Schema（DC-10 步结构——description/tool_name/arguments）"""

    description: NonEmptyStr = Field(..., description="步骤描述")
    tool_name: str = Field(default="", description="工具名称（L1 视图选择；零工具步留空）")
    arguments: dict[str, Any] = Field(default_factory=dict, description="步骤执行参数")


class PlanSchema(BaseModel):
    """规划阶段 Schema（任务分解 + 工具匹配）"""

    steps: list[PlanStep] = Field(..., min_length=1, description="任务分解步骤（至少 1 步）")
    selected_tools: list[NonEmptyStr] = Field(
        default_factory=list,
        description="选中的工具名称清单（零工具任务为空）",
    )


class VerificationSchema(BaseModel):
    """验证阶段 Schema（结构化检查——passed/confidence/rationale）"""

    passed: bool = Field(..., description="是否通过结构化检查")
    confidence: float = Field(..., ge=0.0, le=1.0, description="验证置信度（0-1）")
    rationale: NonEmptyStr = Field(..., description="判定依据（通过理由或失败摘要）")


class ReflectionSchema(BaseModel):
    """反思阶段 Schema（错误分析与修正计划）"""

    error_analysis: NonEmptyStr = Field(..., description="验证失败根因分析")
    revised_plan: str = Field(default="", description="修正计划（revised=False 时可为空）")
    revised: bool = Field(..., description="是否可通过修正计划重试")


class ChainOfThoughtSchema(BaseModel):
    """终局思维链合成 Schema（package 阶段单次 structured_generate——DC-2）

    注意：input_summary 与 tools_used 由服务按真实记录组装覆写（LLM 输出
    仅是回声面）——本 Schema 五字段仍全量定义以保持终局合成契约完整，
    覆写发生在 to_domain 之前的组装层。
    """

    input_summary: NonEmptyStr = Field(..., description="输入摘要（回声面——服务覆写）")
    reflection: NonEmptyStr = Field(..., description="整体反思（一次通过性总结或修正过程）")
    tools_used: list[NonEmptyStr] = Field(
        default_factory=list,
        description="工具调用轨迹（回声面——服务以真实轨迹覆写）",
    )
    constraints_check: NonEmptyStr = Field(..., description="约束核查结论（终局合成产物——DC-2 三字段之一，非覆写面）")
    final_answer: NonEmptyStr = Field(..., description="最终结构化答案（JSON 形态）")

    def to_domain(self) -> ChainOfThought:
        """转换为领域 ChainOfThought 值对象（list→tuple 转换职责）。

        Returns:
            ChainOfThought 领域值对象（Pydantic 校验 + VO 不变量双重保障）
        """
        return ChainOfThought(
            input_summary=self.input_summary,
            reflection=self.reflection,
            tools_used=tuple(self.tools_used),
            constraints_check=self.constraints_check,
            final_answer=self.final_answer,
        )


__all__ = [
    "ChainOfThoughtSchema",
    "NonEmptyStr",
    "PerceptionSchema",
    "PlanSchema",
    "PlanStep",
    "ReflectionSchema",
    "VerificationSchema",
]
