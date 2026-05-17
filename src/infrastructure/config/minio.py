"""SISYS 基础设施层 MinIO 配置模块

提供 MinIO 对象存储连接配置，用于 L4 对象存储层

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2024-2026 SISYS. All rights reserved.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class MinIOConfig:
    """MinIO 连接配置

    用于 L4 对象存储层（MinIO），支持连接池管理和超时配置

    Attributes:
        host: MinIO 服务主机地址
        port: MinIO 服务端口
        access_key: 访问密钥
        secret_key: 密钥
        secure: 是否使用 HTTPS
        bucket_prefix: Bucket 名称前缀（用于多租户隔离）
        connect_timeout: 连接超时（秒）
        read_timeout: 读取超时（秒）
    """

    host: str = "localhost"
    port: int = 9000
    access_key: str = ""
    secret_key: str = ""
    secure: bool = False
    bucket_prefix: str = "sisys"
    connect_timeout: float = 5.0
    read_timeout: float = 30.0

    @property
    def endpoint(self) -> str:
        """返回 host:port 格式的 endpoint

        Returns:
            MinIO endpoint 字符串
        """
        return f"{self.host}:{self.port}"

    @classmethod
    def from_env(cls) -> MinIOConfig:
        """从环境变量加载配置

        Args:
            无（从 os.environ 读取）

        Returns:
            MinIOConfig 实例

        Raises:
            ValueError: 当环境变量值无法解析为正确类型时
        """
        connect_timeout_str = os.getenv("MINIO_CONNECT_TIMEOUT", "5.0")
        try:
            connect_timeout = float(connect_timeout_str)
        except ValueError as e:
            raise ValueError(f"Invalid MINIO_CONNECT_TIMEOUT value: {connect_timeout_str}") from e

        read_timeout_str = os.getenv("MINIO_READ_TIMEOUT", "30.0")
        try:
            read_timeout = float(read_timeout_str)
        except ValueError as e:
            raise ValueError(f"Invalid MINIO_READ_TIMEOUT value: {read_timeout_str}") from e

        return cls(
            host=os.getenv("MINIO_HOST", "localhost"),
            port=int(os.getenv("MINIO_API_PORT", "9000")),
            access_key=os.getenv("MINIO_ROOT_USER", ""),
            secret_key=os.getenv("MINIO_ROOT_PASSWORD", ""),
            secure=os.getenv("MINIO_SECURE", "false").lower() in ("true", "1", "yes"),
            bucket_prefix=os.getenv("MINIO_BUCKET_PREFIX", "sisys"),
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
        )
