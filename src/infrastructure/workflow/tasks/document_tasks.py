"""基础设施层文档处理任务模块

定义 parse_document, generate_embedding, index_document Prefect tasks。
parse_document 已替换为真实解析逻辑（Story 2-2a）。
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from prefect import task

logger = logging.getLogger(__name__)


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
            "pages": len(doc.metadata.get("parse_result", {}).get("pages", [])),
        }
        return result_dict
    except Exception as e:
        logger.error("解析文档 %s 失败: %s", document_id, e)
        return {"status": "failed", "document_id": str(document_id), "error": str(e)}


@task(retries=2)
async def generate_embedding(parse_result: dict[str, Any]) -> list[float]:
    """生成嵌入向量任务

    通过 DI 容器获取 embedding_service 和 document_repository，
    从文档解析结果中提取文本并生成嵌入向量。

    Args:
        parse_result: 解析结果（含 document_id）

    Returns:
        嵌入向量列表，失败时返回空列表
    """
    from src.domain.ports.resolver import get_resolver

    try:
        if parse_result.get("status") == "failed":
            return []

        resolver = get_resolver()
        service = resolver.resolve("embedding_service")
        repo = resolver.resolve("document_repository")
        doc = await repo.find(uuid.UUID(parse_result["document_id"]))

        if not doc or not doc.metadata.get("parse_result"):
            return []

        pages = doc.metadata["parse_result"].get("pages", [])
        text = " ".join(elem.get("content", "") for page in pages for elem in page.get("texts", []) if isinstance(elem, dict))

        if not text.strip():
            return []

        import asyncio
        from typing import cast

        embedding = await asyncio.to_thread(service.encode_text, text[:8192])
        return cast(list[float], embedding)
    except Exception as e:
        logger.error("生成嵌入失败: %s", e)
        return []


@task(retries=2)
async def index_document(embedding_result: list[float]) -> dict[str, Any]:
    """索引文档任务

    MVP 占位实现，返回 mock 数据。
    真实索引逻辑由 Epic 3 故事补充。

    Args:
        embedding_result: 嵌入结果

    Returns:
        IndexResult mock 数据
    """
    return {"indexed": False, "chunk_count": 0}
