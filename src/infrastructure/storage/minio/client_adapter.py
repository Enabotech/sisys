"""MinIO 客户端适配器。

封装 MinIO Python SDK，提供连接池管理、错误处理和重试机制。
各组件独立 `_get_client()` 懒加载，不引入全局连接池。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from minio import Minio
from minio.error import S3Error

if TYPE_CHECKING:
    from src.infrastructure.config.minio import MinIOConfig


class BucketNotFoundError(Exception):
    """Bucket 不存在异常。"""


class PermissionDeniedError(Exception):
    """权限不足异常。"""


class ComplianceLockError(Exception):
    """WORM 合规锁定异常。"""


class MinIOConnectionError(Exception):
    """MinIO 连接错误。"""


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
        """映射 S3 错误到领域异常。

        Args:
            error: S3 原始错误

        Returns:
            映射后的领域异常
        """
        code = error.code
        if code == "NoSuchBucket":
            return BucketNotFoundError(error.message or "Bucket not found")
        if code in ("AccessDenied", "Forbidden"):
            return PermissionDeniedError(error.message or "Access denied")
        if code in ("ObjectLockConfigurationNotFoundError",):
            return ComplianceLockError(error.message or "Object lock error")
        return error

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
