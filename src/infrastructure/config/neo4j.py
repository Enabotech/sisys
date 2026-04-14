"""Neo4j 图数据库连接配置模型。

参考 Story 1.4 RedisConfig / Story 1.5 PostgreSQLConfig / Story 1.6 QdrantConfig / Story 1.7 MinIOConfig 模式，
保持配置风格一致。
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Neo4jConfig:
    """Neo4j 图数据库连接配置。

    用于 L5 图存储层（Neo4j 5.x），支持连接池管理和超时配置。

    字段说明:
        uri: Neo4j 服务地址（bolt://host:port 或 neo4j://host:port）
        username: 认证用户名
        password: 认证密码
        database: 数据库名称
        max_connection_pool_size: 最大连接池大小
        connection_timeout: 连接超时（秒）
        max_retry_time: 最大重试时间（秒）
    """

    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: str = ""
    database: str = "neo4j"
    max_connection_pool_size: int = 50
    connection_timeout: float = 30.0
    max_retry_time: float = 30.0

    @classmethod
    def from_env(cls) -> Neo4jConfig:
        """从环境变量加载配置。

        环境变量:
            NEO4J_URI: Neo4j 服务地址 (默认: bolt://localhost:7687)
            NEO4J_USERNAME: 认证用户名 (默认: neo4j)
            NEO4J_PASSWORD: 认证密码 (默认: 空字符串)
            NEO4J_DATABASE: 数据库名称 (默认: neo4j)
            NEO4J_MAX_POOL_SIZE: 最大连接池大小 (默认: 50)
            NEO4J_CONNECT_TIMEOUT: 连接超时秒数 (默认: 30.0)
            NEO4J_MAX_RETRY_TIME: 最大重试时间秒数 (默认: 30.0)

        Raises:
            ValueError: 当环境变量值无法解析为正确类型时
        """
        max_pool_size_str = os.getenv("NEO4J_MAX_POOL_SIZE", "50")
        try:
            max_connection_pool_size = int(max_pool_size_str)
        except ValueError as e:
            raise ValueError(f"Invalid NEO4J_MAX_POOL_SIZE value: {max_pool_size_str}") from e

        connection_timeout_str = os.getenv("NEO4J_CONNECT_TIMEOUT", "30.0")
        try:
            connection_timeout = float(connection_timeout_str)
        except ValueError as e:
            raise ValueError(f"Invalid NEO4J_CONNECT_TIMEOUT value: {connection_timeout_str}") from e

        max_retry_time_str = os.getenv("NEO4J_MAX_RETRY_TIME", "30.0")
        try:
            max_retry_time = float(max_retry_time_str)
        except ValueError as e:
            raise ValueError(f"Invalid NEO4J_MAX_RETRY_TIME value: {max_retry_time_str}") from e

        return cls(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            username=os.getenv("NEO4J_USERNAME", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", ""),
            database=os.getenv("NEO4J_DATABASE", "neo4j"),
            max_connection_pool_size=max_connection_pool_size,
            connection_timeout=connection_timeout,
            max_retry_time=max_retry_time,
        )
