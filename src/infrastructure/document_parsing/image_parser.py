"""图像文档解析器

使用 Pillow 提取图像元数据，并通过注入的 OCRPort 执行 OCR。
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.domain.ports.document_parser import DocumentParserPort
from src.domain.value_objects.parsed_document import (
    ParsedDocument,
    ParsedElement,
    ParsedPage,
)
from src.infrastructure.document_parsing._limits import MAX_IMAGE_BYTES

if TYPE_CHECKING:
    from src.domain.ports.ocr import OCRPort

logger = logging.getLogger(__name__)


class ImageParser(DocumentParserPort):
    """图像文档解析器

    使用 Pillow 提取元数据，通过注入的 OCRPort 执行 RapidOCR，支持：
    - 图像元数据提取（format/size/mode）
    - OCR 文本提取（中英双语）
    - GIF 仅处理第一帧
    - OCR 不可用时优雅降级
    - 文件大小上限保护
    - 可选 OCR 端口注入
    """

    def __init__(self, ocr: "OCRPort | None" = None) -> None:
        """初始化图像解析器

        Args:
            ocr: 可选的 OCR 端口实例（通常为 RapidOCRAdapter）
        """
        self._ocr = ocr

    def parse(self, file_path: str, mime_type: str) -> ParsedDocument:
        """解析图像文件

        Args:
            file_path: 本地图像文件路径
            mime_type: MIME 类型

        Returns:
            结构化解析结果
        """
        doc_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).isoformat()

        try:
            file_size = os.path.getsize(file_path)
        except OSError:
            logger.exception("图像文件大小检查失败")
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
                error_message="图像文件为空",
                parse_timestamp=timestamp,
            )

        if file_size > MAX_IMAGE_BYTES:
            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                parse_status="failed",
                error_message=f"图像文件大小 {file_size // (1024 * 1024)}MB 超过 {MAX_IMAGE_BYTES // (1024 * 1024)}MB 限制",
                parse_timestamp=timestamp,
            )

        try:
            from PIL import Image

            with Image.open(file_path) as img:
                # GIF 仅处理第一帧
                if getattr(img, "is_animated", False):
                    img.seek(0)

                metadata = {
                    "format": img.format or "UNKNOWN",
                    "width": img.width,
                    "height": img.height,
                    "mode": img.mode,
                }

                # 图像条目（content 为空字符串，元数据在 metadata 中）
                image_element = ParsedElement(content="", metadata=metadata)

                # OCR 文本提取
                texts: list[ParsedElement] = []
                try:
                    if self._ocr is not None:
                        # RapidOCR 端口为异步契约，同步解析器在调用线程中桥接
                        ocr_results = asyncio.run(self._ocr.recognize(file_path))
                        if ocr_results and ocr_results[0].elements:
                            texts = ocr_results[0].elements
                        else:
                            logger.info("RapidOCR 返回空结果，保持图像元数据")
                    else:
                        logger.debug("OCR 端口未注入，跳过图像文字提取")
                except ImportError:
                    logger.warning("RapidOCR 运行时不可用，跳过 OCR 文本提取")
                except Exception:
                    logger.warning("OCR 文本提取失败，继续返回图像元数据", exc_info=True)

            page = ParsedPage(
                page_number=1,
                texts=texts,
                images=[image_element],
            )

            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                pages=[page],
                parse_status="completed",
                parse_timestamp=timestamp,
            )

        except Exception:
            logger.exception("图像解析失败")
            return ParsedDocument(
                document_id=doc_id,
                mime_type=mime_type,
                parse_status="failed",
                error_message="图像文档解析失败，文件可能已损坏或格式不正确",
                parse_timestamp=timestamp,
            )
