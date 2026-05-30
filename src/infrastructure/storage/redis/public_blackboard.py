"""基础设施层 Redis 公共黑板模块

实现 PublicBlackboard 接口，使用 Redis Sorted Set 存储黑板内容，按时间戳排序
支持 MVCC（多版本并发控制），每次写入自动递增版本号
"""

from __future__ import annotations

import json
import logging
import time

import redis.asyncio as aioredis

from src.infrastructure.storage.redis.key_builder import build_key
from src.infrastructure.utils import json_dumps, json_loads

logger = logging.getLogger(__name__)


class RedisPublicBlackboard:
    """Redis 公共黑板

    使用 Redis Sorted Set（按时间戳排序）存储多 Agent 共享信息
    键格式: sisys:blackboard:{conversation_id}
    支持 MVCC：每次写入自动递增版本号

    Args:
        config: Redis 连接配置
    """

    _NAMESPACE = "blackboard"

    def __init__(self, redis_client: aioredis.Redis):
        """初始化 Redis 公共黑板

        Args:
            redis_client: Redis 异步客户端（由 RedisConnectionManager 提供）
        """
        self._redis = redis_client

    def _get_version_key(self, conversation_id: str) -> str:
        """获取版本键"""
        return build_key(self._NAMESPACE, conversation_id, "version")

    async def post(
        self,
        conversation_id: str,
        agent_id: str,
        content: dict,
        confidence: float = 1.0,
        citations: list[str] | None = None,
    ) -> int:
        """发布内容到黑板

        Args:
            conversation_id: 会话唯一标识
            agent_id: Agent 唯一标识
            content: 内容数据
            confidence: 置信度（0.0-1.0）
            citations: 引用来源列表

        Returns:
            版本号
        """
        key = build_key(self._NAMESPACE, conversation_id)
        version_key = self._get_version_key(conversation_id)

        if citations is None:
            citations = []

        try:
            version = await self._redis.incr(version_key)

            entry = {
                "conversation_id": conversation_id,
                "agent_id": agent_id,
                "content": content,
                "confidence": confidence,
                "citations": citations,
                "version": version,
                "timestamp": time.time(),
            }

            score = float(version)
            await self._redis.zadd(key, {json_dumps(entry): score})

            logger.debug(
                "Posted to blackboard %s by agent %s, version %d",
                conversation_id,
                agent_id,
                version,
            )
            return version

        except (aioredis.ConnectionError, aioredis.TimeoutError) as e:
            logger.error(
                "Failed to post to blackboard %s in Redis: %s",
                conversation_id,
                e,
            )
            return 0

    async def get(self, conversation_id: str) -> list[dict]:
        """获取会话的所有内容

        Args:
            conversation_id: 会话唯一标识

        Returns:
            内容列表（按时间排序）

        Raises:
            aioredis.ConnectionError: Redis 连接失败时抛出
        """
        key = build_key(self._NAMESPACE, conversation_id)
        try:
            entries = await self._redis.zrange(key, 0, -1)
            result = []
            for entry in entries:
                try:
                    raw = json_loads(entry)
                    if isinstance(raw, dict):
                        result.append(raw)
                    else:
                        logger.warning("Unexpected data type in blackboard key %s: %s", key, type(raw).__name__)
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning("Corrupt data in blackboard key %s: %s", key, e)
            return result
        except (aioredis.ConnectionError, aioredis.TimeoutError) as e:
            logger.error(
                "Failed to get blackboard %s from Redis: %s",
                conversation_id,
                e,
            )
            return []

    async def get_by_agent(self, conversation_id: str, agent_id: str) -> dict | None:
        """获取指定 Agent 的最新内容

        Args:
            conversation_id: 会话唯一标识
            agent_id: Agent 唯一标识

        Returns:
            内容数据，如果不存在则返回 None
        """
        all_entries = await self.get(conversation_id)
        # 过滤出指定 Agent 的条目，返回最新的
        agent_entries = [e for e in all_entries if e.get("agent_id") == agent_id]
        if agent_entries:
            # 按版本号降序排序，返回最新的
            agent_entries.sort(key=lambda e: e.get("version", 0), reverse=True)
            return agent_entries[0]
        return None

    async def get_latest(self, conversation_id: str) -> dict | None:
        """获取会话的最新内容

        Args:
            conversation_id: 会话唯一标识

        Returns:
            最新内容数据，如果不存在则返回 None

        Raises:
            aioredis.ConnectionError: Redis 连接失败时抛出
        """
        key = build_key(self._NAMESPACE, conversation_id)
        try:
            entries = await self._redis.zrange(key, -1, -1)
            if entries:
                raw = json_loads(entries[0])
                if isinstance(raw, dict):
                    return raw
                logger.warning("Unexpected data type in blackboard key %s: %s", key, type(raw).__name__)
            return None
        except (aioredis.ConnectionError, aioredis.TimeoutError) as e:
            logger.error(
                "Failed to get latest blackboard %s from Redis: %s",
                conversation_id,
                e,
            )
            return None

    async def __aenter__(self) -> RedisPublicBlackboard:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        pass
