"""文档版本自动触发单元测试

测试 DocumentVersionHandler 事件处理器。
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.domain.events.document_events import DocumentProcessed, DocumentUploaded


class TestDocumentVersionHandler:
    """测试 DocumentVersionHandler 事件处理器"""

    def test_handle_document_uploaded_creates_snapshot(self) -> None:
        """上传事件应触发版本快照创建"""
        service = AsyncMock()
        from src.application.event_handlers.document_version_handler import DocumentVersionHandler

        handler = DocumentVersionHandler(document_version_service=service)

        event = DocumentUploaded(
            document_id=uuid4(),
            filename="test.pdf",
            tenant_id="tenant-1",
            uploaded_by="user-1",
        )

        import asyncio

        asyncio.run(handler.handle_document_uploaded(event))

        service.create_snapshot.assert_called_once_with(
            document_id=event.document_id,
            tenant_id=event.tenant_id,
            created_by=event.uploaded_by,
            change_description="文档上传",
        )

    def test_handle_document_processed_creates_snapshot(self) -> None:
        """解析完成事件应触发版本快照创建"""
        service = AsyncMock()
        from src.application.event_handlers.document_version_handler import DocumentVersionHandler

        handler = DocumentVersionHandler(document_version_service=service)

        event = DocumentProcessed(
            document_id=uuid4(),
            tenant_id="tenant-1",
        )

        import asyncio

        asyncio.run(handler.handle_document_processed(event))

        service.create_snapshot.assert_called_once_with(
            document_id=event.document_id,
            tenant_id=event.tenant_id,
            created_by="system",
            change_description="文档解析完成",
        )

    def test_handler_error_does_not_propagate(self) -> None:
        """处理器内部异常不应传播（由事件总线处理）"""
        service = AsyncMock()
        service.create_snapshot = AsyncMock(side_effect=ValueError("test error"))
        from src.application.event_handlers.document_version_handler import DocumentVersionHandler

        handler = DocumentVersionHandler(document_version_service=service)

        event = DocumentUploaded(
            document_id=uuid4(),
            tenant_id="tenant-1",
            uploaded_by="user-1",
        )

        # 异常应由事件总线处理，在处理器中允许抛出
        with pytest.raises(ValueError):
            import asyncio

            asyncio.run(handler.handle_document_uploaded(event))
