"""TXT 文档解析器单元测试

TDD 红阶段：测试 TextParser 的编码检测、段落分割、超大文件处理。
"""

from __future__ import annotations

import os
import tempfile


def _create_txt(content: bytes, suffix: str = ".txt") -> str:
    """创建 TXT fixture 文件"""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(content)
    tmp.close()
    return tmp.name


class TestTextParserCreation:
    """TextParser 构造测试"""

    def test_create_parser(self) -> None:
        from src.infrastructure.document_parsing.text_parser import TextParser

        parser = TextParser()
        assert parser is not None


class TestTextParserEncoding:
    """编码检测测试"""

    def test_utf8_encoding(self) -> None:
        from src.infrastructure.document_parsing.text_parser import TextParser

        parser = TextParser()
        path = _create_txt("Hello World\n这是中文".encode("utf-8"))
        try:
            result = parser.parse(path, "text/plain")
            assert result.parse_status == "completed"
            all_text = " ".join(t.content for p in result.pages for t in p.texts)
            assert "Hello World" in all_text
            assert "中文" in all_text
        finally:
            os.unlink(path)

    def test_gbk_encoding(self) -> None:
        from src.infrastructure.document_parsing.text_parser import TextParser

        parser = TextParser()
        path = _create_txt("中文测试内容".encode("gbk"))
        try:
            result = parser.parse(path, "text/plain")
            assert result.parse_status == "completed"
            all_text = " ".join(t.content for p in result.pages for t in p.texts)
            assert "中文测试内容" in all_text
        finally:
            os.unlink(path)

    def test_gb18030_encoding(self) -> None:
        from src.infrastructure.document_parsing.text_parser import TextParser

        parser = TextParser()
        path = _create_txt("测试内容".encode("gb18030"))
        try:
            result = parser.parse(path, "text/plain")
            assert result.parse_status == "completed"
        finally:
            os.unlink(path)


class TestTextParserParagraphSplit:
    """段落分割测试"""

    def test_split_by_blank_lines(self) -> None:
        from src.infrastructure.document_parsing.text_parser import TextParser

        parser = TextParser()
        content = "第一段\n\n第二段\n\n第三段"
        path = _create_txt(content.encode("utf-8"))
        try:
            result = parser.parse(path, "text/plain")
            assert result.parse_status == "completed"
            # 应该至少提取到3段文本
            texts = [t.content for p in result.pages for t in p.texts]
            assert len(texts) >= 3
        finally:
            os.unlink(path)

    def test_single_paragraph(self) -> None:
        from src.infrastructure.document_parsing.text_parser import TextParser

        parser = TextParser()
        path = _create_txt("只有一段文字没有空行".encode("utf-8"))
        try:
            result = parser.parse(path, "text/plain")
            assert result.parse_status == "completed"
            texts = [t.content for p in result.pages for t in p.texts]
            assert len(texts) >= 1
        finally:
            os.unlink(path)


class TestTextParserEdgeCases:
    """边界场景测试"""

    def test_empty_file(self) -> None:
        """空 TXT 文件应返回 failed 状态（AC-3 严格验证）"""
        from src.infrastructure.document_parsing.text_parser import TextParser

        parser = TextParser()
        path = _create_txt(b"")
        try:
            result = parser.parse(path, "text/plain")
            assert result.is_failed()
            assert result.error_message is not None
            assert "TXT 文件为空" in result.error_message
            assert len(result.pages) == 0
        finally:
            os.unlink(path)

    def test_output_structure(self) -> None:
        import json

        from src.infrastructure.document_parsing.text_parser import TextParser

        parser = TextParser()
        path = _create_txt("test content".encode("utf-8"))
        try:
            result = parser.parse(path, "text/plain")
            assert result.mime_type == "text/plain"
            assert result.document_id
            d = result.to_dict()
            json.dumps(d, ensure_ascii=False)  # 确认可序列化
        finally:
            os.unlink(path)

    def test_single_page_structure(self) -> None:
        """TXT 文件应作为单页处理"""
        from src.infrastructure.document_parsing.text_parser import TextParser

        parser = TextParser()
        path = _create_txt("content".encode("utf-8"))
        try:
            result = parser.parse(path, "text/plain")
            assert len(result.pages) == 1
            assert result.pages[0].page_number == 1
        finally:
            os.unlink(path)

    def test_oversized_file_returns_failed(self) -> None:
        """超过 10MB 的 TXT 文件应返回 failed 状态"""
        from unittest.mock import patch

        from src.infrastructure.document_parsing.text_parser import TextParser

        parser = TextParser()
        path = _create_txt(b"small")
        try:
            # Mock os.path.getsize 返回超大文件尺寸
            with patch(
                "src.infrastructure.document_parsing.text_parser.os.path.getsize",
                return_value=11 * 1024 * 1024,
            ):
                result = parser.parse(path, "text/plain")
            assert result.parse_status == "failed"
            assert result.error_message is not None
            assert "10MB" in result.error_message
        finally:
            os.unlink(path)

    def test_getsize_oserror_returns_failed(self, monkeypatch) -> None:
        """os.path.getsize 抛出 OSError 时应返回 failed 而非异常穿透"""
        from src.infrastructure.document_parsing.text_parser import TextParser

        monkeypatch.setattr("os.path.getsize", lambda _: (_ for _ in ()).throw(OSError("Permission denied")))
        parser = TextParser()
        result = parser.parse("/inaccessible/file.txt", "text/plain")
        assert result.is_failed()
        assert "权限" in (result.error_message or "")
