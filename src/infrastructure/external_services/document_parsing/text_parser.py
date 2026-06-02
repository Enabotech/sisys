"""TXT 文档解析器

支持 UTF-8/GBK/GB18030 编码检测和段落分割的文本解析器。
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
)
from src.infrastructure.external_services.document_parsing._limits import MAX_TXT_BYTES

logger = logging.getLogger(__name__)


class TextParser(DocumentParserPort):
    """TXT 文档解析器

    支持特性：
    - 编码自动检测（UTF-8 → GBK → GB18030，窄集优先超集兜底）
    - 段落分割（连续空行分隔）
    - 文件大小上限保护
    """

    def parse(self, file_path: str, mime_type: str) -> ParsedDocument:
        """解析 TXT 文件

        Args:
            file_path: 本地 TXT 文件路径
            mime_type: MIME 类型（TextParser 忽略此参数）

        Returns:
            结构化解析结果
        """
        doc_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).isoformat()

        try:
            file_size = os.path.getsize(file_path)
            if file_size > MAX_TXT_BYTES:
                size_mb = file_size // (1024 * 1024)
                limit_mb = MAX_TXT_BYTES // (1024 * 1024)
                return ParsedDocument(
                    document_id=doc_id,
                    mime_type=mime_type,
                    parse_status="failed",
                    error_message=(f"TXT 文件大小 {size_mb}MB 超过 {limit_mb}MB 限制，当前版本不支持分块处理"),
                    parse_timestamp=timestamp,
                )
            with open(file_path, "rb") as f:
                raw_bytes = f.read()
        except OSError:
            # 安全：原始异常可能含文件路径，详细 traceback 记录到日志
            logger.exception("TXT 文件读取失败")
            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                parse_status="failed",
                error_message="无法访问文件，请检查文件路径或权限",
                parse_timestamp=timestamp,
            )

        if not raw_bytes:
            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                parse_status="failed",
                error_message="TXT 文件为空",
                parse_timestamp=timestamp,
            )

        # 编码检测：UTF-8 → GBK → GB18030（GB18030 是 GBK 超集，作为兜底）
        text = self._detect_and_decode(raw_bytes)

        # 段落分割
        paragraphs = self._split_paragraphs(text)

        texts = [ParsedElement(content=p) for p in paragraphs if p.strip()]

        page = ParsedPage(
            page_number=1,
            texts=texts,
            tables=[],
            images=[],
        )

        return ParsedDocument(
            document_id=doc_id,
            mime_type=mime_type,
            pages=[page],
            parse_status="completed",
            parse_timestamp=timestamp,
        )

    def _detect_and_decode(self, raw_bytes: bytes) -> str:
        """编码自动检测

        依次尝试 UTF-8 → GBK → GB18030（GB18030 是 GBK 超集，兜底），
        不引入 chardet 依赖。
        """
        for encoding in ["utf-8", "gbk", "gb18030"]:
            try:
                return raw_bytes.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                continue
        # 全部失败，使用 UTF-8 + replace
        return raw_bytes.decode("utf-8", errors="replace")

    def _split_paragraphs(self, text: str) -> list[str]:
        """按连续空行分割段落"""
        paragraphs = re.split(r"\n\s*\n", text)
        return [p.strip() for p in paragraphs]
