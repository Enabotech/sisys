"""语义分块事件处理器

监听 DocumentProcessed 事件，异步触发语义分块。
对齐 Story 2-6 DocumentVersionHandler 模式：
- 错误隔离：分块失败不影响文档的 parse_status
- 异步非阻塞：不阻塞解析主流程
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.application.services.semantic_chunking_service import SemanticChunkingService
    from src.domain.events.base import DomainEvent
    from src.domain.events.document_events import DocumentProcessed
    from src.domain.ports.event_listener import EventListener

logger = logging.getLogger(__name__)


class SemanticChunkingHandler:
    """语义分块事件处理器

    监听 DocumentProcessed 事件，异步触发语义分块。
    错误隔离：处理器内部异常不影响文档解析主流程。

    对齐 DocumentVersionHandler 模式，必须提供 register_handlers() 方法
    以便在 composition_root 中统一注册到事件总线。
    """

    def __init__(
        self,
        semantic_chunking_service: SemanticChunkingService,
        event_listener: EventListener | None = None,
    ) -> None:
        """初始化语义分块事件处理器

        Args:
            semantic_chunking_service: 语义分块服务
            event_listener: 事件监听器（用于注册处理器，可选）
        """
        self._service = semantic_chunking_service
        self._event_listener = event_listener

    def register_handlers(self) -> None:
        """注册事件处理器到事件监听器

        监听 DocumentProcessed 事件，触发 handle_document_processed。
        """
        if self._event_listener is None:
            logger.warning("event_listener 未注入，跳过事件处理器注册")
            return

        self._event_listener.on_event("DocumentProcessed", self._wrap_handler())
        logger.info("SemanticChunkingHandler 已注册: DocumentProcessed")

    def _wrap_handler(self) -> Callable[[DomainEvent], None]:
        """将异步处理器包装为同步回调"""

        def handle(event: DomainEvent) -> None:
            try:
                if isinstance(event, DocumentProcessed):
                    asyncio.run(self.handle_document_processed(event))
            except Exception:
                logger.exception("语义分块失败，不影响主流程")

        return handle

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
