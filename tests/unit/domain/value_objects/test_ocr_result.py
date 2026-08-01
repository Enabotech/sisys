"""OCRResult 值对象测试

测试 OCRPageResult 和 OCRConfidenceMark 的构造、序列化、校验。
"""

from __future__ import annotations

from src.domain.value_objects.ocr_result import OCRConfidenceMark, OCRPageResult
from src.domain.value_objects.parsed_document import ParsedElement


class TestOCRConfidenceMark:
    """OCRConfidenceMark 值对象测试"""

    def test_constructor_default(self) -> None:
        """测试默认构造"""
        mark = OCRConfidenceMark(element_index=0)
        assert mark.element_index == 0
        assert mark.confidence == 0.5
        assert mark.needs_review is False

    def test_constructor_with_values(self) -> None:
        """测试带值构造"""
        mark = OCRConfidenceMark(element_index=0, confidence=0.95, needs_review=False)
        assert mark.confidence == 0.95
        assert mark.needs_review is False

    def test_constructor_low_confidence(self) -> None:
        """测试低置信度标记"""
        mark = OCRConfidenceMark(element_index=0, confidence=0.45, needs_review=True)
        assert mark.needs_review is True

    def test_to_dict(self) -> None:
        """测试序列化"""
        mark = OCRConfidenceMark(element_index=0, confidence=0.95)
        result = mark.to_dict()
        assert result["element_index"] == 0
        assert result["confidence"] == 0.95
        assert result["needs_review"] is False

    def test_immutable(self) -> None:
        """测试不可变性（frozen dataclass）"""
        from dataclasses import fields

        mark = OCRConfidenceMark(element_index=0)
        # 验证 frozen dataclass 的字段不可修改
        for field in fields(mark):
            assert field.name in ("element_index", "confidence", "needs_review"), f"意外字段: {field.name}"
        # 验证 confidence 默认值
        assert mark.confidence == 0.5


class TestOCRPageResult:
    """OCRPageResult 值对象测试"""

    def test_constructor_default(self) -> None:
        """测试默认构造"""
        result = OCRPageResult(page_number=1)
        assert result.page_number == 1
        assert result.elements == []
        assert result.raw_response == {}

    def test_constructor_with_elements(self) -> None:
        """测试带元素构造"""
        elements = [
            ParsedElement(content="测试文本", confidence=0.95),
            ParsedElement(content="hello world", confidence=0.88),
        ]
        result = OCRPageResult(page_number=1, elements=elements)
        assert len(result.elements) == 2
        assert result.elements[0].content == "测试文本"
        assert result.elements[0].confidence == 0.95

    def test_to_dict(self) -> None:
        """测试序列化（不含 raw_response）"""
        elements = [ParsedElement(content="test", confidence=0.95)]
        result = OCRPageResult(page_number=1, elements=elements, raw_response={"key": "secret"})
        output = result.to_dict()
        assert output["page_number"] == 1
        assert len(output["elements"]) == 1
        assert "raw_response" not in output  # raw_response 不序列化

    def test_immutable(self) -> None:
        """测试不可变性（frozen dataclass）"""
        from dataclasses import fields

        result = OCRPageResult(page_number=1)
        # 验证 frozen dataclass 的字段不可修改
        for field in fields(result):
            assert field.name in ("page_number", "elements", "raw_response", "markdown_text", "markdown_images"), (
                f"意外字段: {field.name}"
            )
        # 验证 page_number 默认值
        assert result.page_number == 1

    def test_empty_elements(self) -> None:
        """测试空元素列表"""
        result = OCRPageResult(page_number=1, elements=[])
        assert result.elements == []
        output = result.to_dict()
        assert output["elements"] == []
