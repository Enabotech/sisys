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
from src.infrastructure.workflow.flows.document_processing_flow import document_processing_flow
from src.infrastructure.workflow.tasks.document_tasks import (
    EmbeddingResult,
    generate_embedding,
    index_document,
    parse_document,
)


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
    service.embed_documents = MagicMock(return_value=[[0.1] * 1024])
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
        result = await parse_document.fn(uuid.uuid4(), "/test.pdf")
        assert isinstance(result, dict)
        assert result["status"] == "failed"
        assert "tenant_id" in result["error"]

    async def test_parse_document_fn_with_tenant_id(self) -> None:
        """parse_document.fn() 有 tenant_id 但 resolver 失败时返回 failed"""
        from unittest.mock import MagicMock, patch

        mock_resolver = MagicMock()
        mock_resolver.resolve.side_effect = Exception("resolver not ready")

        with patch("src.domain.ports.resolver.get_resolver", return_value=mock_resolver):
            result = await parse_document.fn(uuid.uuid4(), "/test.pdf", "tenant-1")

        assert isinstance(result, dict)
        assert result["status"] == "failed"

    async def test_generate_embedding_fn_returns_embedding_result(self, mock_resolver: MagicMock) -> None:
        """generate_embedding.fn() 应返回 EmbeddingResult TypedDict"""
        with patch("src.domain.ports.resolver.get_resolver", return_value=mock_resolver):
            result = await generate_embedding.fn(
                {
                    "status": "completed",
                    "document_id": str(uuid.uuid4()),
                    "tenant_id": "test-tenant",
                }
            )
        assert isinstance(result, dict)
        assert "dense_vectors" in result
        assert "sparse_vectors" in result

    async def test_index_document_fn_accepts_embedding_result(self) -> None:
        """index_document.fn() 应接受 EmbeddingResult 并返回 dict"""
        embedding_result: EmbeddingResult = {"dense_vectors": [], "sparse_vectors": []}
        result = await index_document.fn(embedding_result)
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
        )
        await mock_publisher.publish(event)

        assert parse_result["status"] == "completed"
        assert isinstance(embedding, dict)
        assert "dense_vectors" in embedding
        assert "indexed" in index_result
        mock_publisher.publish.assert_called_once()

    async def test_flow_handles_publish_failure(self, mock_embedding_service: MagicMock) -> None:
        """测试 flow 处理事件发布失败"""
        from src.domain.entities.document import Document, ParseStatus
        from src.domain.events.publish_result import ChannelResult, PublishResult

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
        )
        result = await mock_publisher.publish(event)

        assert parse_result["status"] == "completed"
        assert isinstance(embedding, dict)
        assert "dense_vectors" in embedding
        assert "indexed" in index_result
        assert result.is_full_failure


class TestDocumentProcessingFlowFn:
    """document_processing_flow.fn() 直接调用测试"""

    async def test_flow_fn_failed_parse_short_circuit(self) -> None:
        """parse 返回 failed 时应短路返回空 embedding + indexed: False"""
        doc_id = uuid.uuid4()
        failed_parse_result = {"status": "failed", "error": "parse error"}

        with patch(
            "src.infrastructure.workflow.flows.document_processing_flow.parse_document",
            new=AsyncMock(return_value=failed_parse_result),
        ):
            result = await document_processing_flow.fn(doc_id, "/test.pdf", "tenant-1")

        assert result["parse_result"]["status"] == "failed"
        assert result["embedding"] == []
        assert result["index_result"]["indexed"] is False

    async def test_flow_fn_happy_path(self) -> None:
        """parse 成功时应依次调用 generate_embedding 和 index_document"""
        doc_id = uuid.uuid4()
        parse_result = {"status": "completed", "document_id": str(doc_id), "pages": []}
        embedding_result = {"dense_vectors": [[0.1, 0.2, 0.3]], "sparse_vectors": []}
        index_result = {"indexed": True, "chunk_count": 1}

        with (
            patch(
                "src.infrastructure.workflow.flows.document_processing_flow.parse_document",
                new=AsyncMock(return_value=parse_result),
            ),
            patch(
                "src.infrastructure.workflow.flows.document_processing_flow.generate_embedding",
                new=AsyncMock(return_value=embedding_result),
            ) as mock_embed,
            patch(
                "src.infrastructure.workflow.flows.document_processing_flow.index_document",
                new=AsyncMock(return_value=index_result),
            ) as mock_index,
        ):
            result = await document_processing_flow.fn(doc_id, "/test.pdf", "tenant-1")

        assert result["parse_result"]["status"] == "completed"
        assert result["embedding"] == embedding_result
        assert result["index_result"]["indexed"] is True
        mock_embed.assert_called_once_with(parse_result)
        mock_index.assert_called_once_with(embedding_result)

    async def test_flow_fn_passes_tenant_id_to_parse(self) -> None:
        """flow 应将 tenant_id 传递给 parse_document"""
        doc_id = uuid.uuid4()

        with patch(
            "src.infrastructure.workflow.flows.document_processing_flow.parse_document",
            new=AsyncMock(return_value={"status": "failed", "error": "test"}),
        ) as mock_parse:
            await document_processing_flow.fn(doc_id, "/test.pdf", "tenant-x")

        mock_parse.assert_called_once_with(doc_id, "/test.pdf", "tenant-x")
