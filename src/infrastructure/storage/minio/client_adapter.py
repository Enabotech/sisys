"""MinIO 客户端适配器。

封装 MinIO Python SDK，提供连接池管理、错误处理和重试机制。
各组件独立 `_get_client()` 懒加载，不引入全局连接池。
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


class MinioClientAdapter:
    """MinIO 客户端适配器。

    封装 MinIO Python SDK，提供：
    - 独立懒加载连接池（与 Story 1.3/1.4 一致）
    - S3 错误映射
    - 健康检查
    """

    def __init__(self, config: MinIOConfig) -> None:
        """初始化客户端适配器。

        Args:
            config: MinIO 连接配置
        """
        self._config = config
        self._client: Minio | None = None

    def _get_client(self) -> Minio:
        """获取或创建 MinIO 客户端（懒加载）。

        Returns:
            MinIO 客户端实例
        """
        if self._client is None:
            self._client = Minio(
                self._config.endpoint,
                access_key=self._config.access_key,
                secret_key=self._config.secret_key,
                secure=self._config.secure,
            )
        return self._client

    @property
    def client(self) -> Minio:
        """MinIO 客户端属性。

        Returns:
            MinIO 客户端实例
        """
        return self._get_client()

    @staticmethod
    def _map_error(error: S3Error) -> Exception:
        """映射 S3 错误到领域异常（使用 ErrorMapper + legacy 异常）。

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
        """健康检查。

        Returns:
            连接是否正常
        """
        try:
            # 尝试列出 bucket（不要求任何 bucket 存在）
            self._get_client().list_buckets()
            return True
        except Exception:
            return False
