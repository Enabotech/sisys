"""文本文件格式处理器单元测试

验证 TextFormatHandler 首行标题提取、空白行跳过、Markdown # 剥离、UTF-8 BOM 处理

"""

from __future__ import annotations

import tempfile
from pathlib import Path

from plugins.crawler.core.format.handlers.text_handler import TextFormatHandler
from plugins.crawler.core.value_objects import FileMetadata


class TestTextFormatHandler:
    """TextFormatHandler 测试"""

    def setup_method(self) -> None:
        self.handler = TextFormatHandler()

    def _create_text_file(self, content: str, suffix: str = ".txt") -> str:
        """创建测试文本文件

        Args:
            content: 文件内容
            suffix: 文件后缀

        Returns:
            临时文件路径
        """
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False, mode="w", encoding="utf-8")
        tmp.write(content)
        tmp.close()
        return tmp.name

    def test_can_handle_txt(self) -> None:
        """应识别 .txt 扩展名"""
        assert self.handler.can_handle("test.txt", "")

    def test_can_handle_csv(self) -> None:
        """应识别 .csv 扩展名"""
        assert self.handler.can_handle("test.csv", "")

    def test_can_handle_md(self) -> None:
        """应识别 .md 扩展名"""
        assert self.handler.can_handle("test.md", "")

    def test_can_handle_text_mime(self) -> None:
        """应识别 text/ MIME 前缀"""
        assert self.handler.can_handle("test.bin", "text/plain")

    def test_cannot_handle_non_text(self) -> None:
        """不应处理非文本文件"""
        assert not self.handler.can_handle("test.pdf", "application/pdf")

    def test_first_line_as_title(self) -> None:
        """首行应作为标题"""
        path = self._create_text_file("项目规划书\n第二行内容")
        try:
            meta = self.handler.extract_metadata(path)
            assert meta.title == "项目规划书"
            assert meta.content_title == "项目规划书"
        finally:
            Path(path).unlink(missing_ok=True)

    def test_skip_blank_lines(self) -> None:
        """应跳过前导空白行"""
        path = self._create_text_file("\n\n\n实际标题\n内容")
        try:
            meta = self.handler.extract_metadata(path)
            assert meta.title == "实际标题"
        finally:
            Path(path).unlink(missing_ok=True)

    def test_markdown_heading_stripped(self) -> None:
        """应剥离 Markdown # 前缀"""
        path = self._create_text_file("# Markdown 标题\n正文", suffix=".md")
        try:
            meta = self.handler.extract_metadata(path)
            assert "Markdown 标题" in meta.title
            assert "#" not in meta.title
        finally:
            Path(path).unlink(missing_ok=True)

    def test_markdown_h2_stripped(self) -> None:
        """应剥离 ## 前缀"""
        path = self._create_text_file("## 二级标题\n正文", suffix=".md")
        try:
            meta = self.handler.extract_metadata(path)
            assert "二级标题" in meta.title
            assert "#" not in meta.title
        finally:
            Path(path).unlink(missing_ok=True)

    def test_utf8_bom_stripped(self) -> None:
        """应处理 UTF-8 BOM"""
        tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
        tmp.write("﻿BOM 标题\n内容".encode("utf-8-sig"))
        tmp.close()
        try:
            meta = self.handler.extract_metadata(tmp.name)
            assert "BOM" in meta.title
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    def test_empty_file_returns_empty(self) -> None:
        """空文件应返回空元数据"""
        path = self._create_text_file("")
        try:
            meta = self.handler.extract_metadata(path)
            assert meta == FileMetadata()
        finally:
            Path(path).unlink(missing_ok=True)

    def test_only_blank_lines_returns_empty(self) -> None:
        """仅含空白行时应返回空元数据"""
        path = self._create_text_file("\n\n  \n\t\n")
        try:
            meta = self.handler.extract_metadata(path)
            assert meta == FileMetadata()
        finally:
            Path(path).unlink(missing_ok=True)

    def test_short_line_ignored(self) -> None:
        """过短行（≤2字符）应被忽略"""
        path = self._create_text_file("ab\n完整标题行\n内容")
        try:
            meta = self.handler.extract_metadata(path)
            assert meta.title == "完整标题行"
        finally:
            Path(path).unlink(missing_ok=True)
