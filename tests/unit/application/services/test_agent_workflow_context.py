"""Agent 工作流上下文装配器单元测试（Story 5-3 — 单 Agent 标准工作流）

覆盖启动上下文装配契约（DC-3 定稿——5-2 风险 #1 核销）：
- build_system_prompt 五分节定序（IDENTITY→SOUL→CODE→核心约束→TOOLS L1）
  + USER/MEMORY 追加 system 尾节
- HEARTBEAT 档案不注入（调度心跳配置非推理上下文——内容零出现断言）
- cjk_estimate_tokens 中文感知计量（中文 1.5 字/token 其他 4 字/token、
  max(·,1) 下限——context_compressor._estimate_chars_tokens L408-425 照抄）
- 装配总计量（assembled_context_tokens 口径：五档案 + L1 视图 + 核心约束
  文本——heartbeat 不入）
- TOOLS.md 缺失/降级空 L1 时的装配行为（R3-DF1 核销交付物：显式降级注记）
- build_context 装配入口（WorkflowContext 五字段——Subtask 3.3）

Run with:
    poetry run pytest tests/unit/application/services/test_agent_workflow_context.py -v
"""

from __future__ import annotations

import uuid
from typing import Any

from src.domain.entities.agent import AgentRole


def _make_profile():
    """构造真实 AgentProfile VO（六档案——HEARTBEAT 带唯一标记锚）。"""
    from src.domain.value_objects.agent_profile import AgentProfile

    return AgentProfile(
        agent_id=uuid.uuid4(),
        role=AgentRole.CEO,
        identity="# IDENTITY\nCEO 首席执行官，负责战略方向与最终决策。",
        code_of_conduct="# CODE\n1. 证据优先；2. 角色隔离纪律。",
        soul="# SOUL\n高管决策视角：宏观趋势、竞争格局、战略意图。",
        user_preferences="# USER\n偏好简明扼要的结论先行表达。",
        memory="# MEMORY\n暂无系统级记忆，此为加载占位。",
        heartbeat="# HEARTBEAT\n每 30 秒上报健康状态一次（调度心跳配置标记 HEARTBEAT-SHOULD-NOT-APPEAR）。",
    )


def _make_tools_l1() -> tuple[Any, ...]:
    """构造两条 L1 工具元数据。"""
    from src.application.ports.skill_loader import ToolMetadata

    def _meta(tool_name: str, description: str) -> ToolMetadata:
        return ToolMetadata(
            tool_name=tool_name,
            slug="test-slug",
            category="environment_analysis",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            description=description,
            when_to_use=("分析",),
        )

    return (_meta("PESTEL 分析", "宏观环境六维度分析"), _meta("SWOT 分析", "优势劣势机会威胁矩阵"))


# ===================================================================
# build_system_prompt 五分节定序 + HEARTBEAT 不注入
# ===================================================================


class TestBuildSystemPrompt:
    """system_prompt 五分节装配（DC-3）。"""

    def test_section_order_in_prompt(self) -> None:
        """五分节顺序：IDENTITY→SOUL→CODE→核心约束→TOOLS L1（位置递增）。"""
        from src.application.services.agent_workflow_context import build_system_prompt

        prompt = build_system_prompt(_make_profile(), _make_tools_l1())
        positions = [
            prompt.index("IDENTITY"),
            prompt.index("SOUL"),
            prompt.index("CODE"),
            prompt.index("核心约束"),
            prompt.index("TOOLS L1"),
        ]
        assert positions == sorted(positions), f"分节顺序异常: {positions}"

    def test_user_memory_as_tail_sections(self) -> None:
        """USER/MEMORY 追加 system 尾节（在 TOOLS L1 之后）。"""
        from src.application.services.agent_workflow_context import build_system_prompt

        prompt = build_system_prompt(_make_profile(), _make_tools_l1())
        assert prompt.index("TOOLS L1") < prompt.index("USER")
        assert prompt.index("USER") < prompt.index("MEMORY")

    def test_heartbeat_not_injected(self) -> None:
        """HEARTBEAT 档案内容零出现（DC-3 裁决——唯一标记锚断言）。"""
        from src.application.services.agent_workflow_context import build_system_prompt

        prompt = build_system_prompt(_make_profile(), _make_tools_l1())
        assert "HEARTBEAT-SHOULD-NOT-APPEAR" not in prompt, "心跳配置不得注入 prompt"

    def test_profile_contents_present(self) -> None:
        """五档案内容与 L1 视图进入 prompt。"""
        from src.application.services.agent_workflow_context import build_system_prompt

        prompt = build_system_prompt(_make_profile(), _make_tools_l1())
        assert "CEO 首席执行官" in prompt
        assert "证据优先" in prompt
        assert "高管决策视角" in prompt
        assert "结论先行" in prompt
        assert "加载占位" in prompt
        assert "PESTEL 分析" in prompt

    def test_core_constraints_text_embedded(self) -> None:
        """核心约束文本（模块常量）嵌入 prompt。"""
        from src.application.services.agent_workflow_context import build_system_prompt
        from src.application.services.agent_workflow_prompts import CORE_CONSTRAINTS_TEXT

        prompt = build_system_prompt(_make_profile(), _make_tools_l1())
        assert CORE_CONSTRAINTS_TEXT in prompt


# ===================================================================
# CJK 感知计量（照抄 context_compressor._estimate_chars_tokens）
# ===================================================================


class TestCjkEstimateTokens:
    """cjk_estimate_tokens 中文感知计量（context_compressor L408-425 照抄）。"""

    def test_empty_text_floor(self) -> None:
        """空文本下限 1（max(·,1)）。"""
        from src.application.services.agent_workflow_context import cjk_estimate_tokens

        assert cjk_estimate_tokens("") == 1

    def test_pure_chinese_ratio(self) -> None:
        """纯中文 1.5 字/token（10 个中文字 → int(10/1.5)=6）。"""
        from src.application.services.agent_workflow_context import cjk_estimate_tokens

        assert cjk_estimate_tokens("一二三四五六七八九十") == int(10 / 1.5)

    def test_pure_ascii_ratio(self) -> None:
        """纯 ASCII 4 字/token（12 字符 → 3）。"""
        from src.application.services.agent_workflow_context import cjk_estimate_tokens

        assert cjk_estimate_tokens("abcdefghijkl") == 3

    def test_mixed_text(self) -> None:
        """混合文本：中文 1.5 + 其他 4。"""
        from src.application.services.agent_workflow_context import cjk_estimate_tokens

        text = "一二三四五六七八九十" + "abcdefghijkl"  # 10 CJK + 12 ASCII
        assert cjk_estimate_tokens(text) == int(10 / 1.5 + 12 / 4)

    def test_chinese_not_underestimated(self) -> None:
        """中文低估防线：CJK 计量高于 chars//4 口径（5-2 风险 #1 核心）。"""
        from src.application.services.agent_workflow_context import cjk_estimate_tokens

        text = "一" * 100
        assert cjk_estimate_tokens(text) > len(text) // 4


# ===================================================================
# 装配总计量（assembled_context_tokens 新口径）
# ===================================================================


class TestAssembledTokens:
    """装配总计量口径（五档案 + L1 视图 + 核心约束——heartbeat 不入）。"""

    def test_estimate_equals_sum_of_sections(self) -> None:
        """总计量 == 各分节 CJK 计量之和（口径一致性）。"""
        from src.application.services.agent_workflow_context import (
            build_system_prompt,
            estimate_assembled_tokens,
        )

        profile = _make_profile()
        tools_l1 = _make_tools_l1()
        total = estimate_assembled_tokens(profile, tools_l1)
        assert total == cjk_sum_of(build_system_prompt(profile, tools_l1))

    def test_heartbeat_not_counted(self) -> None:
        """heartbeat 内容不进计量（超长心跳不影响 assembled tokens）。"""
        from src.application.services.agent_workflow_context import estimate_assembled_tokens

        base_profile = _make_profile()

        import dataclasses

        long_heartbeat_profile = dataclasses.replace(base_profile, heartbeat="心跳" * 500 + "HEARTBEAT-SHOULD-NOT-APPEAR")
        assert estimate_assembled_tokens(base_profile, _make_tools_l1()) == estimate_assembled_tokens(
            long_heartbeat_profile, _make_tools_l1()
        )

    def test_tokens_positive(self) -> None:
        """总计量为正。"""
        from src.application.services.agent_workflow_context import estimate_assembled_tokens

        assert estimate_assembled_tokens(_make_profile(), _make_tools_l1()) > 0


def cjk_sum_of(text: str) -> int:
    """测试侧独立计量（口径参照实现——总和一致性断言用）。"""
    cjk_count = sum(1 for c in text if "一" <= c <= "鿿" or "　" <= c <= "〿" or "＀" <= c <= "￯")
    non_cjk = max(len(text) - cjk_count, 0)
    return max(int(cjk_count / 1.5 + non_cjk / 4), 1)


# ===================================================================
# 空 L1 降级行为（R3-DF1 核销交付物）
# ===================================================================


class TestEmptyL1Degradation:
    """TOOLS.md 缺失/降级空 L1 时的装配行为（387 传播或显式降级注记）。"""

    def test_empty_l1_degrades_explicitly(self) -> None:
        """空 L1：装配不炸 + 显式降级注记（非静默空段——可观测性）。"""
        from src.application.services.agent_workflow_context import build_system_prompt

        prompt = build_system_prompt(_make_profile(), ())
        assert "无可用工具" in prompt, "空 L1 应显式降级注记"

    def test_empty_l1_tokens_still_estimated(self) -> None:
        """空 L1 仍可计量（降级形态的完整装配产物）。"""
        from src.application.services.agent_workflow_context import estimate_assembled_tokens

        assert estimate_assembled_tokens(_make_profile(), ()) > 0


# ===================================================================
# build_context 装配入口（Subtask 3.3——WorkflowContext 五字段）
# ===================================================================


class TestBuildContext:
    """装配入口：profile_result + task → WorkflowContext（五字段定稿）。"""

    def _make_profile_result(self):
        from src.application.use_cases.agent_profile_loading import AgentProfileLoadResult

        profile = _make_profile()
        tools_l1 = _make_tools_l1()
        return AgentProfileLoadResult(
            agent_id=profile.agent_id,
            role=AgentRole.CEO,
            profile=profile,
            tools_l1=tools_l1,
            startup_context_tokens=0,
        )

    def test_build_context_fields(self) -> None:
        """WorkflowContext 五字段：system_prompt/tools_l1/task/tenant_id/assembled_context_tokens。"""
        from src.application.ports.agent_workflow import WorkflowContext
        from src.application.services.agent_workflow_context import build_context

        result = self._make_profile_result()
        context = build_context(result, "分析新能源汽车行业进入战略")
        assert isinstance(context, WorkflowContext)
        assert "CEO 首席执行官" in context.system_prompt
        assert context.tools_l1 == result.tools_l1
        assert context.task == "分析新能源汽车行业进入战略"
        assert context.assembled_context_tokens > 0
        assert context.tenant_id is not None

    def test_tenant_id_is_fixed_mvp_constant(self) -> None:
        """tenant_id 为 MVP 固定单租户 UUID 常量（两次装配一致——DC-10）。"""
        from src.application.services.agent_workflow_context import build_context

        first = build_context(self._make_profile_result(), "任务一")
        second = build_context(self._make_profile_result(), "任务二")
        assert first.tenant_id == second.tenant_id
