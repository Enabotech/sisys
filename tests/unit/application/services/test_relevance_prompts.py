"""Story 3.7 检索相关性评估 Prompt 模板单元测试

验证评估 Prompt 模板的变量替换、维度评估标准完整性和评分规则。
"""

from __future__ import annotations


class TestRuntimeSystemPrompt:
    """评估 System Prompt 验证"""

    def test_system_prompt_exists(self) -> None:
        """系统提示模板存在"""
        from src.application.services.relevance_prompts import SYSTEM_PROMPT

        assert SYSTEM_PROMPT is not None
        assert len(SYSTEM_PROMPT) > 50

    def test_system_prompt_has_role_definition(self) -> None:
        """System Prompt 包含角色定义"""
        from src.application.services.relevance_prompts import SYSTEM_PROMPT

        assert "检索质量评估专家" in SYSTEM_PROMPT
        assert "相关性" in SYSTEM_PROMPT
        assert "完整性" in SYSTEM_PROMPT
        assert "时效性" in SYSTEM_PROMPT

    def test_system_prompt_has_scoring_standard(self) -> None:
        """System Prompt 包含评分标准（0-1 分，0.6 合格线）"""
        from src.application.services.relevance_prompts import SYSTEM_PROMPT

        assert "0-1" in SYSTEM_PROMPT or "0 到 1" in SYSTEM_PROMPT
        assert "0.6" in SYSTEM_PROMPT

    def test_system_prompt_has_output_format_constraint(self) -> None:
        """System Prompt 包含输出格式约束"""
        from src.application.services.relevance_prompts import SYSTEM_PROMPT

        assert "JSON" in SYSTEM_PROMPT

    def test_system_prompt_has_block_rule(self) -> None:
        """System Prompt 包含阻断规则说明"""
        from src.application.services.relevance_prompts import SYSTEM_PROMPT

        assert "阻断" in SYSTEM_PROMPT


class TestUserPromptTemplate:
    """评估 User Prompt 模板验证"""

    def test_user_prompt_template_exists(self) -> None:
        """用户提示模板存在"""
        from src.application.services.relevance_prompts import USER_PROMPT_TEMPLATE

        assert USER_PROMPT_TEMPLATE is not None
        assert len(USER_PROMPT_TEMPLATE) > 50

    def test_template_has_query_text_placeholder(self) -> None:
        """模板包含 query_text 占位符"""
        from src.application.services.relevance_prompts import USER_PROMPT_TEMPLATE

        assert "{query_text}" in USER_PROMPT_TEMPLATE

    def test_template_has_search_context_placeholder(self) -> None:
        """模板包含 search_context 占位符"""
        from src.application.services.relevance_prompts import USER_PROMPT_TEMPLATE

        assert "{search_context}" in USER_PROMPT_TEMPLATE

    def test_template_formats_with_variables(self) -> None:
        """模板支持动态注入 var 变量"""
        from src.application.services.relevance_prompts import USER_PROMPT_TEMPLATE

        result = USER_PROMPT_TEMPLATE.format(
            query_text="测试查询",
            search_context="检索结果内容",
        )
        assert "测试查询" in result
        assert "检索结果内容" in result

    def test_template_has_evaluation_requirements(self) -> None:
        """User Prompt 包含评估要求"""
        from src.application.services.relevance_prompts import USER_PROMPT_TEMPLATE

        assert "评估" in USER_PROMPT_TEMPLATE
        assert "分数" in USER_PROMPT_TEMPLATE
        assert "理由" in USER_PROMPT_TEMPLATE


class TestDimensionStandards:
    """三维度评分标准验证"""

    def test_context_relevance_standard(self) -> None:
        """相关性标准存在（完全匹配查询意图 = 1.0）"""
        from src.application.services.relevance_prompts import (
            CONTEXT_RELEVANCE_STANDARD,
        )

        assert "相关性" in CONTEXT_RELEVANCE_STANDARD
        assert "1.0" in CONTEXT_RELEVANCE_STANDARD
        assert "0.0" in CONTEXT_RELEVANCE_STANDARD

    def test_completeness_standard(self) -> None:
        """完整性标准存在（全部信息覆盖 = 1.0）"""
        from src.application.services.relevance_prompts import COMPLETENESS_STANDARD

        assert "完整性" in COMPLETENESS_STANDARD
        assert "1.0" in COMPLETENESS_STANDARD
        assert "0.0" in COMPLETENESS_STANDARD

    def test_timeliness_standard(self) -> None:
        """时效性标准存在"""
        from src.application.services.relevance_prompts import TIMELINESS_STANDARD

        assert "时效性" in TIMELINESS_STANDARD
        assert "1.0" in TIMELINESS_STANDARD
        assert "0.0" in TIMELINESS_STANDARD

    def test_timeliness_standard_mentions_payload_fields(self) -> None:
        """时效性标准提及 updated_at/created_at 字段"""
        from src.application.services.relevance_prompts import TIMELINESS_STANDARD

        assert "updated_at" in TIMELINESS_STANDARD
        assert "created_at" in TIMELINESS_STANDARD

    def test_dimension_standards_combined_into_system_prompt(self) -> None:
        """维度标准整合进系统 Prompt"""
        from src.application.services.relevance_prompts import (
            COMPLETENESS_STANDARD,
            CONTEXT_RELEVANCE_STANDARD,
            SYSTEM_PROMPT,
            TIMELINESS_STANDARD,
        )

        assert CONTEXT_RELEVANCE_STANDARD in SYSTEM_PROMPT
        assert COMPLETENESS_STANDARD in SYSTEM_PROMPT
        assert TIMELINESS_STANDARD in SYSTEM_PROMPT
