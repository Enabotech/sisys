"""Story 3.8 溯源 Prompt 模板单元测试

验证 traceability_prompts.py 中的模板结构、变量替换正确性和格式化输出。
"""

from __future__ import annotations

import uuid

from src.application.services.traceability_prompts import (
    ACCURACY_STANDARD,
    COMPLETENESS_STANDARD,
    RELEVANCE_STANDARD,
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    build_traceability_prompt,
    format_citation_context,
)
from src.domain.value_objects.citation import Citation
from src.domain.value_objects.parsed_document import BoundingBox


def _make_citation(bbox: BoundingBox | None = None) -> Citation:
    """构造测试用 Citation"""
    return Citation(
        citation_id="chunk-001-cit",
        document_id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
        chunk_id="chunk-001",
        text="公司营收2024年同比增长15%，净利润率达到12%。",
        start_offset=0,
        end_offset=20,
        page_number=3,
        bbox=bbox,
        confidence=0.92,
    )


class TestSystemPrompt:
    """System Prompt 结构测试"""

    def test_system_prompt_contains_role_definition(self) -> None:
        """System Prompt 包含角色定义"""
        assert "你是一位文献引用质量评估专家" in SYSTEM_PROMPT

    def test_system_prompt_contains_output_format(self) -> None:
        """System Prompt 包含输出格式约束"""
        assert "输出符合以下 JSON Schema" in SYSTEM_PROMPT

    def test_system_prompt_contains_all_standards(self) -> None:
        """System Prompt 包含三维评分标准"""
        assert RELEVANCE_STANDARD in SYSTEM_PROMPT
        assert COMPLETENESS_STANDARD in SYSTEM_PROMPT
        assert ACCURACY_STANDARD in SYSTEM_PROMPT


class TestUserPrompt:
    """User Prompt 模板测试"""

    def test_user_prompt_template_has_placeholders(self) -> None:
        """User Prompt 模板包含 claim 和 citations_context 占位符"""
        assert "{claim}" in USER_PROMPT_TEMPLATE
        assert "{citations_context}" in USER_PROMPT_TEMPLATE

    def test_user_prompt_format_variable_substitution(self) -> None:
        """User Prompt 变量替换正确"""
        user_prompt = USER_PROMPT_TEMPLATE.format(
            claim="测试结论",
            citations_context="引文列表",
        )
        assert "测试结论" in user_prompt
        assert "引文列表" in user_prompt
        assert "{claim}" not in user_prompt


class TestCitationContextFormatting:
    """引文上下文格式化测试"""

    def test_format_citation_context(self) -> None:
        """格式化引文列表为上下文"""
        citation = _make_citation()
        context = format_citation_context([citation])
        assert "chunk-001-cit" in context
        assert "公司营收2024年同比增长15%" in context
        assert "0.92" in context

    def test_format_citation_context_with_bbox(self) -> None:
        """含 bbox 的引文格式化包含坐标信息"""
        bbox = BoundingBox(x=10.5, y=20.3, width=300.0, height=50.0, page=2)
        citation = _make_citation(bbox=bbox)
        context = format_citation_context([citation])
        assert "page=2" in context
        assert "x=10.5" in context
        assert "width=300.0" in context

    def test_format_citation_context_without_bbox(self) -> None:
        """无 bbox 的引文格式化标记为无"""
        citation = _make_citation(bbox=None)
        context = format_citation_context([citation])
        assert "无" in context

    def test_format_citation_context_empty_list(self) -> None:
        """空引文列表返回空字符串"""
        context = format_citation_context([])
        assert context == ""


class TestBuildTraceabilityPrompt:
    """Prompt 构建测试"""

    def test_build_prompt_returns_tuple(self) -> None:
        """build_traceability_prompt 返回 (system_prompt, user_prompt)"""
        citation = _make_citation()
        system_prompt, user_prompt = build_traceability_prompt(
            claim="测试结论",
            citations=[citation],
        )
        assert system_prompt == SYSTEM_PROMPT
        assert "测试结论" in user_prompt
        assert "chunk-001-cit" in user_prompt

    def test_prompt_contains_claim_and_citations(self) -> None:
        """Prompt 包含结论文本和引文列表"""
        citation = _make_citation()
        _, user_prompt = build_traceability_prompt(
            claim="营收增长15%",
            citations=[citation],
        )
        assert "营收增长15%" in user_prompt
        assert "公司营收2024年同比增长15%" in user_prompt
