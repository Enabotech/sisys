"""基础设施层 MinIO 文档存储模块

实现 DocumentStoragePort 接口，组合 MinIOAdapter 并添加文档业务语义：
自动路径生成、用户文档列表和元数据管理
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.application.ports.document_storage_port import DocumentStoragePort

if TYPE_CHECKING:
    from src.infrastructure.storage.minio.minio_adapter import MinIOAdapter


class MinIODocumentStorage(DocumentStoragePort):
    """MinIO 文档存储 — 实现 DocumentStoragePort

    组合 MinIOAdapter（Rule 3，L4ObjectPort 实现），
    添加文档业务语义：自动路径生成、用户文档列表
    """

    def __init__(self, adapter: MinIOAdapter):
        """初始化 MinIODocumentStorage

        Args:
            adapter: MinIOAdapter 实例（Rule 3）
        """
        self._adapter = adapter

    # -- L4ObjectPort methods (delegate to adapter) --

    async def store(
        self,
        bucket_type: str,
        object_key: str,
        file_path: str,
        content_type: str = "application/octet-stream",
        tags: dict[str, str] | None = None,
    ) -> str:
        """存储对象

        Args:
            bucket_type: Bucket 类型
            object_key: 对象键
            file_path: 本地文件路径
            content_type: MIME 类型
            tags: 对象标签

        Returns:
            版本 ID 或 ETag
        """
        return await self._adapter.store(bucket_type, object_key, file_path, content_type, tags)

    def retrieve(
        self,
        bucket_type: str,
        object_key: str,
        version_id: str | None = None,
    ):
        """流式下载对象

        Args:
            bucket_type: Bucket 类型
            object_key: 对象键
            version_id: 版本 ID

        Returns:
            字节流异步迭代器
        """
        return self._adapter.retrieve(bucket_type, object_key, version_id)

    async def delete(
        self,
        bucket_type: str,
        object_key: str,
        version_id: str | None = None,
    ) -> bool:
        """删除对象

        Args:
            bucket_type: Bucket 类型
            object_key: 对象键
            version_id: 版本 ID

        Returns:
            是否成功
        """
        return await self._adapter.delete(bucket_type, object_key, version_id)

    async def get_metadata(
        self,
        bucket_type: str,
        object_key: str,
        version_id: str | None = None,
    ) -> dict:
        """获取对象元数据

        Args:
            bucket_type: Bucket 类型
            object_key: 对象键
            version_id: 版本 ID

        Returns:
            元数据字典
        """
        return await self._adapter.get_metadata(bucket_type, object_key, version_id)

    async def archive(
        self,
        bucket_type: str,
        object_key: str,
        content: bytes | None = None,
        retention_days: int = 2555,
    ) -> str:
        """归档对象

        Args:
            bucket_type: Bucket 类型
            object_key: 对象键
            content: 对象内容，None 表示只设置 retention
            retention_days: retention 天数

        Returns:
            对象 ID 或 ETag
        """
        return await self._adapter.archive(bucket_type, object_key, content, retention_days)

    async def list_objects(
        self,
        bucket_type: str,
        prefix: str = "",
        recursive: bool = True,
    ) -> list[dict]:
        """列出对象

        Args:
            bucket_type: Bucket 类型
            prefix: 前缀过滤
            recursive: 是否递归列出子目录

        Returns:
            对象元数据列表
        """
        return await self._adapter.list_objects(bucket_type, prefix, recursive)

    # -- DocumentStoragePort specific methods --

    async def store_document(
        self,
        user_id: str,
        doc_type: str,
        file_path: str,
        content_type: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """存储文档并自动生成对象路径

        路径格式: documents/{user_id}/{doc_type}/{YYYY-MM}/{timestamp}

        Args:
            user_id: 用户 ID
            doc_type: 文档类型
            file_path: 本地文件路径
            content_type: 文件 MIME 类型（默认 application/octet-stream）
            metadata: 附加元数据（将作为对象标签存储）

        Returns:
            生成的对象键
        """
        now = datetime.now(UTC)
        month_key = now.strftime("%Y-%m")
        object_key = f"documents/{user_id}/{doc_type}/{month_key}/{now.strftime('%Y%m%d%H%M%S')}"

        tags = {"user_id": user_id, "doc_type": doc_type}
        if metadata:
            for k, v in metadata.items():
                tags[f"meta_{k}"] = str(v)

        resolved_content_type = content_type or "application/octet-stream"
        await self._adapter.store("raw-documents", object_key, file_path, content_type=resolved_content_type, tags=tags)
        return object_key

    async def list_user_documents(
        self,
        user_id: str,
        doc_type: str | None = None,
    ) -> list[dict]:
        """列出用户文档

        Args:
            user_id: 用户 ID
            doc_type: 可选文档类型过滤

        Returns:
            文档对象元数据列表
        """
        prefix = f"documents/{user_id}/"
        if doc_type:
            prefix += f"{doc_type}/"
        return await self._adapter.list_objects("raw-documents", prefix=prefix)

    async def get_document_metadata(
        self,
        user_id: str,
        document_id: str,
    ) -> dict | None:
        """获取文档元数据

        Args:
            user_id: 用户 ID
            document_id: 文档对象键

        Returns:
            文档元数据字典，不存在返回 None
        """
        try:
            return await self._adapter.get_metadata("raw-documents", document_id)
        except Exception:
            return None
