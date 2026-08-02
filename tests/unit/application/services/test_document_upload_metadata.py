"""Story 2-7 TDD 单元测试 — DocumentUploadService 元数据校验集成

验证 DocumentUploadService 的 upload()/register_document()/upload_batch() 方法
在集成元数据校验后的行为。

Run with: poetry run pytest tests/unit/application/services/test_document_upload_metadata.py -v
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.domain.entities.document import Document, DocumentType, ParseStatus
from src.domain.ports.document_repository import DocumentRepositoryPort
from src.domain.ports.event_publisher import EventPublisher


def _make_upload_service(
    repo_mock: AsyncMock | None = None,
    storage_mock: AsyncMock | None = None,
    publisher_mock: AsyncMock | None = None,
):
    """创建 DocumentUploadService 实例，依赖全部 Mock

    Args:
        repo_mock: DocumentRepositoryPort Mock
        storage_mock: DocumentStoragePort Mock
        publisher_mock: EventPublisher Mock

    Returns:
        DocumentUploadService 实例
    """
    from src.application.ports.document_storage_port import DocumentStoragePort
    from src.application.services.document_upload_service import DocumentUploadService

    repo = repo_mock or AsyncMock(spec=DocumentRepositoryPort)
    repo.save = AsyncMock(side_effect=lambda d: d)
    repo.find = AsyncMock(return_value=None)
    repo.list = AsyncMock(return_value=[])
    storage = storage_mock or AsyncMock(spec=DocumentStoragePort)
    storage.store_document = AsyncMock(return_value=f"test-object-key-{uuid4().hex}")
    publisher = publisher_mock or AsyncMock(spec=EventPublisher)
    publisher.publish = AsyncMock()
    return DocumentUploadService(
        document_repository=repo,
        document_storage=storage,
        event_publisher=publisher,
    )


def _make_doc(
    document_id=None,
    filename="test.pdf",
    mime_type="application/pdf",
    file_size=1024,
    tenant_id="test-tenant",
    uploaded_by="test-user",
):
    """创建 Document 实体辅助函数"""
    return Document(
        document_id=document_id or uuid4(),
        filename=filename,
        mime_type=mime_type,
        file_size_bytes=file_size,
        document_type=DocumentType.OTHER,
        parse_status=ParseStatus.PENDING,
        tenant_id=tenant_id,
        uploaded_by=uploaded_by,
    )


class TestUploadMetadataIntegration:
    """验证 upload() 方法集成元数据校验"""

    @pytest.mark.asyncio
    async def test_upload_with_complete_metadata_success(self) -> None:
        """验证完整 metadata 上传成功"""
        svc = _make_upload_service()
        metadata = {
            "creator": "test-user",
            "created_at": "2024-01-15T10:30:00Z",
            "source": "internal",
            "license": "confidential",
            "business_domain": "finance",
        }
        doc = await svc.upload(
            filename="test.pdf",
            mime_type="application/pdf",
            file_size_bytes=1024,
            tenant_id="tenant-1",
            uploaded_by="user-1",
            file_path="/tmp/test.pdf",
            metadata=metadata,
        )
        assert doc is not None
        assert doc.metadata.get("source") == "internal"
        assert doc.metadata.get("license") == "confidential"

    @pytest.mark.asyncio
    async def test_upload_with_autofill_success(self) -> None:
        """验证部分 metadata + 自动填充成功"""
        svc = _make_upload_service()
        metadata = {
            "source": "internal",
            "license": "confidential",
            "business_domain": "finance",
        }
        doc = await svc.upload(
            filename="test.pdf",
            mime_type="application/pdf",
            file_size_bytes=1024,
            tenant_id="tenant-1",
            uploaded_by="user-1",
            file_path="/tmp/test.pdf",
            metadata=metadata,
        )
        assert doc is not None
        assert doc.metadata.get("creator") == "user-1"  # 自动填充
        assert "created_at" in doc.metadata  # 自动填充

    @pytest.mark.asyncio
    async def test_upload_missing_metadata_blocks_and_no_side_effects(self) -> None:
        """验证缺失必需字段时阻断（无 MinIO 存储、无 PG 持久化）"""
        from src.domain.exceptions.storage_exceptions import MetadataValidationError

        svc = _make_upload_service()
        metadata = {
            "creator": "test-user",
            "created_at": "2024-01-15T10:30:00Z",
            "source": "internal",
            # 缺少 license 和 business_domain
        }
        with pytest.raises(MetadataValidationError) as exc_info:
            await svc.upload(
                filename="test.pdf",
                mime_type="application/pdf",
                file_size_bytes=1024,
                tenant_id="tenant-1",
                uploaded_by="user-1",
                file_path="/tmp/test.pdf",
                metadata=metadata,
            )
        # 验证 MinIO 存储未被调用（校验在 MinIO 前执行）
        svc._storage.store_document.assert_not_called()
        # 验证 PG 持久化未被调用
        svc._repository.save.assert_not_called()
        # 验证异常包含缺失字段
        assert "license" in exc_info.value.context["missing_fields"]
        assert "business_domain" in exc_info.value.context["missing_fields"]

    @pytest.mark.asyncio
    async def test_upload_empty_value_blocks(self) -> None:
        """验证空字符串值阻断"""
        from src.domain.exceptions.storage_exceptions import MetadataValidationError

        svc = _make_upload_service()
        metadata = {
            "creator": "test-user",
            "created_at": "2024-01-15T10:30:00Z",
            "source": "",
            "license": "confidential",
            "business_domain": "finance",
        }
        with pytest.raises(MetadataValidationError) as exc_info:
            await svc.upload(
                filename="test.pdf",
                mime_type="application/pdf",
                file_size_bytes=1024,
                tenant_id="tenant-1",
                uploaded_by="user-1",
                file_path="/tmp/test.pdf",
                metadata=metadata,
            )
        assert "source" in exc_info.value.context["missing_fields"]

    @pytest.mark.asyncio
    async def test_upload_no_metadata_autofills_and_blocks(self) -> None:
        """验证不传 metadata 时自动填充 creator/created_at 但阻断"""
        from src.domain.exceptions.storage_exceptions import MetadataValidationError

        svc = _make_upload_service()
        with pytest.raises(MetadataValidationError) as exc_info:
            await svc.upload(
                filename="test.pdf",
                mime_type="application/pdf",
                file_size_bytes=1024,
                tenant_id="tenant-1",
                uploaded_by="user-1",
                file_path="/tmp/test.pdf",
            )
        missing = exc_info.value.context["missing_fields"]
        assert "source" in missing
        assert "license" in missing
        assert "business_domain" in missing
        # MinIO 不应被调用（校验在 MinIO 前执行）
        svc._storage.store_document.assert_not_called()

    @pytest.mark.asyncio
    async def test_upload_with_metadata_preserves_existing_behavior(self) -> None:
        """验证完整 metadata 时原有上传成功路径不变"""
        svc = _make_upload_service()
        metadata = {
            "creator": "test-user",
            "created_at": "2024-01-15T10:30:00Z",
            "source": "internal",
            "license": "confidential",
            "business_domain": "finance",
        }
        doc = await svc.upload(
            filename="test.pdf",
            mime_type="application/pdf",
            file_size_bytes=1024,
            tenant_id="tenant-1",
            uploaded_by="user-1",
            file_path="/tmp/test.pdf",
            metadata=metadata,
        )
        # MinIO 存储被调用
        svc._storage.store_document.assert_called_once()
        # PG 持久化被调用
        svc._repository.save.assert_called_once()
        # 事件发布被调用
        svc._publisher.publish.assert_called_once()
        assert doc.metadata.get("source") == "internal"

    @pytest.mark.asyncio
    async def test_upload_log_only_mode_does_not_block(self) -> None:
        """验证灰度日志模式（log_only）下校验失败不阻断上传"""
        svc = _make_upload_service()
        # 设置 log_only 模式
        svc._validation_mode = "log_only"
        # 不传 metadata 触发校验失败，但应不阻断
        doc = await svc.upload(
            filename="test.pdf",
            mime_type="application/pdf",
            file_size_bytes=1024,
            tenant_id="tenant-1",
            uploaded_by="user-1",
            file_path="/tmp/test.pdf",
        )
        # 上传仍成功（不抛出异常）
        assert doc is not None
        # MinIO 存储被调用
        svc._storage.store_document.assert_called_once()
        # PG 持久化被调用
        svc._repository.save.assert_called_once()


class TestRegisterDocumentMetadataIntegration:
    """验证 register_document() 方法集成元数据校验"""

    @pytest.mark.asyncio
    async def test_register_document_with_complete_metadata_success(self) -> None:
        """验证完整 metadata 注册成功"""
        svc = _make_upload_service()
        metadata = {
            "creator": "test-user",
            "created_at": "2024-01-15T10:30:00Z",
            "source": "internal",
            "license": "confidential",
            "business_domain": "finance",
        }
        doc = await svc.register_document(
            filename="test.pdf",
            mime_type="application/pdf",
            file_size_bytes=1024,
            tenant_id="tenant-1",
            uploaded_by="user-1",
            object_key="test-object-key",
            metadata=metadata,
        )
        assert doc is not None
        assert doc.metadata.get("source") == "internal"

    @pytest.mark.asyncio
    async def test_register_document_with_autofill_success(self) -> None:
        """验证部分 metadata + 自动填充注册成功"""
        svc = _make_upload_service()
        metadata = {
            "source": "internal",
            "license": "confidential",
            "business_domain": "finance",
        }
        doc = await svc.register_document(
            filename="test.pdf",
            mime_type="application/pdf",
            file_size_bytes=1024,
            tenant_id="tenant-1",
            uploaded_by="user-1",
            object_key="test-object-key",
            metadata=metadata,
        )
        assert doc is not None
        assert doc.metadata.get("creator") == "user-1"

    @pytest.mark.asyncio
    async def test_register_document_missing_metadata_blocks(self) -> None:
        """验证缺失必需字段时阻断"""
        from src.domain.exceptions.storage_exceptions import MetadataValidationError

        svc = _make_upload_service()
        metadata = {
            "creator": "test-user",
            "created_at": "2024-01-15T10:30:00Z",
            "source": "internal",
        }
        with pytest.raises(MetadataValidationError) as exc_info:
            await svc.register_document(
                filename="test.pdf",
                mime_type="application/pdf",
                file_size_bytes=1024,
                tenant_id="tenant-1",
                uploaded_by="user-1",
                object_key="test-object-key",
                metadata=metadata,
            )
        missing = exc_info.value.context["missing_fields"]
        assert "license" in missing
        assert "business_domain" in missing

    @pytest.mark.asyncio
    async def test_register_document_no_metadata_blocks(self) -> None:
        """验证不传 metadata 时阻断"""
        from src.domain.exceptions.storage_exceptions import MetadataValidationError

        svc = _make_upload_service()
        with pytest.raises(MetadataValidationError) as exc_info:
            await svc.register_document(
                filename="test.pdf",
                mime_type="application/pdf",
                file_size_bytes=1024,
                tenant_id="tenant-1",
                uploaded_by="user-1",
                object_key="test-object-key",
            )
        missing = exc_info.value.context["missing_fields"]
        assert "source" in missing
        assert "license" in missing
        assert "business_domain" in missing


class TestUploadBatchMetadataIntegration:
    """验证 upload_batch() 方法集成元数据校验"""

    @pytest.mark.asyncio
    async def test_upload_batch_with_metadata_list_success(self) -> None:
        """验证批量上传 metadata_list 传递成功"""
        svc = _make_upload_service()
        file_infos = [
            {"filename": "doc1.pdf", "mime_type": "application/pdf", "file_size_bytes": 100},
            {"filename": "doc2.pdf", "mime_type": "application/pdf", "file_size_bytes": 200},
        ]
        metadata_list = [
            {
                "creator": "user1",
                "created_at": "2024-01-15T10:30:00Z",
                "source": "internal",
                "license": "confidential",
                "business_domain": "finance",
            },
            {
                "creator": "user2",
                "created_at": "2024-01-16T11:00:00Z",
                "source": "external",
                "license": "public",
                "business_domain": "marketing",
            },
        ]
        result = await svc.upload_batch(
            files=file_infos,
            tenant_id="tenant-1",
            uploaded_by="user-1",
            file_paths=["/tmp/doc1.pdf", "/tmp/doc2.pdf"],
            metadata_list=metadata_list,
        )
        assert result["success"] == 2
        assert result["failed"] == 0

    @pytest.mark.asyncio
    async def test_upload_batch_metadata_index_alignment(self) -> None:
        """验证 metadata_list 索引与文件一一对应"""
        svc = _make_upload_service()
        file_infos = [
            {"filename": "doc1.pdf", "mime_type": "application/pdf", "file_size_bytes": 100},
            {"filename": "doc2.pdf", "mime_type": "application/pdf", "file_size_bytes": 200},
        ]
        metadata_list = [
            {
                "creator": "user1",
                "created_at": "2024-01-15T10:30:00Z",
                "source": "internal",
                "license": "confidential",
                "business_domain": "finance",
            },
            None,  # 第二个文件无 metadata
        ]
        result = await svc.upload_batch(
            files=file_infos,
            tenant_id="tenant-1",
            uploaded_by="user-1",
            file_paths=["/tmp/doc1.pdf", "/tmp/doc2.pdf"],
            metadata_list=metadata_list,
        )
        # 第一个文件（有完整 metadata）成功，第二个文件（无 metadata）失败
        assert result["success"] == 1
        assert result["failed"] == 1

    @pytest.mark.asyncio
    async def test_upload_batch_mixed_metadata(self) -> None:
        """验证混合场景：部分文件有 metadata、部分文件无 metadata"""
        svc = _make_upload_service()
        file_infos = [
            {"filename": "doc1.pdf", "mime_type": "application/pdf", "file_size_bytes": 100},
            {"filename": "doc2.pdf", "mime_type": "application/pdf", "file_size_bytes": 200},
            {"filename": "doc3.pdf", "mime_type": "application/pdf", "file_size_bytes": 300},
        ]
        metadata_list = [
            None,  # 无 metadata
            {
                "creator": "user2",
                "created_at": "2024-01-16T11:00:00Z",
                "source": "external",
                "license": "public",
                "business_domain": "marketing",
            },
            None,  # 无 metadata
        ]
        result = await svc.upload_batch(
            files=file_infos,
            tenant_id="tenant-1",
            uploaded_by="user-1",
            file_paths=["/tmp/doc1.pdf", "/tmp/doc2.pdf", "/tmp/doc3.pdf"],
            metadata_list=metadata_list,
        )
        # 只有第二个文件有完整 metadata 能成功
        assert result["success"] == 1
        assert result["failed"] == 2

    @pytest.mark.asyncio
    async def test_upload_batch_metadata_list_longer_than_files(self) -> None:
        """验证 metadata_list 长度大于 files 时超出部分被忽略"""
        svc = _make_upload_service()
        file_infos = [
            {"filename": "doc1.pdf", "mime_type": "application/pdf", "file_size_bytes": 100},
        ]
        metadata_list = [
            {
                "creator": "user1",
                "created_at": "2024-01-15T10:30:00Z",
                "source": "internal",
                "license": "confidential",
                "business_domain": "finance",
            },
            None,  # 超出部分，应被忽略
        ]
        result = await svc.upload_batch(
            files=file_infos,
            tenant_id="tenant-1",
            uploaded_by="user-1",
            file_paths=["/tmp/doc1.pdf"],
            metadata_list=metadata_list,
        )
        assert result["success"] == 1
        assert result["failed"] == 0

    @pytest.mark.asyncio
    async def test_upload_batch_metadata_list_shorter_than_files(self) -> None:
        """验证 metadata_list 长度小于 files 时不足部分传 None"""
        svc = _make_upload_service()
        file_infos = [
            {"filename": "doc1.pdf", "mime_type": "application/pdf", "file_size_bytes": 100},
            {"filename": "doc2.pdf", "mime_type": "application/pdf", "file_size_bytes": 200},
        ]
        metadata_list = [
            {
                "creator": "user1",
                "created_at": "2024-01-15T10:30:00Z",
                "source": "internal",
                "license": "confidential",
                "business_domain": "finance",
            },
            # 不足部分，第二个文件传 None
        ]
        result = await svc.upload_batch(
            files=file_infos,
            tenant_id="tenant-1",
            uploaded_by="user-1",
            file_paths=["/tmp/doc1.pdf", "/tmp/doc2.pdf"],
            metadata_list=metadata_list,
        )
        # 第一个文件有完整 metadata 成功，第二个文件无 metadata 失败
        assert result["success"] == 1
        assert result["failed"] == 1


class TestChunkedUploadStateMetadata:
    """验证 ChunkedUploadState metadata 持久化"""

    def test_chunked_upload_state_metadata_serialization(self) -> None:
        """验证 metadata 字段在 to_json() 序列化后被保留"""
        from src.infrastructure.storage.redis.chunked_upload_manager import ChunkedUploadState

        state = ChunkedUploadState(
            upload_id="test-123",
            filename="test.pdf",
            file_size=1024,
            chunk_size=256,
            metadata='{"creator": "test-user", "source": "internal"}',
        )
        json_str = state.to_json()
        assert "metadata" in json_str
        assert "test-user" in json_str

    def test_chunked_upload_state_metadata_deserialization(self) -> None:
        """验证 from_json() 反序列化后 metadata 字段正确恢复"""
        from src.infrastructure.storage.redis.chunked_upload_manager import ChunkedUploadState

        state = ChunkedUploadState(
            upload_id="test-123",
            filename="test.pdf",
            file_size=1024,
            chunk_size=256,
            metadata='{"creator": "test-user", "source": "internal"}',
        )
        json_str = state.to_json()
        restored = ChunkedUploadState.from_json(json_str)
        assert restored.metadata == '{"creator": "test-user", "source": "internal"}'

    def test_chunked_upload_state_metadata_none(self) -> None:
        """验证 metadata=None 时向后兼容"""
        from src.infrastructure.storage.redis.chunked_upload_manager import ChunkedUploadState

        state = ChunkedUploadState(
            upload_id="test-123",
            filename="test.pdf",
            file_size=1024,
            chunk_size=256,
            metadata=None,
        )
        json_str = state.to_json()
        restored = ChunkedUploadState.from_json(json_str)
        assert restored.metadata is None

    def test_chunked_upload_state_metadata_missing_in_json(self) -> None:
        """验证旧数据（无 metadata 字段）反序列化时兼容"""
        import json

        from src.infrastructure.storage.redis.chunked_upload_manager import ChunkedUploadState

        old_json = json.dumps(
            {
                "upload_id": "test-123",
                "filename": "test.pdf",
                "file_size": 1024,
                "chunk_size": 256,
                "uploaded_parts": [],
                "minio_upload_id": None,
                "object_key": None,
            }
        )
        restored = ChunkedUploadState.from_json(old_json)
        assert restored.metadata is None

    @pytest.mark.asyncio
    async def test_init_upload_accepts_metadata(self) -> None:
        """验证 init_upload() 接收 metadata 参数并存储到状态中"""
        from unittest.mock import AsyncMock, MagicMock

        from src.domain.ports.l1_cache import L1CachePort
        from src.infrastructure.storage.redis.chunked_upload_manager import ChunkedUploadManager

        cache = MagicMock(spec=L1CachePort)
        cache.set = AsyncMock()
        mgr = ChunkedUploadManager(cache=cache)
        metadata_str = '{"creator": "test-user", "source": "internal"}'
        result = await mgr.init_upload(
            filename="test.pdf",
            file_size=1024,
            metadata=metadata_str,
        )
        assert "upload_id" in result
        # 验证 set 调用包含 metadata
        set_call = cache.set.call_args
        assert set_call is not None
        set_data = set_call[0][1]
        assert "metadata" in set_data
        assert "test-user" in set_data
