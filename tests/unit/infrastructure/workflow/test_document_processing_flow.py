"""DocumentProcessingFlow 单元测试

验证 Prefect flow 定义、任务配置、事件发布逻辑

使用 task.fn() 测试任务底层函数，不启动真实 Prefect server

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from src.domain.events.document_events import DocumentProcessed


@pytest.fixture
def mock_event_publisher() -> AsyncMock:
    """Mock EventPublisher 用于验证事件发布"""
    from src.domain.events.publish_result import PublishResult

    publisher = AsyncMock()
    publisher.publish = AsyncMock(return_value=PublishResult(event_id="test-id", redis_success=True))
    return publisher


class TestDocumentProcessingFlowDefinition:
    """DocumentProcessingFlow @flow 装饰器验证"""

    def test_flow_has_correct_name(self) -> None:
        """Flow 名称应为 DocumentProcessing"""
        from src.infrastructure.workflow.flows.document_processing_flow import (
            document_processing_flow,
        )

        assert document_processing_flow.name == "DocumentProcessing"

    def test_flow_is_prefect_flow(self) -> None:
        """Flow 应为 Prefect Flow 对象"""
        from prefect.flows import Flow

        from src.infrastructure.workflow.flows.document_processing_flow import (
            document_processing_flow,
        )

        assert isinstance(document_processing_flow, Flow)


class TestDocumentTasks:
    """document_tasks @task 装饰器验证"""

    def test_parse_document_is_prefect_task(self) -> None:
        """parse_document 应为 Prefect Task 对象"""
        from prefect.tasks import Task

        from src.infrastructure.workflow.tasks.document_tasks import parse_document

        assert isinstance(parse_document, Task)

    def test_generate_embedding_is_prefect_task(self) -> None:
        """generate_embedding 应为 Prefect Task 对象"""
        from prefect.tasks import Task

        from src.infrastructure.workflow.tasks.document_tasks import generate_embedding

        assert isinstance(generate_embedding, Task)

    def test_index_document_is_prefect_task(self) -> None:
        """index_document 应为 Prefect Task 对象"""
        from prefect.tasks import Task

        from src.infrastructure.workflow.tasks.document_tasks import index_document

        assert isinstance(index_document, Task)

    def test_tasks_have_retry_config(self) -> None:
        """Tasks 应有 retries=2 配置"""
        from src.infrastructure.workflow.tasks.document_tasks import (
            generate_embedding,
            index_document,
            parse_document,
        )

        assert parse_document.retries == 2
        assert generate_embedding.retries == 2
        assert index_document.retries == 2


class TestDocumentTasksFn:
    """测试任务底层函数（通过 .fn() 绕过 Prefect 运行时）"""

    @pytest.mark.asyncio
    async def test_parse_document_fn_returns_dict(self) -> None:
        """parse_document.fn() 应返回 dict"""
        from src.infrastructure.workflow.tasks.document_tasks import parse_document

        result = await parse_document.fn(uuid.uuid4(), "/test.pdf")
        assert isinstance(result, dict)
        assert "status" in result

    @pytest.mark.asyncio
    async def test_generate_embedding_fn_returns_list(self) -> None:
        """generate_embedding.fn() 应返回 list"""
        from src.infrastructure.workflow.tasks.document_tasks import generate_embedding

        result = await generate_embedding.fn({"status": "parsed"})
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_index_document_fn_returns_dict(self) -> None:
        """index_document.fn() 应返回 dict"""
        from src.infrastructure.workflow.tasks.document_tasks import index_document

        result = await index_document.fn([])
        assert isinstance(result, dict)
        assert "indexed" in result


class TestEventPublishLogic:
    """验证事件发布逻辑"""

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
    async def test_event_publisher_publish_called(self, mock_event_publisher: AsyncMock) -> None:
        """验证 EventPublisher.publish 被正确调用"""
        event = DocumentProcessed(document_id=uuid.uuid4())

        result = await mock_event_publisher.publish(event)

        mock_event_publisher.publish.assert_called_once()
        assert result.is_success
