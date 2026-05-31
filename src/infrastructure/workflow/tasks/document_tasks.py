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
async def parse_document(document_id: uuid.UUID, file_path: str) -> dict[str, Any]:
    """解析文档任务

    通过 DI 容器获取 DocumentParsingService 执行真实解析。
    file_path 参数保留以保持 API 兼容性（Service 内部从 MinIO 下载）。

    Args:
        document_id: 文档 UUID
        file_path: 文件路径（保留参数，Service 内部不使用）

    Returns:
        解析结果字典
    """
    from src.domain.ports.resolver import get_resolver

    try:
        service = get_resolver().resolve("document_parsing_service")
    except Exception as e:
        logger.error("获取 DocumentParsingService 失败: %s", e)
        return {"status": "failed", "document_id": str(document_id), "error": str(e)}

    try:
        # 从 document_id 关联的 metadata 中获取 tenant_id
        # MVP 阶段使用空 tenant_id 占位，实际由上层传入
        doc = await service.parse_document(document_id, tenant_id="")
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

    MVP 占位实现，返回 mock 数据。
    真实嵌入逻辑由 Epic 3 故事补充。

    Args:
        parse_result: 解析结果

    Returns:
        Embedding mock 数据
    """
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
