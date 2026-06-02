"""HTML 文档解析器

使用 BeautifulSoup + lxml 提取 HTML 文本、表格和标题层级的解析器实现。
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import UTC, datetime

from src.domain.ports.document_parser import DocumentParserPort
from src.domain.value_objects.parsed_document import (
    ParsedDocument,
    ParsedElement,
    ParsedPage,
    ParsedTable,
)
from src.infrastructure.external_services.document_parsing._limits import MAX_HTML_BYTES

logger = logging.getLogger(__name__)


class HTMLParser(DocumentParserPort):
    """HTML 文档解析器

    使用 BeautifulSoup + lxml 解析 HTML，支持：
    - 纯文本提取（get_text(separator='\\n', strip=True)）
    - 表格提取（<table> 元素 → ParsedTable）
    - 标题层级识别（h1-h6 → metadata.style）
    - 编码自动检测（BeautifulSoup 内置）
    - 文件大小上限保护
    """

    def parse(self, file_path: str, mime_type: str) -> ParsedDocument:
        """解析 HTML 文件

        Args:
            file_path: 本地 HTML 文件路径
            mime_type: MIME 类型

        Returns:
            结构化解析结果
        """
        doc_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).isoformat()

        try:
            file_size = os.path.getsize(file_path)
        except OSError:
            logger.exception("HTML 文件大小检查失败")
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
                error_message="HTML 文档为空",
                parse_timestamp=timestamp,
            )

        if file_size > MAX_HTML_BYTES:
            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                parse_status="failed",
                error_message=f"HTML 文件大小 {file_size // (1024 * 1024)}MB 超过 {MAX_HTML_BYTES // (1024 * 1024)}MB 限制",
                parse_timestamp=timestamp,
            )

        try:
            from bs4 import BeautifulSoup

            with open(file_path, "rb") as f:
                raw = f.read()

            # BeautifulSoup 内置编码检测
            soup = BeautifulSoup(raw, "lxml")

            # 提取 body 文本
            body = soup.body
            if body is None:
                body = soup

            texts: list[ParsedElement] = []

            # 提取标题元素（h1-h6），保留层级（跳过表格内的标题）
            heading_tags = body.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
            for tag in heading_tags:
                if tag.find_parent("table"):
                    continue
                content = tag.get_text(separator=" ", strip=True)
                if content:
                    texts.append(ParsedElement(content=content, metadata={"style": tag.name}))
                tag.decompose()

            # 提取正文段落（标题已从 DOM 中移除，不会重复）
            main_text = body.get_text(separator="\n", strip=True)
            if main_text:
                texts.append(ParsedElement(content=main_text, metadata={"style": "body"}))

            # 提取表格
            tables: list[ParsedTable] = []
            for table_elem in body.find_all("table"):
                rows_data: list[list[str]] = []
                for tr in table_elem.find_all("tr"):
                    cells = tr.find_all(["th", "td"])
                    if cells:
                        rows_data.append([cell.get_text(separator=" ", strip=True) for cell in cells])
                if rows_data:
                    tables.append(ParsedTable(rows=rows_data))

            if not texts and not tables:
                return ParsedDocument(
                    document_id=doc_id,
                    mime_type=mime_type,
                    parse_status="failed",
                    error_message="HTML 文档无有效文本或表格内容",
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
            logger.exception("HTML 解析失败")
            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                parse_status="failed",
                error_message="HTML 文档解析失败，文件可能已损坏或格式不正确",
                parse_timestamp=timestamp,
            )
