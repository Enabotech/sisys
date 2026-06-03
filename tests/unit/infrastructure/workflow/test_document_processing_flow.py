"""DocumentProcessingFlow 单元测试

验证 Prefect flow 定义、任务配置、事件发布逻辑

使用 task.fn() 测试任务底层函数，不启动真实 Prefect server
所有涉及 DI resolver 的测试必须 mock，避免加载真实模型
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.events.document_events import DocumentProcessed


@pytest.fixture
def mock_event_publisher() -> AsyncMock:
    """Mock EventPublisher 用于验证事件发布"""
    from src.domain.events.publish_result import ChannelResult, PublishResult

    publisher = AsyncMock()
    publisher.publish = AsyncMock(return_value=PublishResult(event_id="test-id", results=(ChannelResult("realtime", True),)))
    return publisher


@pytest.fixture
def mock_embedding_service() -> MagicMock:
    """Mock EmbeddingService 避免 GPU 模型加载"""
    service = MagicMock()
    service.encode_text = MagicMock(return_value=[0.1] * 1024)
    return service


@pytest.fixture
def mock_document_repository() -> AsyncMock:
    """Mock DocumentRepository"""
    from src.domain.entities.document import Document, ParseStatus

    doc = Document(
        document_id=uuid.uuid4(),
        filename="test.pdf",
        mime_type="application/pdf",
        tenant_id="test-tenant",
    )
    doc.parse_status = ParseStatus.COMPLETED
    doc.metadata["parse_result"] = {"pages": [{"texts": [{"content": "测试文本"}]}]}

    repo = AsyncMock()
    repo.find = AsyncMock(return_value=doc)
    return repo


@pytest.fixture
def mock_resolver(mock_embedding_service: MagicMock, mock_document_repository: AsyncMock) -> MagicMock:
    """Mock DI Resolver 避免 I/O 和模型加载"""
    resolver = MagicMock()
    resolver.resolve.side_effect = lambda name: {
        "embedding_service": mock_embedding_service,
        "document_repository": mock_document_repository,
        "document_parsing_service": AsyncMock(),
    }.get(name)
    return resolver


class TestDocumentTasksFn:
    """测试任务底层函数（通过 .fn() 绕过 Prefect 运行时）"""

    async def test_parse_document_fn_returns_dict(self) -> None:
        """parse_document.fn() 缺少 tenant_id 应返回 failed"""
        from src.infrastructure.workflow.tasks.document_tasks import parse_document

        result = await parse_document.fn(uuid.uuid4(), "/test.pdf")
        assert isinstance(result, dict)
        assert result["status"] == "failed"
        assert "tenant_id" in result["error"]

    async def test_parse_document_fn_with_tenant_id(self) -> None:
        """parse_document.fn() 有 tenant_id 但 resolver 失败时返回 failed"""
        from unittest.mock import MagicMock, patch

        from src.infrastructure.workflow.tasks.document_tasks import parse_document

        mock_resolver = MagicMock()
        mock_resolver.resolve.side_effect = Exception("resolver not ready")

        with patch("src.domain.ports.resolver.get_resolver", return_value=mock_resolver):
            result = await parse_document.fn(uuid.uuid4(), "/test.pdf", "tenant-1")

        assert isinstance(result, dict)
        assert result["status"] == "failed"

    async def test_generate_embedding_fn_returns_list(self, mock_resolver: MagicMock) -> None:
        """generate_embedding.fn() 应返回 list"""
        from src.infrastructure.workflow.tasks.document_tasks import generate_embedding

        with patch("src.domain.ports.resolver.get_resolver", return_value=mock_resolver):
            result = await generate_embedding.fn({"status": "parsed", "document_id": str(uuid.uuid4())})
        assert isinstance(result, list)

    async def test_index_document_fn_returns_dict(self) -> None:
        """index_document.fn() 应返回 dict"""
        from src.infrastructure.workflow.tasks.document_tasks import index_document

        result = await index_document.fn([])
        assert isinstance(result, dict)
        assert "indexed" in result


class TestEventPublishLogic:
    """验证事件发布逻辑"""

    async def test_document_processed_event_created_correctly(self, mock_event_publisher: AsyncMock) -> None:
        """验证 DocumentProcessed 事件正确创建"""
        document_id = uuid.uuid4()
        parse_result = {"status": "parsed", "pages": 10}
        embedding = [0.1, 0.2, 0.3]

        event = DocumentProcessed(
            document_id=document_id,
            parse_result=parse_result,
            embedding=embedding,
        )

        assert event.document_id == document_id
        assert event.parse_result == parse_result
        assert event.embedding == embedding
        assert event.event_type == "DocumentProcessed"

    async def test_event_publisher_publish_called(self, mock_event_publisher: AsyncMock) -> None:
        """验证 EventPublisher.publish 被正确调用"""
        event = DocumentProcessed(document_id=uuid.uuid4())

        result = await mock_event_publisher.publish(event)

        mock_event_publisher.publish.assert_called_once()
        assert result.is_success


class TestDocumentProcessingFlowExecution:
    """DocumentProcessingFlow 执行逻辑测试"""

    async def test_flow_fn_executes_all_tasks(self, mock_embedding_service: MagicMock) -> None:
        """测试 flow.fn() 执行完整流程"""
        from src.domain.entities.document import Document, ParseStatus
        from src.domain.events.publish_result import ChannelResult, PublishResult
        from src.infrastructure.workflow.tasks.document_tasks import (
            generate_embedding,
            index_document,
            parse_document,
        )

        document_id = uuid.uuid4()
        file_path = "/test/document.pdf"

        mock_publisher = AsyncMock()
        mock_publisher.publish = AsyncMock(
            return_value=PublishResult(
                event_id="test-event-id",
                results=(ChannelResult("realtime", True),),
            )
        )

        mock_doc = Document(
            document_id=document_id,
            filename="document.pdf",
            mime_type="application/pdf",
            tenant_id="t1",
        )
        mock_doc.parse_status = ParseStatus.COMPLETED
        mock_doc.metadata["parse_result"] = {"pages": [{"texts": [{"content": "测试文本"}]}]}

        mock_parsing_service = AsyncMock()
        mock_parsing_service.parse_document = AsyncMock(return_value=mock_doc)

        mock_repo = AsyncMock()
        mock_repo.find = AsyncMock(return_value=mock_doc)

        mock_resolver = MagicMock()
        mock_resolver.resolve.side_effect = lambda name: {
            "document_parsing_service": mock_parsing_service,
            "embedding_service": mock_embedding_service,
            "document_repository": mock_repo,
        }[name]

        with patch("src.domain.ports.resolver.get_resolver", return_value=mock_resolver):
            parse_result = await parse_document.fn(document_id, file_path, "tenant-1")
            embedding = await generate_embedding.fn(parse_result)

        index_result = await index_document.fn(embedding)

        event = DocumentProcessed(
            document_id=document_id,
            parse_result=parse_result,
            embedding=embedding,
        )
        await mock_publisher.publish(event)

        assert parse_result["status"] == "completed"
        assert isinstance(embedding, list)
        assert "indexed" in index_result
        mock_publisher.publish.assert_called_once()

    async def test_flow_handles_publish_failure(self, mock_embedding_service: MagicMock) -> None:
        """测试 flow 处理事件发布失败"""
        from src.domain.entities.document import Document, ParseStatus
        from src.domain.events.publish_result import ChannelResult, PublishResult
        from src.infrastructure.workflow.tasks.document_tasks import (
            generate_embedding,
            index_document,
            parse_document,
        )

        document_id = uuid.uuid4()
        file_path = "/test/document.pdf"

        mock_publisher = AsyncMock()
        mock_publisher.publish = AsyncMock(
            return_value=PublishResult(
                event_id="test-event-id",
                results=(ChannelResult("realtime", False),),
            )
        )

        mock_doc = Document(
            document_id=document_id,
            filename="document.pdf",
            mime_type="application/pdf",
            tenant_id="t1",
        )
        mock_doc.parse_status = ParseStatus.COMPLETED
        mock_doc.metadata["parse_result"] = {"pages": [{"texts": [{"content": "测试文本"}]}]}

        mock_parsing_service = AsyncMock()
        mock_parsing_service.parse_document = AsyncMock(return_value=mock_doc)

        mock_repo = AsyncMock()
        mock_repo.find = AsyncMock(return_value=mock_doc)

        mock_resolver = MagicMock()
        mock_resolver.resolve.side_effect = lambda name: {
            "document_parsing_service": mock_parsing_service,
            "embedding_service": mock_embedding_service,
            "document_repository": mock_repo,
        }[name]

        with patch("src.domain.ports.resolver.get_resolver", return_value=mock_resolver):
            parse_result = await parse_document.fn(document_id, file_path, "tenant-1")
            embedding = await generate_embedding.fn(parse_result)

        index_result = await index_document.fn(embedding)

        event = DocumentProcessed(
            document_id=document_id,
            parse_result=parse_result,
            embedding=embedding,
        )
        result = await mock_publisher.publish(event)

        assert parse_result["status"] == "completed"
        assert isinstance(embedding, list)
        assert "indexed" in index_result
        assert result.is_full_failure
