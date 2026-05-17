"""Tests for L1TextExtractor.

RED PHASE: 验证 L1TextExtractor 文本提取功能
"""

from __future__ import annotations

import pytest

from src.application.use_cases.text_processing.l1_text_extractor import L1ExtractionResult, L1TextExtractor


class TestL1TextExtractorPatterns:
    """L1TextExtractor 模式匹配验证"""

    def test_remember_pattern(self):
        """验证"记住 X"模式"""
        extractor = L1TextExtractor()
        result = extractor.extract("记住，以后用 bun 而不是 npm")
        assert result.operation == "save"
        assert "bun" in result.content
        assert "npm" in result.content

    def test_remembered_pattern(self):
        """验证"记住了 X"模式"""
        extractor = L1TextExtractor()
        result = extractor.extract("记住了，Python 是最好的语言")
        assert result.operation == "save"
        assert "Python" in result.content

    def test_future_use_pattern(self):
        """验证"以后用 X"模式"""
        extractor = L1TextExtractor()
        result = extractor.extract("以后用 docker 而不是 vm")
        assert result.operation == "save"
        assert "docker" in result.content

    def test_should_remember_pattern(self):
        """验证"要记住 X"模式"""
        extractor = L1TextExtractor()
        result = extractor.extract("要记住，每天早上要看邮件")
        assert result.operation == "save"
        assert "邮件" in result.content

    def test_dont_forget_pattern(self):
        """验证"别忘了 X"模式"""
        extractor = L1TextExtractor()
        result = extractor.extract("别忘了，周五要开会")
        assert result.operation == "delete"
        assert "开会" in result.content

    def test_delete_pattern(self):
        """验证"不要记住 X"模式"""
        extractor = L1TextExtractor()
        result = extractor.extract("不要记住 那个会议")
        assert result.operation == "delete"
        assert "会议" in result.content

    def test_update_pattern(self):
        """验证"改成 X"模式"""
        extractor = L1TextExtractor()
        result = extractor.extract("改成使用 VSCode 作为编辑器")
        assert result.operation == "update"
        assert "VSCode" in result.content

    def test_no_space_remember_pattern(self):
        """验证无空格边界情况（如"记住abc"）"""
        extractor = L1TextExtractor()
        result = extractor.extract("记住密码是 123456")
        assert result.operation == "save"
        assert "123456" in result.content


class TestL1TextExtractorEdgeCases:
    """L1TextExtractor 边界情况验证"""

    def test_empty_input_raises(self):
        """验证空输入抛出异常"""
        extractor = L1TextExtractor()
        with pytest.raises(ValueError, match="输入不能为空"):
            extractor.extract("")

    def test_whitespace_only_raises(self):
        """验证空白输入抛出异常"""
        extractor = L1TextExtractor()
        with pytest.raises(ValueError, match="输入不能为空"):
            extractor.extract("   ")

    def test_unsupported_pattern_raises(self):
        """验证不支持的模式抛出异常"""
        extractor = L1TextExtractor()
        with pytest.raises(ValueError, match="无法识别输入模式"):
            extractor.extract("hello world")


class TestL1TextExtractorSupports:
    """L1TextExtractor supports 方法验证"""

    @pytest.mark.parametrize(
        "user_input,expected",
        [
            ("记住 X", True),
            ("记住了 X", True),
            ("别忘了 X", True),
            ("不要记住 X", True),
            ("hello world", False),
            ("", False),
        ],
    )
    def test_supports(self, user_input: str, expected: bool):
        """验证 supports 方法"""
        extractor = L1TextExtractor()
        assert extractor.supports(user_input) == expected


class TestL1ExtractionResult:
    """L1ExtractionResult 数据类验证"""

    def test_result_has_required_fields(self):
        """验证结果包含必需字段"""
        result = L1ExtractionResult(
            content="test content",
            original="记住 test content",
            pattern=r"记住\s+(.+)",
            operation="save",
        )
        assert result.content == "test content"
        assert result.original == "记住 test content"
        assert result.pattern == r"记住\s+(.+)"
        assert result.operation == "save"
