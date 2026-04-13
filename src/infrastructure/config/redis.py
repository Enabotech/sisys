"""Redis 配置模型。"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class RedisConfig:
    """Redis 连接配置。

    用于 Redis Pub/Sub 实时通知通道和幂等性检查。
    """

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str | None = None
    max_connections: int = 10
    socket_timeout: float = 5.0

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
        """
        return cls(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            password=os.getenv("REDIS_PASSWORD") or None,
            max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "10")),
            socket_timeout=float(os.getenv("REDIS_SOCKET_TIMEOUT", "5.0")),
        )
