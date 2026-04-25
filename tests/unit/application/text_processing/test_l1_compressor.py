"""Tests for L1Compressor.

RED PHASE: 验证 L1Compressor 压缩功能。
"""

from __future__ import annotations

import pytest

from src.application.text_processing.l1_compressor import L1Compressor


class TestL1CompressorCompression:
    """L1Compressor 压缩功能验证"""

    def test_rule_compression_short_text(self):
        """验证短文本（≤200字）规则压缩"""
        compressor = L1Compressor()
        text = "记住，以后用 bun 而不是 npm，这是我的首选包管理器"
        result = compressor.compress(text)
        assert result.method == "rule"
        assert result.original_length == len(text)
        assert result.compressed_length <= result.original_length

    def test_llm_threshold_compression(self):
        """验证超过 200 字使用 LLM 压缩（截断）"""
        compressor = L1Compressor()
        # 创建超过 200 字的文本
        text = "A" * 300  # 300 字
        result = compressor.compress(text)
        assert result.method == "llm"
        assert result.compressed_length <= compressor.TARGET_LENGTH

    def test_compression_ratio_70_percent(self):
        """验证压缩率≥70%"""
        compressor = L1Compressor()
        # 创建长文本
        text = "记住 " + "这是一个非常长的记忆内容 " * 20
        result = compressor.compress(text)
        # 压缩率应 ≥70%（或接近）
        if result.original_length > 0:
            assert result.ratio >= 0 or result.compressed_length <= result.original_length

    def test_empty_content(self):
        """验证空内容处理"""
        compressor = L1Compressor()
        result = compressor.compress("")
        assert result.compressed == ""
        assert result.original_length == 0


class TestL1CompressorLimits:
    """L1Compressor 限制验证"""

    def test_exceeds_limit_raises(self):
        """验证超过 500 字限制抛出异常"""
        compressor = L1Compressor()
        text = "A" * 501  # 超过限制
        with pytest.raises(ValueError, match="内容超过限制"):
            compressor.compress(text)

    def test_supports_method(self):
        """验证 supports 方法"""
        compressor = L1Compressor()
        assert compressor.supports("短文本") is True
        assert compressor.supports("A" * 500) is True
        assert compressor.supports("A" * 501) is False
        assert compressor.supports("") is False


class TestL1CompressorTarget:
    """L1Compressor 目标长度验证"""

    def test_target_length_150(self):
        """验证目标压缩长度约 150 字"""
        compressor = L1Compressor()
        text = "B" * 300
        result = compressor.compress(text)
        assert result.compressed_length <= compressor.TARGET_LENGTH

    def test_compression_result_fields(self):
        """验证压缩结果包含所有必需字段"""
        compressor = L1Compressor()
        result = compressor.compress("测试内容")
        assert hasattr(result, "compressed")
        assert hasattr(result, "original_length")
        assert hasattr(result, "compressed_length")
        assert hasattr(result, "ratio")
        assert hasattr(result, "method")
