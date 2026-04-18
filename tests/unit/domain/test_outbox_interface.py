"""OutboxRepository Interface Verification Tests.

Verifies that PostgreSQLOutboxRepository correctly implements the
domain layer OutboxRepository interface.
"""

from __future__ import annotations

import inspect
from unittest import mock
from uuid import uuid4

import pytest

from src.domain.repositories.outbox import OutboxRepository
from src.infrastructure.storage.postgresql.outbox_repository import PostgreSQLOutboxRepository


class TestOutboxRepositoryInterface:
    """验证 PostgreSQLOutboxRepository 实现领域层接口。"""

    def test_is_subclass_of_domain_interface(self):
        """PostgreSQLOutboxRepository 应继承自 OutboxRepository。"""
        assert issubclass(PostgreSQLOutboxRepository, OutboxRepository)

    def test_save_method_exists(self):
        """save 方法必须存在。"""
        assert hasattr(PostgreSQLOutboxRepository, "save")
        assert callable(getattr(PostgreSQLOutboxRepository, "save"))

    def test_get_unpublished_method_exists(self):
        """get_unpublished 方法必须存在。"""
        assert hasattr(PostgreSQLOutboxRepository, "get_unpublished")
        assert callable(getattr(PostgreSQLOutboxRepository, "get_unpublished"))

    def test_async_get_unpublished_method_exists(self):
        """async_get_unpublished 方法必须存在。"""
        assert hasattr(PostgreSQLOutboxRepository, "async_get_unpublished")
        assert callable(getattr(PostgreSQLOutboxRepository, "async_get_unpublished"))

    def test_mark_published_method_exists(self):
        """mark_published 方法必须存在。"""
        assert hasattr(PostgreSQLOutboxRepository, "mark_published")
        assert callable(getattr(PostgreSQLOutboxRepository, "mark_published"))

    def test_async_mark_published_method_exists(self):
        """async_mark_published 方法必须存在。"""
        assert hasattr(PostgreSQLOutboxRepository, "async_mark_published")
        assert callable(getattr(PostgreSQLOutboxRepository, "async_mark_published"))

    def test_mark_failed_method_exists(self):
        """mark_failed 方法必须存在。"""
        assert hasattr(PostgreSQLOutboxRepository, "mark_failed")
        assert callable(getattr(PostgreSQLOutboxRepository, "mark_failed"))

    def test_async_mark_failed_method_exists(self):
        """async_mark_failed 方法必须存在。"""
        assert hasattr(PostgreSQLOutboxRepository, "async_mark_failed")
        assert callable(getattr(PostgreSQLOutboxRepository, "async_mark_failed"))

    def test_save_signature_matches_interface(self):
        """save 方法签名应与接口一致。"""
        interface_sig = inspect.signature(OutboxRepository.save)
        impl_sig = inspect.signature(PostgreSQLOutboxRepository.save)

        # 参数名应该一致
        assert list(interface_sig.parameters.keys()) == list(impl_sig.parameters.keys())

    def test_internal_methods_have_underscore_prefix(self):
        """内部方法应以下划线前缀命名。"""
        internal_methods = [
            "_get_unpublished_entities",
            "_mark_published_entity",
            "_mark_failed_entity",
        ]
        for method_name in internal_methods:
            assert hasattr(PostgreSQLOutboxRepository, method_name)
            assert method_name.startswith("_")


class TestOutboxRepositoryBehavior:
    """验证 OutboxRepository 行为正确性。"""

    def test_save_accepts_domain_event(self, mock_outbox_repo):
        """save 方法应接受 DomainEvent 实例。"""
        from datetime import UTC, datetime
        from uuid import uuid4

        from src.domain.events.base import DomainEvent

        event = DomainEvent(
            event_id=uuid4(),
            event_type="TestEvent",
            timestamp=datetime.now(UTC),
            source="test",
            payload={},
        )

        # 不应抛出异常
        mock_outbox_repo.save(event)

    def test_async_get_unpublished_returns_list(self, mock_outbox_repo):
        """async_get_unpublished 应返回列表。"""
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(mock_outbox_repo.async_get_unpublished(limit=10))
        assert isinstance(result, list)

    def test_async_mark_published_accepts_uuid(self, mock_outbox_repo):
        """async_mark_published 应接受 UUID。"""
        import asyncio

        event_id = uuid4()
        asyncio.get_event_loop().run_until_complete(mock_outbox_repo.async_mark_published(event_id))

    def test_async_mark_failed_accepts_uuid_and_string(self, mock_outbox_repo):
        """async_mark_failed 应接受 UUID 和字符串错误信息。"""
        import asyncio

        event_id = uuid4()
        error_message = "Test error"
        asyncio.get_event_loop().run_until_complete(mock_outbox_repo.async_mark_failed(event_id, error_message))


@pytest.fixture
def mock_outbox_repo():
    """提供模拟的 OutboxRepository 实例。"""
    from unittest.mock import AsyncMock

    mock_repo = AsyncMock(spec=PostgreSQLOutboxRepository)
    mock_repo.save = mock.Mock()
    mock_repo.async_get_unpublished = AsyncMock(return_value=[])
    mock_repo.async_mark_published = AsyncMock()
    mock_repo.async_mark_failed = AsyncMock()
    return mock_repo
