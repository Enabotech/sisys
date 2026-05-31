"""文档解析结果值对象

定义解析结果的结构化数据模型，包含 ParsedDocument/ParsedPage/ParsedElement/ParsedTable/BoundingBox。
所有值对象均为 frozen dataclass（不可变），通过 to_dict() 方法支持 JSON 序列化。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class BoundingBox:
    """元素边界框坐标（DocLayNet 标准）

    Attributes:
        x: 左上角 x 坐标
        y: 左上角 y 坐标
        width: 宽度
        height: 高度
        page: 所在页码（0-indexed）
    """

    x: float
    y: float
    width: float
    height: float
    page: int


@dataclass(frozen=True)
class ParsedElement:
    """解析元素（文本/图像）

    Attributes:
        content: 元素文本内容
        bbox: 边界框坐标（DocLayNet 预留，MVP 填 None）
        confidence: 解析置信度（OCR 场景由 Story 2-5 实现）
        metadata: 附加元数据（如段落样式 style、字体信息等）
    """

    content: str
    bbox: BoundingBox | None = None
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 可存储字典"""
        return {
            "content": self.content,
            "bbox": None,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class ParsedTable:
    """表格解析结果

    Attributes:
        rows: 二维字符串数组，每行每列的单元格文本
        bbox: 边界框坐标（DocLayNet 预留，MVP 填 None）
        confidence: 解析置信度
    """

    rows: list[list[str]] = field(default_factory=list)
    bbox: BoundingBox | None = None
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 可存储字典"""
        return {
            "rows": self.rows,
            "bbox": None,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class ParsedPage:
    """单页解析结果

    Attributes:
        page_number: 页码（1-indexed）
        texts: 文本元素列表
        tables: 表格元素列表
        images: 图像元素列表（MVP 仅记录存在，不提取内容）
    """

    page_number: int
    texts: list[ParsedElement] = field(default_factory=list)
    tables: list[ParsedTable] = field(default_factory=list)
    images: list[ParsedElement] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 可存储字典"""
        return {
            "page_number": self.page_number,
            "texts": [t.to_dict() for t in self.texts],
            "tables": [t.to_dict() for t in self.tables],
            "images": [i.to_dict() for i in self.images],
        }


@dataclass(frozen=True)
class ParsedDocument:
    """解析结果顶层容器

    Attributes:
        document_id: 文档标识符
        mime_type: 文档 MIME 类型
        pages: 解析页面列表
        parse_status: 解析状态（"completed" 或 "failed"）
        error_message: 错误信息（解析失败时非空）
        parse_timestamp: 解析时间（ISO 8601）
    """

    document_id: str
    mime_type: str
    pages: list[ParsedPage] = field(default_factory=list)
    parse_status: Literal["completed", "failed"] = "completed"
    error_message: str | None = None
    parse_timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 可存储字典"""
        return {
            "document_id": self.document_id,
            "mime_type": self.mime_type,
            "pages": [p.to_dict() for p in self.pages],
            "parse_status": self.parse_status,
            "error_message": self.error_message,
            "parse_timestamp": self.parse_timestamp,
        }
