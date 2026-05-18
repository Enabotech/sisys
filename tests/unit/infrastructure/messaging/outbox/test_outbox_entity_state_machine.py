"""OutboxEntity 状态机与 OutboxRepository 接口协议测试

验证 OutboxEntity 状态转换规则、InvalidStateTransitionError 异常、
以及 OutboxRepository 接口契约

Reference: src/infrastructure/messaging/outbox/outbox.py
           src/domain/ports/outbox.py
"""

from __future__ import annotations

import pytest

from src.domain.ports.outbox import OutboxRepository
from src.infrastructure.messaging.outbox.outbox import (
    InvalidStateTransitionError,
    OutboxEntity,
)


class TestOutboxEntityStateTransitions:
    """验证 OutboxEntity 状态机转换规则"""

    def test_initial_state_is_pending(self) -> None:
        """初始状态必须是 pending"""
        entity = OutboxEntity()
        assert entity.status == "pending"

    def test_pending_to_published(self) -> None:
        """pending → published 转换有效"""
        entity = OutboxEntity()
        entity.mark_published()
        assert entity.status == "published"
        assert entity.published_at is not None

    def test_pending_to_failed(self) -> None:
        """pending → failed 转换有效"""
        entity = OutboxEntity()
        entity.mark_failed("Test error")
        assert entity.status == "failed"
        assert entity.error_message == "Test error"
        assert entity.retry_count == 1

    def test_failed_to_pending_retry(self) -> None:
        """failed → pending（重试）转换有效"""
        entity = OutboxEntity()
        entity.mark_failed("First error")
        assert entity.retry_count == 1

        entity.mark_pending()  # 重试
        assert entity.status == "pending"
        assert entity.error_message is None
        assert entity.retry_count == 1  # 重试不改变 count

    def test_failed_to_archived(self) -> None:
        """failed → archived 转换有效"""
        entity = OutboxEntity()
        entity.mark_failed("Final error")
        entity.mark_archived()
        assert entity.status == "archived"

    def test_pending_cannot_go_to_pending(self) -> None:
        """pending 不能再转为 pending（无效转换）"""
        entity = OutboxEntity()
        with pytest.raises(InvalidStateTransitionError) as exc_info:
            entity.mark_pending()
        assert "pending → pending" in str(exc_info.value)

    def test_published_cannot_transition(self) -> None:
        """published 是终态，不能再转换"""
        entity = OutboxEntity()
        entity.mark_published()

        with pytest.raises(InvalidStateTransitionError):
            entity.mark_published()

        with pytest.raises(InvalidStateTransitionError):
            entity.mark_failed("error")

        with pytest.raises(InvalidStateTransitionError):
            entity.mark_pending()

        with pytest.raises(InvalidStateTransitionError):
            entity.mark_archived()

    def test_archived_cannot_transition(self) -> None:
        """archived 是终态，不能再转换"""
        entity = OutboxEntity()
        entity.mark_failed("error")
        entity.mark_archived()

        with pytest.raises(InvalidStateTransitionError):
            entity.mark_published()

        with pytest.raises(InvalidStateTransitionError):
            entity.mark_failed("error2")

        with pytest.raises(InvalidStateTransitionError):
            entity.mark_pending()

    def test_max_retries_exceeded_prevents_pending(self) -> None:
        """超过最大重试次数后，不能再 mark_pending"""
        entity = OutboxEntity(max_retries=3)

        # 前两次失败后可以重试
        for i in range(2):
            entity.mark_failed(f"error {i}")
            assert entity.status == "failed"
            entity.mark_pending()  # 重试成功
            assert entity.status == "pending"

        # 第三次失败后，不能再重试
        entity.mark_failed("third error")
        assert entity.retry_count == 3
        with pytest.raises(InvalidStateTransitionError) as exc_info:
            entity.mark_pending()
        assert "Max retries" in str(exc_info.value)


class TestOutboxEntityInvalidStateTransitionError:
    """验证 InvalidStateTransitionError 异常信息"""

    def test_error_message_format(self) -> None:
        """异常消息格式：from → to"""
        error = InvalidStateTransitionError("pending", "archived")
        assert "pending → archived" in str(error)
        assert error.from_status == "pending"
        assert error.to_status == "archived"

    def test_error_with_custom_message(self) -> None:
        """带自定义消息的异常"""
        error = InvalidStateTransitionError(
            "failed",
            "pending",
            "Max retries (3) exceeded",
        )
        assert "failed → pending" in str(error)
        assert "Max retries" in str(error)


class TestOutboxRepositoryMockBehavior:
    """Mock behavior tests — verify OutboxRepository Protocol contract via spec约束."""

    @pytest.mark.asyncio
    async def test_mock_save_verified(self):
        """Mock save should be verifiable."""
        from unittest.mock import AsyncMock

        mock = AsyncMock(spec=OutboxRepository)

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
        await mock.save(event)
        mock.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_mock_get_unpublished_verified(self):
        """Mock get_unpublished should be verifiable."""
        from unittest.mock import AsyncMock

        mock = AsyncMock(spec=OutboxRepository)
        mock.get_unpublished.return_value = []

        result = await mock.get_unpublished(10)
        assert result == []
        mock.get_unpublished.assert_called_once_with(10)

    @pytest.mark.asyncio
    async def test_mock_mark_published_verified(self):
        """Mock mark_published should be verifiable."""
        from unittest.mock import AsyncMock
        from uuid import uuid4

        mock = AsyncMock(spec=OutboxRepository)
        mock.mark_published.return_value = None

        event_id = uuid4()
        await mock.mark_published(event_id)
        mock.mark_published.assert_called_once_with(event_id)

    @pytest.mark.asyncio
    async def test_mock_mark_failed_verified(self):
        """Mock mark_failed should be verifiable."""
        from unittest.mock import AsyncMock
        from uuid import uuid4

        mock = AsyncMock(spec=OutboxRepository)
        mock.mark_failed.return_value = None

        event_id = uuid4()
        await mock.mark_failed(event_id, "error message")
        mock.mark_failed.assert_called_once_with(event_id, "error message")


class TestOutboxEntityFieldDefaults:
    """验证 OutboxEntity 字段默认值"""

    def test_default_values(self) -> None:
        """验证所有字段的默认值"""
        entity = OutboxEntity()
        assert entity.id == 0
        assert entity.status == "pending"
        assert entity.retry_count == 0
        assert entity.max_retries == 3
        assert entity.error_message is None
        assert entity.published_at is None
        assert entity.created_at is not None

    def test_custom_field_values(self) -> None:
        """验证自定义字段值"""
        from uuid import uuid4

        eid = uuid4()
        entity = OutboxEntity(
            event_id=eid,
            event_type="TestEvent",
            payload={"key": "value"},
            status="failed",
            retry_count=2,
            max_retries=5,
            error_message="test error",
        )
        # id 是 init=False，不能通过构造函数设置
        assert entity.event_id == eid
        assert entity.event_type == "TestEvent"
        assert entity.payload == {"key": "value"}
        assert entity.status == "failed"
        assert entity.retry_count == 2
        assert entity.max_retries == 5
        assert entity.error_message == "test error"

    def test_entity_fields_are_mutable(self) -> None:
        """验证 OutboxEntity 字段可修改（非 frozen）"""
        entity = OutboxEntity()
        entity.id = 100
        entity.status = "published"
        entity.retry_count = 5
        assert entity.id == 100
        assert entity.status == "published"
        assert entity.retry_count == 5
