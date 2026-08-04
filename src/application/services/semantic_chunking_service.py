"""语义分块应用服务

编排文档分块流程：获取文档 → 重构 ParsedDocument → 调用分块器 → 持久化 → 发布事件。
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from src.domain.events.workflow_events import RAGIndexed
from src.domain.ports.document_repository import DocumentRepositoryPort
from src.domain.ports.event_publisher import EventPublisher
from src.domain.ports.semantic_chunker import SemanticChunkerPort
from src.domain.value_objects.parsed_document import (
    BoundingBox,
    ColumnInfo,
    ColumnType,
    MergedCell,
    ParsedDocument,
    ParsedElement,
    ParsedPage,
    ParsedTable,
)
from src.domain.value_objects.semantic_chunk import ChunkingConfig, ChunkingProfile, SemanticChunk

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# v4: business_domain → ChunkingProfile 映射（应用层）
# ---------------------------------------------------------------------------

_BUSINESS_DOMAIN_PROFILE_MAP: dict[str, ChunkingProfile] = {
    "finance": ChunkingProfile.FINANCIAL,
    "legal": ChunkingProfile.CONTRACT,
    "research": ChunkingProfile.RESEARCH,
}


def _resolve_profile_from_domain(business_domain: str) -> ChunkingProfile:
    """将业务域字符串映射到分块策略配置档案（应用层）

    应用层职责：business_domain（Document 实体中的字符串）→ ChunkingProfile 枚举。
    领域层 ChunkingConfig.for_profile() 接收 ChunkingProfile 枚举值（非字符串）。

    Args:
        business_domain: Document.metadata 中的业务域字符串

    Returns:
        ChunkingProfile 枚举值（未匹配时返回 GENERAL）
    """
    return _BUSINESS_DOMAIN_PROFILE_MAP.get(business_domain, ChunkingProfile.GENERAL)


class SemanticChunkingService:
    """语义分块应用服务

    编排文档分块流程：
    1. 从仓储获取 Document 实体
    2. 从 document.metadata["parse_result"] 重构 ParsedDocument
    3. 调用 semantic_chunker.chunk(parsed_doc, config)
    4. 将分块列表序列化为 dict 列表，存入 document.metadata["chunks"]
    5. 保存 Document 实体
    6. 发布 RAGIndexed 事件（chunk_count=len(chunks)）
    """

    def __init__(
        self,
        document_repository: DocumentRepositoryPort,
        semantic_chunker: SemanticChunkerPort,
        event_publisher: EventPublisher,
    ) -> None:
        """初始化语义分块服务

        Args:
            document_repository: 文档仓储端口
            semantic_chunker: 语义分块器端口
            event_publisher: 事件发布器端口
        """
        self._document_repository = document_repository
        self._semantic_chunker = semantic_chunker
        self._event_publisher = event_publisher

    async def _publish_rag_indexed(
        self,
        document_id: uuid.UUID,
        tenant_id: str,
        chunk_count: int,
    ) -> None:
        """发布 RAGIndexed 事件

        Args:
            document_id: 文档标识符
            tenant_id: 租户标识符
            chunk_count: 分块数量（0 表示无分块）
        """
        event = RAGIndexed(
            document_id=document_id,
            chunk_count=chunk_count,
            tenant_id=tenant_id,
        )
        await self._event_publisher.publish(event)

    async def chunk_document(
        self,
        document_id: uuid.UUID,
        tenant_id: str,
        config: ChunkingConfig | None = None,
    ) -> list[SemanticChunk]:
        """对文档执行语义分块并持久化结果

        Args:
            document_id: 文档唯一标识符
            tenant_id: 租户标识符
            config: 分块配置（为 None 时使用默认值）

        Returns:
            SemanticChunk 列表
        """
        from src.domain.ports.document_repository import DocumentQuery

        # 1. 获取文档实体
        query = DocumentQuery(tenant_id=tenant_id, document_id=document_id)
        doc = await self._document_repository.find(query)
        if doc is None:
            logger.warning("文档未找到: document_id=%s, tenant_id=%s", document_id, tenant_id)
            await self._publish_rag_indexed(document_id, tenant_id, chunk_count=0)
            return []

        # 2. 从 parse_result 重构 ParsedDocument
        parse_result = doc.metadata.get("parse_result", {})
        if not parse_result:
            logger.warning("文档解析结果为空: document_id=%s", document_id)
            await self._publish_rag_indexed(document_id, tenant_id, chunk_count=0)
            return []

        parsed_doc = self.parsed_document_from_dict(parse_result)

        # 3. v4: 构建文档级元数据（doc_title + business_domain）
        chunk_metadata = {
            "doc_title": doc.filename,
            "business_domain": doc.metadata.get("business_domain", ""),
        }

        # 4. v4: 自动选择 ChunkingProfile（无显式 config 时）
        if config is None:
            business_domain = doc.metadata.get("business_domain", "")
            profile = _resolve_profile_from_domain(business_domain)
            if profile != ChunkingProfile.GENERAL:
                config = ChunkingConfig.for_profile(profile)

        # 5. 执行语义分块（传入 metadata）
        chunks = await self._semantic_chunker.chunk(parsed_doc, config=config, metadata=chunk_metadata)

        # 6. 持久化分块结果到 metadata.chunks
        chunks_data = [chunk.to_dict() for chunk in chunks]
        doc.metadata["chunks"] = chunks_data

        # 7. 保存文档实体
        await self._document_repository.save(doc)

        # 8. 发布 RAGIndexed 事件
        await self._publish_rag_indexed(document_id, tenant_id, chunk_count=len(chunks))

        logger.info(
            "语义分块完成: document_id=%s, chunk_count=%s",
            document_id,
            len(chunks),
        )

        return chunks

    @staticmethod
    def parsed_document_from_dict(data: dict[str, Any]) -> ParsedDocument:
        """从 parse_result dict 重构 ParsedDocument 值对象

        Args:
            data: parse_result 字典

        Returns:
            ParsedDocument 实例
        """
        pages: list[ParsedPage] = []
        for page_data in data.get("pages", []):
            texts = [
                ParsedElement(
                    content=e["content"],
                    bbox=BoundingBox(**e["bbox"]) if e.get("bbox") else None,
                    confidence=e.get("confidence", 1.0),
                    metadata=e.get("metadata", {}),
                )
                for e in page_data.get("texts", [])
            ]
            tables = [SemanticChunkingService._parsed_table_from_dict(t) for t in page_data.get("tables", [])]
            images = [
                ParsedElement(
                    content=img["content"],
                    bbox=BoundingBox(**img["bbox"]) if img.get("bbox") else None,
                    confidence=img.get("confidence", 1.0),
                    metadata=img.get("metadata", {}),
                )
                for img in page_data.get("images", [])
            ]
            pages.append(
                ParsedPage(
                    page_number=page_data["page_number"],
                    texts=texts,
                    tables=tables,
                    images=images,
                )
            )

        return ParsedDocument(
            document_id=data["document_id"],
            mime_type=data["mime_type"],
            pages=pages,
            parse_status=data.get("parse_status", "completed"),
            error_message=data.get("error_message"),
            parse_timestamp=data.get("parse_timestamp", ""),
        )

    @staticmethod
    def _parsed_table_from_dict(data: dict[str, Any]) -> ParsedTable:
        """从 dict 重构 ParsedTable 值对象

        Args:
            data: 表格字典

        Returns:
            ParsedTable 实例
        """
        column_types = None
        if data.get("column_types"):
            column_types = [
                ColumnInfo(
                    name=ct["name"],
                    col_type=ColumnType(ct["col_type"]),
                    confidence=ct.get("confidence", 1.0),
                    nullable_ratio=ct.get("nullable_ratio", 0.0),
                    sample_values=ct.get("sample_values", []),
                )
                for ct in data["column_types"]
            ]

        merged_cells = None
        if data.get("merged_cells"):
            merged_cells = [MergedCell(**mc) for mc in data["merged_cells"]]

        return ParsedTable(
            rows=data.get("rows", []),
            bbox=BoundingBox(**data["bbox"]) if data.get("bbox") else None,
            confidence=data.get("confidence", 1.0),
            metadata=data.get("metadata", {}),
            header=data.get("header"),
            column_types=column_types,
            merged_cells=merged_cells,
            semantic_confidence=data.get("semantic_confidence"),
            table_caption=data.get("table_caption"),
        )
