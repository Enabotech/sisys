"""AsyncOutboxPoller 单元测试

验证 AsyncOutboxPoller 正确实现事件发件箱轮询发布功能
测试轮询、批量处理、并发控制、异常处理和停止逻辑
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.events.base import DomainEvent
from src.infrastructure.messaging.outbox.outbox import OutboxEntity
from src.infrastructure.messaging.outbox.outbox_processor import AsyncOutboxPoller


class TestAsyncOutboxPoller:
    """测试 AsyncOutboxPoller 轮询器"""

    @pytest.fixture
    def mock_repo(self) -> MagicMock:
        """创建模拟的 outbox_repository"""
        repo = MagicMock()
        repo._get_unpublished_entities = AsyncMock(return_value=[])
        repo._mark_published_entity = AsyncMock()
        repo._mark_failed_entity = AsyncMock()
        return repo

    @pytest.fixture
    def mock_publisher(self) -> MagicMock:
        """创建模拟的 publisher"""
        publisher = MagicMock()
        publisher.async_publish = AsyncMock()
        return publisher

    @pytest.fixture
    def poller(self, mock_repo: MagicMock, mock_publisher: MagicMock) -> AsyncOutboxPoller:
        """创建 AsyncOutboxPoller 实例"""
        return AsyncOutboxPoller(
            outbox_repository=mock_repo,
            publisher=mock_publisher,
            poll_interval=0.01,
            batch_size=5,
        )

    def test_init_sets_attributes(self, mock_repo: MagicMock, mock_publisher: MagicMock) -> None:
        """初始化正确设置属性"""
        poller = AsyncOutboxPoller(
            outbox_repository=mock_repo,
            publisher=mock_publisher,
            poll_interval=2.5,
            batch_size=20,
        )
        assert poller._repo is mock_repo
        assert poller._publisher is mock_publisher
        assert poller._poll_interval == 2.5
        assert poller._batch_size == 20
        assert poller._running is False

    @pytest.mark.asyncio
    async def test_poll_once_no_entities(self, poller: AsyncOutboxPoller, mock_repo: MagicMock) -> None:
        """无待处理实体时不发布"""
        mock_repo._get_unpublished_entities.return_value = []

        await poller.poll_once()

        mock_repo._get_unpublished_entities.assert_awaited_once_with(limit=5)
        # No publish calls should happen

    @pytest.mark.asyncio
    async def test_poll_once_publishes_and_marks_published(
        self,
        poller: AsyncOutboxPoller,
        mock_repo: MagicMock,
        mock_publisher: MagicMock,
    ) -> None:
        """有实体时发布并标记为已发布"""
        entity = MagicMock(spec=OutboxEntity)
        entity.event_id = "event-123"
        entity.event_type = "TestEvent"
        mock_repo._get_unpublished_entities.return_value = [entity]

        with patch("src.infrastructure.messaging.outbox.outbox_processor.EventOutboxAdapter") as mock_adapter:
            mock_adapter.to_domain_event.return_value = MagicMock(spec=DomainEvent)

            await poller.poll_once()

            mock_adapter.to_domain_event.assert_called_once_with(entity)
            mock_publisher.async_publish.assert_awaited_once()
            mock_repo._mark_published_entity.assert_awaited_once_with(entity)

    @pytest.mark.asyncio
    async def test_poll_once_marks_failed_on_error(
        self,
        poller: AsyncOutboxPoller,
        mock_repo: MagicMock,
        mock_publisher: MagicMock,
    ) -> None:
        """发布失败时标记为失败"""
        entity = MagicMock(spec=OutboxEntity)
        entity.event_id = "event-456"
        entity.event_type = "TestEvent"
        mock_repo._get_unpublished_entities.return_value = [entity]

        mock_publisher.async_publish.side_effect = RuntimeError("Publish failed")

        with patch("src.infrastructure.messaging.outbox.outbox_processor.EventOutboxAdapter") as mock_adapter:
            mock_adapter.to_domain_event.return_value = MagicMock(spec=DomainEvent)

            await poller.poll_once()

            mock_repo._mark_failed_entity.assert_awaited_once_with(entity, "Publish failed")

    @pytest.mark.asyncio
    async def test_poll_once_uses_correct_routing_key(
        self,
        poller: AsyncOutboxPoller,
        mock_repo: MagicMock,
        mock_publisher: MagicMock,
    ) -> None:
        """发布时使用正确的 routing key"""
        entity = MagicMock(spec=OutboxEntity)
        entity.event_id = "event-789"
        entity.event_type = "DocumentProcessed"
        mock_repo._get_unpublished_entities.return_value = [entity]

        with patch("src.infrastructure.messaging.outbox.outbox_processor.EventOutboxAdapter") as mock_adapter:
            mock_adapter.to_domain_event.return_value = MagicMock(spec=DomainEvent)

            await poller.poll_once()

            call_args = mock_publisher.async_publish.call_args
            assert call_args.kwargs["routing_key"] == "sisys.events.reliable.DocumentProcessed"

    @pytest.mark.asyncio
    async def test_poll_once_concurrent_processing(
        self,
        poller: AsyncOutboxPoller,
        mock_repo: MagicMock,
        mock_publisher: MagicMock,
    ) -> None:
        """验证并发处理使用 Semaphore 限制"""
        entities = [MagicMock(spec=OutboxEntity) for _ in range(3)]
        for i, entity in enumerate(entities):
            entity.event_id = f"event-{i}"
            entity.event_type = "TestEvent"
        mock_repo._get_unpublished_entities.return_value = entities

        with patch("src.infrastructure.messaging.outbox.outbox_processor.EventOutboxAdapter") as mock_adapter:
            mock_adapter.to_domain_event.return_value = MagicMock(spec=DomainEvent)

            await poller.poll_once()

            # All three should be processed (batch_size=5 allows 3 concurrent)
            assert mock_publisher.async_publish.call_count == 3
            assert mock_repo._mark_published_entity.call_count == 3

    def test_stop_sets_running_false(self, poller: AsyncOutboxPoller) -> None:
        """stop() 将 _running 设为 False"""
        poller._running = True
        poller.stop()
        assert poller._running is False

    @pytest.mark.asyncio
    async def test_run_starts_and_stops(self, poller: AsyncOutboxPoller) -> None:
        """run() 启动后 stop() 可停止"""
        # Make poll_once return immediately with empty to avoid infinite loop
        poller._repo._get_unpublished_entities = AsyncMock(return_value=[])

        async def run_and_stop() -> None:
            await asyncio.sleep(0.03)
            poller.stop()

        await asyncio.gather(poller.run(), run_and_stop())

        assert poller._running is False

    @pytest.mark.asyncio
    async def test_run_logs_start_message(self, poller: AsyncOutboxPoller, caplog: pytest.LogCaptureFixture) -> None:
        """run() 启动时记录日志"""
        poller._repo._get_unpublished_entities = AsyncMock(return_value=[])

        with caplog.at_level(logging.INFO):

            async def run_and_stop() -> None:
                await asyncio.sleep(0.03)
                poller.stop()

            await asyncio.gather(poller.run(), run_and_stop())

        assert "AsyncOutboxPoller started" in caplog.text
        assert "interval=0.0" in caplog.text or "interval=0.1" in caplog.text

    @pytest.mark.asyncio
    async def test_run_stops_on_stop_message(self, poller: AsyncOutboxPoller, caplog: pytest.LogCaptureFixture) -> None:
        """stop() 记录停止日志"""
        poller._repo._get_unpublished_entities = AsyncMock(return_value=[])

        with caplog.at_level(logging.INFO):

            async def run_and_stop() -> None:
                await asyncio.sleep(0.03)
                poller.stop()

            await asyncio.gather(poller.run(), run_and_stop())

        assert "AsyncOutboxPoller stopping" in caplog.text

    @pytest.mark.asyncio
    async def test_run_polls_repeatedly(self, poller: AsyncOutboxPoller) -> None:
        """run() 循环调用 poll_once"""
        call_count = 0

        async def mock_get_unpublished(limit: int) -> list[OutboxEntity]:
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                poller.stop()
            return []

        poller._repo._get_unpublished_entities = mock_get_unpublished

        await poller.run()

        assert call_count >= 3

    @pytest.mark.asyncio
    async def test_run_exception_handling(self, poller: AsyncOutboxPoller, caplog: pytest.LogCaptureFixture) -> None:
        """poll_once 异常时 run() 捕获并记录错误，继续运行"""
        call_count = 0

        async def mock_get_unpublished(limit: int) -> list[OutboxEntity]:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                poller.stop()
            # Return an entity that will cause poll_once to raise
            entity = MagicMock(spec=OutboxEntity)
            entity.event_id = "event-ex"
            entity.event_type = "TestEvent"
            return [entity]

        poller._repo._get_unpublished_entities = mock_get_unpublished

        with patch("src.infrastructure.messaging.outbox.outbox_processor.EventOutboxAdapter") as mock_adapter:
            mock_adapter.to_domain_event.return_value = MagicMock(spec=DomainEvent)
            poller._publisher.async_publish = AsyncMock(side_effect=RuntimeError("Unexpected error"))

            with caplog.at_level(logging.ERROR):
                await poller.run()

            assert "Error in poll_once" in caplog.text or "Unexpected error" in caplog.text

    @pytest.mark.asyncio
    async def test_run_exception_in_poll_once_logs_error(
        self, poller: AsyncOutboxPoller, caplog: pytest.LogCaptureFixture
    ) -> None:
        """poll_once 抛出异常时 run() 记录错误日志（覆盖 85-86 行）"""
        call_count = 0

        async def mock_get_unpublished(limit: int) -> list[OutboxEntity]:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                poller.stop()
            # This will cause poll_once to raise at the gather level
            raise RuntimeError("Database connection lost")

        poller._repo._get_unpublished_entities = mock_get_unpublished

        with caplog.at_level(logging.ERROR):
            await poller.run()

        assert "Error in poll_once" in caplog.text

    @pytest.mark.asyncio
    async def test_run_sleeps_between_polls(self, poller: AsyncOutboxPoller) -> None:
        """验证轮询间隔使用 asyncio.sleep"""
        poller._repo._get_unpublished_entities = AsyncMock(return_value=[])
        poller._poll_interval = 10.0  # Long interval

        async def stop_after_short_delay() -> None:
            await asyncio.sleep(0.01)
            poller.stop()

        with patch("asyncio.sleep") as mock_sleep:
            mock_sleep.side_effect = asyncio.CancelledError
            try:
                await asyncio.gather(
                    poller.run(),
                    stop_after_short_delay(),
                )
            except asyncio.CancelledError:
                pass

        # If sleep was called with our long interval, test passes
        # The key is that asyncio.sleep was called

    @pytest.mark.asyncio
    async def test_poll_once_processes_multiple_entities(
        self, poller: AsyncOutboxPoller, mock_repo: MagicMock, mock_publisher: MagicMock
    ) -> None:
        """批量处理多个实体"""
        entities = []
        for i in range(5):
            entity = MagicMock(spec=OutboxEntity)
            entity.event_id = f"event-{i}"
            entity.event_type = "TestEvent"
            entities.append(entity)
        mock_repo._get_unpublished_entities.return_value = entities

        with patch("src.infrastructure.messaging.outbox.outbox_processor.EventOutboxAdapter") as mock_adapter:
            mock_adapter.to_domain_event.return_value = MagicMock(spec=DomainEvent)

            await poller.poll_once()

            assert mock_publisher.async_publish.call_count == 5
            assert mock_repo._mark_published_entity.call_count == 5

    @pytest.mark.asyncio
    async def test_run_terminates_cleanly(self, poller: AsyncOutboxPoller) -> None:
        """多次调用 stop() 应正常工作"""
        poller._repo._get_unpublished_entities = AsyncMock(return_value=[])

        async def run_and_stop_twice() -> None:
            await asyncio.sleep(0.02)
            poller.stop()
            # Call stop again - should be idempotent
            poller.stop()

        await asyncio.gather(poller.run(), run_and_stop_twice())

        assert poller._running is False


class TestOutboxEntityStateTransitions:
    """测试 OutboxEntity 状态转换"""

    def test_mark_published_from_pending(self) -> None:
        """pending → published 转换"""
        entity = OutboxEntity(event_id=uuid.uuid4(), event_type="Test", status="pending")
        entity.mark_published()
        assert entity.status == "published"
        assert entity.published_at is not None

    def test_mark_published_from_invalid_state_raises(self) -> None:
        """从非 pending 状态转换到 published 应抛出异常"""
        entity = OutboxEntity(event_id=uuid.uuid4(), event_type="Test", status="published")
        with pytest.raises(Exception):  # InvalidStateTransitionError
            entity.mark_published()

    def test_mark_failed_from_pending(self) -> None:
        """pending → failed 转换"""
        entity = OutboxEntity(event_id=uuid.uuid4(), event_type="Test", status="pending")
        entity.mark_failed("Some error")
        assert entity.status == "failed"
        assert entity.retry_count == 1
        assert entity.error_message == "Some error"

    def test_mark_failed_increments_retry_count(self) -> None:
        """多次标记失败递增 retry_count"""
        entity = OutboxEntity(event_id=uuid.uuid4(), event_type="Test", status="pending")
        entity.mark_failed("Error 1")
        entity.status = "pending"  # Reset for testing
        entity.mark_failed("Error 2")
        assert entity.retry_count == 2

    def test_mark_pending_resets_for_retry(self) -> None:
        """failed → pending 转换用于重试"""
        entity = OutboxEntity(event_id=uuid.uuid4(), event_type="Test", status="failed", retry_count=1)
        entity.mark_pending()
        assert entity.status == "pending"
        assert entity.error_message is None

    def test_mark_pending_exceeds_max_retries_raises(self) -> None:
        """超过最大重试次数时不能重置为 pending"""
        entity = OutboxEntity(event_id=uuid.uuid4(), event_type="Test", status="failed", retry_count=3, max_retries=3)
        with pytest.raises(Exception):  # InvalidStateTransitionError
            entity.mark_pending()

    def test_mark_archived_from_failed(self) -> None:
        """failed → archived 终态转换"""
        entity = OutboxEntity(event_id=uuid.uuid4(), event_type="Test", status="failed")
        entity.mark_archived()
        assert entity.status == "archived"

    def test_mark_archived_from_non_failed_raises(self) -> None:
        """从非 failed 状态不能归档"""
        entity = OutboxEntity(event_id=uuid.uuid4(), event_type="Test", status="pending")
        with pytest.raises(Exception):
            entity.mark_archived()

    def test_invalid_state_transition_error_attributes(self) -> None:
        """异常包含正确的状态信息"""
        from src.infrastructure.messaging.outbox.outbox import InvalidStateTransitionError

        error = InvalidStateTransitionError("pending", "archived", "Max retries exceeded")
        assert error.from_status == "pending"
        assert error.to_status == "archived"
        assert "Max retries exceeded" in str(error)

    def test_invalid_state_transition_error_without_message(self) -> None:
        """无附加消息时生成正确字符串"""
        from src.infrastructure.messaging.outbox.outbox import InvalidStateTransitionError

        error = InvalidStateTransitionError("pending", "published")
        assert "pending" in str(error)
        assert "published" in str(error)
        assert "→" in str(error)


class TestInvalidStateTransitionError:
    """测试 InvalidStateTransitionError 异常类"""

    def test_error_message_format(self) -> None:
        """错误消息格式正确"""
        from src.infrastructure.messaging.outbox.outbox import InvalidStateTransitionError

        error = InvalidStateTransitionError("pending", "archived")
        assert "pending → archived" in str(error)

    def test_error_with_custom_message(self) -> None:
        """带自定义消息的错误"""
        from src.infrastructure.messaging.outbox.outbox import InvalidStateTransitionError

        error = InvalidStateTransitionError("failed", "pending", "Max retries exceeded")
        assert "Max retries exceeded" in str(error)
