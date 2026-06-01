"""应用层 Dense 语义检索服务

编排嵌入生成与向量检索两个端口，提供端到端 Dense 语义检索能力
架构参考: architecture.md §4.3 检索服务编排
"""

from __future__ import annotations

import asyncio
from typing import Any, TypedDict

from src.domain.ports.embedding_service import EmbeddingServicePort
from src.domain.ports.l3_vector import L3VectorPort


class DenseSearchResult(TypedDict):
    """Dense 检索结果

    Attributes:
        id: 向量点标识
        score: 相似度得分
        payload: 元数据
    """

    id: str | int
    score: float
    payload: dict[str, Any]


class DenseSemanticSearchService:
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
    ) -> list[DenseSearchResult]:
        """执行 Dense 语义检索

        Args:
            collection: Collection 名称
            query_text: 查询文本
            limit: 返回结果数量限制
            tenant_id: 租户 ID（自动注入到 filter）
            filter_payload: Payload 过滤条件

        Returns:
            检索结果列表，按相似度降序排列
        """
        query_vector = await asyncio.to_thread(self._embedding.encode_text, query_text)

        combined_filter = self._build_filter(tenant_id, filter_payload)

        raw_results = await self._vector.search(
            collection=collection,
            query_vector=query_vector,
            limit=limit,
            filter_payload=combined_filter,
        )
        return [DenseSearchResult(id=r["id"], score=r["score"], payload=r.get("payload", {})) for r in raw_results]

    def _build_filter(
        self,
        tenant_id: str | None,
        filter_payload: dict | None,
    ) -> dict | None:
        """构建组合过滤条件

        Args:
            tenant_id: 租户 ID
            filter_payload: 原始过滤条件

        Returns:
            组合后的过滤条件
        """
        if tenant_id is None and filter_payload is None:
            return None

        combined: dict[str, Any] = {}
        if filter_payload:
            safe_payload = {k: v for k, v in filter_payload.items() if k != "tenant_id"}
            combined.update(safe_payload)
        if tenant_id is not None:
            combined["tenant_id"] = tenant_id
        return combined if combined else None
