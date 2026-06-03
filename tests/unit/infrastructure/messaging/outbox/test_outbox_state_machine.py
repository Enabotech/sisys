"""Outbox 状态机修复测试

验证 AC-4: Outbox archived 状态修复 + 状态机修复
对应 Task 4 的 TDD 红色测试
"""

from __future__ import annotations

from dataclasses import field
from unittest import mock
from uuid import uuid4

import pytest

from src.domain.events.base import DomainEvent
from src.domain.exceptions import InvalidStateTransitionError
from src.infrastructure.messaging.outbox.inmemory_outbox import InMemoryOutboxRepository
from src.infrastructure.messaging.outbox.outbox import OutboxEntity


class _TestEventForOutbox(DomainEvent):
    """Test event for outbox testing."""

    event_type: str = field(default="TestEventForOutbox", init=False)


class TestInMemoryOutboxStateTransition:
    """验证 InMemoryOutboxRepository 使用状态机方法而非直接赋值"""

    @pytest.fixture
    def repository(self) -> InMemoryOutboxRepository:
        """创建 InMemoryOutboxRepository 实例"""
        return InMemoryOutboxRepository()

    async def test_mark_published_calls_entity_method(self, repository: InMemoryOutboxRepository) -> None:
        """mark_published() 应调用 entity.mark_published() 而非直接赋值"""
        entity = OutboxEntity(event_id=uuid4(), event_type="test", payload={}, status="pending")
        repository._entities.append(entity)

        with mock.patch.object(entity, "mark_published", wraps=entity.mark_published) as mock_mark:
            await repository.mark_published(entity.event_id)

            mock_mark.assert_called_once()

    async def test_mark_published_raises_on_invalid_state(self, repository: InMemoryOutboxRepository) -> None:
        """从非 pending 状态调用 mark_published 应抛出异常"""
        entity = OutboxEntity(event_id=uuid4(), event_type="test", payload={}, status="failed")
        repository._entities.append(entity)

        with pytest.raises(InvalidStateTransitionError):
            await repository.mark_published(entity.event_id)

    async def test_mark_failed_calls_entity_method(self, repository: InMemoryOutboxRepository) -> None:
        """mark_failed() 应调用 entity.mark_failed() 而非直接赋值"""
        entity = OutboxEntity(event_id=uuid4(), event_type="test", payload={}, status="pending")
        repository._entities.append(entity)

        with mock.patch.object(entity, "mark_failed", wraps=entity.mark_failed) as mock_mark:
            await repository.mark_failed(entity.event_id, "test error")

            mock_mark.assert_called_once_with("test error")

    async def test_mark_failed_raises_on_invalid_state(self, repository: InMemoryOutboxRepository) -> None:
        """从 published 状态调用 mark_failed 应抛出异常"""
        entity = OutboxEntity(event_id=uuid4(), event_type="test", payload={}, status="published")
        repository._entities.append(entity)

        with pytest.raises(InvalidStateTransitionError):
            await repository.mark_failed(entity.event_id, "test error")

    async def test_mark_failed_allows_from_failed_state(self, repository: InMemoryOutboxRepository) -> None:
        """mark_failed() 应允许从 failed 状态再次调用（递增 retry_count）"""
        entity = OutboxEntity(event_id=uuid4(), event_type="test", payload={}, status="failed", retry_count=1)
        repository._entities.append(entity)

        await repository.mark_failed(entity.event_id, "retry error")

        assert entity.retry_count == 2
        assert entity.error_message == "retry error"


class TestOutboxEntityArchivedState:
    """验证 OutboxEntity archived 状态"""

    def test_mark_archived_from_failed(self) -> None:
        """从 failed 状态可归档"""
        entity = OutboxEntity(event_id=uuid4(), event_type="test", payload={}, status="failed")

        entity.mark_archived()

        assert entity.status == "archived"

    def test_mark_archived_raises_from_pending(self) -> None:
        """从 pending 状态不可归档"""
        entity = OutboxEntity(event_id=uuid4(), event_type="test", payload={}, status="pending")

        with pytest.raises(InvalidStateTransitionError):
            entity.mark_archived()

    def test_mark_archived_raises_from_published(self) -> None:
        """从 published 状态不可归档"""
        entity = OutboxEntity(event_id=uuid4(), event_type="test", payload={}, status="published")

        with pytest.raises(InvalidStateTransitionError):
            entity.mark_archived()


class TestPostgreSQLOutboxStateTransition:
    """验证 PostgreSQLOutboxRepository 状态转换校验"""

    async def test_mark_published_validates_pending_status(self) -> None:
        """mark_published() 仅允许从 pending 状态转换"""
        from unittest import mock

        from src.infrastructure.messaging.outbox.outbox_repository import (
            PostgreSQLOutboxRepository,
        )
        from src.infrastructure.storage.postgresql.session_context import (
            reset_session,
            set_session,
        )

        mock_session = mock.AsyncMock()
        mock_session.add = mock.Mock()  # AsyncSession.add() 是同步方法
        token = set_session(mock_session)

        try:
            repository = PostgreSQLOutboxRepository()

            from src.infrastructure.storage.postgresql.models import OutboxModel

            mock_model = mock.MagicMock(spec=OutboxModel)
            mock_model.status = "failed"
            mock_model.event_id = uuid4()

            mock_result = mock.MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_model
            mock_session.execute.return_value = mock_result

            with pytest.raises(InvalidStateTransitionError):
                await repository.mark_published(mock_model.event_id)

            mock_session.commit.assert_not_awaited()
        finally:
            reset_session(token)

    async def test_mark_failed_validates_allowed_status(self) -> None:
        """mark_failed() 仅允许从 pending/failed 状态转换"""
        from unittest import mock

        from src.infrastructure.messaging.outbox.outbox_repository import (
            PostgreSQLOutboxRepository,
        )
        from src.infrastructure.storage.postgresql.session_context import (
            reset_session,
            set_session,
        )

        mock_session = mock.AsyncMock()
        mock_session.add = mock.Mock()  # AsyncSession.add() 是同步方法
        token = set_session(mock_session)

        try:
            repository = PostgreSQLOutboxRepository()

            from src.infrastructure.storage.postgresql.models import OutboxModel

            mock_model = mock.MagicMock(spec=OutboxModel)
            mock_model.status = "published"
            mock_model.event_id = uuid4()

            mock_result = mock.MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_model
            mock_session.execute.return_value = mock_result

            with pytest.raises(InvalidStateTransitionError):
                await repository.mark_failed(mock_model.event_id, "test error")

            mock_session.commit.assert_not_awaited()
        finally:
            reset_session(token)
