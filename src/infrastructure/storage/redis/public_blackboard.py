"""Redis Public Blackboard — 基础设施层实现。

实现 Story 1.4 定义的 PublicBlackboard 接口。
使用 Redis Sorted Set 存储黑板内容，按时间戳排序。
支持 MVCC（多版本并发控制），每次写入自动递增版本号。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

import redis.asyncio as aioredis

from src.infrastructure.config.redis import RedisConfig
from src.infrastructure.storage.redis.key_builder import build_key
from src.infrastructure.utils import json_dumps, json_loads

logger = logging.getLogger(__name__)


class RedisPublicBlackboard:
    """Redis 公共黑板。

    使用 Redis Sorted Set（按时间戳排序）存储多 Agent 共享信息。
    键格式: sisys:blackboard:{conversation_id}
    支持 MVCC：每次写入自动递增版本号。

    Args:
        config: Redis 连接配置
    """

    _NAMESPACE = "blackboard"

    def __init__(self, config: RedisConfig):
        """初始化 Redis 公共黑板。

        Args:
            config: Redis 连接配置
        """
        self._config = config
        self._pool: aioredis.ConnectionPool | None = None
        self._pool_lock = asyncio.Lock()

    def _get_pool(self) -> aioredis.ConnectionPool:
        """懒加载连接池（异步安全）。"""
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

    def _get_version_key(self, conversation_id: str) -> str:
        """获取版本号键。"""
        return build_key(self._NAMESPACE, conversation_id, "version")

    async def post(
        self,
        conversation_id: str,
        agent_id: str,
        content: dict,
        confidence: float = 1.0,
        citations: list[str] | None = None,
    ) -> int:
        """发布内容到黑板。

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
        pool = self._get_pool()

        if citations is None:
            citations = []

        try:
            async with aioredis.Redis(connection_pool=pool) as client:
                # 原子递增版本号
                version = await client.incr(version_key)

                entry = {
                    "conversation_id": conversation_id,
                    "agent_id": agent_id,
                    "content": content,
                    "confidence": confidence,
                    "citations": citations,
                    "version": version,
                    "timestamp": time.time(),
                }

                # 使用版本号作为 score，支持排序
                score = float(version)
                await client.zadd(key, {json_dumps(entry): score})

                logger.debug(
                    "Posted to blackboard %s by agent %s, version %d",
                    conversation_id,
                    agent_id,
                    version,
                )
                return version

        except aioredis.ConnectionError as e:
            logger.error(
                "Failed to post to blackboard %s in Redis: %s",
                conversation_id,
                e,
            )
            return 0

    async def get(self, conversation_id: str) -> list[dict]:
        """获取会话的所有内容。

        Args:
            conversation_id: 会话唯一标识

        Returns:
            内容列表（按时间排序）

        Raises:
            aioredis.ConnectionError: Redis 连接失败时抛出
        """
        key = build_key(self._NAMESPACE, conversation_id)
        pool = self._get_pool()
        try:
            async with aioredis.Redis(connection_pool=pool) as client:
                entries = await client.zrange(key, 0, -1)
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
        except aioredis.ConnectionError as e:
            logger.error(
                "Failed to get blackboard %s from Redis: %s",
                conversation_id,
                e,
            )
            return []

    async def get_by_agent(self, conversation_id: str, agent_id: str) -> dict | None:
        """获取指定 Agent 的最新内容。

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
        """获取会话的最新内容。

        Args:
            conversation_id: 会话唯一标识

        Returns:
            最新内容数据，如果不存在则返回 None

        Raises:
            aioredis.ConnectionError: Redis 连接失败时抛出
        """
        key = build_key(self._NAMESPACE, conversation_id)
        pool = self._get_pool()
        try:
            async with aioredis.Redis(connection_pool=pool) as client:
                # 获取 score 最高的条目（最新版本）
                entries = await client.zrange(key, -1, -1)
                if entries:
                    raw = json_loads(entries[0])
                    if isinstance(raw, dict):
                        return raw
                    logger.warning("Unexpected data type in blackboard key %s: %s", key, type(raw).__name__)
                return None
        except aioredis.ConnectionError as e:
            logger.error(
                "Failed to get latest blackboard %s from Redis: %s",
                conversation_id,
                e,
            )
            return None

    async def close(self) -> None:
        """异步关闭连接池。"""
        if self._pool:
            await self._pool.aclose()  # type: ignore[attr-defined]
            self._pool = None
            logger.debug("Redis connection pool closed")

    async def __aenter__(self) -> RedisPublicBlackboard:
        """异步上下文管理器入口。"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器出口，确保连接池关闭。"""
        await self.close()
