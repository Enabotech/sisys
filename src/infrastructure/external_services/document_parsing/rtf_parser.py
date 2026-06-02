"""RTF 文档解析器

尝试使用 striprtf 库提取纯文本内容，库不可用时优雅降级的解析器实现。
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
)
from src.infrastructure.external_services.document_parsing._limits import MAX_RTF_BYTES

logger = logging.getLogger(__name__)


class RTFParser(DocumentParserPort):
    """RTF 文档解析器

    使用 striprtf 提取纯文本内容，支持：
    - RTF 纯文本提取
    - striprtf 不可用时优雅降级（建议转换为 DOCX）
    - 文件大小上限保护
    """

    def parse(self, file_path: str, mime_type: str) -> ParsedDocument:
        """解析 RTF 文件

        Args:
            file_path: 本地 RTF 文件路径
            mime_type: MIME 类型

        Returns:
            结构化解析结果
        """
        doc_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).isoformat()

        try:
            file_size = os.path.getsize(file_path)
        except OSError:
            logger.exception("RTF 文件大小检查失败")
            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                parse_status="failed",
                error_message="无法访问文件，请检查文件路径或权限",
                parse_timestamp=timestamp,
            )

        if file_size > MAX_RTF_BYTES:
            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                parse_status="failed",
                error_message=f"RTF 文件大小 {file_size // (1024 * 1024)}MB 超过 {MAX_RTF_BYTES // (1024 * 1024)}MB 限制",
                parse_timestamp=timestamp,
            )

        try:
            try:
                from striprtf.striprtf import rtf_to_text
            except ImportError:
                logger.warning("striprtf 库未安装，无法解析 RTF 文档")
                return ParsedDocument(
                    document_id=doc_id,
                    mime_type=mime_type,
                    parse_status="failed",
                    error_message="RTF 解析需要 striprtf 库，请安装后重试或转换为 DOCX",
                    parse_timestamp=timestamp,
                )

            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                rtf_content = f.read()

            text = rtf_to_text(rtf_content).strip()
            if not text:
                return ParsedDocument(
                    document_id=doc_id,
                    mime_type=mime_type,
                    parse_status="failed",
                    error_message="RTF 文档无有效文本内容",
                    parse_timestamp=timestamp,
                )

            page = ParsedPage(
                page_number=1,
                texts=[ParsedElement(content=text)],
            )

            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                pages=[page],
                parse_status="completed",
                parse_timestamp=timestamp,
            )

        except Exception:
            logger.exception("RTF 解析失败")
            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                parse_status="failed",
                error_message="RTF 文档解析失败，文件可能已损坏或格式不正确",
                parse_timestamp=timestamp,
            )
