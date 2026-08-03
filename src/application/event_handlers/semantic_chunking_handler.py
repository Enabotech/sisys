"""语义分块事件处理器

监听 DocumentProcessed 事件，异步触发语义分块。
对齐 Story 2-6 DocumentVersionHandler 模式：
- 错误隔离：分块失败不影响文档的 parse_status
- 异步非阻塞：不阻塞解析主流程
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.application.services.semantic_chunking_service import SemanticChunkingService
    from src.domain.events.document_events import DocumentProcessed

logger = logging.getLogger(__name__)


class SemanticChunkingHandler:
    """语义分块事件处理器

    监听 DocumentProcessed 事件，异步触发语义分块。
    错误隔离：处理器内部异常不影响文档解析主流程。
    """

    def __init__(
        self,
        semantic_chunking_service: SemanticChunkingService,
    ) -> None:
        """初始化语义分块事件处理器

        Args:
            semantic_chunking_service: 语义分块服务
        """
        self._service = semantic_chunking_service

    async def handle_document_processed(self, event: DocumentProcessed) -> None:
        """文档解析完成后自动触发语义分块

        Args:
            event: 文档解析完成事件
        """
        try:
            await self._service.chunk_document(
                document_id=event.document_id,
                tenant_id=event.tenant_id,
            )
        except Exception:
            logger.exception(
                "语义分块失败（不影响解析状态）: document_id=%s, tenant_id=%s",
                event.document_id,
                event.tenant_id,
            )
