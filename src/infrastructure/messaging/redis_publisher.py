"""基础设施层 Redis 事件发布模块

实现领域事件的 Redis 发布/订阅通道，用于实时通知型事件的低延迟分发
允许事件丢失（与业务状态型事件通过 RabbitMQ + Outbox 保证可靠性不同）

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

import redis.asyncio as aioredis

from src.domain.events.base import DomainEvent
from src.domain.events.publish_result import PublishResult
from src.infrastructure.config.redis import RedisConfig
from src.infrastructure.utils import json_dumps

logger = logging.getLogger(__name__)


class RedisEventPublisher:
    """Redis 事件发布器

    通过 Redis 发布/订阅通道分发实时通知型事件
    允许事件丢失（与业务状态型事件通过 RabbitMQ + Outbox 保证可靠性不同）

    Args:
        config: Redis 连接配置
    """

    _NAMESPACE = "rt"

    def __init__(self, config: RedisConfig):
        """初始化 Redis 事件发布器

        Args:
            config: Redis 连接配置
        """
        self._config = config
        self._pool: aioredis.ConnectionPool | None = None
        self._pool_lock = asyncio.Lock()

    def _get_pool(self) -> aioredis.ConnectionPool:
        """懒加载连接池（异步安全）"""
        if self._pool is None:
            self._pool = aioredis.ConnectionPool(
                host=self._config.host,
                port=self._config.port,
                db=self._config.db,
                password=self._config.password,
                max_connections=self._config.max_connections,
                socket_timeout=self._config.socket_timeout,
                decode_responses=True,
            )
        return self._pool

    async def publish(self, event: DomainEvent, channel: str | None = None) -> PublishResult:
        """发布领域事件到 Redis 通道

        Args:
            event: 领域事件实例
            channel: 通道名，默认使用事件类型

        Returns:
            PublishResult: 发布结果
        """
        if channel is None:
            channel = f"{self._NAMESPACE}:{event.event_type}"

        pool = self._get_pool()
        try:
            async with aioredis.Redis(connection_pool=pool) as client:
                payload = json_dumps(event.to_dict())
                await client.publish(channel, payload)
                logger.debug("Published event %s to channel %s", event.event_id, channel)
                return PublishResult(event_id=str(event.event_id), redis_success=True)
        except (aioredis.ConnectionError, aioredis.TimeoutError) as e:
            logger.error(
                "Failed to publish event %s to Redis channel %s: %s",
                event.event_id,
                channel,
                e,
            )
            return PublishResult(
                event_id=str(event.event_id),
                redis_success=False,
                redis_error=str(e),
            )

    async def close(self) -> None:
        """异步关闭连接池"""
        if self._pool:
            await cast(Any, self._pool).aclose()
            self._pool = None
            logger.debug("Redis connection pool closed")

    async def __aenter__(self) -> RedisEventPublisher:
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器出口，确保连接池关闭"""
        await self.close()
