"""基础设施层文档处理任务模块

定义 parse_document, generate_embedding, index_document Prefect tasks。
parse_document 已替换为真实解析逻辑（Story 2-2a）。
generate_embedding 扩展为双向量生成（Dense + Sparse），返回 EmbeddingResult TypedDict。
index_document 从 mock 替换为真实 Qdrant upsert（PointStruct + NamedSparseVector）。
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any, TypedDict, cast

from prefect import task

from src.domain.ports.embedding_service import SparseEmbedding

logger = logging.getLogger(__name__)


class EmbeddingResult(TypedDict):
    """嵌入生成结果 TypedDict

    替代 generate_embedding 原 list[float] 返回类型，
    同时承载 Dense 向量和 Sparse 向量。

    Attributes:
        dense_vectors: Dense 嵌入向量列表（bge-m3 1024 维）
        sparse_vectors: Sparse 嵌入向量列表（bge-m3 词法权重）
    """

    dense_vectors: list[list[float]]
    sparse_vectors: list[SparseEmbedding]


@task(retries=2)
async def parse_document(document_id: uuid.UUID, file_path: str, tenant_id: str = "") -> dict[str, Any]:
    """解析文档任务

    通过 DI 容器获取 DocumentParsingService 执行真实解析。
    file_path 参数保留以保持 API 兼容性（Service 内部从 MinIO 下载）。

    Args:
        document_id: 文档 UUID
        file_path: 文件路径（保留参数，Service 内部不使用）
        tenant_id: 租户标识符（必填，空值将导致查询失败）

    Returns:
        解析结果字典
    """
    from src.domain.ports.resolver import get_resolver

    if not tenant_id:
        logger.error("parse_document 调用缺少 tenant_id, document_id=%s", document_id)
        return {"status": "failed", "document_id": str(document_id), "error": "tenant_id is required"}

    try:
        service = get_resolver().resolve("document_parsing_service")
    except Exception as e:
        logger.error("获取 DocumentParsingService 失败: %s", e)
        return {"status": "failed", "document_id": str(document_id), "error": str(e)}

    try:
        doc = await service.parse_document(document_id, tenant_id=tenant_id)
        result_dict = {
            "status": doc.parse_status.value,
            "document_id": str(doc.document_id),
            "tenant_id": tenant_id,
            "pages": len(doc.metadata.get("parse_result", {}).get("pages", [])),
        }
        return result_dict
    except Exception as e:
        logger.error("解析文档 %s 失败: %s", document_id, e)
        return {"status": "failed", "document_id": str(document_id), "error": str(e)}


@task(retries=2)
async def generate_embedding(parse_result: dict[str, Any]) -> EmbeddingResult:
    """生成双向量嵌入任务（Dense + Sparse）

    通过 DI 容器获取 embedding_service 和 document_repository，
    从文档解析结果中提取文本，并行生成 Dense 和 Sparse 嵌入向量。

    Args:
        parse_result: 解析结果（含 document_id, tenant_id）

    Returns:
        EmbeddingResult TypedDict（dense_vectors + sparse_vectors），失败时返回空列表
    """
    from src.domain.ports.document_repository import DocumentQuery
    from src.domain.ports.resolver import get_resolver

    empty: EmbeddingResult = {"dense_vectors": [], "sparse_vectors": []}

    try:
        if parse_result.get("status") == "failed":
            return empty

        tenant_id = parse_result.get("tenant_id", "")
        if not tenant_id:
            logger.error("generate_embedding 缺少 tenant_id, document_id=%s", parse_result.get("document_id"))
            return empty

        resolver = get_resolver()
        service = resolver.resolve("embedding_service")
        repo = resolver.resolve("document_repository")
        doc = await repo.find(
            DocumentQuery(
                tenant_id=tenant_id,
                document_id=uuid.UUID(parse_result["document_id"]),
            )
        )

        if not doc or not doc.metadata.get("parse_result"):
            return empty

        pages = doc.metadata["parse_result"].get("pages", [])
        # 提取 texts 中的文本
        text_parts: list[str] = [
            elem.get("content", "") for page in pages for elem in page.get("texts", []) if isinstance(elem, dict)
        ]
        # 提取 tables 中的文本（表格行展平为 "cell1 cell2 ..." 格式）
        for page in pages:
            for table in page.get("tables", []):
                if isinstance(table, dict):
                    for row in table.get("rows", []):
                        if isinstance(row, list):
                            text_parts.append(" ".join(str(cell) for cell in row if cell))
        text = " ".join(text_parts)

        if not text.strip():
            return empty

        # 并行生成 Dense 和 Sparse 嵌入
        dense_task = asyncio.to_thread(service.embed_documents, [text])

        async def _safe_sparse() -> list[SparseEmbedding]:
            try:
                return await asyncio.to_thread(service.embed_sparse, [text])
            except Exception as e:
                logger.warning(
                    "Sparse 嵌入生成失败，降级为仅 Dense 索引: document_id=%s, error=%s",
                    parse_result.get("document_id"),
                    e,
                )
                return []

        sparse_task = asyncio.create_task(_safe_sparse())

        dense_vectors = await dense_task
        sparse_vectors = await sparse_task

        return EmbeddingResult(
            dense_vectors=cast(list[list[float]], dense_vectors),
            sparse_vectors=sparse_vectors,
        )
    except Exception as e:
        logger.error("生成嵌入失败: %s", e)
        return empty


@task(retries=2)
async def index_document(embedding_result: EmbeddingResult) -> dict[str, Any]:
    """索引文档任务（真实 Qdrant upsert）

    将 Dense 和 Sparse 向量写入 Qdrant Collection。
    通过 DI 容器获取 l3_vector 端口，使用 PointStruct + NamedSparseVector 写入。

    Args:
        embedding_result: EmbeddingResult TypedDict（dense_vectors + sparse_vectors）

    Returns:
        IndexResult dict（indexed: bool, chunk_count: int）
    """
    from src.domain.ports.resolver import get_resolver

    dense_vectors = embedding_result.get("dense_vectors", [])
    sparse_vectors = embedding_result.get("sparse_vectors", [])

    if not dense_vectors:
        logger.warning("index_document: 无 Dense 向量，跳过索引")
        return {"indexed": False, "chunk_count": 0}

    try:
        l3_vector = get_resolver().resolve("l3_vector")

        points: list[dict[str, Any]] = []
        for i, dense_vec in enumerate(dense_vectors):
            point: dict[str, Any] = {
                "id": str(uuid.uuid4()),
                "vector": dense_vec,
                "payload": {
                    "chunk_index": i,
                    "created_at": datetime.now(UTC).isoformat(),
                },
            }
            # 如果有稀疏向量，附加到 payload
            if i < len(sparse_vectors):
                sv = sparse_vectors[i]
                point["sparse_vector"] = {
                    "indices": sv["indices"],
                    "values": sv["values"],
                }

            points.append(point)

        success = await l3_vector.upsert_points("documents", points)
        if not success:
            logger.error("index_document: upsert_points 返回 False")
            return {"indexed": False, "chunk_count": 0}

        return {"indexed": True, "chunk_count": len(points)}
    except Exception as e:
        logger.error("索引文档失败: %s", e)
        return {"indexed": False, "chunk_count": 0, "error": str(e)}
