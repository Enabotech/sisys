"""基础设施层异步发件箱轮询处理器模块

异步协程定期轮询 Outbox，将 pending 状态的事件发布至 RabbitMQ，
使用 asyncio.Semaphore 控制并发
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.domain.events.base import DomainEvent
from src.domain.ports.outbox import OutboxRepository
from src.infrastructure.messaging.channel_router import ChannelRouter
from src.infrastructure.messaging.retry.retry_policy import RetryPolicy
from src.infrastructure.storage.postgresql.session_context import session_context

logger = logging.getLogger(__name__)


class AsyncOutboxPoller:
    """异步发件箱轮询器

    定期轮询 Outbox，将 pending 状态的事件发布至 RabbitMQ
    成功则标记为 published，失败则标记为 failed
    仅使用 OutboxRepository 公共接口（无私有方法访问）
    """

    def __init__(
        self,
        outbox_repository: OutboxRepository,
        publisher: Any,
        router: ChannelRouter,
        session_factory: Any = None,
        poll_interval: float = 1.0,
        batch_size: int = 10,
        retry_policy: RetryPolicy | None = None,
    ):
        """初始化 AsyncOutboxPoller

        Args:
            outbox_repository: OutboxRepository Protocol 实现实例
            publisher: 异步发布者（需提供 async_publish 方法）
            router: 通道路由器
            session_factory: AsyncSession 工厂，用于每次 poll 周期创建独立 session
            poll_interval: 轮询间隔（秒）
            batch_size: 每批处理数量
            retry_policy: 重试策略（默认使用 RetryPolicy 默认值）
        """
        self._repo = outbox_repository
        self._publisher = publisher
        self._router = router
        self._session_factory = session_factory
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._retry_policy = retry_policy or RetryPolicy()
        self._running = False

    async def poll_once(self) -> None:
        """轮询一次并发布待处理事件

        从发件箱获取 pending 状态的 DomainEvent，并发发布到 RabbitMQ，
        成功标记为 published，失败标记为 failed
        """
        events: list[DomainEvent] = await self._repo.get_unpublished(limit=self._batch_size)
        if not events:
            return

        semaphore = asyncio.Semaphore(self._batch_size)

        async def process_one(event: DomainEvent) -> None:
            async with semaphore:
                routing_key = self._router.get_rabbitmq_routing_key(event.event_type)
                if routing_key is None:
                    logger.warning(
                        "No routing key mapping for event_type=%s, marking as failed",
                        event.event_type,
                    )
                    await self._repo.mark_failed(
                        event.event_id,
                        f"No routing key mapping for {event.event_type}",
                    )
                    return

                last_error: Exception | None = None
                for attempt in range(self._retry_policy.max_retries + 1):
                    try:
                        await self._publisher.async_publish(
                            event,
                            routing_key=routing_key,
                        )
                        await self._repo.mark_published(event.event_id)
                        logger.debug("Published event %s", event.event_id)
                        return
                    except Exception as e:
                        last_error = e
                        if self._retry_policy.should_retry(attempt):
                            delay = self._retry_policy.get_delay(attempt)
                            logger.warning(
                                "Publish attempt %d/%d failed for event %s, retrying in %.1fs: %s",
                                attempt + 1,
                                self._retry_policy.max_retries + 1,
                                event.event_id,
                                delay,
                                e,
                            )
                            await asyncio.sleep(delay)
                        else:
                            break

                if last_error is not None:
                    try:
                        await self._repo.mark_failed(event.event_id, str(last_error))
                    except Exception:
                        logger.error(
                            "Failed to mark event %s as failed: %s",
                            event.event_id,
                            last_error,
                        )
                    logger.error(
                        "All %d attempts exhausted for event %s: %s",
                        self._retry_policy.max_retries + 1,
                        event.event_id,
                        last_error,
                    )

        await asyncio.gather(*[process_one(e) for e in events])

    async def run(self) -> None:
        """启动轮询循环，按配置间隔持续轮询发件箱"""
        self._running = True
        logger.info(
            "AsyncOutboxPoller started (interval=%.1fs, batch_size=%d)",
            self._poll_interval,
            self._batch_size,
        )
        while self._running:
            try:
                if self._session_factory is not None:
                    async with session_context(self._session_factory):
                        await self.poll_once()
                else:
                    await self.poll_once()
            except Exception as e:
                logger.error("Error in poll_once: %s", e)
            await asyncio.sleep(self._poll_interval)

    def stop(self) -> None:
        """停止轮询循环"""
        self._running = False
        logger.info("AsyncOutboxPoller stopping")
