"""语义分块值对象模块

定义语义分块相关的值对象：ChunkBoundaryType 枚举、ChunkingProfile 枚举、IndexLevel 枚举、
ChunkingConfig 值对象、SemanticChunk 值对象。
所有值对象均为 frozen dataclass（不可变），通过 to_dict() 方法支持 JSON 序列化。
领域层零依赖，仅使用 Python 标准库。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ChunkBoundaryType(str, Enum):
    """分块边界类型枚举

    表示创建分块时的语义边界类型，决定分块的触发原因。

    Values:
        PARAGRAPH: 段落边界（\\n\\n 双换行分隔）
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


class ChunkingProfile(str, Enum):
    """分块策略配置档案枚举

    定义四种文档类型的推荐分块参数，对标 LlamaIndex DocAwareChunker (2026)。

    Values:
        GENERAL: 通用文档（默认，等价 v3 行为）
        FINANCIAL: 财报/财务报表（表格密集，需更大上下文）
        CONTRACT: 合同/法律文档（条款精读）
        RESEARCH: 研报/白皮书（章节清晰）
    """

    GENERAL = "general"
    FINANCIAL = "financial"
    CONTRACT = "contract"
    RESEARCH = "research"


class IndexLevel(str, Enum):
    """分块索引层级枚举

    用于 Child-Parent 双层索引模式，区分检索粒度和返回粒度。
    对标 Qdrant 1.15 Multivector group_by。

    Values:
        CHILD: 子块（~150 tokens），用于 Qdrant 向量索引
        PARENT: 父块（~600 tokens），子块命中时返回给 LLM
    """

    CHILD = "child"
    PARENT = "parent"


@dataclass(frozen=True)
class ChunkingConfig:
    """分块配置值对象

    控制语义分块的核心参数，所有阈值可配置，允许未来根据模型变更调整。

    Attributes:
        profile: 分块策略配置档案
        target_chunk_size_tokens: 目标分块大小（父块 token 数），默认 300
        min_chunk_size_tokens: 最小分块阈值（低于此值合并到前一个分块），默认 50
        max_chunk_size_tokens: 硬限制最大 token 数（对齐 BGE-M3 的 max_length），默认 8192
        child_chunk_size_tokens: 子块目标大小（None=单层模式，等价 v3），默认 None
        parent_chunk_size_tokens: 父块目标大小（None=单层模式，等价 v3），默认 None
        token_count_type: Token 计数方式（"bge-m3" | "heuristic"），默认 "bge-m3"
    """

    profile: ChunkingProfile = ChunkingProfile.GENERAL
    target_chunk_size_tokens: int = 300
    min_chunk_size_tokens: int = 50
    max_chunk_size_tokens: int = 8192
    child_chunk_size_tokens: int | None = None
    parent_chunk_size_tokens: int | None = None
    token_count_type: str = "bge-m3"

    @staticmethod
    def for_profile(profile: ChunkingProfile) -> ChunkingConfig:
        """根据 profile 创建推荐配置（领域层工厂方法）

        注意：此方法接收 ChunkingProfile 枚举值，
        business_domain → ChunkingProfile 的映射在应用层完成。

        Profile 默认值映射：
        - GENERAL:   target=300, min=50,  max=8192, child=None, parent=None  (单层模式)
        - FINANCIAL: target=400, min=100, max=8192, child=200, parent=800    (双层模式)
        - CONTRACT:  target=250, min=80,  max=8192, child=125, parent=500    (双层模式)
        - RESEARCH:  target=350, min=60,  max=8192, child=175, parent=700    (双层模式)
        """
        _profile_configs = {
            ChunkingProfile.GENERAL: (300, 50, None, None),
            ChunkingProfile.FINANCIAL: (400, 100, 200, 800),
            ChunkingProfile.CONTRACT: (250, 80, 125, 500),
            ChunkingProfile.RESEARCH: (350, 60, 175, 700),
        }
        target, min_size, child, parent = _profile_configs[profile]
        return ChunkingConfig(
            profile=profile,
            target_chunk_size_tokens=target,
            min_chunk_size_tokens=min_size,
            child_chunk_size_tokens=child,
            parent_chunk_size_tokens=parent,
        )

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 可存储字典"""
        return {
            "profile": self.profile.value,
            "target_chunk_size_tokens": self.target_chunk_size_tokens,
            "min_chunk_size_tokens": self.min_chunk_size_tokens,
            "max_chunk_size_tokens": self.max_chunk_size_tokens,
            "child_chunk_size_tokens": self.child_chunk_size_tokens,
            "parent_chunk_size_tokens": self.parent_chunk_size_tokens,
            "token_count_type": self.token_count_type,
        }


@dataclass(frozen=True)
class SemanticChunk:
    """语义分块值对象

    表示文档语义分块的结果，包含完整的分块元数据。
    所有字段在构造时强制传入（无默认值），确保值对象语义完整。

    Attributes:
        chunk_id: 分块唯一标识（UUID）
        document_id: 所属文档 UUID
        content: 分块文本内容（v4: 包含上下文前缀）
        chunk_index: 文档内排序序号（0-indexed，严格递增）
        boundary_type: 创建此分块的语义边界类型
        token_count: 精确 token 数（v4: 默认使用 BGE-M3 tokenizer）
        page_start: 起始页码（1-indexed）
        page_end: 结束页码（1-indexed）
        content_hash: 分块内容的 SHA256 哈希
        metadata: 扩展元数据字典（包含文档级 business_domain 等透传字段）
        parent_chunk_id: 父块 UUID（v4 新增，Child-Parent 关联；None=单层模式）
        index_level: 索引层级（v4 新增，"child" | "parent"）
        chunk_header: 上下文前缀（v4 新增，格式：[文档: {title} → {section_path}]）
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
    metadata: dict[str, Any]
    parent_chunk_id: uuid.UUID | None = None
    index_level: IndexLevel = IndexLevel.PARENT
    chunk_header: str = ""

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 可存储字典

        chunk_id 和 document_id 序列化为字符串格式。
        v4 新增字段提供合理默认值，向后兼容 v3 消费者。

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
            "parent_chunk_id": str(self.parent_chunk_id) if self.parent_chunk_id else None,
            "index_level": self.index_level.value,
            "chunk_header": self.chunk_header,
        }


__all__ = [
    "ChunkBoundaryType",
    "ChunkingConfig",
    "ChunkingProfile",
    "IndexLevel",
    "SemanticChunk",
]
