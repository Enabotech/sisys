"""Word 文档解析器

使用 python-docx 提取 DOCX 文本和表格的解析器实现。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from src.domain.value_objects.parsed_document import (
    ParsedDocument,
    ParsedElement,
    ParsedPage,
    ParsedTable,
)


class WordParser:
    """Word 文档解析器

    使用 python-docx.Document 提取文本和表格内容，支持：
    - 段落文本提取（含标题样式识别）
    - 表格行列结构提取
    - 旧版 DOC 格式拒绝
    """

    def parse(self, file_path: str, mime_type: str) -> ParsedDocument:
        """解析 DOCX 文件

        Args:
            file_path: 本地 DOCX 文件路径
            mime_type: MIME 类型（用于 DOC 格式拒绝）

        Returns:
            结构化解析结果
        """
        doc_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).isoformat()

        if mime_type == "application/msword":
            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                parse_status="failed",
                error_message="不支持旧版 DOC 格式，请转换为 DOCX",
                parse_timestamp=timestamp,
            )

        try:
            from docx import Document

            with open(file_path, "rb") as f:
                doc = Document(f)

                texts: list[ParsedElement] = []
                for paragraph in doc.paragraphs:
                    text = paragraph.text.strip()
                    if text:
                        style_name = paragraph.style.name if paragraph.style else ""
                        texts.append(ParsedElement(content=text, metadata={"style": style_name}))

                tables: list[ParsedTable] = []
                for table in doc.tables:
                    rows = []
                    for row in table.rows:
                        row_data = [cell.text for cell in row.cells]
                        rows.append(row_data)
                    if rows:
                        tables.append(ParsedTable(rows=rows))

                page = ParsedPage(
                    page_number=1,
                    texts=texts,
                    tables=tables,
                    images=[],
                )

                return ParsedDocument(
                    document_id=doc_id,
                    mime_type=mime_type,
                    pages=[page],
                    parse_status="completed",
                    parse_timestamp=timestamp,
                )
        except Exception as e:
            error_msg = str(e)
            if "docx" in error_msg.lower() or "zip" in error_msg.lower():
                error_msg = f"文件格式无效，请确保为 DOCX 格式: {error_msg}"
            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                parse_status="failed",
                error_message=error_msg,
                parse_timestamp=timestamp,
            )
