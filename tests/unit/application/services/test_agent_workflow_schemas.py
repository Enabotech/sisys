"""Agent 工作流思维链阶段 Schema 单元测试（Story 5-3 — 单 Agent 标准工作流）

覆盖六阶段 LLM 结构化输出 Schema 契约（debate_schemas 先例同构）：
- 五 Schema 两两不同（Fake LLM response_schema 身份分派前提——隔离约束）
- NonEmptyStr 条目级校验（空串/纯空白在 Schema 层即拒）
- PlanSchema 步结构（PlanStep{description, tool_name, arguments}——DC-10）
  与 selected_tools；零工具步合法（tool_name 空串）
- VerificationSchema（passed/confidence 值域/rationale）
- ReflectionSchema（error_analysis/revised_plan/revised）
- ChainOfThoughtSchema.to_domain() → ChainOfThought VO（list→tuple 桥接）

Run with:
    poetry run pytest tests/unit/application/services/test_agent_workflow_schemas.py -v
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

# ===================================================================
# 五 Schema 身份互异（Fake 分派前提）
# ===================================================================


class TestSchemaIdentity:
    """五 Schema 类两两不同（response_schema is X 身份分派的前提）。"""

    def test_five_schemas_distinct(self) -> None:
        from src.application.services.agent_workflow_schemas import (
            ChainOfThoughtSchema,
            PerceptionSchema,
            PlanSchema,
            ReflectionSchema,
            VerificationSchema,
        )

        schemas = {PerceptionSchema, PlanSchema, VerificationSchema, ReflectionSchema, ChainOfThoughtSchema}
        assert len(schemas) == 5


# ===================================================================
# PerceptionSchema
# ===================================================================


class TestPerceptionSchema:
    """感知阶段 Schema（任务摘要）。"""

    def test_valid_construction(self) -> None:
        from src.application.services.agent_workflow_schemas import PerceptionSchema

        schema = PerceptionSchema(summary="任务摘要：分析新能源汽车行业进入战略")
        assert schema.summary.startswith("任务摘要")

    def test_blank_summary_rejected(self) -> None:
        from src.application.services.agent_workflow_schemas import PerceptionSchema

        with pytest.raises(PydanticValidationError):
            PerceptionSchema(summary="   ")

    def test_missing_summary_rejected(self) -> None:
        from src.application.services.agent_workflow_schemas import PerceptionSchema

        # model_validate({}) 承载「必填缺失」负向构造（裸 PerceptionSchema()
        # 缺参形态对 mypy 是 call-arg 静态错误——model_validate 等价运行时语义）
        with pytest.raises(PydanticValidationError):
            PerceptionSchema.model_validate({})


# ===================================================================
# PlanSchema（步结构 + 工具选择——DC-10）
# ===================================================================


class TestPlanSchema:
    """规划阶段 Schema（任务分解 + 工具匹配）。"""

    def test_valid_steps_and_tools(self) -> None:
        from src.application.services.agent_workflow_schemas import PlanSchema

        schema = PlanSchema(
            steps=[
                {"description": "执行宏观环境分析", "tool_name": "PESTEL 分析", "arguments": {"scope": "CN"}},
                {"description": "综合给出建议", "tool_name": "", "arguments": {}},
            ],
            selected_tools=["PESTEL 分析"],
        )
        assert schema.steps[0].tool_name == "PESTEL 分析"
        assert schema.steps[0].arguments == {"scope": "CN"}
        assert schema.steps[1].tool_name == ""
        assert schema.selected_tools == ["PESTEL 分析"]

    def test_zero_tool_step_legal(self) -> None:
        """零工具步合法（tool_name 空串——纯推理任务形态）。"""
        from src.application.services.agent_workflow_schemas import PlanSchema

        schema = PlanSchema(
            steps=[{"description": "直接推理给出结论", "tool_name": "", "arguments": {}}],
            selected_tools=[],
        )
        assert schema.selected_tools == []

    def test_empty_steps_rejected(self) -> None:
        """steps 至少 1 条（空规划非法）。"""
        from src.application.services.agent_workflow_schemas import PlanSchema

        with pytest.raises(PydanticValidationError):
            PlanSchema(steps=[], selected_tools=[])

    def test_blank_step_description_rejected(self) -> None:
        from src.application.services.agent_workflow_schemas import PlanSchema

        with pytest.raises(PydanticValidationError):
            PlanSchema(steps=[{"description": "  ", "tool_name": "", "arguments": {}}], selected_tools=[])


# ===================================================================
# VerificationSchema
# ===================================================================


class TestVerificationSchema:
    """验证阶段 Schema（结构化检查）。"""

    def test_valid_pass_and_fail(self) -> None:
        from src.application.services.agent_workflow_schemas import VerificationSchema

        passed = VerificationSchema(passed=True, confidence=0.85, rationale="结构化检查通过")
        failed = VerificationSchema(passed=False, confidence=0.42, rationale="第 1 次验证未通过")
        assert passed.passed is True
        assert failed.passed is False

    @pytest.mark.parametrize("bad_confidence", [-0.01, 1.01])
    def test_confidence_out_of_range_rejected(self, bad_confidence: float) -> None:
        from src.application.services.agent_workflow_schemas import VerificationSchema

        with pytest.raises(PydanticValidationError):
            VerificationSchema(passed=True, confidence=bad_confidence, rationale="依据")

    def test_blank_rationale_rejected(self) -> None:
        from src.application.services.agent_workflow_schemas import VerificationSchema

        with pytest.raises(PydanticValidationError):
            VerificationSchema(passed=True, confidence=0.9, rationale="")


# ===================================================================
# ReflectionSchema
# ===================================================================


class TestReflectionSchema:
    """反思阶段 Schema（错误分析与修正计划）。"""

    def test_revisable_reflection(self) -> None:
        from src.application.services.agent_workflow_schemas import ReflectionSchema

        schema = ReflectionSchema(
            error_analysis="工具输出缺少关键约束字段",
            revised_plan="补充约束参数后重新执行",
            revised=True,
        )
        assert schema.revised is True
        assert "补充约束" in schema.revised_plan

    def test_not_revisable_reflection(self) -> None:
        """不可修正形态：revised=False + revised_plan 空（早退路径）。"""
        from src.application.services.agent_workflow_schemas import ReflectionSchema

        schema = ReflectionSchema(
            error_analysis="任务目标超出可用工具能力边界，属根本性障碍",
            revised_plan="",
            revised=False,
        )
        assert schema.revised is False

    def test_blank_error_analysis_rejected(self) -> None:
        from src.application.services.agent_workflow_schemas import ReflectionSchema

        with pytest.raises(PydanticValidationError):
            ReflectionSchema(error_analysis="  ", revised_plan="x", revised=True)


# ===================================================================
# ChainOfThoughtSchema + to_domain 桥接
# ===================================================================


class TestChainOfThoughtSchema:
    """终局合成 Schema + to_domain() → VO（list→tuple）。"""

    def _make_schema(self):
        from src.application.services.agent_workflow_schemas import ChainOfThoughtSchema

        return ChainOfThoughtSchema(
            input_summary="Fake 回声摘要",
            reflection="Fake 回声反思",
            tools_used=["fake-echo:not-a-real-tool"],
            constraints_check="Fake 回声约束",
            final_answer='{"answer": "终局答案"}',
        )

    def test_valid_construction(self) -> None:
        schema = self._make_schema()
        assert schema.final_answer.startswith("{")

    def test_empty_tools_used_legal(self) -> None:
        """tools_used 空列表合法（无工具任务——VO 允许空元组同语义）。"""
        from src.application.services.agent_workflow_schemas import ChainOfThoughtSchema

        schema = ChainOfThoughtSchema(
            input_summary="a", reflection="b", tools_used=[], constraints_check="c", final_answer="{}"
        )
        assert schema.tools_used == []

    def test_to_domain_list_to_tuple(self) -> None:
        """to_domain() 桥接：list→tuple（VO 字段形态）。"""
        from src.domain.value_objects.chain_of_thought import ChainOfThought

        vo = self._make_schema().to_domain()
        assert isinstance(vo, ChainOfThought)
        assert isinstance(vo.tools_used, tuple)
        assert vo.tools_used == ("fake-echo:not-a-real-tool",)
        assert vo.input_summary == "Fake 回声摘要"

    def test_to_domain_blank_field_rejected_by_vo(self) -> None:
        """空字段在 VO 层拦截（双层不变量——Schema 允许后 VO 仍守卫）。"""
        from src.application.services.agent_workflow_schemas import ChainOfThoughtSchema
        from src.domain.exceptions import EntityValidationError

        schema = ChainOfThoughtSchema(
            input_summary="a", reflection="b", tools_used=[], constraints_check="c", final_answer="{}"
        )
        object.__setattr__(schema, "reflection", "  ")  # 绕过 Schema 校验模拟深层缺陷
        with pytest.raises(EntityValidationError):
            schema.to_domain()
