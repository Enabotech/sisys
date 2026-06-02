"""图像文档解析器

使用 Pillow 提取图像元数据，pytesseract 执行 OCR 文本提取的解析器实现。
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
from src.infrastructure.external_services.document_parsing._limits import MAX_IMAGE_BYTES

logger = logging.getLogger(__name__)


class ImageParser(DocumentParserPort):
    """图像文档解析器

    使用 Pillow 提取元数据，pytesseract 执行 OCR，支持：
    - 图像元数据提取（format/size/mode）
    - OCR 文本提取（中英双语）
    - GIF 仅处理第一帧
    - Tesseract 不可用时优雅降级
    - 文件大小上限保护
    """

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
                    import pytesseract

                    ocr_text = pytesseract.image_to_string(img, lang="chi_sim+eng")
                    if ocr_text.strip():
                        # 获取置信度
                        try:
                            data = pytesseract.image_to_data(img, lang="chi_sim+eng", output_type=pytesseract.Output.DICT)
                            confidences = [int(c) for c in data.get("conf", []) if c != "-1"]
                            avg_confidence = sum(confidences) / len(confidences) / 100.0 if confidences else 1.0
                        except Exception:
                            avg_confidence = 1.0

                        texts.append(
                            ParsedElement(
                                content=ocr_text.strip(),
                                confidence=round(avg_confidence, 4),
                                metadata={"source": "ocr"},
                            )
                        )
                except ImportError:
                    logger.warning("pytesseract 未安装，跳过 OCR 文本提取")
                except Exception:
                    logger.warning("OCR 文本提取失败，继续返回图像元数据")

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
