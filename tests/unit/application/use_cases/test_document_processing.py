"""DocumentProcessingUseCase 单元测试

验证 DocumentProcessingUseCase 用例正确
Story 2.x: 文档处理（骨架实现，待完整功能）

Reference: src/application/use_cases/document_processing.py
"""

from __future__ import annotations

from unittest import mock

import pytest

from src.application.use_cases.document_processing import DocumentProcessingUseCase
from src.domain.ports.outbox import OutboxRepository


class TestDocumentProcessingUseCase:
    """验证 DocumentProcessingUseCase 用例"""

    @pytest.fixture
    def mock_outbox_repo(self) -> mock.Mock:
        """创建 mock OutboxRepository"""
        return mock.Mock(spec=OutboxRepository)

    @pytest.fixture
    def use_case(self, mock_outbox_repo: mock.Mock) -> DocumentProcessingUseCase:
        """创建 DocumentProcessingUseCase 实例"""
        return DocumentProcessingUseCase(mock_outbox_repo)

    def test_process_document_success(self, use_case: DocumentProcessingUseCase, mock_outbox_repo: mock.Mock) -> None:
        """验证成功处理文档"""
        result = use_case.process_document("doc-123")

        assert result["status"] == "success"
        assert result["document_id"] == "doc-123"
        mock_outbox_repo.save.assert_called_once()

    def test_process_document_with_metadata(self, use_case: DocumentProcessingUseCase, mock_outbox_repo: mock.Mock) -> None:
        """验证带元数据处理文档"""
        metadata = {"source": "upload", "format": "pdf"}
        result = use_case.process_document("doc-456", metadata=metadata)

        assert result["status"] == "success"
        assert result["document_id"] == "doc-456"

    def test_process_document_publishes_event(self, use_case: DocumentProcessingUseCase, mock_outbox_repo: mock.Mock) -> None:
        """验证处理文档时发布事件"""
        use_case.process_document("doc-789")

        mock_outbox_repo.save.assert_called_once()
        event = mock_outbox_repo.save.call_args[0][0]
        assert event.source == "DocumentProcessingUseCase"

    def test_init_requires_outbox_repo(self, mock_outbox_repo: mock.Mock) -> None:
        """验证初始化需要 outbox_repo 参数"""
        use_case = DocumentProcessingUseCase(mock_outbox_repo)
        assert use_case._outbox_repo is mock_outbox_repo

    def test_process_document_event_payload(self, use_case: DocumentProcessingUseCase, mock_outbox_repo: mock.Mock) -> None:
        """验证事件 payload 包含正确信息"""
        use_case.process_document("doc-999")

        event = mock_outbox_repo.save.call_args[0][0]
        assert event.payload["document_id"] == "doc-999"
        assert event.payload["status"] == "processed"
        assert event.event_type == "DocumentProcessed"
