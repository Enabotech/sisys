"""MinIODocumentStorage — DocumentStoragePort 实现（Rule 4）

组合注入 MinIOAdapter（Rule 3），添加文档业务语义：
自动路径生成、用户文档列表、元数据管理
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
        """存储对象。"""
        return await self._adapter.store(bucket_type, object_key, file_path, content_type, tags)

    def retrieve(
        self,
        bucket_type: str,
        object_key: str,
        version_id: str | None = None,
    ):
        """流式下载对象。"""
        return self._adapter.retrieve(bucket_type, object_key, version_id)

    async def delete(
        self,
        bucket_type: str,
        object_key: str,
        version_id: str | None = None,
    ) -> bool:
        """删除对象。"""
        return await self._adapter.delete(bucket_type, object_key, version_id)

    async def get_metadata(
        self,
        bucket_type: str,
        object_key: str,
        version_id: str | None = None,
    ) -> dict:
        """获取对象元数据。"""
        return await self._adapter.get_metadata(bucket_type, object_key, version_id)

    async def archive(
        self,
        bucket_type: str,
        object_key: str,
        content: bytes | None = None,
        retention_days: int = 2555,
    ) -> str:
        """归档对象。"""
        return await self._adapter.archive(bucket_type, object_key, content, retention_days)

    async def list_objects(
        self,
        bucket_type: str,
        prefix: str = "",
        recursive: bool = True,
    ) -> list[dict]:
        """列出对象。"""
        return await self._adapter.list_objects(bucket_type, prefix, recursive)

    # -- DocumentStoragePort specific methods --

    async def store_document(
        self,
        user_id: str,
        doc_type: str,
        file_path: str,
        metadata: dict | None = None,
    ) -> str:
        """存储文档（自动生成对象路径）。"""
        now = datetime.now(UTC)
        month_key = now.strftime("%Y-%m")
        object_key = f"documents/{user_id}/{doc_type}/{month_key}/{now.strftime('%Y%m%d%H%M%S')}"

        tags = {"user_id": user_id, "doc_type": doc_type}
        if metadata:
            for k, v in metadata.items():
                tags[f"meta_{k}"] = str(v)

        await self._adapter.store("raw-documents", object_key, file_path, tags=tags)
        return object_key

    async def list_user_documents(
        self,
        user_id: str,
        doc_type: str | None = None,
    ) -> list[dict]:
        """列出用户文档。"""
        prefix = f"documents/{user_id}/"
        if doc_type:
            prefix += f"{doc_type}/"
        return await self._adapter.list_objects("raw-documents", prefix=prefix)

    async def get_document_metadata(
        self,
        user_id: str,
        document_id: str,
    ) -> dict | None:
        """获取文档元数据。"""
        try:
            return await self._adapter.get_metadata("raw-documents", document_id)
        except Exception:
            return None
