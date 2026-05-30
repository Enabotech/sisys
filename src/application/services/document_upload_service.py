"""应用层文档上传服务

编排文档上传流程：格式校验 → 实体构造 → MinIO 存储 → PG 元数据持久化 → 事件发布。
作为应用服务直接注册到 composition_root（非端口模式）。
"""

from __future__ import annotations

import re
import uuid
from typing import TypedDict

from src.application.ports.document_storage_port import DocumentStoragePort
from src.domain.entities.document import Document, DocumentType, ParseStatus
from src.domain.events.document_events import DocumentUploaded
from src.domain.ports.document_repository import DocumentQuery, DocumentRepositoryPort
from src.domain.ports.event_publisher import EventPublisher
from src.domain.value_objects.document_format import get_mime_type, is_supported
from src.domain.value_objects.upload_limits import MAX_FILE_SIZE, MAX_FILENAME_LENGTH

# 文件名非法字符模式
_INVALID_FILENAME_PATTERN = re.compile(r"[\x00\\/]")


class BatchFileInfo(TypedDict):
    """批量上传文件信息"""

    filename: str
    mime_type: str
    file_size_bytes: int


class _BatchDetailRequired(TypedDict):
    filename: str
    status: str


class BatchUploadDetail(_BatchDetailRequired, total=False):
    """批量上传单项结果"""

    document_id: str
    error: str


class BatchUploadResult(TypedDict):
    """批量上传结果汇总"""

    total: int
    success: int
    failed: int
    details: list[BatchUploadDetail]


class DocumentUploadService:
    """文档上传编排服务

    依赖注入 DocumentRepositoryPort + DocumentStoragePort + EventPublisher，
    编排单文件上传、批量上传和事件发布流程。
    """

    def __init__(
        self,
        document_repository: DocumentRepositoryPort,
        document_storage: DocumentStoragePort,
        event_publisher: EventPublisher,
    ) -> None:
        self._repository = document_repository
        self._storage = document_storage
        self._publisher = event_publisher

    async def upload(
        self,
        filename: str,
        mime_type: str,
        file_size_bytes: int,
        tenant_id: str,
        uploaded_by: str,
        file_path: str,
        document_type: str = "other",
    ) -> Document:
        """上传单个文件

        流程：格式校验 → 实体构造 → MinIO 存储 → PG 元数据 → 事件发布

        Args:
            filename: 原始文件名
            mime_type: 文件 MIME 类型
            file_size_bytes: 文件大小（字节）
            tenant_id: 租户标识符
            uploaded_by: 上传者用户标识符
            file_path: 临时文件路径
            document_type: 文档类型（默认 other）

        Returns:
            持久化后的 Document 实体

        Raises:
            ValueError: 格式不支持、文件大小超限、文件名非法等
        """
        self._validate_upload(filename, mime_type, file_size_bytes)

        doc = Document(
            document_id=uuid.uuid4(),
            filename=filename,
            mime_type=mime_type,
            file_size_bytes=file_size_bytes,
            document_type=DocumentType(document_type),
            parse_status=ParseStatus.PENDING,
            tenant_id=tenant_id,
            uploaded_by=uploaded_by,
        )

        await self._storage.store_document(
            user_id=uploaded_by,
            doc_type=document_type,
            file_path=file_path,
            content_type=mime_type,
        )

        saved_doc = await self._repository.save(doc)

        event = DocumentUploaded(
            document_id=saved_doc.document_id,
            filename=saved_doc.filename,
            mime_type=saved_doc.mime_type,
            file_size_bytes=saved_doc.file_size_bytes,
            tenant_id=saved_doc.tenant_id,
            uploaded_by=saved_doc.uploaded_by,
        )
        await self._publisher.publish(event)

        return saved_doc

    async def upload_batch(
        self,
        files: list[BatchFileInfo],
        tenant_id: str,
        uploaded_by: str,
        file_paths: list[str],
    ) -> BatchUploadResult:
        """批量上传文件

        每个文件独立校验、独立存储，部分失败不影响其他文件。

        Args:
            files: 文件信息列表，每个 dict 包含 filename/mime_type/file_size_bytes
            tenant_id: 租户标识符
            uploaded_by: 上传者
            file_paths: 对应的临时文件路径列表

        Returns:
            批量结果汇总

        Raises:
            ValueError: 空批量请求
        """
        if not files:
            raise ValueError("空批量请求，至少需要一个文件")

        results: list[BatchUploadDetail] = []
        success_count = 0
        failed_count = 0

        for i, file_info in enumerate(files):
            try:
                doc = await self.upload(
                    filename=file_info["filename"],
                    mime_type=file_info["mime_type"],
                    file_size_bytes=file_info["file_size_bytes"],
                    tenant_id=tenant_id,
                    uploaded_by=uploaded_by,
                    file_path=file_paths[i] if i < len(file_paths) else "",
                )
                detail: BatchUploadDetail = {
                    "filename": file_info["filename"],
                    "status": "success",
                    "document_id": str(doc.document_id),
                }
                results.append(detail)
                success_count += 1
            except (ValueError, Exception) as e:
                fail_detail: BatchUploadDetail = {
                    "filename": file_info["filename"],
                    "status": "failed",
                    "error": str(e),
                }
                results.append(fail_detail)
                failed_count += 1

        return {
            "total": len(files),
            "success": success_count,
            "failed": failed_count,
            "details": results,
        }

    async def get_document(self, document_id: uuid.UUID, tenant_id: str) -> Document | None:
        """查询文档

        Args:
            document_id: 文档 ID
            tenant_id: 租户标识符

        Returns:
            Document 实体或 None
        """
        query = DocumentQuery(tenant_id=tenant_id, document_id=document_id)
        return await self._repository.find(query)

    async def register_document(
        self,
        filename: str,
        mime_type: str,
        file_size_bytes: int,
        tenant_id: str,
        uploaded_by: str,
        document_type: str = "other",
    ) -> Document:
        """注册已上传的文档（分片上传完成后调用）

        仅执行 PG 元数据持久化和事件发布，不调用对象存储。
        文件数据已通过分片上传存储至 MinIO。

        Args:
            filename: 文件名
            mime_type: MIME 类型
            file_size_bytes: 文件大小
            tenant_id: 租户标识符
            uploaded_by: 上传者
            document_type: 文档类型

        Returns:
            持久化后的 Document 实体

        Raises:
            ValueError: 格式校验失败
        """
        self._validate_upload(filename, mime_type, file_size_bytes)

        doc = Document(
            document_id=uuid.uuid4(),
            filename=filename,
            mime_type=mime_type,
            file_size_bytes=file_size_bytes,
            document_type=DocumentType(document_type),
            parse_status=ParseStatus.PENDING,
            tenant_id=tenant_id,
            uploaded_by=uploaded_by,
        )

        saved_doc = await self._repository.save(doc)

        event = DocumentUploaded(
            document_id=saved_doc.document_id,
            filename=saved_doc.filename,
            mime_type=saved_doc.mime_type,
            file_size_bytes=saved_doc.file_size_bytes,
            tenant_id=saved_doc.tenant_id,
            uploaded_by=saved_doc.uploaded_by,
        )
        await self._publisher.publish(event)

        return saved_doc

    def _validate_upload(self, filename: str, mime_type: str, file_size_bytes: int) -> None:
        """校验上传请求的合法性"""
        if not filename or not filename.strip():
            raise ValueError("文件名不能为空")

        if len(filename) > MAX_FILENAME_LENGTH:
            raise ValueError(f"文件名长度超过限制（最大 {MAX_FILENAME_LENGTH} 字符）")

        if _INVALID_FILENAME_PATTERN.search(filename):
            raise ValueError("文件名包含非法字符")

        if not is_supported(filename, mime_type):
            expected = get_mime_type(filename)
            if expected is None:
                raise ValueError(f"不支持的格式: {filename}")
            raise ValueError(f"MIME 类型不匹配: 扩展名期望 {expected}，实际 {mime_type}")

        if file_size_bytes <= 0:
            raise ValueError("空文件，文件大小必须大于 0")

        if file_size_bytes > MAX_FILE_SIZE:
            raise ValueError(f"文件大小超过限制（最大 {MAX_FILE_SIZE // (1024**3)}GB）")
