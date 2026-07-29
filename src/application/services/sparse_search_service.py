"""应用层 BM25 稀疏检索服务

编排 embedding_service.embed_sparse()（文本→稀疏向量）和
l3_vector.search_sparse()（稀疏向量→检索）两个端口，
提供端到端 BM25 稀疏检索能力。

严格镜像 DenseSemanticSearchService [Source: src/application/services/dense_search_service.py]
的架构模式：构造函数注入 + tenant_id 注入。
"""

from __future__ import annotations

from typing import Any, cast

from src.domain.exceptions import ValidationError
from src.domain.ports.embedding_service import EmbeddingServicePort
from src.domain.ports.l3_vector import L3VectorPort, SearchResult


class Bm25SparseSearchService:
    """BM25 稀疏检索服务

    编排 embedding_service（文本→稀疏向量）和 l3_vector（稀疏向量→检索）两个端口。
    签名严格对齐 DenseSemanticSearchService.search() 的参数顺序和异常类型。
    """

    def __init__(
        self,
        embedding_service: EmbeddingServicePort,
        vector_storage: L3VectorPort,
    ) -> None:
        """初始化稀疏检索服务

        Args:
            embedding_service: 嵌入服务端口（提供 embed_sparse 方法）
            vector_storage: 向量存储端口（提供 search_sparse 方法）
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
        """执行 BM25 稀疏检索

        Args:
            collection: Collection 名称
            query_text: 查询文本
            limit: 返回结果数量限制
            tenant_id: 租户 ID（自动注入到 filter）
            filter_payload: Payload 过滤条件

        Returns:
            检索结果列表，按 BM25 相似度降序排列

        Raises:
            ValidationError: 查询文本为空、Collection 名称为空或 limit 无效时
        """
        # 输入验证（与 DenseSemanticSearchService 一致）
        if not query_text or not query_text.strip():
            raise ValidationError(message="查询文本不能为空")
        if not collection or not collection.strip():
            raise ValidationError(message="Collection 名称不能为空")
        if limit < 1:
            raise ValidationError(message=f"limit 必须为正整数，当前值: {limit}")

        # 生成查询稀疏向量（批量接口取首元素）
        sparse_embeddings = await self._embedding.embed_sparse([query_text])
        query_sparse = sparse_embeddings[0]

        # 构建组合过滤条件（自动注入 tenant_id）
        combined_filter = self._build_filter(tenant_id, filter_payload)

        # 执行稀疏检索
        raw_results = await self._vector.search_sparse(
            collection=collection,
            sparse_vector=cast(dict[str, Any], query_sparse),
            limit=limit,
            filter_payload=combined_filter,
        )
        return [SearchResult(id=r["id"], score=r["score"], payload=r["payload"]) for r in raw_results]

    def _build_filter(
        self,
        tenant_id: str | None,
        filter_payload: dict | None,
    ) -> dict | None:
        """构建组合过滤条件，自动注入 tenant_id

        逻辑与 DenseSemanticSearchService._build_filter() 完全一致。

        Args:
            tenant_id: 租户 ID
            filter_payload: 原始过滤条件

        Returns:
            组合后的过滤条件（含 tenant_id 注入）

        Raises:
            ValidationError: tenant_id 为空或仅含空白字符时
        """
        if tenant_id is None and filter_payload is None:
            return None

        combined: dict[str, Any] = {}
        if filter_payload:
            safe_payload = {k: v for k, v in filter_payload.items() if k != "tenant_id"}
            combined.update(safe_payload)
        if tenant_id is not None:
            safe_tid = tenant_id.strip()
            if not safe_tid:
                raise ValidationError(message="tenant_id 不能为空或仅含空白字符")
            combined["tenant_id"] = safe_tid
        return combined if combined else None
