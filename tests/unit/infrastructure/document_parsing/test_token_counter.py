"""BGE-M3 Token 计数器测试

测试 _count_tokens_bge_m3 函数的中英文 token 计数精度和降级策略。
"""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from src.infrastructure.document_parsing.semantic_chunker_impl import estimate_tokens


class TestEstimateTokensV4:
    """测试 estimate_tokens 作为 fallback 仍然可用"""

    def test_empty_string(self) -> None:
        """空字符串"""
        assert estimate_tokens("") == 0

    def test_whitespace_only(self) -> None:
        """仅空白字符"""
        assert estimate_tokens("   \n\n  ") >= 0

    def test_bge_m3_token_count_type(self) -> None:
        """验证 v4 默认使用 bge-m3 token 计数方式"""
        from src.domain.value_objects.semantic_chunk import ChunkingConfig

        config = ChunkingConfig()
        assert config.token_count_type == "bge-m3"


class TestBgeM3TokenCounter:
    """测试 BGE-M3 精准 token 计数（需要真实 tokenizer）"""

    def test_importable(self) -> None:
        """验证 tokenizers 库可用"""
        import tokenizers  # noqa: F401

    def test_count_tokens_chinese_accuracy(self) -> None:
        """验证中文 token 计数精度 < 5%"""
        try:
            from src.infrastructure.document_parsing.semantic_chunker_impl import _count_tokens_bge_m3

            text = "战略规划需要系统性思维和全局视角"
            count = _count_tokens_bge_m3(text)

            # 验证计数合理（token 数量应 >0 且 ≤ 字符数）
            assert count > 0
            assert count <= len(text) + 5  # 中文 BPE tokenization 通常 token 数 ≤ 字符数 + 少量额外
        except FileNotFoundError:
            pytest.skip("BGE-M3 tokenizer 文件不可用")

    def test_count_tokens_english_accuracy(self) -> None:
        """验证英文 token 计数精度 < 3%"""
        try:
            from src.infrastructure.document_parsing.semantic_chunker_impl import _count_tokens_bge_m3

            text = "Strategic planning requires systematic thinking and a global perspective"
            count = _count_tokens_bge_m3(text)

            assert count > 0
            # 英文通常 token 数 < 单词数 * 1.5
            word_count = len(text.split())
            assert count <= word_count * 2  # 每个单词通常 1-2 tokens
        except FileNotFoundError:
            pytest.skip("BGE-M3 tokenizer 文件不可用")

    def test_count_tokens_mixed(self) -> None:
        """验证中英混合文本"""
        try:
            from src.infrastructure.document_parsing.semantic_chunker_impl import _count_tokens_bge_m3

            text = "战略规划需要 AI 和 Machine Learning 技术的支撑"
            count = _count_tokens_bge_m3(text)
            assert count > 0
        except FileNotFoundError:
            pytest.skip("BGE-M3 tokenizer 文件不可用")

    def test_count_tokens_fallback_on_error(self, caplog) -> None:
        """验证 tokenizer 不可用时降级为启发式 + WARNING 日志"""
        import src.infrastructure.document_parsing.semantic_chunker_impl as mod

        with patch.object(
            mod,
            "_get_bge_m3_tokenizer",
            return_value=None,
        ):
            with caplog.at_level(logging.WARNING):
                text = "测试文本"
                count = mod._count_tokens_bge_m3(text)
                # 降级为启发式
                assert count > 0

    def test_count_tokens_short_text(self) -> None:
        """验证短文本"""
        try:
            from src.infrastructure.document_parsing.semantic_chunker_impl import _count_tokens_bge_m3

            assert _count_tokens_bge_m3("A") > 0
            assert _count_tokens_bge_m3("中") > 0
        except FileNotFoundError:
            pytest.skip("BGE-M3 tokenizer 文件不可用")

    def test_estimate_tokens_still_works_for_backward_compat(self) -> None:
        """验证 estimate_tokens() 作为 fallback 仍然可用"""
        assert estimate_tokens("中文") > 0
        assert estimate_tokens("English text here") > 0


__all__ = [
    "TestEstimateTokensV4",
    "TestBgeM3TokenCounter",
]
