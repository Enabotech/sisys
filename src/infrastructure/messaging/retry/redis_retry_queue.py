"""基础设施层 Redis 延迟重试队列模块。

使用 Redis ZSET 实现延迟重试调度，失败事件以重试时间戳为 score 入队，
轮询器检查到期事件进行重试，避免 nack(requeue=True) 造成的消息饥饿

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# 默认重试队列键名
DEFAULT_RETRY_QUEUE_KEY = "sisys:retry:queue"


class RetryQueueEntry:
    """重试队列条目数据类。

    Attributes:
        event_id: 事件唯一标识。
        event_type: 事件类型名称。
        payload: 事件负载数据。
        retry_at: 重试时间戳。
        retry_count: 已重试次数。
        error: 错误信息。
    """

    def __init__(
        self,
        event_id: UUID,
        event_type: str,
        payload: dict,
        retry_at: datetime,
        retry_count: int = 0,
        error: str | None = None,
    ):
        """初始化重试队列条目。

        Args:
            event_id: 事件唯一标识。
            event_type: 事件类型名称。
            payload: 事件负载数据。
            retry_at: 重试时间戳。
            retry_count: 已重试次数。
            error: 错误信息。
        """
        self.event_id = event_id
        self.event_type = event_type
        self.payload = payload
        self.retry_at = retry_at
        self.retry_count = retry_count
        self.error = error

    def to_json(self) -> str:
        """序列化为 JSON 字符串。

        Returns:
            JSON 格式的字符串。
        """
        return json.dumps(
            {
                "event_id": str(self.event_id),
                "event_type": self.event_type,
                "payload": self.payload,
                "retry_at": self.retry_at.isoformat(),
                "retry_count": self.retry_count,
                "error": self.error,
            }
        )

    @classmethod
    def from_json(cls, data: str) -> RetryQueueEntry:
        """从 JSON 字符串反序列化。

        Args:
            data: JSON 格式的字符串。

        Returns:
            反序列化后的 RetryQueueEntry 实例。
        """
        obj = json.loads(data)
        return cls(
            event_id=UUID(obj["event_id"]),
            event_type=obj["event_type"],
            payload=obj["payload"],
            retry_at=datetime.fromisoformat(obj["retry_at"]),
            retry_count=obj.get("retry_count", 0),
            error=obj.get("error"),
        )


class RedisRetryQueue:
    """Redis ZSET 延迟重试队列

    使用有序集合存储待重试事件，score 为重试时间戳
    支持：
    - 添加重试事件（带延迟）
    - 获取到期事件
    - 移除已处理事件
    - 统计待重试事件数量
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        queue_key: str = DEFAULT_RETRY_QUEUE_KEY,
    ):
        """初始化 RedisRetryQueue

        Args:
            redis_client: 异步 Redis 客户端
            queue_key: ZSET 键名
        """
        self._redis = redis_client
        self._queue_key = queue_key

    async def enqueue(
        self,
        event_id: UUID,
        event_type: str,
        payload: dict,
        retry_at: datetime,
        retry_count: int = 0,
        error: str | None = None,
    ) -> None:
        """添加重试事件到队列

        Args:
            event_id: 事件 ID
            event_type: 事件类型
            payload: 事件负载
            retry_at: 重试时间戳
            retry_count: 重试次数
            error: 错误信息
        """
        entry = RetryQueueEntry(
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            retry_at=retry_at,
            retry_count=retry_count,
            error=error,
        )
        # ZADD with timestamp as score
        await self._redis.zadd(self._queue_key, {entry.to_json(): retry_at.timestamp()})
        logger.warning(
            "Event %s enqueued to RedisRetryQueue, retry_at=%s (attempt %d)",
            event_id,
            retry_at.isoformat(),
            retry_count,
        )

    async def dequeue(self, limit: int = 10) -> list[RetryQueueEntry]:
        """获取已到期的重试事件

        Args:
            limit: 最大返回数量

        Returns:
            已到期的事件列表（已从队列移除）
        """
        now = datetime.now(UTC).timestamp()

        # 获取到期事件（score <= now）
        entries = await self._redis.zrangebyscore(
            self._queue_key,
            "-inf",
            now,
            start=0,
            num=limit,
        )

        if not entries:
            return []

        result = []
        for entry_json in entries:
            try:
                entry = RetryQueueEntry.from_json(entry_json)
                # 移除已处理的事件
                await self._redis.zrem(self._queue_key, entry_json)
                result.append(entry)
            except (ValueError, KeyError) as e:
                logger.error("Failed to parse retry entry: %s", e)
                # 删除无效条目
                await self._redis.zrem(self._queue_key, entry_json)

        return result

    async def count(self) -> int:
        """统计待重试事件数量

        Returns:
            队列中的事件数量
        """
        return await self._redis.zcard(self._queue_key)

    async def peek(self, limit: int = 10) -> list[RetryQueueEntry]:
        """查看即将重试的事件（不移除）

        Args:
            limit: 最大返回数量

        Returns:
            事件列表（按时间排序）
        """
        entries = await self._redis.zrange(self._queue_key, 0, limit - 1)
        result = []
        for entry_json in entries:
            try:
                result.append(RetryQueueEntry.from_json(entry_json))
            except (ValueError, KeyError):
                continue
        return result

    async def remove(self, event_id: UUID) -> bool:
        """移除指定事件

        Args:
            event_id: 事件 ID

        Returns:
            是否成功移除
        """
        # 需要先找到对应的事件
        entries = await self._redis.zrange(self._queue_key, 0, -1)
        for entry_json in entries:
            try:
                entry = RetryQueueEntry.from_json(entry_json)
                if entry.event_id == event_id:
                    removed = await self._redis.zrem(self._queue_key, entry_json)
                    return removed > 0
            except (ValueError, KeyError):
                continue
        return False

    async def clear(self) -> None:
        """清空重试队列"""
        await self._redis.delete(self._queue_key)
