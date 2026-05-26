"""RabbitMQ 事件发布实现模块

将爬取事件发布到 RabbitMQ 消息队列

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from plugins.crawler.core.entities import CrawledFile, CrawlResult

if TYPE_CHECKING:
    from aio_pika.abc import AbstractChannel, AbstractRobustConnection

logger = logging.getLogger(__name__)


class RabbitMQPublisher:
    """RabbitMQ 事件发布实现"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5672,
        exchange: str = "sisys.events",
    ):
        """初始化 RabbitMQ 发布器

        Args:
            host: RabbitMQ 主机地址
            port: RabbitMQ 端口
            exchange: 交换机名称
        """
        self._host = host
        self._port = port
        self._exchange = exchange
        self._connection: AbstractRobustConnection | None = None
        self._channel: AbstractChannel | None = None

    async def connect(self) -> None:
        """建立 RabbitMQ 连接"""
        import aio_pika

        url = f"amqp://{self._host}:{self._port}/"
        self._connection = await aio_pika.connect_robust(url)
        self._channel = await self._connection.channel()
        await self._channel.declare_exchange(
            self._exchange,
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )
        logger.info("RabbitMQ 已连接: %s:%d", self._host, self._port)

    async def close(self) -> None:
        """关闭 RabbitMQ 连接"""
        if self._connection:
            await self._connection.close()
            self._connection = None
            self._channel = None
            logger.info("RabbitMQ 连接已关闭")

    async def publish_crawl_completed(self, result: CrawlResult) -> None:
        """发布爬取完成事件

        Args:
            result: 爬取结果
        """
        message = self._build_message(
            "CrawlCompleted",
            {
                "task_id": result.task_id,
                "status": result.status.value,
                "files_count": len(result.files),
                "total_size_bytes": result.total_size_bytes,
                "failed_urls_count": len(result.failed_urls),
                "started_at": result.started_at.isoformat() if result.started_at else None,
                "completed_at": result.completed_at.isoformat() if result.completed_at else None,
            },
        )
        await self._publish("sisys.events.reliable.crawl_completed", message)

    async def publish_crawl_failed(self, task_id: str, error: str) -> None:
        """发布爬取失败事件

        Args:
            task_id: 任务 ID
            error: 错误信息
        """
        message = self._build_message(
            "CrawlFailed",
            {
                "task_id": task_id,
                "error": error,
            },
        )
        await self._publish("sisys.events.reliable.crawl_failed", message)

    async def publish_file_crawled(self, file_info: CrawledFile) -> None:
        """发布单文件爬取完成事件

        Args:
            file_info: 爬取到的文件信息
        """
        message = self._build_message(
            "FileCrawled",
            {
                "task_id": file_info.task_id,
                "url": file_info.url,
                "smart_name": file_info.smart_name,
                "naming_strategy": file_info.naming_strategy,
                "file_size": file_info.file_size,
                "content_type": file_info.content_type,
                "file_extension": file_info.file_extension,
                "parent_url": file_info.parent_url,
                "depth": file_info.depth,
            },
        )
        await self._publish("sisys.events.reliable.file_crawled", message)

    def _build_message(self, event_type: str, payload: dict) -> dict:
        """构造符合 SISYS 事件契约的消息体

        Args:
            event_type: 事件类型
            payload: 事件数据

        Returns:
            完整消息字典
        """
        return {
            "event_type": event_type,
            "event_id": str(uuid4()),
            "timestamp": datetime.now(UTC).isoformat(),
            "source": "crawler-service",
            "schema_version": "1.0.0",
            "aggregate_type": "CrawlTask",
            "payload": payload,
        }

    async def _publish(self, routing_key: str, message: dict) -> None:
        """发布消息到 RabbitMQ

        Args:
            routing_key: 路由键
            message: 消息内容
        """
        import aio_pika

        if not self._channel:
            await self.connect()

        assert self._channel is not None

        await self._channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(message).encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=routing_key,
        )
        logger.debug("事件已发布: %s", routing_key)
