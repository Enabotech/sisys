"""领域层 引文值对象模块（Citation）

定义高保真溯源的核心值对象——Citation，包含文档 ID、切片 ID、字符范围、
Bounding Box 坐标和置信度评分。BoundingBox 复用 parsed_document.py 中已有定义。

设计决策：
- frozen dataclass（不可变值对象）
- BoundingBox 从 parsed_document.py 导入，不重复定义
- 置信度基于检索结果 score 归一化（0-1），非 LLM 计算
- 支持 to_dict() 序列化和 from_dict() 反序列化
- 领域层零外部依赖（仅使用 Python 标准库 + uuid）
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from src.domain.exceptions import EntityValidationError
from src.domain.value_objects.parsed_document import BoundingBox


@dataclass(frozen=True)
class Citation:
    """引文值对象

    表示从结论溯源到原始文档中某个切片的结构化引文信息。
    包含完整的"三元组"特征（文档 ID、切片 ID、字符范围）和可选的 Bounding Box 坐标。

    Attributes:
        citation_id: 引文唯一标识（由 chunk_id 或其 SHA256 哈希生成）
        document_id: 文档 UUID
        chunk_id: 切片 ID
        text: 引文文本片段
        start_offset: 字符起始偏移量
        end_offset: 字符结束偏移量
        page_number: 页码
        bbox: Bounding Box 坐标（可选，有版面信息时填充）
        confidence: 引用置信度（0-1，基于检索结果 score 归一化）
    """

    citation_id: str
    document_id: uuid.UUID
    chunk_id: str
    text: str
    start_offset: int
    end_offset: int
    page_number: int
    bbox: BoundingBox | None = None
    confidence: float = 1.0

    def __post_init__(self) -> None:
        """校验不变量：确保值对象处于有效状态

        校验规则：
        - citation_id: 非空字符串
        - start_offset: >= 0
        - end_offset: > start_offset
        - page_number: >= 1
        - confidence: [0.0, 1.0]
        """
        if not isinstance(self.citation_id, str) or not self.citation_id.strip():
            raise EntityValidationError("citation_id 必须为非空字符串")
        if self.start_offset < 0:
            raise EntityValidationError(f"start_offset 必须 >= 0，实际值: {self.start_offset}")
        if self.end_offset <= self.start_offset:
            raise EntityValidationError(
                f"end_offset 必须 > start_offset，start_offset={self.start_offset}, end_offset={self.end_offset}"
            )
        if self.page_number < 1:
            raise EntityValidationError(f"page_number 必须 >= 1，实际值: {self.page_number}")
        if not (0.0 <= self.confidence <= 1.0):
            raise EntityValidationError(f"confidence 必须在 [0.0, 1.0] 范围内，实际值: {self.confidence}")

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 可存储字典

        Returns:
            包含所有字段的字典，bbox 为 None 时序列化为 None
        """
        return {
            "citation_id": self.citation_id,
            "document_id": str(self.document_id),
            "chunk_id": self.chunk_id,
            "text": self.text,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "page_number": self.page_number,
            "bbox": self.bbox.to_dict() if self.bbox else None,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Citation:
        """从字典反序列化创建 Citation 实例

        Args:
            data: 包含 Citation 字段的字典

        Returns:
            Citation 实例
        """
        bbox_data = data.get("bbox")
        bbox: BoundingBox | None = None
        if bbox_data is not None:
            bbox = BoundingBox(
                x=bbox_data["x"],
                y=bbox_data["y"],
                width=bbox_data["width"],
                height=bbox_data["height"],
                page=bbox_data["page"],
            )

        document_id = data["document_id"]
        if isinstance(document_id, str):
            document_id = uuid.UUID(document_id)

        return cls(
            citation_id=data["citation_id"],
            document_id=document_id,
            chunk_id=data["chunk_id"],
            text=data["text"],
            start_offset=data["start_offset"],
            end_offset=data["end_offset"],
            page_number=data["page_number"],
            bbox=bbox,
            confidence=data.get("confidence", 1.0),
        )


__all__ = [
    "Citation",
]
