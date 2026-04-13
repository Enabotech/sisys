"""Redis 配置模型。"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class RedisConfig:
    """Redis 连接配置。

    用于 Redis Pub/Sub 实时通知通道、幂等性检查和缓存存储服务。
    """

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str | None = None
    max_connections: int = 10
    socket_timeout: float = 5.0
    retry_on_timeout: bool = True
    default_ttl: int = 86400  # 24 小时

    @classmethod
    def from_env(cls) -> RedisConfig:
        """从环境变量加载配置。

        环境变量:
            REDIS_HOST: Redis 主机地址 (默认: localhost)
            REDIS_PORT: Redis 端口 (默认: 6379)
            REDIS_DB: Redis 数据库号 (默认: 0)
            REDIS_PASSWORD: Redis 密码 (默认: None)
            REDIS_MAX_CONNECTIONS: 最大连接数 (默认: 10)
            REDIS_SOCKET_TIMEOUT: Socket 超时秒数 (默认: 5.0)
            REDIS_RETRY_ON_TIMEOUT: 超时时重试 (默认: true)
            REDIS_DEFAULT_TTL: 默认 TTL 秒数 (默认: 86400)
        """
        retry_on_timeout_env = os.getenv("REDIS_RETRY_ON_TIMEOUT", "true").lower()
        default_ttl_env = os.getenv("REDIS_DEFAULT_TTL", "86400")

        return cls(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            password=os.getenv("REDIS_PASSWORD") or None,
            max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "10")),
            socket_timeout=float(os.getenv("REDIS_SOCKET_TIMEOUT", "5.0")),
            retry_on_timeout=retry_on_timeout_env in ("true", "1", "yes"),
            default_ttl=int(default_ttl_env),
        )
