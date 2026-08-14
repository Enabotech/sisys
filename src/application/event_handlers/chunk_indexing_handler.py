"""分块索引事件处理器

监听 RAGIndexed 事件，异步触发分块向量索引。
从 PostgreSQL 读取已持久化的 chunks 并逐块嵌入、索引到 Qdrant。
点 ID 必须等于 str(chunk.chunk_id)，确保 get_point() 可通过 parent_chunk_id 回溯。

嵌入保护：批量嵌入增加 max_batch_size（默认 32）和 token 截断保护。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from src.domain.ports.document_repository import DocumentQuery, DocumentRepositoryPort
from src.domain.ports.embedding_service import EmbeddingServicePort, SparseEmbedding
from src.domain.ports.l3_vector import L3VectorPort

if TYPE_CHECKING:
    from src.domain.events.workflow_events import RAGIndexed

logger = logging.getLogger(__name__)

# 批量嵌入的最大块数（超出则分批，避免 API 超时/内存峰值）
DEFAULT_MAX_BATCH_SIZE = 32

# bge-m3 输入 token 上限，超出部分截断以避免 HTTP 413
MAX_INPUT_TOKENS = 8192

# 简易启发式 token 估算：按 1 个 CJK 字符 ≈ 1 token，其余按 4 字符 / token
_CHARS_PER_TOKEN_DEFAULT = 4
_CJK_CHARS_PER_TOKEN = 1


class ChunkIndexingHandler:
    """分块索引事件处理器

    监听 RAGIndexed 事件（分块完成），异步触发分块向量索引。
    从 PostgreSQL 读取已持久化的 chunks，逐块嵌入并 upsert 到 Qdrant。
    """

    def __init__(
        self,
        embedding_service: EmbeddingServicePort,
        l3_vector: L3VectorPort,
        document_repository: DocumentRepositoryPort,
        max_batch_size: int = DEFAULT_MAX_BATCH_SIZE,
    ) -> None:
        """初始化分块索引处理器

        Args:
            embedding_service: EmbeddingServicePort 实例
            l3_vector: L3VectorPort 实例
            document_repository: DocumentRepositoryPort 实例
            max_batch_size: 单批嵌入的 chunk 数上限（默认 32）
        """
        self._embedding_service = embedding_service
        self._l3_vector = l3_vector
        self._document_repository = document_repository
        self._max_batch_size = max(max_batch_size, 1)

    async def handle_chunk_indexed(self, event: RAGIndexed) -> None:
        """处理 RAGIndexed 事件，执行分块向量索引

        Args:
            event: RAGIndexed 事件实例
        """
        if event.chunk_count == 0:
            logger.warning("ChunkIndexingHandler: chunk_count=0，跳过索引")
            return

        try:
            await self._index_chunks(event)
        except Exception:
            logger.exception(
                "分块索引失败: document_id=%s",
                event.document_id,
            )

    async def _index_chunks(self, event: RAGIndexed) -> None:
        """执行分块向量索引

        1. 从 document_repository 获取文档
        2. 从 metadata.chunks 读取 SemanticChunk 列表
        3. 分批嵌入 Dense + Sparse 向量（max_batch_size + token 截断）
        4. 逐块 upsert 到 Qdrant（点 ID = chunk_id）
        5. payload 包含 parent_chunk_id/index_level/chunk_id/document_id

        Args:
            event: RAGIndexed 事件实例
        """
        # 1. 获取文档实体
        query = DocumentQuery(tenant_id=event.tenant_id, document_id=event.document_id)
        doc = await self._document_repository.find(query)
        if doc is None:
            logger.warning("分块索引: 文档未找到，跳过索引: document_id=%s", event.document_id)
            return

        # 2. 从 metadata.chunks 读取分块列表
        chunk_dicts: list[dict[str, Any]] = doc.metadata.get("chunks", [])
        if not chunk_dicts:
            logger.warning("分块索引: 文档无分块数据，跳过索引: document_id=%s", event.document_id)
            return

        # 构造 Qdrant 点并嵌入
        all_texts: list[str] = []
        points: list[dict[str, Any]] = []
        for i, chunk in enumerate(chunk_dicts):
            content = _safe_chunk_content(chunk, i)
            if content is None:
                continue

            # 点 ID = chunk_id（必须与持久化 ID 一致，供 get_point() 回溯）
            point_id = str(chunk.get("chunk_id") or doc.document_id)
            if chunk.get("index_level") == "parent" and chunk.get("parent_chunk_id") is None:
                # 父块自身是文档切片（无上一级）
                point_id = str(chunk.get("chunk_id"))
            points.append(
                {
                    "id": point_id,
                    "payload": {
                        "chunk_id": str(chunk.get("chunk_id") or ""),
                        "document_id": str(doc.document_id),
                        "parent_chunk_id": str(chunk.get("parent_chunk_id")) if chunk.get("parent_chunk_id") else None,
                        "index_level": chunk.get("index_level", "child"),
                        "content": content,
                        "chunk_header": str(chunk.get("chunk_header", "")),
                    },
                }
            )
            all_texts.append(content)

        if not points:
            logger.warning("分块索引: 无有效分块可索引: document_id=%s", event.document_id)
            return

        # 3. 分批嵌入 Dense + Sparse 向量
        indexed = 0
        for start in range(0, len(all_texts), self._max_batch_size):
            batch_texts = all_texts[start : start + self._max_batch_size]
            batch_points = points[start : start + self._max_batch_size]

            try:
                dense_vectors = await self._embedding_service.embed_documents(batch_texts)
            except Exception:
                logger.exception(
                    "分块索引: Dense 嵌入失败（批次 %d，共 %d 块）: document_id=%s",
                    start // self._max_batch_size,
                    len(batch_texts),
                    event.document_id,
                )
                continue

            # Sparse 嵌入失败不阻断 Dense 索引（降级为仅 Dense）
            sparse_vectors: list[SparseEmbedding] | None = None
            try:
                sparse_vectors = await self._embedding_service.embed_sparse(batch_texts)
            except Exception:
                logger.warning(
                    "分块索引: Sparse 嵌入失败（批次 %d），降级为仅 Dense 索引: document_id=%s",
                    start // self._max_batch_size,
                    event.document_id,
                )

            for j, point in enumerate(batch_points):
                if j >= len(dense_vectors):
                    break
                point["vector"] = dense_vectors[j]
                if sparse_vectors is not None and j < len(sparse_vectors):
                    point["sparse_vector"] = {
                        "indices": sparse_vectors[j]["indices"],
                        "values": sparse_vectors[j]["values"],
                    }

            # 4. 执行 upsert
            try:
                success = await self._l3_vector.upsert_points("documents", batch_points)
                if not success:
                    logger.error(
                        "分块索引: upsert_points 返回 False（批次 %d）: document_id=%s",
                        start // self._max_batch_size,
                        event.document_id,
                    )
                    continue
                indexed += len(batch_points)
            except Exception:
                logger.exception(
                    "分块索引: upsert 失败（批次 %d）: document_id=%s",
                    start // self._max_batch_size,
                    event.document_id,
                )

        logger.info(
            "分块索引完成: document_id=%s, 总块数=%d, 成功=%d",
            event.document_id,
            len(all_texts),
            indexed,
        )

    async def _embeddable_text(self, content: str) -> str:
        """截断超长文本至 bge-m3 token 上限（按字符估算）

        Args:
            content: 原始文本

        Returns:
            截断后的文本
        """
        del self
        return _truncate_tokens(content)


def _safe_chunk_content(chunk: dict[str, Any], index: int) -> str | None:
    """安全提取分块内容并校正字段类型

    对 metadata.chunks 中的分块 dict 进行健壮性处理：
    - content 非字符串或为空时返回 None（跳过该块）
    - content 超长时按 token 估算截断

    Args:
        chunk: 分块 dict（SemanticChunk.to_dict() 产物）
        index: 分块序号（用于日志定位）

    Returns:
        可嵌入的文本，或 None（跳过该块）
    """
    content = chunk.get("content")
    if not isinstance(content, str) or not content.strip():
        logger.warning("分块索引: 第 %d 块 content 为空或类型非法，跳过", index)
        return None
    return _truncate_tokens(content)


def _truncate_tokens(content: str, max_tokens: int = MAX_INPUT_TOKENS) -> str:
    """按 token 估算截断超长文本

    启发式估算：CJK 字符按 1 token 计，其余字符按 _CHARS_PER_TOKEN_DEFAULT 字符/token 计。
    超出 max_tokens 时截断（以字符数估算），确保嵌入请求不触发 bge-m3 的 8192 上限。

    Args:
        content: 原始文本
        max_tokens: token 上限（默认 8192）

    Returns:
        截断后的文本（不超上限）
    """
    # 快速路径：按最保守估算（全部按 CJK 1 字符/token）判断无需截断
    if len(content) <= max_tokens:
        return content

    # 统计中文等宽字符数量，估算 token 数
    cjk_chars = sum(1 for ch in content if "一" <= ch <= "鿿")
    non_cjk_chars = len(content) - cjk_chars
    estimated_tokens = cjk_chars * _CJK_CHARS_PER_TOKEN + non_cjk_chars / _CHARS_PER_TOKEN_DEFAULT
    if estimated_tokens <= max_tokens:
        return content

    # 需要截断：优先保留内容前缀，字符数按最坏情况（全 CJK）倒推
    allowed_chars = int(max_tokens * _CJK_CHARS_PER_TOKEN)
    return content[:allowed_chars]
