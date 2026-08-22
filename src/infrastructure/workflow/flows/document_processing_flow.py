"""基础设施层文档处理工作流模块

DocumentProcessingFlow 使用 Prefect @flow 装饰器定义文档处理编排。
事件发布由 DocumentParsingService 统一管理（避免重复发布）。

⚠️ 索引迁移说明（Epic 3 架构对齐重构）：
- 本 Flow 仅负责文档【解析】阶段（parse_document）。
- 向量索引已统一迁移至事件驱动链：
  DocumentProcessed → SemanticChunkingHandler → SemanticChunkingService（发布 RAGIndexed）
  → ChunkIndexingHandler（分块级 Dense+Sparse upsert）。
- 原 generate_embedding / index_document 全文索引轨已废弃（见 document_tasks.py DEPRECATED 标记），
  避免双轨混写同一 collection（文档级点 + 分块级点噪声）。
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from prefect import flow

from src.infrastructure.workflow.tasks.document_tasks import parse_document

logger = logging.getLogger(__name__)


@flow(name="DocumentProcessing")
async def document_processing_flow(
    document_id: uuid.UUID,
    file_path: str,
    tenant_id: str = "",
) -> dict[str, Any]:
    """文档处理工作流

    仅执行解析阶段（parse_document）。向量索引由事件驱动链完成：
    DocumentProcessed → 语义分块（RAGIndexed）→ ChunkIndexingHandler → Qdrant upsert。

    Args:
        document_id: 文档 UUID
        file_path: 文件路径（保留参数，兼容现有调用方）
        tenant_id: 租户标识符（必填，透传至 parse_document task）

    Returns:
        解析任务执行结果
    """
    parse_result = await parse_document(document_id, file_path, tenant_id)

    return {
        "parse_result": parse_result,
        "indexing": "event-driven",
        "index_result": {"indexed": True, "note": "向量索引由 RAGIndexed 事件驱动链完成"},
    }
