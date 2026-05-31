"""基础设施层文档处理工作流模块

DocumentProcessingFlow 使用 Prefect @flow 装饰器定义文档处理编排。
事件发布由 DocumentParsingService 统一管理（避免重复发布）。
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from prefect import flow

from src.infrastructure.workflow.tasks.document_tasks import (
    generate_embedding,
    index_document,
    parse_document,
)

logger = logging.getLogger(__name__)


@flow(name="DocumentProcessing")
async def document_processing_flow(
    document_id: uuid.UUID,
    file_path: str,
    tenant_id: str = "",
) -> dict[str, Any]:
    """文档处理工作流

    编排：parse_document -> generate_embedding -> index_document。
    事件发布由 DocumentParsingService 内部完成（Story 2-2a 重构后统一管理）。

    Args:
        document_id: 文档 UUID
        file_path: 文件路径（保留参数，兼容现有调用方）
        tenant_id: 租户标识符（必填，透传至 parse_document task）

    Returns:
        各任务执行结果
    """
    parse_result = await parse_document(document_id, file_path, tenant_id)
    embedding = await generate_embedding(parse_result)
    index_result = await index_document(embedding)

    return {
        "parse_result": parse_result,
        "embedding": embedding,
        "index_result": index_result,
    }
