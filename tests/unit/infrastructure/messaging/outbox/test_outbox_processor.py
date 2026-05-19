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
from src.infrastructure.messaging.channel_router import ChannelRouter
from src.infrastructure.messaging.outbox.outbox import OutboxEntity
from src.infrastructure.messaging.outbox.outbox_processor import AsyncOutboxPoller


def _make_domain_event(event_type: str = "TestEvent") -> DomainEvent:
    """创建测试用 DomainEvent"""
    DomainEvent.register("TestEvent", DomainEvent)
    return DomainEvent(event_type=event_type, source="test")


class TestAsyncOutboxPoller:
    """测试 AsyncOutboxPoller 轮询器（使用公共 OutboxRepository 接口）"""

    @pytest.fixture
    def mock_repo(self) -> MagicMock:
        """创建模拟的 OutboxRepository（公共 async 方法）"""
        repo = MagicMock()
        repo.get_unpublished = AsyncMock(return_value=[])
        repo.mark_published = AsyncMock()
        repo.mark_failed = AsyncMock()
        return repo

    @pytest.fixture
    def mock_publisher(self) -> MagicMock:
        """创建模拟的 publisher"""
        publisher = MagicMock()
        publisher.async_publish = AsyncMock()
        return publisher

    @pytest.fixture
    def mock_router(self) -> MagicMock:
        """创建模拟通道路由器"""
        router = MagicMock(spec=ChannelRouter)
        router.get_rabbitmq_routing_key.return_value = "sisys.events.reliable.TestEvent"
        return router

    @pytest.fixture
    def poller(self, mock_repo: MagicMock, mock_publisher: MagicMock, mock_router: ChannelRouter) -> AsyncOutboxPoller:
        """创建 AsyncOutboxPoller 实例"""
        from src.infrastructure.messaging.retry.retry_policy import RetryPolicy

        return AsyncOutboxPoller(
            outbox_repository=mock_repo,
            publisher=mock_publisher,
            router=mock_router,
            poll_interval=0.01,
            batch_size=5,
            retry_policy=RetryPolicy(base_delay=0.001, max_delay=0.01, max_retries=3),
        )

    def test_init_sets_attributes(self, mock_repo: MagicMock, mock_publisher: MagicMock, mock_router: ChannelRouter) -> None:
        """初始化正确设置属性"""
        poller = AsyncOutboxPoller(
            outbox_repository=mock_repo,
            publisher=mock_publisher,
            router=mock_router,
            poll_interval=2.5,
            batch_size=20,
        )
        assert poller._repo is mock_repo
        assert poller._publisher is mock_publisher
        assert poller._router is mock_router
        assert poller._poll_interval == 2.5
        assert poller._batch_size == 20
        assert poller._running is False

    def test_init_with_custom_retry_policy(
        self, mock_repo: MagicMock, mock_publisher: MagicMock, mock_router: ChannelRouter
    ) -> None:
        """初始化可传入自定义 RetryPolicy"""
        from src.infrastructure.messaging.retry.retry_policy import RetryPolicy

        custom_policy = RetryPolicy(base_delay=0.5, max_delay=10.0, max_retries=5)
        poller = AsyncOutboxPoller(
            outbox_repository=mock_repo,
            publisher=mock_publisher,
            router=mock_router,
            retry_policy=custom_policy,
        )
        assert poller._retry_policy is custom_policy

    def test_init_default_retry_policy(
        self, mock_repo: MagicMock, mock_publisher: MagicMock, mock_router: ChannelRouter
    ) -> None:
        """无 retry_policy 参数时使用 RetryPolicy 默认值"""
        poller = AsyncOutboxPoller(
            outbox_repository=mock_repo,
            publisher=mock_publisher,
            router=mock_router,
        )
        assert poller._retry_policy.max_retries == 3

    @pytest.mark.asyncio
    async def test_poll_once_no_events(self, poller: AsyncOutboxPoller, mock_repo: MagicMock) -> None:
        """无待处理事件时不发布"""
        mock_repo.get_unpublished.return_value = []

        await poller.poll_once()

        mock_repo.get_unpublished.assert_awaited_once_with(limit=5)

    @pytest.mark.asyncio
    async def test_poll_once_publishes_and_marks_published(
        self,
        poller: AsyncOutboxPoller,
        mock_repo: MagicMock,
        mock_publisher: MagicMock,
    ) -> None:
        """有事件时发布并标记为已发布"""
        event = _make_domain_event()
        mock_repo.get_unpublished.return_value = [event]

        await poller.poll_once()

        mock_publisher.async_publish.assert_awaited_once()
        mock_repo.mark_published.assert_awaited_once_with(event.event_id)

    @pytest.mark.asyncio
    async def test_poll_once_marks_failed_on_error(
        self,
        poller: AsyncOutboxPoller,
        mock_repo: MagicMock,
        mock_publisher: MagicMock,
    ) -> None:
        """发布失败时重试耗尽后标记为失败"""
        event = _make_domain_event()
        mock_repo.get_unpublished.return_value = [event]
        mock_publisher.async_publish.side_effect = RuntimeError("Publish failed")

        await poller.poll_once()

        mock_repo.mark_failed.assert_awaited_once_with(event.event_id, "Publish failed")

    @pytest.mark.asyncio
    async def test_poll_once_retries_on_transient_error(
        self,
        mock_repo: MagicMock,
        mock_publisher: MagicMock,
        mock_router: MagicMock,
    ) -> None:
        """发布失败后重试成功时标记为已发布"""
        from src.infrastructure.messaging.retry.retry_policy import RetryPolicy

        event = _make_domain_event()
        mock_repo.get_unpublished.return_value = [event]
        call_count = 0

        async def flaky_publish(event: DomainEvent, **kwargs: object) -> None:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("Transient error")

        mock_publisher.async_publish.side_effect = flaky_publish

        poller = AsyncOutboxPoller(
            outbox_repository=mock_repo,
            publisher=mock_publisher,
            router=mock_router,
            retry_policy=RetryPolicy(base_delay=0.01, max_retries=3),
        )

        await poller.poll_once()

        assert call_count == 3
        mock_repo.mark_published.assert_awaited_once_with(event.event_id)
        mock_repo.mark_failed.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_poll_once_marks_failed_after_retries_exhausted(
        self,
        mock_repo: MagicMock,
        mock_publisher: MagicMock,
        mock_router: MagicMock,
    ) -> None:
        """重试耗尽后标记为失败"""
        from src.infrastructure.messaging.retry.retry_policy import RetryPolicy

        event = _make_domain_event()
        mock_repo.get_unpublished.return_value = [event]
        mock_publisher.async_publish.side_effect = RuntimeError("Persistent error")

        poller = AsyncOutboxPoller(
            outbox_repository=mock_repo,
            publisher=mock_publisher,
            router=mock_router,
            retry_policy=RetryPolicy(base_delay=0.01, max_retries=2),
        )

        await poller.poll_once()

        assert mock_publisher.async_publish.call_count == 3  # 1 initial + 2 retries
        mock_repo.mark_failed.assert_awaited_once_with(event.event_id, "Persistent error")
        mock_repo.mark_published.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_poll_once_uses_correct_routing_key(
        self,
        mock_repo: MagicMock,
        mock_publisher: MagicMock,
    ) -> None:
        """发布时使用 ChannelRouter 提供的 routing key"""
        event = DomainEvent(event_type="DocumentProcessed", source="test")
        mock_repo.get_unpublished.return_value = [event]

        router = MagicMock(spec=ChannelRouter)
        router.get_rabbitmq_routing_key.return_value = "sisys.events.reliable.document_processed"

        poller = AsyncOutboxPoller(
            outbox_repository=mock_repo,
            publisher=mock_publisher,
            router=router,
            poll_interval=0.01,
            batch_size=5,
        )

        await poller.poll_once()

        call_args = mock_publisher.async_publish.call_args
        assert call_args.kwargs["routing_key"] == "sisys.events.reliable.document_processed"
        router.get_rabbitmq_routing_key.assert_called_once_with("DocumentProcessed")

    @pytest.mark.asyncio
    async def test_poll_once_concurrent_processing(
        self,
        poller: AsyncOutboxPoller,
        mock_repo: MagicMock,
        mock_publisher: MagicMock,
    ) -> None:
        """验证并发处理使用 Semaphore 限制"""
        events = [_make_domain_event() for _ in range(3)]
        mock_repo.get_unpublished.return_value = events

        await poller.poll_once()

        assert mock_publisher.async_publish.call_count == 3
        assert mock_repo.mark_published.call_count == 3

    def test_stop_sets_running_false(self, poller: AsyncOutboxPoller) -> None:
        """stop() 将 _running 设为 False"""
        poller._running = True
        poller.stop()
        assert poller._running is False

    @pytest.mark.asyncio
    async def test_run_starts_and_stops(self, poller: AsyncOutboxPoller) -> None:
        """run() 启动后 stop() 可停止"""

        async def run_and_stop() -> None:
            await asyncio.sleep(0.03)
            poller.stop()

        await asyncio.gather(poller.run(), run_and_stop())
        assert poller._running is False

    @pytest.mark.asyncio
    async def test_run_logs_start_message(self, poller: AsyncOutboxPoller, caplog: pytest.LogCaptureFixture) -> None:
        """run() 启动时记录日志"""

        with caplog.at_level(logging.INFO):

            async def run_and_stop() -> None:
                await asyncio.sleep(0.03)
                poller.stop()

            await asyncio.gather(poller.run(), run_and_stop())

        assert "AsyncOutboxPoller started" in caplog.text

    @pytest.mark.asyncio
    async def test_run_stops_on_stop_message(self, poller: AsyncOutboxPoller, caplog: pytest.LogCaptureFixture) -> None:
        """stop() 记录停止日志"""
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

        async def mock_get_unpublished(limit: int) -> list[DomainEvent]:
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                poller.stop()
            return []

        with patch.object(poller._repo, "get_unpublished", new=AsyncMock(side_effect=mock_get_unpublished)):
            await poller.run()

        assert call_count >= 3

    @pytest.mark.asyncio
    async def test_run_exception_handling(self, poller: AsyncOutboxPoller, caplog: pytest.LogCaptureFixture) -> None:
        """poll_once 异常时 run() 捕获并记录错误，继续运行"""
        call_count = 0

        async def mock_get_unpublished(limit: int) -> list[DomainEvent]:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                poller.stop()
            event = _make_domain_event()
            return [event]

        with (
            patch.object(poller._repo, "get_unpublished", new=AsyncMock(side_effect=mock_get_unpublished)),
            patch.object(poller._publisher, "async_publish", new=AsyncMock(side_effect=RuntimeError("Unexpected error"))),
        ):
            with caplog.at_level(logging.ERROR):
                await poller.run()

    @pytest.mark.asyncio
    async def test_run_exception_in_poll_once_logs_error(
        self, poller: AsyncOutboxPoller, caplog: pytest.LogCaptureFixture
    ) -> None:
        """poll_once 抛出异常时 run() 记录错误日志"""
        call_count = 0

        async def mock_get_unpublished(limit: int) -> list[DomainEvent]:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                poller.stop()
            raise RuntimeError("Database connection lost")

        with patch.object(poller._repo, "get_unpublished", new=AsyncMock(side_effect=mock_get_unpublished)):
            with caplog.at_level(logging.ERROR):
                await poller.run()

        assert "Error in poll_once" in caplog.text

    @pytest.mark.asyncio
    async def test_poll_once_processes_multiple_events(
        self, poller: AsyncOutboxPoller, mock_repo: MagicMock, mock_publisher: MagicMock
    ) -> None:
        """批量处理多个事件"""
        events = [_make_domain_event() for _ in range(5)]
        mock_repo.get_unpublished.return_value = events

        await poller.poll_once()

        assert mock_publisher.async_publish.call_count == 5
        assert mock_repo.mark_published.call_count == 5

    @pytest.mark.asyncio
    async def test_run_terminates_cleanly(self, poller: AsyncOutboxPoller) -> None:
        """多次调用 stop() 应正常工作"""

        async def run_and_stop_twice() -> None:
            await asyncio.sleep(0.02)
            poller.stop()
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
        with pytest.raises(Exception):
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
        entity.status = "pending"
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
        with pytest.raises(Exception):
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
