"""基础设施层幂等性检查器模块

基于 Redis SET NX 原子操作实现事件处理幂等性保证，
使用原子方法 try_acquire()，禁止分离 is_processed() + mark_processed()
"""

from __future__ import annotations

import logging
from uuid import UUID

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class IdempotencyChecker:
    """事件处理幂等性检查器

    使用 Redis SET NX 原子操作确保同一事件仅被处理一次
    TTL 默认 7 天
    """

    def __init__(
        self,
        redis_client: aioredis.Redis | None = None,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
    ):
        """初始化 IdempotencyChecker

        Args:
            redis_client: Redis 客户端实例（用于测试 Mock）
            host: Redis 主机地址
            port: Redis 端口
            db: Redis 数据库号
            password: Redis 密码
        """
        if redis_client is not None:
            self._redis = redis_client
        else:
            pool = aioredis.ConnectionPool(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,
            )
            self._redis = aioredis.Redis(connection_pool=pool)

    async def try_acquire(self, event_id: UUID, ttl: int = 7 * 24 * 3600) -> bool:
        """原子性尝试获取事件处理权

        Args:
            event_id: 事件唯一标识
            ttl: 去重 TTL（秒），默认 7 天

        Returns:
            True: 首次处理（获取成功）
            False: 已处理（获取失败）
        """
        key = f"idempotency:{event_id}"
        try:
            result = await self._redis.set(key, "1", nx=True, ex=ttl)
            # redis-py returns True on success, None/False on failure
            success = bool(result)
            if success:
                logger.debug("Acquired processing lock for event %s", event_id)
            else:
                logger.debug("Event %s already processed", event_id)
            return success
        except aioredis.RedisError as e:
            logger.error("Redis error during idempotency check: %s", e)
            # 连接失败时允许处理（fail-open），避免阻塞正常流程
            return True
