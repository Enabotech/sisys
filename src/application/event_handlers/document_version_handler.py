"""文档版本事件处理器

监听 DocumentUploaded 和 DocumentProcessed 事件，自动创建版本快照。
采用事件驱动方案，实现关注点分离，不阻塞上传/解析主流程。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.application.services.document_version_service import DocumentVersionService
    from src.domain.events.base import DomainEvent
    from src.domain.events.document_events import DocumentProcessed, DocumentUploaded
    from src.domain.ports.event_listener import EventListener

logger = logging.getLogger(__name__)


class DocumentVersionHandler:
    """文档版本事件处理器

    监听 DocumentUploaded 和 DocumentProcessed 事件，
    自动创建文档版本快照。

    错误隔离：处理器内部异常不影响上传/解析主流程。
    """

    def __init__(
        self,
        document_version_service: DocumentVersionService,
        event_listener: EventListener | None = None,
    ) -> None:
        """初始化文档版本事件处理器

        Args:
            document_version_service: 文档版本快照服务
            event_listener: 事件监听器（用于注册处理器，可选）
        """
        self._document_version_service = document_version_service
        self._event_listener = event_listener

    def register_handlers(self) -> None:
        """注册事件处理器到事件监听器

        监听 DocumentUploaded 和 DocumentProcessed 事件，
        分别触发 handle_document_uploaded 和 handle_document_processed。
        """
        if self._event_listener is None:
            logger.warning("event_listener 未注入，跳过事件处理器注册")
            return

        self._event_listener.on_event("DocumentUploaded", self._wrap_handler("uploaded"))
        self._event_listener.on_event("DocumentProcessed", self._wrap_handler("processed"))
        logger.info("DocumentVersionHandler 已注册: DocumentUploaded, DocumentProcessed")

    def _wrap_handler(self, handler_type: str) -> Callable[[DomainEvent], None]:
        """将异步处理器包装为同步回调

        Args:
            handler_type: 处理器类型（"uploaded" 或 "processed"）

        Returns:
            同步包装函数
        """

        def handle(event: DomainEvent) -> None:
            try:
                if handler_type == "uploaded":
                    asyncio.run(self.handle_document_uploaded(event))  # type: ignore[arg-type]
                else:
                    asyncio.run(self.handle_document_processed(event))  # type: ignore[arg-type]
            except Exception:
                logger.exception("文档版本快照自动创建失败，不影响主流程")

        return handle

    async def handle_document_uploaded(self, event: DocumentUploaded) -> None:
        """文档上传后自动创建首次版本快照（version=1）

        Args:
            event: 文档上传事件
        """
        try:
            await self._document_version_service.create_snapshot(
                document_id=event.document_id,
                tenant_id=event.tenant_id,
                created_by=event.uploaded_by,
                change_description="文档上传",
            )
        except Exception:
            logger.exception(
                "文档上传后自动创建版本快照失败，不影响主流程: document_id=%s, tenant_id=%s",
                event.document_id,
                event.tenant_id,
            )

    async def handle_document_processed(self, event: DocumentProcessed) -> None:
        """文档解析后自动创建版本快照（version=2）

        Args:
            event: 文档解析完成事件
        """
        try:
            await self._document_version_service.create_snapshot(
                document_id=event.document_id,
                tenant_id=event.tenant_id,
                created_by="system",
                change_description="文档解析完成",
            )
        except Exception:
            logger.exception(
                "文档解析后自动创建版本快照失败，不影响主流程: document_id=%s, tenant_id=%s",
                event.document_id,
                event.tenant_id,
            )
