"""RTF 文档解析器单元测试

TDD 红阶段：测试 RTFParser 的纯文本提取、库不可用降级、空文档拒绝。
使用临时 .rtf 文件 fixture。
"""

from __future__ import annotations

import os
import tempfile


def _create_rtf_file(content: str) -> str:
    """创建 RTF fixture"""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".rtf")
    tmp.write(content.encode("utf-8"))
    tmp.close()
    return tmp.name


MIME_RTF = "application/rtf"


class TestRTFParserCreation:
    """RTFParser 构造和基本功能测试"""

    def test_create_parser(self) -> None:
        from src.infrastructure.external_services.document_parsing.rtf_parser import RTFParser

        assert RTFParser() is not None

    def test_parser_implements_document_parser_port(self) -> None:
        from src.domain.ports.document_parser import DocumentParserPort
        from src.infrastructure.external_services.document_parsing.rtf_parser import RTFParser

        assert isinstance(RTFParser(), DocumentParserPort)


class TestRTFParserBasic:
    """RTF 基本解析测试"""

    def test_parse_rtf_text(self) -> None:
        """提取 RTF 纯文本内容"""
        from src.infrastructure.external_services.document_parsing.rtf_parser import RTFParser

        rtf = r"{\rtf1\ansi\deff0 {\fonttbl {\f0 Times New Roman;}} \f0\fs24 RTF 测试文档内容}"
        path = _create_rtf_file(rtf)
        try:
            parser = RTFParser()
            result = parser.parse(path, MIME_RTF)

            assert result.is_completed(), f"RTF 解析应成功，实际: {result.error_message}"
            all_text = " ".join(t.content for p in result.pages for t in p.texts)
            assert "RTF" in all_text, f"应提取到 RTF 文本内容，实际: {all_text}"
        finally:
            os.unlink(path)


class TestRTFParserFallback:
    """striprtf 不可用降级测试"""

    def test_striprtf_unavailable_returns_failed(self) -> None:
        """striprtf 不可用时返回 failed"""
        import builtins
        from unittest import mock

        from src.infrastructure.external_services.document_parsing.rtf_parser import RTFParser

        rtf = r"{\rtf1\ansi 内容}"
        path = _create_rtf_file(rtf)
        try:
            parser = RTFParser()
            original_import = builtins.__import__

            def _block_striprtf_import(name, *args, **kwargs):
                if name in ("striprtf", "striprtf.striprtf"):
                    raise ImportError("striprtf not installed")
                return original_import(name, *args, **kwargs)

            with mock.patch("builtins.__import__", side_effect=_block_striprtf_import):
                result = parser.parse(path, MIME_RTF)

            assert result.parse_status == "failed"
            assert result.error_message is not None
            assert "DOCX" in result.error_message or "striprtf" in result.error_message.lower(), (
                f"错误信息应建议转换为 DOCX，实际: {result.error_message}"
            )
        finally:
            os.unlink(path)


class TestRTFParserEmptyDocument:
    """空文档检测测试"""

    def test_empty_rtf_returns_failed(self) -> None:
        """空 RTF 返回 failed"""
        from src.infrastructure.external_services.document_parsing.rtf_parser import RTFParser

        path = _create_rtf_file(r"{\rtf1\ansi}")
        try:
            parser = RTFParser()
            result = parser.parse(path, MIME_RTF)

            assert result.parse_status == "failed"
            assert result.error_message is not None
        finally:
            os.unlink(path)
