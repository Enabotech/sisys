"""应用层 Dense 语义检索服务

编排嵌入生成与向量检索两个端口，提供端到端 Dense 语义检索能力
架构参考: architecture.md §4.3 检索服务编排
"""

from __future__ import annotations

from src.application.services._filter_utils import build_search_filter
from src.domain.exceptions import ValidationError
from src.domain.ports.embedding_service import EmbeddingServicePort
from src.domain.ports.l3_vector import L3VectorPort, SearchResult
from src.domain.ports.search_service import DenseSearchPort


class DenseSemanticSearchService(DenseSearchPort):
    """Dense 语义检索服务

    编排 embedding_service（文本→向量）和 l3_vector（向量→检索）两个端口
    """

    def __init__(
        self,
        embedding_service: EmbeddingServicePort,
        vector_storage: L3VectorPort,
    ) -> None:
        """初始化检索服务

        Args:
            embedding_service: 嵌入服务端口
            vector_storage: 向量存储端口
        """
        self._embedding = embedding_service
        self._vector = vector_storage

    async def search(
        self,
        collection: str,
        query_text: str,
        limit: int = 10,
        tenant_id: str | None = None,
        filter_payload: dict | None = None,
    ) -> list[SearchResult]:
        """执行 Dense 语义检索

        Args:
            collection: Collection 名称
            query_text: 查询文本
            limit: 返回结果数量限制
            tenant_id: 租户 ID（自动注入到 filter）
            filter_payload: Payload 过滤条件

        Returns:
            检索结果列表，按相似度降序排列

        Raises:
            ValidationError: 查询文本为空时
        """
        if not query_text or not query_text.strip():
            raise ValidationError(message="查询文本不能为空")
        if not collection or not collection.strip():
            raise ValidationError(message="Collection 名称不能为空")
        if limit < 1:
            raise ValidationError(message=f"limit 必须为正整数，当前值: {limit}")

        query_vector = await self._embedding.embed_query(query_text)

        combined_filter = build_search_filter(tenant_id, filter_payload)

        raw_results = await self._vector.search(
            collection=collection,
            query_vector=query_vector,
            limit=limit,
            filter_payload=combined_filter,
        )
        return [
            SearchResult(id=r["id"], score=r["score"], payload=r.get("payload") or {})
            for r in raw_results
            if isinstance(r, dict) and "id" in r and "score" in r
        ]


__all__ = [
    "DenseSemanticSearchService",
]
