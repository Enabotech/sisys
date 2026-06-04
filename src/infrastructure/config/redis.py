"""基础设施层 Redis 配置模块

提供 Redis 连接配置，用于 Pub/Sub 实时通知通道和缓存存储
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from src.domain.exceptions import ConfigurationError


@dataclass
class RedisConfig:
    """Redis 连接配置

    用于 Redis Pub/Sub 实时通知通道、幂等性检查和缓存存储服务

    Attributes:
        host: Redis 主机地址
        port: Redis 端口
        db: Redis 数据库号
        password: Redis 密码（可选）
        max_connections: 最大连接数
        socket_timeout: Socket 超时（秒）
        retry_on_timeout: 超时时是否重试
        default_ttl: 默认 TTL（秒）
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
        """从环境变量加载配置

        Args:
            无（从 os.environ 读取）

        Returns:
            RedisConfig 实例

        Raises:
            ValueError: 当环境变量值无法解析为正确类型时
        """
        retry_on_timeout_env = os.getenv("REDIS_RETRY_ON_TIMEOUT", "true").lower()

        socket_timeout_str = os.getenv("REDIS_SOCKET_TIMEOUT", "5.0")
        try:
            socket_timeout = float(socket_timeout_str)
        except ValueError as e:
            raise ConfigurationError(message=f"Invalid REDIS_SOCKET_TIMEOUT value: {socket_timeout_str}") from e

        default_ttl_str = os.getenv("REDIS_DEFAULT_TTL", "86400")
        try:
            default_ttl = int(default_ttl_str)
        except ValueError as e:
            raise ConfigurationError(message=f"Invalid REDIS_DEFAULT_TTL value: {default_ttl_str}") from e

        return cls(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            password=os.getenv("REDIS_PASSWORD") or None,
            max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "100")),
            socket_timeout=socket_timeout,
            retry_on_timeout=retry_on_timeout_env in ("true", "1", "yes"),
            default_ttl=default_ttl,
        )
