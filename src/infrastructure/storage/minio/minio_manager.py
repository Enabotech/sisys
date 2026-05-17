"""基础设施层 MinIO 客户端管理模块

封装 MinIO Python SDK，提供连接池管理、S3 错误映射和健康检查功能

Author:
    agimtech <agimtech@126.com>

Copyright:
    Copyright (c) 2025-2026 AGIMTECH. All rights reserved.

"""

from __future__ import annotations

from minio import Minio
from minio.error import S3Error

from src.domain.exceptions import InvalidStateError, NotFoundError, PermissionDeniedError
from src.domain.exceptions.external_exceptions import ThirdPartyError
from src.domain.exceptions.service_exceptions import ComplianceLockError
from src.domain.exceptions.storage_exceptions import (
    BucketNotFoundError,
    MinIOConnectionError,
)
from src.infrastructure.config.minio import MinIOConfig
from src.infrastructure.messaging.error_mapper import ErrorMapper

__all__ = [
    "BucketNotFoundError",
    "PermissionDeniedError",
    "ComplianceLockError",
    "MinIOConnectionError",
]


class MinioManager:
    """MinIO 客户端适配器

    封装 MinIO Python SDK，提供：
    - 客户端实例注入（符合 Cosmic Python DI 模式）
    - S3 错误映射
    - 健康检查
    """

    def __init__(self, client: Minio) -> None:
        """初始化客户端适配器

        Args:
            client: Minio 客户端实例
        """
        self._client = client

    @classmethod
    def from_config(cls, config: MinIOConfig) -> MinioManager:
        """从配置创建适配器实例（生产环境入口）

        Args:
            config: MinIO 连接配置

        Returns:
            MinioManager 实例
        """
        client = Minio(
            config.endpoint,
            access_key=config.access_key,
            secret_key=config.secret_key,
            secure=config.secure,
        )
        return cls(client)

    @property
    def client(self) -> Minio:
        """MinIO 客户端属性

        Returns:
            MinIO 客户端实例
        """
        return self._client

    @staticmethod
    def _map_error(error: S3Error) -> Exception:
        """映射 S3 错误到领域异常（使用 ErrorMapper + legacy 异常）

        Args:
            error: S3 原始错误

        Returns:
            映射后的领域异常
        """
        code = error.code or "Unknown"
        message = error.message or f"S3 error: {code}"

        # 使用 ErrorMapper 获取异常类，再实例化 legacy 异常以保持接口兼容
        exc_class = ErrorMapper.S3_ERROR_MAP.get(code.lower(), ThirdPartyError)

        # 根据异常类型选择 legacy 包装类
        if exc_class is NotFoundError:
            return BucketNotFoundError(message)
        if exc_class is PermissionDeniedError:
            return PermissionDeniedError(message)
        if exc_class is InvalidStateError:
            return ComplianceLockError(message)
        if exc_class is ThirdPartyError:
            return ThirdPartyError(message=message)
        # 其他情况直接实例化
        return exc_class(message=message)

    def health_check(self) -> bool:
        """健康检查

        Returns:
            连接是否正常
        """
        try:
            # 尝试列出 bucket（不要求任何 bucket 存在）
            self._client.list_buckets()
            return True
        except Exception:
            return False
