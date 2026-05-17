"""AsyncOutboxPoller — 基础设施层实现

异步协程轮询 OutboxEntity，发布至 RabbitMQ
统一 async 路径，使用 asyncio.Semaphore 控制并发
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.infrastructure.messaging.adapters.event_outbox_adapter import EventOutboxAdapter

logger = logging.getLogger(__name__)


class AsyncOutboxPoller:
    """异步发件箱轮询器

    定期轮询 OutboxEntity，将 pending 状态的事件发布至 RabbitMQ
    成功则标记为 published，失败则标记为 failed
    """

    def __init__(
        self,
        outbox_repository: Any,
        publisher: Any,
        poll_interval: float = 1.0,
        batch_size: int = 10,
    ):
        """初始化 AsyncOutboxPoller

        Args:
            outbox_repository: InMemoryOutboxRepository 实例
            publisher: RabbitMQPublisher 实例
            poll_interval: 轮询间隔（秒）
            batch_size: 每批处理数量
        """
        self._repo = outbox_repository
        self._publisher = publisher
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._running = False

    async def poll_once(self) -> None:
        """轮询一次并发布待处理事件"""
        entities = await self._repo._get_unpublished_entities(limit=self._batch_size)
        if not entities:
            return

        semaphore = asyncio.Semaphore(self._batch_size)

        async def process_one(entity) -> None:
            async with semaphore:
                try:
                    domain_event = EventOutboxAdapter.to_domain_event(entity)
                    await self._publisher.async_publish(
                        domain_event,
                        routing_key=f"sisys.events.reliable.{entity.event_type}",
                    )
                    await self._repo._mark_published_entity(entity)
                    logger.debug("Published event %s", entity.event_id)
                except Exception as e:
                    await self._repo._mark_failed_entity(entity, str(e))
                    logger.error(
                        "Failed to publish event %s: %s",
                        entity.event_id,
                        e,
                    )

        await asyncio.gather(*[process_one(e) for e in entities])

    async def run(self) -> None:
        """启动轮询循环"""
        self._running = True
        logger.info(
            "AsyncOutboxPoller started (interval=%.1fs, batch_size=%d)",
            self._poll_interval,
            self._batch_size,
        )
        while self._running:
            try:
                await self.poll_once()
            except Exception as e:
                logger.error("Error in poll_once: %s", e)
            await asyncio.sleep(self._poll_interval)

    def stop(self) -> None:
        """停止轮询循环"""
        self._running = False
        logger.info("AsyncOutboxPoller stopping")
