"""基础设施层 Neo4j 配置模块

提供 Neo4j 图数据库连接配置，用于 L5 图存储层

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Neo4jConfig:
    """Neo4j 图数据库连接配置

    用于 L5 图存储层（Neo4j 5.x），支持连接池管理和超时配置

    Attributes:
        host: Neo4j 服务主机地址
        bolt_port: Neo4j Bolt 协议端口
        username: 认证用户名
        password: 认证密码
        database: 数据库名称
        max_connection_pool_size: 最大连接池大小
        connection_timeout: 连接超时（秒）
        max_retry_time: 最大重试时间（秒）
    """

    host: str = "localhost"
    bolt_port: int = 7687
    username: str = "neo4j"
    password: str = ""
    database: str = "neo4j"
    max_connection_pool_size: int = 50
    connection_timeout: float = 30.0
    max_retry_time: float = 30.0

    @property
    def uri(self) -> str:
        """返回 bolt://host:port 格式的 URI

        Returns:
            Neo4j Bolt URI 字符串
        """
        return f"bolt://{self.host}:{self.bolt_port}"

    @classmethod
    def from_env(cls) -> Neo4jConfig:
        """从环境变量加载配置

        Args:
            无（从 os.environ 读取）

        Returns:
            Neo4jConfig 实例

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
            host=os.getenv("NEO4J_HOST", "localhost"),
            bolt_port=int(os.getenv("NEO4J_BOLT_PORT", "7687")),
            username=os.getenv("NEO4J_USERNAME", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", ""),
            database=os.getenv("NEO4J_DATABASE", "neo4j"),
            max_connection_pool_size=max_connection_pool_size,
            connection_timeout=connection_timeout,
            max_retry_time=max_retry_time,
        )
