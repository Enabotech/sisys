"""PDF 文档解析器

使用 pypdf 提取 PDF 文本的解析器实现，支持加密检测和多页处理。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pypdf import PdfReader

from src.domain.ports.document_parser import DocumentParserPort
from src.domain.value_objects.parsed_document import (
    ParsedDocument,
    ParsedElement,
    ParsedPage,
)

_MAX_PDF_PAGES = 500  # AC-1: 超大 PDF（>500 页）降级处理


class PDFParser(DocumentParserPort):
    """PDF 文档解析器

    使用 pypdf.PdfReader 提取文本内容，支持：
    - 纯文本提取
    - 多页文档处理
    - 加密 PDF 检测与拒绝
    - 空文档检测
    - 超大文档保护（>500 页返回失败）
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

                if num_pages > _MAX_PDF_PAGES:
                    return ParsedDocument(
                        document_id=doc_id,
                        mime_type=mime_type,
                        parse_status="failed",
                        error_message=f"PDF 文档页数({num_pages})超过限制({_MAX_PDF_PAGES})，请分段处理",
                        parse_timestamp=timestamp,
                    )

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
        except Exception as e:
            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                parse_status="failed",
                error_message=f"PDF 文件读取失败: {e}",
                parse_timestamp=timestamp,
            )
