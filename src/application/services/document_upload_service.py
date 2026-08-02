"""应用层文档上传服务

编排文档上传流程：格式校验 → 实体构造 → MinIO 存储 → PG 元数据持久化 → 事件发布。
作为应用服务直接注册到 composition_root（非端口模式）。
"""

from __future__ import annotations

import asyncio
import os
import re
import uuid
from typing import Any, TypedDict

from src.application.ports.document_storage_port import DocumentStoragePort
from src.domain.entities.document import Document, DocumentType, ParseStatus
from src.domain.events.document_events import DocumentUploaded
from src.domain.exceptions import ValidationError
from src.domain.ports.document_repository import DocumentQuery, DocumentRepositoryPort
from src.domain.ports.event_publisher import EventPublisher
from src.domain.value_objects.document_format import get_mime_type, is_supported
from src.domain.value_objects.document_metadata import DocumentMetadata
from src.domain.value_objects.upload_limits import MAX_BATCH_SIZE, MAX_FILE_SIZE, MAX_FILENAME_LENGTH

# 文件名非法字符模式
_INVALID_FILENAME_PATTERN = re.compile(r"[\x00\\/]")

# 批量上传并发数
_BATCH_CONCURRENCY = 20

# 元数据校验模式（灰度日志模式：校验失败仅记录日志，不阻断上传）
_VALIDATION_MODE = os.getenv("METADATA_VALIDATION_MODE", "enforce")


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
        metadata: dict[str, Any] | None = None,
    ) -> Document:
        """上传单个文件

        流程：格式校验 → 实体构造 → 元数据校验 → MinIO 存储 → PG 元数据 → 事件发布

        Args:
            filename: 原始文件名
            mime_type: 文件 MIME 类型
            file_size_bytes: 文件大小（字节）
            tenant_id: 租户标识符
            uploaded_by: 上传者用户标识符
            file_path: 临时文件路径
            document_type: 文档类型（默认 other）
            metadata: 文档元数据字典（可选，包含 creator/created_at/source/license/business_domain）

        Returns:
            持久化后的 Document 实体

        Raises:
            ValidationError: 格式不支持、文件大小超限、文件名非法等
            MetadataValidationError: 元数据缺失或不合法
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

        # 元数据校验（MinIO 存储前）
        self._validate_and_apply_metadata(doc, metadata, uploaded_by)

        object_key = await self._storage.store_document(
            user_id=uploaded_by,
            doc_type=document_type,
            file_path=file_path,
            content_type=mime_type,
        )
        doc.metadata["storage_object_key"] = object_key

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
        metadata_list: list[dict[str, Any] | None] | None = None,
    ) -> BatchUploadResult:
        """批量上传文件

        每个文件独立校验、独立存储，部分失败不影响其他文件。
        使用 asyncio.Semaphore 控制并发数（≥20）。

        Args:
            files: 文件信息列表，每个 dict 包含 filename/mime_type/file_size_bytes
            tenant_id: 租户标识符
            uploaded_by: 上传者
            file_paths: 对应的临时文件路径列表
            metadata_list: 每个文件的元数据字典列表（可选，索引与 files 对齐）

        Returns:
            批量结果汇总

        Raises:
            ValidationError: 空批量请求、总大小超限
        """
        if not files:
            raise ValidationError(message="空批量请求，至少需要一个文件")

        # 校验总大小限制
        total_size = sum(f["file_size_bytes"] for f in files)
        if total_size > MAX_BATCH_SIZE:
            raise ValidationError(message=f"批量上传总大小超过限制（最大 {MAX_BATCH_SIZE // (1024**3)}GB）")

        # 使用 Semaphore 控制并发
        semaphore = asyncio.Semaphore(_BATCH_CONCURRENCY)

        async def upload_with_semaphore(index: int, file_info: BatchFileInfo) -> BatchUploadDetail:
            """带并发控制的单文件上传"""
            async with semaphore:
                try:
                    meta = metadata_list[index] if metadata_list and index < len(metadata_list) else None
                    doc = await self.upload(
                        filename=file_info["filename"],
                        mime_type=file_info["mime_type"],
                        file_size_bytes=file_info["file_size_bytes"],
                        tenant_id=tenant_id,
                        uploaded_by=uploaded_by,
                        file_path=file_paths[index] if index < len(file_paths) else "",
                        metadata=meta,
                    )
                    return {
                        "filename": file_info["filename"],
                        "status": "success",
                        "document_id": str(doc.document_id),
                    }
                except Exception as e:
                    return {
                        "filename": file_info["filename"],
                        "status": "failed",
                        "error": str(e),
                    }

        # 并发执行所有上传任务
        tasks = [upload_with_semaphore(i, f) for i, f in enumerate(files)]
        results: list[BatchUploadDetail] = await asyncio.gather(*tasks)

        success_count = sum(1 for r in results if r["status"] == "success")
        failed_count = len(results) - success_count

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
        object_key: str = "",
        metadata: dict[str, Any] | None = None,
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
            object_key: MinIO 对象键（分片上传完成后获取）
            metadata: 文档元数据字典（可选，分片上传在 init 时传入）

        Returns:
            持久化后的 Document 实体

        Raises:
            ValidationError: 格式校验失败
            MetadataValidationError: 元数据缺失或不合法
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

        # 元数据校验（PG 持久化前）
        self._validate_and_apply_metadata(doc, metadata, uploaded_by)

        if object_key:
            doc.metadata["storage_object_key"] = object_key

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
            raise ValidationError(message="文件名不能为空")

        if len(filename) > MAX_FILENAME_LENGTH:
            raise ValidationError(message=f"文件名长度超过限制（最大 {MAX_FILENAME_LENGTH} 字符）")

        if _INVALID_FILENAME_PATTERN.search(filename):
            raise ValidationError(message="文件名包含非法字符")

        if not is_supported(filename, mime_type):
            expected = get_mime_type(filename)
            if expected is None:
                raise ValidationError(message=f"不支持的格式: {filename}")
            raise ValidationError(message=f"MIME 类型不匹配: 扩展名期望 {expected}，实际 {mime_type}")

        if file_size_bytes <= 0:
            raise ValidationError(message="空文件，文件大小必须大于 0")

        if file_size_bytes > MAX_FILE_SIZE:
            raise ValidationError(message=f"文件大小超过限制（最大 {MAX_FILE_SIZE // (1024**3)}GB）")

    def _validate_and_apply_metadata(
        self,
        doc: Document,
        metadata: dict[str, Any] | None,
        uploaded_by: str,
    ) -> None:
        """校验并应用元数据到文档实体。

        使用 DocumentMetadata 值对象执行校验：
        1. 调用 from_upload() 自动填充 creator/created_at
        2. 执行 validate() 校验最小元字段集
        3. 校验通过后将元数据拷贝到 Document 实体

        支持灰度日志模式（METADATA_VALIDATION_MODE=log_only）：
        校验失败仅记录 WARNING 日志，不阻断上传。

        Args:
            doc: 文档实体（将在校验通过后写入 metadata）
            metadata: 原始元数据字典
            uploaded_by: 上传者标识符

        Raises:
            MetadataValidationError: 元数据校验失败
        """
        import logging

        logger = logging.getLogger(__name__)

        doc_metadata = DocumentMetadata.from_upload(
            document_id=doc.document_id,
            raw_metadata=metadata,
            uploaded_by=uploaded_by,
        )
        if _VALIDATION_MODE == "log_only":
            missing = doc_metadata.validate(raise_on_error=False)
            if missing:
                logger.warning(
                    "元数据校验失败（灰度模式）: document_id=%s, missing_fields=%s",
                    doc.document_id,
                    missing,
                )
        else:
            doc_metadata.validate()

        doc.metadata = dict(doc_metadata.metadata)
