"""基础设施层 PostgreSQL 配置模块

提供 PostgreSQL 连接池配置，用于 L2 关系存储层

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class PostgreSQLConfig:
    """PostgreSQL 连接池配置

    用于 L2 关系存储层（PostgreSQL 15+），支持连接池管理和健康检查

    Attributes:
        host: 数据库主机地址
        port: 数据库端口
        database: 数据库名称
        username: 数据库用户名
        password: 数据库密码
        pool_size: 连接池大小
        max_overflow: 最大溢出连接数
        pool_timeout: 连接池超时时间（秒）
        pool_recycle: 连接回收时间（秒）
        echo: 是否输出 SQL 日志
    """

    host: str = "localhost"
    port: int = 5432
    database: str = "sisys"
    username: str = "postgres"
    password: str = ""
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: float = 30.0
    pool_recycle: int = 3600
    echo: bool = False

    @classmethod
    def from_env(cls) -> PostgreSQLConfig:
        """从环境变量加载配置

        Args:
            无（从 os.environ 读取）

        Returns:
            PostgreSQLConfig 实例
        """
        echo_env = os.getenv("POSTGRES_ECHO", "false").lower()

        return cls(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DATABASE", "sisys"),
            username=os.getenv("POSTGRES_USERNAME", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            pool_size=int(os.getenv("POSTGRES_POOL_SIZE", "5")),
            max_overflow=int(os.getenv("POSTGRES_MAX_OVERFLOW", "10")),
            pool_timeout=float(os.getenv("POSTGRES_POOL_TIMEOUT", "30.0")),
            pool_recycle=int(os.getenv("POSTGRES_POOL_RECYCLE", "3600")),
            echo=echo_env in ("true", "1", "yes"),
        )
