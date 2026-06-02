"""Markdown 文档解析器

使用标准库正则提取 Markdown 标题、段落、表格和代码块的解析器实现。
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import UTC, datetime

from src.domain.ports.document_parser import DocumentParserPort
from src.domain.value_objects.parsed_document import (
    ParsedDocument,
    ParsedElement,
    ParsedPage,
    ParsedTable,
)
from src.infrastructure.external_services.document_parsing._limits import MAX_MD_BYTES

logger = logging.getLogger(__name__)

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
TABLE_ROW_PATTERN = re.compile(r"^\|.+\|$", re.MULTILINE)
SEPARATOR_PATTERN = re.compile(r"^\|[\s:-]+(\|[\s:-]+)*\|$")


class MarkdownParser(DocumentParserPort):
    """Markdown 文档解析器

    使用标准库 + 正则实现，零外部依赖，支持：
    - 标题层级识别（# → h1, ## → h2, ...）
    - 段落按连续空行分割
    - Markdown 表格识别（| col | col | 格式）
    - 代码块内容保留
    - 文件大小上限保护
    """

    def parse(self, file_path: str, mime_type: str) -> ParsedDocument:
        """解析 Markdown 文件

        Args:
            file_path: 本地 Markdown 文件路径
            mime_type: MIME 类型

        Returns:
            结构化解析结果
        """
        doc_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).isoformat()

        try:
            file_size = os.path.getsize(file_path)
        except OSError:
            logger.exception("Markdown 文件大小检查失败")
            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                parse_status="failed",
                error_message="无法访问文件，请检查文件路径或权限",
                parse_timestamp=timestamp,
            )

        if file_size == 0:
            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                parse_status="failed",
                error_message="Markdown 文档为空",
                parse_timestamp=timestamp,
            )

        if file_size > MAX_MD_BYTES:
            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                parse_status="failed",
                error_message=f"Markdown 文件大小 {file_size // (1024 * 1024)}MB 超过 {MAX_MD_BYTES // (1024 * 1024)}MB 限制",
                parse_timestamp=timestamp,
            )

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()

            if not text.strip():
                return ParsedDocument(
                    document_id=doc_id,
                    mime_type=mime_type,
                    parse_status="failed",
                    error_message="Markdown 文档为空",
                    parse_timestamp=timestamp,
                )

            texts: list[ParsedElement] = []

            # 提取标题（# → h1, ## → h2, ...）
            heading_levels = {1: "h1", 2: "h2", 3: "h3", 4: "h4", 5: "h5", 6: "h6"}
            for match in HEADING_PATTERN.finditer(text):
                level = len(match.group(1))
                content = match.group(2).strip()
                if content:
                    texts.append(
                        ParsedElement(
                            content=content,
                            metadata={"style": heading_levels.get(level, f"h{level}")},
                        )
                    )

            # 按连续空行分割段落（排除标题行和表格行）
            paragraphs = re.split(r"\n\s*\n", text)
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                # 跳过纯标题行（已被 heading 正则处理）
                if HEADING_PATTERN.match(para):
                    continue
                # 跳过纯表格区域
                if all(TABLE_ROW_PATTERN.match(line) for line in para.splitlines() if line.strip()):
                    continue
                texts.append(ParsedElement(content=para))

            # 提取表格
            tables: list[ParsedTable] = []
            lines = text.splitlines()
            table_buffer: list[str] = []
            for line in lines:
                if SEPARATOR_PATTERN.match(line):
                    continue
                if TABLE_ROW_PATTERN.match(line):
                    table_buffer.append(line)
                else:
                    if table_buffer:
                        table = self._parse_table_lines(table_buffer)
                        if table:
                            tables.append(table)
                        table_buffer = []
            if table_buffer:
                table = self._parse_table_lines(table_buffer)
                if table:
                    tables.append(table)

            if not texts and not tables:
                return ParsedDocument(
                    document_id=doc_id,
                    mime_type=mime_type,
                    parse_status="failed",
                    error_message="Markdown 文档无有效文本或表格内容",
                    parse_timestamp=timestamp,
                )

            page = ParsedPage(page_number=1, texts=texts, tables=tables)
            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                pages=[page],
                parse_status="completed",
                parse_timestamp=timestamp,
            )

        except Exception:
            logger.exception("Markdown 解析失败")
            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                parse_status="failed",
                error_message="Markdown 文档解析失败",
                parse_timestamp=timestamp,
            )

    def _parse_table_lines(self, lines: list[str]) -> ParsedTable | None:
        """解析 Markdown 表格行列表为 ParsedTable"""
        rows_data: list[list[str]] = []
        for line in lines:
            if SEPARATOR_PATTERN.match(line):
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if cells:
                rows_data.append(cells)
        return ParsedTable(rows=rows_data) if rows_data else None
