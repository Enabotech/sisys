"""基础设施层文档处理工作流模块

DocumentProcessingFlow 使用 Prefect @flow 装饰器定义文档处理编排

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from prefect import flow

from src.domain.events.document_events import DocumentProcessed
from src.infrastructure.workflow.tasks.document_tasks import (
    generate_embedding,
    index_document,
    parse_document,
)

if TYPE_CHECKING:
    from src.domain.ports.event_publisher import EventPublisher

logger = logging.getLogger(__name__)


@flow(name="DocumentProcessing")
async def document_processing_flow(
    document_id: uuid.UUID,
    file_path: str,
    event_publisher: EventPublisher,
) -> dict[str, Any]:
    """文档处理工作流

    编排：parse_document → generate_embedding → index_document
    完成后通过 EventPublisher 发布 DocumentProcessed 事件

    Args:
        document_id: 文档 UUID
        file_path: 文件路径
        event_publisher: 事件发布端口

    Returns:
        各任务执行结果
    """
    parse_result = await parse_document(document_id, file_path)
    embedding = await generate_embedding(parse_result)
    index_result = await index_document(embedding)

    event = DocumentProcessed(
        document_id=document_id,
        parse_result=parse_result,
        embedding=embedding,
    )
    result = await event_publisher.publish(event)
    if result.is_full_failure:
        logger.warning("DocumentProcessed event publish failed for %s", document_id)

    return {
        "parse_result": parse_result,
        "embedding": embedding,
        "index_result": index_result,
    }
