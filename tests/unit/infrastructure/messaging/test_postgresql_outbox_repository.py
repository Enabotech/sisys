"""PostgreSQLOutboxRepository 单元测试。"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest import mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.events.base import DomainEvent
from src.infrastructure.messaging.outbox.outbox_repository import PostgreSQLOutboxRepository


@pytest.fixture
def mock_session():
    session = mock.AsyncMock(spec=AsyncSession)
    # add 是同步方法（不执行 I/O）
    session.add = mock.Mock()
    return session


@pytest.fixture
def repository(mock_session):
    return PostgreSQLOutboxRepository(mock_session)


class TestPostgreSQLOutboxRepository:
    """PostgreSQLOutboxRepository 测试。"""

    @pytest.mark.asyncio
    async def test_save(self, repository, mock_session):
        """测试保存事件。"""
        event = DomainEvent(
            event_id=uuid4(),
            event_type="TestEvent",
            timestamp=datetime.now(UTC),
            source="test",
            payload={"key": "value"},
        )

        repository.save(event)

        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_get_unpublished(self, repository, mock_session):
        """测试异步获取未发布事件。"""
        from src.infrastructure.messaging.adapters.event_outbox_adapter import EventRegistry

        # 注册测试事件类型
        EventRegistry.register("TestEvent", DomainEvent)

        model1 = mock.Mock()
        model1.event_type = "TestEvent"
        model1.payload = {
            "event_id": str(uuid4()),
            "event_type": "TestEvent",
            "timestamp": datetime.now(UTC).isoformat(),
            "source": "test",
            "payload": {},
        }
        model2 = mock.Mock()
        model2.event_type = "TestEvent"
        model2.payload = {
            "event_id": str(uuid4()),
            "event_type": "TestEvent",
            "timestamp": datetime.now(UTC).isoformat(),
            "source": "test",
            "payload": {},
        }
        models = [model1, model2]
        mock_scalars = mock.Mock()
        mock_scalars.all.return_value = models
        mock_result = mock.Mock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await repository.async_get_unpublished(limit=10)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_async_mark_published(self, repository, mock_session):
        """测试异步标记已发布。"""
        event_id = uuid4()
        mock_model = mock.Mock()
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = mock_model
        mock_session.execute.return_value = mock_result

        await repository.async_mark_published(event_id)

        assert mock_model.status == "published"
        assert mock_model.published_at is not None

    @pytest.mark.asyncio
    async def test_async_mark_failed(self, repository, mock_session):
        """测试异步标记失败。"""
        event_id = uuid4()
        mock_model = mock.Mock()
        mock_model.retry_count = 0
        mock_result = mock.Mock()
        mock_result.scalar_one_or_none.return_value = mock_model
        mock_session.execute.return_value = mock_result

        await repository.async_mark_failed(event_id, "Test error")

        assert mock_model.status == "failed"
        assert mock_model.retry_count == 1
        assert mock_model.error_message == "Test error"

    @pytest.mark.asyncio
    async def test_internal_get_unpublished(self, repository, mock_session):
        """测试内部方法获取未发布实体。"""
        models = [mock.Mock(), mock.Mock()]
        mock_scalars = mock.Mock()
        mock_scalars.all.return_value = models
        mock_result = mock.Mock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await repository._get_unpublished_entities(limit=10)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_internal_mark_published_entity(self, repository, mock_session):
        """测试内部方法标记已发布实体。"""
        model = mock.Mock()

        await repository._mark_published_entity(model)

        assert model.status == "published"
        assert model.published_at is not None

    @pytest.mark.asyncio
    async def test_internal_mark_failed_entity(self, repository, mock_session):
        """测试内部方法标记失败实体。"""
        model = mock.Mock()
        model.retry_count = 0

        await repository._mark_failed_entity(model, "Error")

        assert model.status == "failed"
        assert model.retry_count == 1
        assert model.error_message == "Error"
