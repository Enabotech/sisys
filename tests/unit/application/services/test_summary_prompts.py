"""Story 3.6 摘要 Prompt 模板单元测试

验证三个视角的 System/User Prompt 模板、变量替换、完整性。
"""

from __future__ import annotations

from src.application.services.summary_prompts import (
    FINANCIAL_SYSTEM_PROMPT,
    FINANCIAL_USER_PROMPT_TEMPLATE,
    MARKET_SYSTEM_PROMPT,
    MARKET_USER_PROMPT_TEMPLATE,
    PERSPECTIVE_PROMPT_MAP,
    TECHNICAL_SYSTEM_PROMPT,
    TECHNICAL_USER_PROMPT_TEMPLATE,
)


class TestFinancialPromptTemplates:
    """财务视角 Prompt 模板验证"""

    def test_financial_system_prompt_defined(self) -> None:
        """Financial System Prompt 已定义"""
        assert FINANCIAL_SYSTEM_PROMPT is not None
        assert len(FINANCIAL_SYSTEM_PROMPT) > 50

    def test_financial_system_prompt_contains_role(self) -> None:
        """Financial System Prompt 包含角色定义"""
        assert "财务" in FINANCIAL_SYSTEM_PROMPT or "分析师" in FINANCIAL_SYSTEM_PROMPT

    def test_financial_system_prompt_contains_json_constraint(self) -> None:
        """Financial System Prompt 包含 JSON Schema 输出约束"""
        assert "JSON" in FINANCIAL_SYSTEM_PROMPT or "Schema" in FINANCIAL_SYSTEM_PROMPT

    def test_financial_user_prompt_template_defined(self) -> None:
        """Financial User Prompt 模板已定义"""
        assert FINANCIAL_USER_PROMPT_TEMPLATE is not None
        assert len(FINANCIAL_USER_PROMPT_TEMPLATE) > 50

    def test_financial_user_prompt_has_query_placeholder(self) -> None:
        """Financial User Prompt 包含查询文本占位符"""
        assert "{query_text}" in FINANCIAL_USER_PROMPT_TEMPLATE

    def test_financial_user_prompt_has_context_placeholder(self) -> None:
        """Financial User Prompt 包含检索上下文占位符"""
        assert "{search_context}" in FINANCIAL_USER_PROMPT_TEMPLATE

    def test_financial_user_prompt_format(self) -> None:
        """Financial User Prompt 模板变量替换正确"""
        formatted = FINANCIAL_USER_PROMPT_TEMPLATE.format(
            query_text="测试查询",
            search_context="这是搜索结果上下文",
        )
        assert "测试查询" in formatted
        assert "这是搜索结果上下文" in formatted


class TestMarketPromptTemplates:
    """市场视角 Prompt 模板验证"""

    def test_market_system_prompt_defined(self) -> None:
        """Market System Prompt 已定义"""
        assert MARKET_SYSTEM_PROMPT is not None
        assert len(MARKET_SYSTEM_PROMPT) > 50

    def test_market_system_prompt_contains_role(self) -> None:
        """Market System Prompt 包含角色定义"""
        assert "市场" in MARKET_SYSTEM_PROMPT or "分析师" in MARKET_SYSTEM_PROMPT

    def test_market_user_prompt_template_defined(self) -> None:
        """Market User Prompt 模板已定义"""
        assert MARKET_USER_PROMPT_TEMPLATE is not None
        assert len(MARKET_USER_PROMPT_TEMPLATE) > 50

    def test_market_user_prompt_has_query_placeholder(self) -> None:
        """Market User Prompt 包含查询文本占位符"""
        assert "{query_text}" in MARKET_USER_PROMPT_TEMPLATE

    def test_market_user_prompt_has_context_placeholder(self) -> None:
        """Market User Prompt 包含检索上下文占位符"""
        assert "{search_context}" in MARKET_USER_PROMPT_TEMPLATE

    def test_market_user_prompt_format(self) -> None:
        """Market User Prompt 模板变量替换正确"""
        formatted = MARKET_USER_PROMPT_TEMPLATE.format(
            query_text="市场分析",
            search_context="市场数据",
        )
        assert "市场分析" in formatted
        assert "市场数据" in formatted


class TestTechnicalPromptTemplates:
    """技术视角 Prompt 模板验证"""

    def test_technical_system_prompt_defined(self) -> None:
        """Technical System Prompt 已定义"""
        assert TECHNICAL_SYSTEM_PROMPT is not None
        assert len(TECHNICAL_SYSTEM_PROMPT) > 50

    def test_technical_system_prompt_contains_role(self) -> None:
        """Technical System Prompt 包含角色定义"""
        assert "技术" in TECHNICAL_SYSTEM_PROMPT or "工程师" in TECHNICAL_SYSTEM_PROMPT

    def test_technical_user_prompt_template_defined(self) -> None:
        """Technical User Prompt 模板已定义"""
        assert TECHNICAL_USER_PROMPT_TEMPLATE is not None
        assert len(TECHNICAL_USER_PROMPT_TEMPLATE) > 50

    def test_technical_user_prompt_has_query_placeholder(self) -> None:
        """Technical User Prompt 包含查询文本占位符"""
        assert "{query_text}" in TECHNICAL_USER_PROMPT_TEMPLATE

    def test_technical_user_prompt_has_context_placeholder(self) -> None:
        """Technical User Prompt 包含检索上下文占位符"""
        assert "{search_context}" in TECHNICAL_USER_PROMPT_TEMPLATE

    def test_technical_user_prompt_format(self) -> None:
        """Technical User Prompt 模板变量替换正确"""
        formatted = TECHNICAL_USER_PROMPT_TEMPLATE.format(
            query_text="技术架构",
            search_context="技术文档内容",
        )
        assert "技术架构" in formatted
        assert "技术文档内容" in formatted


class TestPerspectivePromptMap:
    """PERSPECTIVE_PROMPT_MAP 映射验证"""

    def test_map_contains_all_perspectives(self) -> None:
        """映射包含所有三个视角"""
        assert "financial" in PERSPECTIVE_PROMPT_MAP
        assert "market" in PERSPECTIVE_PROMPT_MAP
        assert "technical" in PERSPECTIVE_PROMPT_MAP

    def test_map_contains_system_and_user_keys(self) -> None:
        """每个视角映射包含 system_prompt 和 user_prompt_template"""
        for perspective in ("financial", "market", "technical"):
            entry = PERSPECTIVE_PROMPT_MAP[perspective]
            assert "system_prompt" in entry
            assert "user_prompt_template" in entry
            assert len(entry["system_prompt"]) > 50
            assert len(entry["user_prompt_template"]) > 50

    def test_map_values_are_strings(self) -> None:
        """映射值均为字符串"""
        for perspective in ("financial", "market", "technical"):
            entry = PERSPECTIVE_PROMPT_MAP[perspective]
            assert isinstance(entry["system_prompt"], str)
            assert isinstance(entry["user_prompt_template"], str)
