"""实体抽取异常体系单元测试

验证 EntityExtractionError 异常的构造、序列化、HTTP 映射和编码唯一性。
遵循故事规范：EntityExtractionError(340)→ExternalException→500
"""

from __future__ import annotations

from src.domain.exceptions import (
    EntityExtractionError,
    ExternalException,
)


class TestEntityExtractionError:
    """EntityExtractionError 异常测试"""

    def test_code(self) -> None:
        """验证异常编码为 EXCEPTION_340"""
        assert EntityExtractionError.code == "EXCEPTION_340"

    def test_inheritance(self) -> None:
        """验证继承 ExternalException"""
        assert issubclass(EntityExtractionError, ExternalException)

    def test_constructor_with_context(self) -> None:
        """验证构造器携带 content_preview/extraction_strategy/entity_count 上下文"""
        error = EntityExtractionError(
            "实体抽取失败",
            content_preview="BLM 模型分析",
            extraction_strategy="hybrid",
            entity_count=5,
        )
        assert str(error) == "实体抽取失败"
        assert error.code == "EXCEPTION_340"
        assert error.context["content_preview"] == "BLM 模型分析"
        assert error.context["extraction_strategy"] == "hybrid"
        assert error.context["entity_count"] == 5

    def test_content_preview_truncated(self) -> None:
        """验证 content_preview 截断至 200 字符"""
        long_content = "x" * 500
        error = EntityExtractionError(
            "实体抽取失败",
            content_preview=long_content,
            extraction_strategy="rule",
        )
        assert len(error.context["content_preview"]) <= 200
        assert error.context.get("content_preview_truncated") is True

    def test_content_preview_not_truncated(self) -> None:
        """验证短内容不标记截断"""
        error = EntityExtractionError(
            "实体抽取失败",
            content_preview="short",
            extraction_strategy="rule",
        )
        assert error.context["content_preview"] == "short"
        assert error.context.get("content_preview_truncated") is False

    def test_to_dict_serialization(self) -> None:
        """验证 to_dict() 序列化正确"""
        error = EntityExtractionError(
            "实体抽取失败",
            content_preview="BLM 模型",
            extraction_strategy="llm",
            entity_count=3,
            cause=ValueError("LLM 调用失败"),
        )
        d = error.to_dict()
        assert d["code"] == "EXCEPTION_340"
        assert d["message"] == "实体抽取失败"
        assert "content_preview" in d["context"]
        assert "extraction_strategy" in d["context"]
        assert "entity_count" in d["context"]
        assert "cause" in d
        assert d["cause"]["type"] == "ValueError"

    def test_http_status_500(self) -> None:
        """验证 HTTP 映射为 500"""
        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert EXCEPTION_HTTP_MAP.get(EntityExtractionError) == 500, "EntityExtractionError 应映射到 500"


class TestEntityExtractionErrorCodeUniqueness:
    """实体抽取异常编码唯一性验证"""

    def test_code_not_conflict_with_llm(self) -> None:
        """验证 340 不与 LLM 330-339 冲突"""
        assert 340 not in set(range(330, 340)), "340 与 LLM 编码冲突"
        assert 340 not in set(range(320, 330)), "340 与 OCR 编码冲突"
        assert 340 not in set(range(309, 320)), "340 与 sandbox 编码冲突"
        assert 340 not in set(range(306, 309)), "340 与 embedding 编码冲突"

    def test_code_within_external_range(self) -> None:
        """验证 340 在 external 子域 301-399 范围内"""
        assert 301 <= 340 <= 399, "340 不在 external 子域范围 301-399 内"

    def test_code_in_entity_extraction_subdomain(self) -> None:
        """验证 340 在 entity_extraction 子域 340-349 范围内"""
        from src.domain.exceptions._code_ranges import get_range_for_subdomain

        range_info = get_range_for_subdomain("entity_extraction")
        assert range_info is not None, "entity_extraction 子域未在 CODE_RANGES 中注册"
        start, end = range_info
        assert 340 <= 340 <= end, "340 不在 entity_extraction 子域 [340, 349] 范围内"
