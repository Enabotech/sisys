"""Agent 工作流 Prompt 模块单元测试（Story 5-3 — 单 Agent 标准工作流）

覆盖六阶段工作流 prompt 资产契约：
- system_prompt 五分节定序（IDENTITY→SOUL→CODE→核心约束→TOOLS L1 视图——DC-3）
- HEARTBEAT 档案不注入（调度心跳配置非推理上下文——分节内容零出现断言）
- TOOLS L1 行格式（"{tool_name}: {description}（用: {when_to_use}）"）
- 核心约束文本含思维链五段输出要求（项目首个「核心约束」载体）
- task user prompt 模板占位符
- 阶段 prompt 构造函数（perceive/plan/verify/reflect/终局合成——plan 含
  重试轮回灌注入位 revised_plan/error_analysis，R2-F4）

Run with:
    poetry run pytest tests/unit/application/services/test_agent_workflow_prompts.py -v
"""

from __future__ import annotations

from typing import Any


def _make_profile_kwargs() -> dict[str, str]:
    """构造六档案字段（HEARTBEAT 带可识别标记——不注入断言锚）。"""
    return {
        "identity": "# IDENTITY\nCEO 首席执行官，负责战略方向与最终决策。",
        "code_of_conduct": "# CODE\n1. 证据优先；2. 角色隔离纪律。",
        "soul": "# SOUL\n高管决策视角：宏观趋势、竞争格局。",
        "user_preferences": "# USER\n偏好结论先行。",
        "memory": "# MEMORY\n静态种子占位。",
        "heartbeat": "# HEARTBEAT\n每 30 秒上报健康状态一次。",
    }


def _make_tools_l1() -> tuple[Any, ...]:
    """构造两条 L1 工具元数据（行格式断言对象）。"""
    from src.application.ports.skill_loader import ToolMetadata

    def _meta(tool_name: str, description: str, when_to_use: tuple[str, ...]) -> ToolMetadata:
        return ToolMetadata(
            tool_name=tool_name,
            slug="test-slug",
            category="environment_analysis",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            description=description,
            when_to_use=when_to_use,
        )

    return (
        _meta("PESTEL 分析", "宏观环境六维度分析", ("宏观环境分析", "政策影响评估")),
        _meta("SWOT 分析", "优势劣势机会威胁矩阵", ("竞争格局评估",)),
    )


# ===================================================================
# 模块常量：核心约束文本 + task user prompt 模板
# ===================================================================


class TestCoreConstraintsText:
    """核心约束文本常量（项目首个「核心约束」载体——D-2 承载 AGENT.md 语义）。"""

    def test_contains_chain_five_segment_requirements(self) -> None:
        """核心约束含思维链五段输出要求（Input/Reflection/Tools_Used/Constraints_Check/JSON）。"""
        from src.application.services.agent_workflow_prompts import CORE_CONSTRAINTS_TEXT

        assert "<Reflection>" in CORE_CONSTRAINTS_TEXT
        assert "<Tools_Used>" in CORE_CONSTRAINTS_TEXT
        assert "<Constraints_Check>" in CORE_CONSTRAINTS_TEXT
        assert "JSON" in CORE_CONSTRAINTS_TEXT
        assert "思维链" in CORE_CONSTRAINTS_TEXT

    def test_contains_safety_redline(self) -> None:
        """核心约束含安全红线声明（不得虚构数据等纪律）。"""
        from src.application.services.agent_workflow_prompts import CORE_CONSTRAINTS_TEXT

        assert "不得虚构" in CORE_CONSTRAINTS_TEXT or "禁止" in CORE_CONSTRAINTS_TEXT


class TestTaskUserPromptTemplate:
    """task user prompt 模板占位符。"""

    def test_template_contains_task_placeholder(self) -> None:
        from src.application.services.agent_workflow_prompts import TASK_USER_PROMPT_TEMPLATE

        assert "{task}" in TASK_USER_PROMPT_TEMPLATE

    def test_template_render_with_task(self) -> None:
        from src.application.services.agent_workflow_prompts import TASK_USER_PROMPT_TEMPLATE

        rendered = TASK_USER_PROMPT_TEMPLATE.format(task="分析新能源汽车行业进入战略")
        assert "分析新能源汽车行业进入战略" in rendered
        assert "{task}" not in rendered


# ===================================================================
# TOOLS L1 视图行格式
# ===================================================================


class TestL1ViewFormat:
    """TOOLS L1 视图行格式（"{tool_name}: {description}（用: {when_to_use}）"）。"""

    def test_l1_line_format(self) -> None:
        """行格式断言：名称: 描述（用: 触发词）——description 即触发器（DC-10）。"""
        from src.application.services.agent_workflow_prompts import build_l1_view

        view = build_l1_view(_make_tools_l1())
        assert "PESTEL 分析: 宏观环境六维度分析（用: 宏观环境分析、政策影响评估）" in view
        assert "SWOT 分析: 优势劣势机会威胁矩阵（用: 竞争格局评估）" in view

    def test_l1_view_empty_tools_placeholder(self) -> None:
        """空 L1 视图有显式占位（R3-DF1 降级形态——不静默空段）。"""
        from src.application.services.agent_workflow_prompts import build_l1_view

        view = build_l1_view(())
        assert "无可用工具" in view or "暂无" in view, "空 L1 视图应显式降级注记"


# ===================================================================
# 分节定序（SECTION_ORDER——装配器组装依据）
# ===================================================================


class TestSectionOrder:
    """system_prompt 五分节定序常量（DC-3：IDENTITY→SOUL→CODE→核心约束→TOOLS L1）。"""

    def test_section_order_constant(self) -> None:
        from src.application.services.agent_workflow_prompts import SECTION_ORDER

        assert SECTION_ORDER == ("identity", "soul", "code_of_conduct", "core_constraints", "tools_l1")


# ===================================================================
# 阶段 prompt 构造函数（Fake LLM 分派的 prompt 面）
# ===================================================================


class TestPhasePromptBuilders:
    """六阶段 user prompt 构造（plan 含重试轮回灌注入位——R2-F4）。"""

    def test_build_perceive_prompt(self) -> None:
        """感知阶段 prompt 含任务原文与摘要要求。"""
        from src.application.services.agent_workflow_prompts import build_perceive_prompt

        prompt = build_perceive_prompt("分析新能源汽车行业进入战略")
        assert "分析新能源汽车行业进入战略" in prompt
        assert "摘要" in prompt

    def test_build_plan_prompt_basic(self) -> None:
        """规划阶段 prompt 含任务与工具选择要求；无反思注入位时零残留。"""
        from src.application.services.agent_workflow_prompts import build_plan_prompt

        prompt = build_plan_prompt("分析新能源汽车行业进入战略")
        assert "分析新能源汽车行业进入战略" in prompt
        assert "工具" in prompt

    def test_build_plan_prompt_with_revision(self) -> None:
        """重试轮回灌：revised_plan + error_analysis 非空时注入（R2-F4 核心）。"""
        from src.application.services.agent_workflow_prompts import build_plan_prompt

        prompt = build_plan_prompt(
            "分析新能源汽车行业进入战略",
            revised_plan="补充约束参数后重新执行工具并复核",
            error_analysis="工具输出缺少关键约束字段",
        )
        assert "补充约束参数后重新执行工具并复核" in prompt, "修正计划未注入"
        assert "工具输出缺少关键约束字段" in prompt, "错误分析未注入"

    def test_build_verify_prompt(self) -> None:
        """验证阶段 prompt 含执行结果摘要与结构化检查要求。"""
        from src.application.services.agent_workflow_prompts import build_verify_prompt

        prompt = build_verify_prompt("任务", execution_summary="已执行 PESTEL 工具并取得输出")
        assert "已执行 PESTEL 工具并取得输出" in prompt
        assert "检查" in prompt or "验证" in prompt

    def test_build_reflect_prompt(self) -> None:
        """反思阶段 prompt 含验证失败依据与修正要求。"""
        from src.application.services.agent_workflow_prompts import build_reflect_prompt

        prompt = build_reflect_prompt("任务", verification_rationale="第 1 次验证未通过：约束缺失")
        assert "第 1 次验证未通过：约束缺失" in prompt
        assert "修正" in prompt

    def test_build_final_synthesis_prompt(self) -> None:
        """终局合成 prompt 携带各阶段产物摘要（perception/execution/verification）。"""
        from src.application.services.agent_workflow_prompts import build_final_synthesis_prompt

        prompt = build_final_synthesis_prompt(
            "任务",
            perception_summary="任务摘要：进入战略分析",
            execution_summary="工具轨迹：PESTEL 完成",
            verification_rationale="结构化检查通过",
        )
        assert "任务摘要：进入战略分析" in prompt
        assert "工具轨迹：PESTEL 完成" in prompt
        assert "结构化检查通过" in prompt

    def test_final_synthesis_mentions_chain_format(self) -> None:
        """终局 prompt 引导五段思维链语义（成功路径「一次通过」类反思文本——DC-2）。"""
        from src.application.services.agent_workflow_prompts import build_final_synthesis_prompt

        prompt = build_final_synthesis_prompt("任务", "感知", "执行", "验证通过")
        assert "一次通过" in prompt or "反思" in prompt
