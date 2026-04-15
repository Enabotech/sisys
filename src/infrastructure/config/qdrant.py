"""Qdrant 向量数据库连接配置模型。

参考 RedisConfig/PostgreSQLConfig 模式，保持配置风格一致。
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class QdrantConfig:
    """Qdrant 向量数据库连接配置。

    用于 L3 向量存储层（Qdrant 1.7+），支持异步客户端连接管理。

    字段说明:
        host: Qdrant 服务主机地址
        port: REST API 端口
        grpc_port: gRPC API 端口
        api_key: API 认证密钥（可选）
        https: 是否使用 HTTPS 连接
        timeout: 请求超时时间（秒）
        max_retries: 最大重试次数
    """

    host: str = "localhost"
    port: int = 6333
    grpc_port: int = 6334
    api_key: str | None = None
    https: bool = False
    timeout: float = 30.0
    max_retries: int = 3

    @classmethod
    def from_env(cls) -> QdrantConfig:
        """从环境变量加载配置。

        环境变量:
            QDRANT_HOST: Qdrant 主机地址 (默认: localhost)
            QDRANT_PORT: REST API 端口 (默认: 6333)
            QDRANT_GRPC_PORT: gRPC API 端口 (默认: 6334)
            QDRANT_API_KEY: API 认证密钥 (默认: None)
            QDRANT_HTTPS: 是否使用 HTTPS (默认: false)
            QDRANT_TIMEOUT: 请求超时秒数 (默认: 30.0)
            QDRANT_MAX_RETRIES: 最大重试次数 (默认: 3)

        Raises:
            ValueError: 当环境变量值无法解析为正确类型时
        """
        https_env = os.getenv("QDRANT_HTTPS", "false").lower()

        port_str = os.getenv("QDRANT_PORT", "6333")
        try:
            port = int(port_str)
        except ValueError as e:
            raise ValueError(f"Invalid QDRANT_PORT value: {port_str}") from e

        grpc_port_str = os.getenv("QDRANT_GRPC_PORT", "6334")
        try:
            grpc_port = int(grpc_port_str)
        except ValueError as e:
            raise ValueError(f"Invalid QDRANT_GRPC_PORT value: {grpc_port_str}") from e

        timeout_str = os.getenv("QDRANT_TIMEOUT", "30.0")
        try:
            timeout = float(timeout_str)
        except ValueError as e:
            raise ValueError(f"Invalid QDRANT_TIMEOUT value: {timeout_str}") from e

        max_retries_str = os.getenv("QDRANT_MAX_RETRIES", "3")
        try:
            max_retries = int(max_retries_str)
        except ValueError as e:
            raise ValueError(f"Invalid QDRANT_MAX_RETRIES value: {max_retries_str}") from e

        return cls(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=port,
            grpc_port=grpc_port,
            api_key=os.getenv("QDRANT_API_KEY") or None,
            https=https_env in ("true", "1", "yes"),
            timeout=timeout,
            max_retries=max_retries,
        )
