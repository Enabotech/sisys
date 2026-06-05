"""文档解析结果值对象

定义解析结果的结构化数据模型，包含 ParsedDocument/ParsedPage/ParsedElement/ParsedTable/
BoundingBox/BoundingBoxResult/ColumnType/ColumnInfo/MergedCell。
所有值对象均为 frozen dataclass（不可变），通过 to_dict() 方法支持 JSON 序列化。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class ColumnType(Enum):
    """表格列数据类型枚举

    用于推断表格列的数据类型，支持 7 种标准类型。
    UNKNOWN 用于无法识别或空列的降级场景。

    Values:
        STRING: 文本字符串
        NUMBER: 数字（整数/浮点数）
        DATE: 日期（各种日期格式）
        CURRENCY: 货币金额（含货币符号）
        PERCENTAGE: 百分比（含 % 符号）
        BOOLEAN: 布尔值（true/false/是/否等）
        UNKNOWN: 未知类型（无法识别或空列）
    """

    STRING = "STRING"
    NUMBER = "NUMBER"
    DATE = "DATE"
    CURRENCY = "CURRENCY"
    PERCENTAGE = "PERCENTAGE"
    BOOLEAN = "BOOLEAN"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ColumnInfo:
    """表格列类型信息值对象

    描述表格中单列的类型推断结果，包含列名、推断类型、
    置信度、空值比率和采样值。

    Attributes:
        name: 列名（来自表头或自动生成的列标识）
        col_type: 推断的列数据类型
        confidence: 类型推断置信度（0.0~1.0）
        nullable_ratio: 空值占比（0.0~1.0，空单元格数/总行数）
        sample_values: 采样值列表（前 N 行 + 随机采样的原始字符串值）
    """

    name: str
    col_type: ColumnType = ColumnType.UNKNOWN
    confidence: float = 1.0
    nullable_ratio: float = 0.0
    sample_values: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 可存储字典"""
        return {
            "name": self.name,
            "col_type": self.col_type.value,
            "confidence": self.confidence,
            "nullable_ratio": self.nullable_ratio,
            "sample_values": self.sample_values,
        }


@dataclass(frozen=True)
class MergedCell:
    """合并单元格值对象（V1）

    描述表格中跨行/跨列的合并单元格区域。由表格合并单元格还原服务生成。

    Attributes:
        row_start: 合并区域起始行索引（0-indexed）
        row_end: 合并区域结束行索引（0-indexed，包含）
        col_start: 合并区域起始列索引（0-indexed）
        col_end: 合并区域结束列索引（0-indexed，包含）
        value: 合并单元格的值（覆盖区域内所有位置共享此值）
    """

    row_start: int
    row_end: int
    col_start: int
    col_end: int
    value: str

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 可存储字典"""
        return {
            "row_start": self.row_start,
            "row_end": self.row_end,
            "col_start": self.col_start,
            "col_end": self.col_end,
            "value": self.value,
        }


@dataclass(frozen=True)
class BoundingBox:
    """元素边界框坐标（DocLayNet 标准）

    Attributes:
        x: 左上角 x 坐标
        y: 左上角 y 坐标
        width: 宽度
        height: 高度
        page: 所在页码（1-indexed，与 ParsedPage.page_number 一致）
    """

    x: float
    y: float
    width: float
    height: float
    page: int

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 可存储字典"""
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "page": self.page,
        }


@dataclass(frozen=True)
class BoundingBoxResult:
    """版面检测结果值对象（DocLayNet 标准）

    表示版面检测模型输出的单个检测结果，包含元素类型标签、
    边界框坐标和检测置信度。页码信息由 bbox.page 承载。

    Attributes:
        label: DocLayNet 11 类标签（Caption/Footnote/Formula/List-item/
            Page-footer/Page-header/Picture/Section-header/Table/Text/Title）
        bbox: 边界框坐标（含页码信息）
        confidence: 检测置信度（0.0~1.0）
    """

    label: str
    bbox: BoundingBox
    confidence: float

    def __post_init__(self) -> None:
        """校验 confidence 值域范围 [0.0, 1.0]"""
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence 必须在 [0.0, 1.0] 范围内，实际值: {self.confidence}")

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 可存储字典"""
        return {
            "label": self.label,
            "bbox": self.bbox.to_dict(),
            "confidence": self.confidence,
        }


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
            "bbox": self.bbox.to_dict() if self.bbox else None,
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
        metadata: 附加元数据（如 sheet_name、编码信息等）
        header: 列名列表（表头识别结果，无表头时为 None）
        column_types: 列类型信息列表（列类型推断结果，未推断时为 None）
        merged_cells: 合并单元格映射列表（V1，仅 xlsx 格式支持，其他为 None）
        semantic_confidence: 语义提取综合置信度（0.0~1.0，未提取时为 None）
        table_caption: 表格标题/说明文本（无标题时为 None）
    """

    rows: list[list[str]] = field(default_factory=list)
    bbox: BoundingBox | None = None
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    header: list[str] | None = None
    column_types: list[ColumnInfo] | None = None
    merged_cells: list[MergedCell] | None = None
    semantic_confidence: float | None = None
    table_caption: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 可存储字典"""
        return {
            "rows": self.rows,
            "bbox": self.bbox.to_dict() if self.bbox else None,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "header": self.header,
            "column_types": [ct.to_dict() for ct in self.column_types] if self.column_types else None,
            "merged_cells": [mc.to_dict() for mc in self.merged_cells] if self.merged_cells else None,
            "semantic_confidence": self.semantic_confidence,
            "table_caption": self.table_caption,
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

    def is_failed(self) -> bool:
        """判断解析是否失败

        封装裸字符串字面量比较，避免调用方直接比对魔术字符串。

        Returns:
            True 当 parse_status == "failed"
        """
        return self.parse_status == "failed"

    def is_completed(self) -> bool:
        """判断解析是否成功

        Returns:
            True 当 parse_status == "completed"
        """
        return self.parse_status == "completed"

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
