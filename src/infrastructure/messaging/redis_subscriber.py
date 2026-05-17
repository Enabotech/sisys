"""SISYS 基础设施层 Redis 事件订阅模块

用于 Redis Pub/Sub 实时通知通道的订阅端，支持多频道订阅、事件反序列化和优雅关闭

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any, cast

import redis.asyncio as aioredis

from src.infrastructure.config.redis import RedisConfig
from src.infrastructure.utils import json_loads

logger = logging.getLogger(__name__)

# 类型别名: 事件处理器接收反序列化后的 dict
EventHandler = Callable[[dict[str, Any]], None]
# 错误处理器: (channel, raw_message, error)
ErrorHandler = Callable[[str, str, Exception], None]


class RedisEventSubscriber:
    """Redis Pub/Sub 事件订阅器

    支持多频道订阅、事件反序列化、优雅关闭
    注意：Redis 通道为"尽力而为"，不保证可靠投递
    """

    def __init__(self, config: RedisConfig):
        """初始化 RedisEventSubscriber

        Args:
            config: Redis 连接配置
        """
        self._config = config
        self._pool: aioredis.ConnectionPool | None = None
        self._handlers: dict[str, list[EventHandler]] = {}
        self._error_handlers: dict[str, ErrorHandler | None] = {}
        self._pubsub: aioredis.client.PubSub | None = None
        self._task: asyncio.Task | None = None
        self._running = False

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

    def subscribe(
        self,
        channel: str,
        handler: EventHandler,
        error_handler: ErrorHandler | None = None,
    ) -> None:
        """订阅 Redis 频道

        Args:
            channel: Redis 频道名
            handler: 事件处理器，接收反序列化后的 event dict
            error_handler: 可选的错误处理器
        """
        if channel not in self._handlers:
            self._handlers[channel] = []
            self._error_handlers[channel] = error_handler
        self._handlers[channel].append(handler)

    async def start(self) -> None:
        """异步开始监听所有订阅的频道"""
        if self._running:
            return

        pool = self._get_pool()
        redis_client = aioredis.Redis(connection_pool=pool)
        self._pubsub = redis_client.pubsub()
        await self._pubsub.subscribe(*self._handlers.keys())

        self._running = True
        self._task = asyncio.create_task(self._listen_loop())
        logger.info("RedisEventSubscriber started, subscribed to: %s", list(self._handlers.keys()))

    async def _listen_loop(self) -> None:
        """后台监听循环（异步版本）"""
        assert self._pubsub is not None
        try:
            async for message in self._pubsub.listen():
                if not self._running:
                    break
                if message["type"] == "message":
                    channel = message["channel"]
                    data = message["data"]
                    self._dispatch_message(channel, data)
        except asyncio.CancelledError:
            logger.debug("RedisEventSubscriber listen loop cancelled")

    def _dispatch_message(self, channel: str, data: str) -> None:
        """分发消息到注册的处理器

        Args:
            channel: 频道名
            data: 原始消息数据（JSON 字符串）
        """
        try:
            event_dict = json_loads(data)
        except (json.JSONDecodeError, TypeError) as e:
            error_handler = self._error_handlers.get(channel)
            if error_handler:
                error_handler(channel, data, e)
            else:
                logger.warning(
                    "Failed to deserialize event from channel %s: %s",
                    channel,
                    e,
                )
            return

        handlers = self._handlers.get(channel, [])
        for handler in handlers:
            try:
                handler(event_dict)
            except Exception as e:
                logger.error(
                    "Error in handler for channel %s, event %s: %s",
                    channel,
                    event_dict.get("event_id"),
                    e,
                )

    async def close(self) -> None:
        """异步停止订阅并关闭连接"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except (TimeoutError, asyncio.CancelledError):
                pass
            self._task = None
        if self._pubsub:
            try:
                await self._pubsub.unsubscribe()
                await self._pubsub.close()
            except Exception:
                pass
            self._pubsub = None
        self._handlers.clear()
        self._error_handlers.clear()
        if self._pool:
            await cast(Any, self._pool).aclose()
            self._pool = None
        logger.info("RedisEventSubscriber closed")
