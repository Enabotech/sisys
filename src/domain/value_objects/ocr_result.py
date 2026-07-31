"""OCR 解析结果值对象

定义 OCR 解析结果的结构化数据模型，包含 OCRPageResult 和 OCRConfidenceMark。
所有值对象均为 frozen dataclass（不可变），通过 to_dict() 方法支持 JSON 序列化。

OCRA 场景下，OCRPageResult 作为 OCRPort.recognize() 的返回类型，
OCRConfidenceMark 作为置信度标记逻辑的内部辅助值对象。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.domain.value_objects.parsed_document import ParsedElement


@dataclass(frozen=True)
class OCRConfidenceMark:
    """OCR 置信度标记辅助值对象

    记录单个元素的置信度评估结果，用于 _mark_low_confidence() 方法内部标记逻辑。
    与 ParsedElement.confidence: float = 1.0 类型对齐，
    OCR 场景下若无法获取置信度则使用默认值 0.5（与 ImageParser pytesseract 降级模式一致）。

    Attributes:
        element_index: 元素在页面列表中的索引
        confidence: OCR 置信度（0.0~1.0，默认 0.5）
        needs_review: 是否需要人工复核（confidence < OCR_CONFIDENCE_THRESHOLD 时标记）
    """

    element_index: int
    confidence: float = 0.5
    needs_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 可存储字典"""
        return {
            "element_index": self.element_index,
            "confidence": self.confidence,
            "needs_review": self.needs_review,
        }


@dataclass(frozen=True)
class OCRPageResult:
    """单页 OCR 解析结果

    包含指定页面的 OCR 识别结果，用于 OCRPort.recognize() 的返回类型。
    每个元素为 ParsedElement（含 content、confidence、metadata 字段），
    其中 confidence 为 OCR 引擎返回的置信度（0.0~1.0），
    无法获取置信度时默认使用 0.5（与 ImageParser pytesseract 降级模式对齐）。

    Attributes:
        page_number: 页码（1-indexed）
        elements: OCR 识别后的 ParsedElement 列表，每个元素含 confidence
        raw_response: PaddleOCR-VL 原始响应（调试用，不序列化到持久化结果）
    """

    page_number: int
    elements: list[ParsedElement] = field(default_factory=list)
    raw_response: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 可存储字典（不含 raw_response）"""
        return {
            "page_number": self.page_number,
            "elements": [e.to_dict() for e in self.elements],
        }


__all__ = [
    "OCRConfidenceMark",
    "OCRPageResult",
]
