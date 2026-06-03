"""PDF 文档解析器

使用 pypdf 提取 PDF 文本的解析器实现，支持加密检测、多页处理与文件大小保护。
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import UTC, datetime

from pypdf import PdfReader

from src.domain.ports.document_parser import DocumentParserPort
from src.domain.value_objects.parsed_document import (
    ParsedDocument,
    ParsedElement,
    ParsedPage,
)
from src.infrastructure.document_parsing._limits import (
    MAX_PDF_BYTES,
    MAX_PDF_PAGES,
)

logger = logging.getLogger(__name__)


class PDFParser(DocumentParserPort):
    """PDF 文档解析器

    使用 pypdf.PdfReader 提取文本内容，支持：
    - 纯文本提取
    - 多页文档处理
    - 加密 PDF 检测与拒绝
    - 空文档检测
    - 文件大小与页数上限保护
    - 表格结构契约预留（真实检测推迟至 Story 2-4）
    """

    def parse(self, file_path: str, mime_type: str) -> ParsedDocument:
        """解析 PDF 文件

        Args:
            file_path: 本地 PDF 文件路径
            mime_type: MIME 类型（PDFParser 忽略此参数）

        Returns:
            结构化解析结果
        """
        doc_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).isoformat()

        # 防御解压炸弹：解析前校验文件大小
        try:
            file_size = os.path.getsize(file_path)
        except OSError:
            logger.exception("PDF 文件大小检查失败")
            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                parse_status="failed",
                error_message="无法访问文件，请检查文件路径或权限",
                parse_timestamp=timestamp,
            )
        if file_size > MAX_PDF_BYTES:
            size_mb = file_size // (1024 * 1024)
            limit_mb = MAX_PDF_BYTES // (1024 * 1024)
            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                parse_status="failed",
                error_message=(f"PDF 文件大小 {size_mb}MB 超过 {limit_mb}MB 限制，可能为解压炸弹"),
                parse_timestamp=timestamp,
            )

        try:
            with open(file_path, "rb") as f:
                reader = PdfReader(f)

                if reader.is_encrypted:
                    return ParsedDocument(
                        document_id=doc_id,
                        mime_type=mime_type,
                        parse_status="failed",
                        error_message="PDF 文档已加密，无法解析",
                        parse_timestamp=timestamp,
                    )

                num_pages = len(reader.pages)
                if num_pages == 0:
                    return ParsedDocument(
                        document_id=doc_id,
                        mime_type=mime_type,
                        parse_status="failed",
                        error_message="PDF 文档为空，包含 0 页",
                        parse_timestamp=timestamp,
                    )

                if num_pages > MAX_PDF_PAGES:
                    return ParsedDocument(
                        document_id=doc_id,
                        mime_type=mime_type,
                        parse_status="failed",
                        error_message=(f"PDF 文档页数({num_pages})超过限制({MAX_PDF_PAGES})，请分段处理"),
                        parse_timestamp=timestamp,
                    )

                # 表格检测：MVP 仅契约预留，真实检测推迟至 Story 2-4
                pages: list[ParsedPage] = []
                for i, page in enumerate(reader.pages):
                    text = page.extract_text() or ""
                    if text.strip():
                        texts = [ParsedElement(content=text.strip())]
                    else:
                        texts = []
                    pages.append(
                        ParsedPage(
                            page_number=i + 1,
                            texts=texts,
                            tables=[],
                            images=[],
                        )
                    )

                return ParsedDocument(
                    document_id=doc_id,
                    mime_type=mime_type,
                    pages=pages,
                    parse_status="completed",
                    parse_timestamp=timestamp,
                )
        except Exception:
            # 安全：原始异常可能含文件路径，详细 traceback 记录到日志
            logger.exception("PDF 文件解析失败")
            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                parse_status="failed",
                error_message="PDF 解析失败，请检查文件是否损坏或重试",
                parse_timestamp=timestamp,
            )
