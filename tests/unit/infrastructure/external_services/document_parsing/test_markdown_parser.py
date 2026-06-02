"""Markdown 文档解析器单元测试

TDD 红阶段：测试 MarkdownParser 的标题层级识别、段落分割、表格提取、代码块保留、空文档拒绝。
使用临时 .md 文件 fixture。
"""

from __future__ import annotations

import os
import tempfile


def _create_md_file(content: str) -> str:
    """创建 Markdown fixture"""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".md")
    tmp.write(content.encode("utf-8"))
    tmp.close()
    return tmp.name


MIME_MD = "text/markdown"


class TestMarkdownParserCreation:
    """MarkdownParser 构造和基本功能测试"""

    def test_create_parser(self) -> None:
        from src.infrastructure.external_services.document_parsing.markdown_parser import MarkdownParser

        assert MarkdownParser() is not None

    def test_parser_implements_document_parser_port(self) -> None:
        from src.domain.ports.document_parser import DocumentParserPort
        from src.infrastructure.external_services.document_parsing.markdown_parser import MarkdownParser

        assert isinstance(MarkdownParser(), DocumentParserPort)


class TestMarkdownParserHeadings:
    """标题层级测试"""

    def test_parse_headings(self) -> None:
        """识别 # → h1，## → h2 标题层级"""
        from src.infrastructure.external_services.document_parsing.markdown_parser import MarkdownParser

        path = _create_md_file("# 一级标题\n\n## 二级标题\n\n### 三级标题\n")
        try:
            parser = MarkdownParser()
            result = parser.parse(path, MIME_MD)

            assert result.is_completed()
            all_text = " ".join(t.content for p in result.pages for t in p.texts)
            assert "一级标题" in all_text
            assert "二级标题" in all_text
            assert "三级标题" in all_text
        finally:
            os.unlink(path)


class TestMarkdownParserParagraphs:
    """段落分割测试"""

    def test_paragraph_split_by_blank_lines(self) -> None:
        """按连续空行分割段落"""
        from src.infrastructure.external_services.document_parsing.markdown_parser import MarkdownParser

        path = _create_md_file("第一段内容\n\n第二段内容\n\n第三段内容\n")
        try:
            parser = MarkdownParser()
            result = parser.parse(path, MIME_MD)

            assert result.is_completed()
            texts = [t.content for p in result.pages for t in p.texts]
            # 至少 3 个段落元素
            assert len(texts) >= 3, f"应按空行分割至少 3 段，实际: {len(texts)}: {texts}"
        finally:
            os.unlink(path)


class TestMarkdownParserTable:
    """Markdown 表格测试"""

    def test_parse_markdown_table(self) -> None:
        """识别 | col | col | 格式表格，过滤分隔符行"""
        from src.infrastructure.external_services.document_parsing.markdown_parser import MarkdownParser

        path = _create_md_file("| A | B |\n|---|---|\n| 1 | 2 |\n")
        try:
            parser = MarkdownParser()
            result = parser.parse(path, MIME_MD)

            assert result.is_completed()
            all_tables = [t for p in result.pages for t in p.tables]
            assert len(all_tables) >= 1, "应提取到 1 个表格"
            # 分隔符行应被过滤，仅 2 行数据
            assert len(all_tables[0].rows) == 2, f"应 2 行，实际: {len(all_tables[0].rows)}"
        finally:
            os.unlink(path)


class TestMarkdownParserCodeBlocks:
    """代码块保留测试"""

    def test_code_block_preserved(self) -> None:
        """代码块内容保留"""
        from src.infrastructure.external_services.document_parsing.markdown_parser import MarkdownParser

        path = _create_md_file("```python\nprint('hello')\n```\n")
        try:
            parser = MarkdownParser()
            result = parser.parse(path, MIME_MD)

            assert result.is_completed()
            all_text = " ".join(t.content for p in result.pages for t in p.texts)
            assert "print" in all_text, f"应保留代码块内容，实际: {all_text}"
        finally:
            os.unlink(path)


class TestMarkdownParserEmptyDocument:
    """空文档检测测试"""

    def test_empty_markdown_returns_failed(self) -> None:
        """空 Markdown 返回 failed"""
        from src.infrastructure.external_services.document_parsing.markdown_parser import MarkdownParser

        path = _create_md_file("")
        try:
            parser = MarkdownParser()
            result = parser.parse(path, MIME_MD)

            assert result.parse_status == "failed"
            assert result.error_message is not None
        finally:
            os.unlink(path)
