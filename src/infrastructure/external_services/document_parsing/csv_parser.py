"""CSV 文档解析器

使用标准库 csv + csv.Sniffer 解析 CSV 的解析器实现。
编码检测复用提取的 detect_and_decode 共享函数。
"""

from __future__ import annotations

import csv
import logging
import os
import uuid
from datetime import UTC, datetime

from src.domain.ports.document_parser import DocumentParserPort
from src.domain.value_objects.parsed_document import (
    ParsedDocument,
    ParsedPage,
    ParsedTable,
)
from src.infrastructure.external_services.document_parsing._encoding import detect_and_decode
from src.infrastructure.external_services.document_parsing._limits import MAX_CSV_BYTES

logger = logging.getLogger(__name__)


class CSVParser(DocumentParserPort):
    """CSV 文档解析器

    使用标准库 csv 模块解析 CSV 文件，支持：
    - 分隔符自动检测（csv.Sniffer）
    - 编码自动检测（UTF-8 → GBK → GB18030）
    - 文件大小上限保护
    """

    def parse(self, file_path: str, mime_type: str) -> ParsedDocument:
        """解析 CSV 文件

        Args:
            file_path: 本地 CSV 文件路径
            mime_type: MIME 类型

        Returns:
            结构化解析结果
        """
        doc_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).isoformat()

        try:
            file_size = os.path.getsize(file_path)
        except OSError:
            logger.exception("CSV 文件大小检查失败")
            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                parse_status="failed",
                error_message="无法访问文件，请检查文件路径或权限",
                parse_timestamp=timestamp,
            )

        if file_size > MAX_CSV_BYTES:
            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                parse_status="failed",
                error_message=f"CSV 文件大小 {file_size // (1024 * 1024)}MB 超过 {MAX_CSV_BYTES // (1024 * 1024)}MB 限制",
                parse_timestamp=timestamp,
            )

        try:
            with open(file_path, "rb") as f:
                raw = f.read()

            if len(raw) == 0:
                return ParsedDocument(
                    document_id=doc_id,
                    mime_type=mime_type,
                    parse_status="failed",
                    error_message="CSV 文档为空",
                    parse_timestamp=timestamp,
                )

            text, detected_encoding = detect_and_decode(raw)
            lines = text.splitlines()
            if not lines:
                return ParsedDocument(
                    document_id=doc_id,
                    mime_type=mime_type,
                    parse_status="failed",
                    error_message="CSV 文档为空",
                    parse_timestamp=timestamp,
                )

            # 使用 csv.Sniffer 自动检测分隔符
            sample = "\n".join(lines[:10])
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            except csv.Error:
                dialect = csv.excel  # 无法检测时回退到默认逗号分隔

            reader = csv.reader(lines, dialect)
            rows_data: list[list[str]] = []
            for row in reader:
                if row:
                    rows_data.append(list(row))

            if not rows_data:
                return ParsedDocument(
                    document_id=doc_id,
                    mime_type=mime_type,
                    parse_status="failed",
                    error_message="CSV 文档无有效数据行",
                    parse_timestamp=timestamp,
                )

            table = ParsedTable(
                rows=rows_data,
                metadata={
                    "encoding": detected_encoding,
                    "delimiter": dialect.delimiter if hasattr(dialect, "delimiter") else ",",
                },
            )
            page = ParsedPage(page_number=1, tables=[table])

            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                pages=[page],
                parse_status="completed",
                parse_timestamp=timestamp,
            )

        except Exception:
            logger.exception("CSV 解析失败")
            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                parse_status="failed",
                error_message="CSV 文档解析失败",
                parse_timestamp=timestamp,
            )
