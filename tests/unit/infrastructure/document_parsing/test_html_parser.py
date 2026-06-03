"""HTML 文档解析器单元测试

TDD 红阶段：测试 HTMLParser 的文本提取、表格提取、标题层级识别、编码检测、空文档拒绝。
使用临时 HTML 文件 fixture。
"""

from __future__ import annotations

import os
import tempfile


def _create_html_file(body: str) -> str:
    """创建 HTML fixture"""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
    tmp.write(body.encode("utf-8"))
    tmp.close()
    return tmp.name


MIME_HTML = "text/html"


class TestHTMLParserCreation:
    """HTMLParser 构造和基本功能测试"""

    def test_create_parser(self) -> None:
        from src.infrastructure.document_parsing.html_parser import HTMLParser

        assert HTMLParser() is not None

    def test_parser_implements_document_parser_port(self) -> None:
        from src.domain.ports.document_parser import DocumentParserPort
        from src.infrastructure.document_parsing.html_parser import HTMLParser

        assert isinstance(HTMLParser(), DocumentParserPort)


class TestHTMLParserTextExtraction:
    """HTML 文本提取测试"""

    def test_parse_basic_html(self) -> None:
        """解析基本 HTML，提取文本内容"""
        from src.infrastructure.document_parsing.html_parser import HTMLParser

        path = _create_html_file("<html><body><h1>标题</h1><p>段落内容</p></body></html>")
        try:
            parser = HTMLParser()
            result = parser.parse(path, MIME_HTML)

            assert result.is_completed()
            all_text = " ".join(t.content for p in result.pages for t in p.texts)
            assert "标题" in all_text
            assert "段落内容" in all_text
        finally:
            os.unlink(path)

    def test_parse_html_heading_styles(self) -> None:
        """HTML 标题层级映射到 metadata.style"""
        from src.infrastructure.document_parsing.html_parser import HTMLParser

        path = _create_html_file("<html><body><h1>一级</h1><h2>二级</h2><h3>三级</h3></body></html>")
        try:
            parser = HTMLParser()
            result = parser.parse(path, MIME_HTML)

            assert result.is_completed()
            styles = [t.metadata.get("style", "") for p in result.pages for t in p.texts]
            assert "h1" in styles, f"应识别到 h1，实际: {styles}"
            assert "h2" in styles, f"应识别到 h2，实际: {styles}"
            assert "h3" in styles, f"应识别到 h3，实际: {styles}"
        finally:
            os.unlink(path)


class TestHTMLParserTableExtraction:
    """HTML 表格提取测试"""

    def test_parse_html_table(self) -> None:
        """提取 HTML 表格为 ParsedTable"""
        from src.infrastructure.document_parsing.html_parser import HTMLParser

        html_content = "<html><body><table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table></body></html>"
        path = _create_html_file(html_content)
        try:
            parser = HTMLParser()
            result = parser.parse(path, MIME_HTML)

            assert result.is_completed()
            all_tables = [t for p in result.pages for t in p.tables]
            assert len(all_tables) >= 1
            assert all_tables[0].rows == [["A", "B"], ["1", "2"]]
        finally:
            os.unlink(path)


class TestHTMLParserEmptyDocument:
    """空文档检测测试"""

    def test_empty_html_returns_failed(self) -> None:
        """空 body HTML 返回 failed"""
        from src.infrastructure.document_parsing.html_parser import HTMLParser

        path = _create_html_file("<html><body></body></html>")
        try:
            parser = HTMLParser()
            result = parser.parse(path, MIME_HTML)

            assert result.parse_status == "failed"
            assert result.error_message is not None
        finally:
            os.unlink(path)
