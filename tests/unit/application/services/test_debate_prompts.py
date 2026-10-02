"""Story 4.5 — debate_prompts（视角/裁判 prompt 映射）单元测试

验证 PERSPECTIVE_PROMPT_MAP 覆盖红蓝两键、模板占位符 format 可用、
角色标记短语存在（供调用断言与立场遵循断言——分派按 response_schema 身份，
角色标记不作分派依据）与 SYNTHESIS 模板红蓝注入占位。
"""

from __future__ import annotations

import pytest

from src.application.services.debate_prompts import (
    PERSPECTIVE_PROMPT_MAP,
    SYNTHESIS_SYSTEM_PROMPT,
    SYNTHESIS_USER_TEMPLATE,
)
from src.domain.value_objects.debate import DebatePerspective


class TestPerspectivePromptMap:
    def test_map_covers_both_perspectives(self) -> None:
        """映射覆盖红蓝两键（且仅两键）"""
        assert set(PERSPECTIVE_PROMPT_MAP) == {
            DebatePerspective.RED_AGGRESSIVE,
            DebatePerspective.BLUE_CONSERVATIVE,
        }

    @pytest.mark.parametrize(
        "perspective",
        [DebatePerspective.RED_AGGRESSIVE, DebatePerspective.BLUE_CONSERVATIVE],
        ids=["red", "blue"],
    )
    def test_prompt_entry_structure(self, perspective: DebatePerspective) -> None:
        """每个条目含 system_prompt + user_prompt_template 两键"""
        entry = PERSPECTIVE_PROMPT_MAP[perspective]
        assert set(entry) == {"system_prompt", "user_prompt_template"}
        assert isinstance(entry["system_prompt"], str)
        assert isinstance(entry["user_prompt_template"], str)
        assert entry["system_prompt"].strip()
        assert entry["user_prompt_template"].strip()

    def test_red_system_prompt_contains_role_marker(self) -> None:
        """红 system_prompt 含"激进派"角色标记（断言锚点，非分派依据）"""
        assert "激进派" in PERSPECTIVE_PROMPT_MAP[DebatePerspective.RED_AGGRESSIVE]["system_prompt"]

    def test_blue_system_prompt_contains_role_marker(self) -> None:
        """蓝 system_prompt 含"保守派"角色标记"""
        assert "保守派" in PERSPECTIVE_PROMPT_MAP[DebatePerspective.BLUE_CONSERVATIVE]["system_prompt"]

    def test_red_and_blue_prompts_are_distinct(self) -> None:
        """红蓝 prompt 差异化（视角对立的承载）"""
        red = PERSPECTIVE_PROMPT_MAP[DebatePerspective.RED_AGGRESSIVE]
        blue = PERSPECTIVE_PROMPT_MAP[DebatePerspective.BLUE_CONSERVATIVE]
        assert red["system_prompt"] != blue["system_prompt"]
        assert red["user_prompt_template"] != blue["user_prompt_template"]

    @pytest.mark.parametrize(
        "perspective",
        [DebatePerspective.RED_AGGRESSIVE, DebatePerspective.BLUE_CONSERVATIVE],
        ids=["red", "blue"],
    )
    def test_user_template_placeholders_format(self, perspective: DebatePerspective) -> None:
        """user_prompt_template 含 {title}/{background} 占位且 format 可用"""
        template = PERSPECTIVE_PROMPT_MAP[perspective]["user_prompt_template"]
        assert "{title}" in template
        assert "{background}" in template
        formatted = template.format(title="测试议题", background="测试背景")
        assert "测试议题" in formatted
        assert "测试背景" in formatted
        assert "{" not in formatted.replace("{}", "")  # 无残留占位符

    @pytest.mark.parametrize(
        "perspective",
        [DebatePerspective.RED_AGGRESSIVE, DebatePerspective.BLUE_CONSERVATIVE],
        ids=["red", "blue"],
    )
    def test_perspective_prompts_no_cross_output_leak(self, perspective: DebatePerspective) -> None:
        """视角 prompt 模板不含对方输出注入占位（独立立场方法论——生成阶段互相不可见）"""
        template = PERSPECTIVE_PROMPT_MAP[perspective]["user_prompt_template"]
        assert "{red_analysis}" not in template
        assert "{blue_analysis}" not in template
        assert "{opponent" not in template


class TestSynthesisPrompts:
    def test_synthesis_system_prompt_contains_judge_marker(self) -> None:
        """裁判 system_prompt 含"裁判"角色标记（必然同时描述红蓝双方——分派禁用子串）"""
        assert "裁判" in SYNTHESIS_SYSTEM_PROMPT

    def test_synthesis_system_prompt_describes_both_sides(self) -> None:
        """裁判 prompt 同时含红蓝双方描述（对抗发生在合成阶段）"""
        assert "激进派" in SYNTHESIS_SYSTEM_PROMPT
        assert "保守派" in SYNTHESIS_SYSTEM_PROMPT

    def test_synthesis_user_template_has_injection_placeholders(self) -> None:
        """合成 user 模板含红蓝注入占位且 format 可用"""
        assert "{red_analysis}" in SYNTHESIS_USER_TEMPLATE
        assert "{blue_analysis}" in SYNTHESIS_USER_TEMPLATE
        formatted = SYNTHESIS_USER_TEMPLATE.format(red_analysis='{"stance": "进入"}', blue_analysis='{"stance": "延后"}')
        assert '{"stance": "进入"}' in formatted
        assert '{"stance": "延后"}' in formatted

    def test_synthesis_output_requirements(self) -> None:
        """裁判 prompt 声明输出要求（共识/分歧/风险等级）"""
        combined = SYNTHESIS_SYSTEM_PROMPT + SYNTHESIS_USER_TEMPLATE
        assert "共识" in combined
        assert "分歧" in combined
        assert "风险" in combined

    def test_all_prompts_in_chinese(self) -> None:
        """prompt 全中文（面向中文战略场景）"""
        for entry in PERSPECTIVE_PROMPT_MAP.values():
            assert "你" in entry["system_prompt"]
        assert "你" in SYNTHESIS_SYSTEM_PROMPT
