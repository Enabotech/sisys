"""文档版本事件处理器

监听 DocumentUploaded 和 DocumentProcessed 事件，自动创建版本快照。
采用事件驱动方案，实现关注点分离，不阻塞上传/解析主流程。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.application.services.document_version_service import DocumentVersionService
    from src.domain.events.document_events import DocumentProcessed, DocumentUploaded


class DocumentVersionHandler:
    """文档版本事件处理器

    监听 DocumentUploaded 和 DocumentProcessed 事件，
    自动创建文档版本快照。

    错误隔离：处理器内部异常不影响上传/解析主流程。
    """

    def __init__(
        self,
        document_version_service: DocumentVersionService,
    ) -> None:
        """初始化文档版本事件处理器

        Args:
            document_version_service: 文档版本快照服务
        """
        self._document_version_service = document_version_service

    async def handle_document_uploaded(self, event: DocumentUploaded) -> None:
        """文档上传后自动创建首次版本快照（version=1）

        Args:
            event: 文档上传事件
        """
        await self._document_version_service.create_snapshot(
            document_id=event.document_id,
            tenant_id=event.tenant_id,
            created_by=event.uploaded_by,
            change_description="文档上传",
        )

    async def handle_document_processed(self, event: DocumentProcessed) -> None:
        """文档解析后自动创建版本快照（version=2）

        Args:
            event: 文档解析完成事件
        """
        await self._document_version_service.create_snapshot(
            document_id=event.document_id,
            tenant_id=event.tenant_id,
            created_by="system",
            change_description="文档解析完成",
        )
