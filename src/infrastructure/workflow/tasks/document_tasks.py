"""基础设施层文档处理任务模块

定义 parse_document 任务，作为 Prefect 工作流的一部分。
parse_document 已替换为真实解析逻辑（Story 2-2a）。
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, TypedDict

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


@task(retries=2, retry_delay_seconds=30)
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

    Raises:
        RuntimeError: 可恢复的基础设施异常，触发 Prefect 重试
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
