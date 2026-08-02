"""语义分块值对象模块

定义语义分块相关的值对象：ChunkBoundaryType 枚举、ChunkingConfig 值对象、SemanticChunk 值对象。
所有值对象均为 frozen dataclass（不可变），通过 to_dict() 方法支持 JSON 序列化。
领域层零依赖，仅使用 Python 标准库。
"""

from __future__ import annotations

import dataclasses
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ChunkBoundaryType(str, Enum):
    """分块边界类型枚举

    表示创建分块时的语义边界类型，决定分块的触发原因。

    Values:
        PARAGRAPH: 段落边界（\n\n 双换行分隔）
        SECTION_HEADER: 章节标题边界（metadata["style"] 中的标题样式）
        TABLE: 表格边界（ParsedTable 元素作为独立分块）
        PAGE_BREAK: 跨页边界（页码变化时必然切分）
        TOKEN_LIMIT: 硬限制 token 上限切分（超过 max_chunk_size_tokens）
    """

    PARAGRAPH = "paragraph"
    SECTION_HEADER = "section_header"
    TABLE = "table"
    PAGE_BREAK = "page_break"
    TOKEN_LIMIT = "token_limit"


@dataclass(frozen=True)
class ChunkingConfig:
    """分块配置值对象

    控制语义分块的核心参数，所有阈值可配置，允许未来根据模型变更调整。

    Attributes:
        target_chunk_size_tokens: 目标分块大小（token 数），默认 300
        min_chunk_size_tokens: 最小分块阈值（低于此值合并到前一个分块），默认 50
        max_chunk_size_tokens: 硬限制最大 token 数（对齐 BGE-M3 的 max_length），默认 8192
    """

    target_chunk_size_tokens: int = 300
    min_chunk_size_tokens: int = 50
    max_chunk_size_tokens: int = 8192

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 可存储字典"""
        return {
            "target_chunk_size_tokens": self.target_chunk_size_tokens,
            "min_chunk_size_tokens": self.min_chunk_size_tokens,
            "max_chunk_size_tokens": self.max_chunk_size_tokens,
        }


@dataclass(frozen=True)
class SemanticChunk:
    """语义分块值对象

    表示文档语义分块的结果，包含完整的分块元数据。
    所有字段在构造时强制传入（无默认值），确保值对象语义完整。

    Attributes:
        chunk_id: 分块唯一标识（UUID）
        document_id: 所属文档 UUID
        content: 分块文本内容
        chunk_index: 文档内排序序号（0-indexed，严格递增）
        boundary_type: 创建此分块的语义边界类型
        token_count: 估算 token 数
        page_start: 起始页码（1-indexed）
        page_end: 结束页码（1-indexed）
        content_hash: 分块内容的 SHA256 哈希
        metadata: 扩展元数据字典（包含文档级 business_domain 等透传字段）
    """

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    chunk_index: int
    boundary_type: ChunkBoundaryType
    token_count: int
    page_start: int
    page_end: int
    content_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 可存储字典

        chunk_id 和 document_id 序列化为字符串格式。

        Returns:
            JSON 可存储的字典
        """
        return {
            "chunk_id": str(self.chunk_id),
            "document_id": str(self.document_id),
            "content": self.content,
            "chunk_index": self.chunk_index,
            "boundary_type": self.boundary_type.value,
            "token_count": self.token_count,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "content_hash": self.content_hash,
            "metadata": self.metadata,
        }


__all__ = [
    "ChunkBoundaryType",
    "ChunkingConfig",
    "SemanticChunk",
]