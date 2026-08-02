"""Story 2-7 集成测试 — 元数据校验完整流程（真实服务）

测试 DocumentUploadService 集成元数据校验后的完整流程，使用真实服务：
- 真实 PostgreSQL（schema 隔离）
- 真实 MinIO（bucket 隔离）
- 填充 DocumentMetadata 值对象校验

Run with: poetry run pytest tests/integration/test_metadata_validation_integration.py -v
"""

from __future__ import annotations

import os
import tempfile
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.ports.document_repository import DocumentQuery
from tests.environments import get_test_env

# ===================================================================
# Helpers
# ===================================================================


def _create_test_pdf(filename: str = "test.pdf") -> str:
    """创建测试 PDF 文件"""
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{filename}")
    writer.write(tmp.name)
    tmp.close()
    return tmp.name


def _cleanup(path: str) -> None:
    """安全清理临时文件"""
    if path and os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass


def _cleanup_minio_bucket(bucket_manager, bucket_name: str) -> None:
    """安全清理 MinIO bucket"""
    try:
        if bucket_manager.bucket_exists(bucket_name):
            bucket_manager.delete_bucket(bucket_name, force=True)
    except Exception:
        pass


# ===================================================================
# PostgreSQL Schema Isolation Fixtures
# ===================================================================


@pytest.fixture
def test_schema() -> str:
    return f"test_sisys_meta_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def pg_config():
    env = get_test_env()
    from src.infrastructure.config.postgresql import PostgreSQLConfig

    return PostgreSQLConfig(
        host=env.postgres.host,
        port=env.postgres.port,
        database=env.postgres.database,
        username=env.postgres.username,
        password=env.postgres.password,
        pool_size=5,
        max_overflow=10,
    )


@pytest.fixture
def db_engine(pg_config):
    from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager

    return PostgreSQLManager(pg_config)


@pytest.fixture
def ensure_schema(db_engine, pg_config, test_schema: str):
    """创建测试专用 schema 及文档表"""
    from sqlalchemy import create_engine

    sync_url = (
        f"postgresql+psycopg2://{pg_config.username}:{pg_config.password}"
        f"@{pg_config.host}:{pg_config.port}/{pg_config.database}"
    )
    sync_engine = create_engine(sync_url)

    try:
        with sync_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        sync_engine.dispose()
        pytest.skip(f"PostgreSQL not available: {e}")

    with sync_engine.connect() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{test_schema}" CASCADE'))
        conn.commit()

    with sync_engine.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA "{test_schema}"'))
        conn.commit()

    from src.infrastructure.storage.postgresql.models import Base

    with sync_engine.connect() as conn:
        conn.execute(text(f'SET search_path TO "{test_schema}"'))
        Base.metadata.create_all(conn)
        conn.commit()

    sync_engine.dispose()

    yield test_schema

    sync_engine = create_engine(sync_url)
    try:
        with sync_engine.connect() as conn:
            conn.execute(text(f'DROP SCHEMA "{test_schema}" CASCADE'))
            conn.commit()
    except Exception:
        pass
    sync_engine.dispose()


@pytest.fixture
async def pg_session(db_engine, ensure_schema: str) -> AsyncGenerator[AsyncSession, None]:
    """创建带 schema 隔离的 PostgreSQL 会话"""
    async_engine = db_engine.get_async_engine()
    session = AsyncSession(async_engine, expire_on_commit=False)
    await session.execute(text(f'SET search_path TO "{ensure_schema}"'))

    async with session.begin_nested():
        yield session

    await session.rollback()
    await session.close()


@pytest.fixture
def repo(pg_session: AsyncSession):
    """注入 session 上下文的 DocumentRepository"""
    from src.infrastructure.storage.postgresql.repository.document_repository import (
        PostgreSQLDocumentRepository,
    )
    from src.infrastructure.storage.postgresql.session_context import reset_session, set_session

    token = set_session(pg_session)
    repository = PostgreSQLDocumentRepository()
    yield repository
    reset_session(token)


# ===================================================================
# MinIO 真实服务 Fixtures
# ===================================================================


@pytest.fixture
def minio_tenant_id() -> str:
    return f"test-meta-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def minio_bucket_name(minio_tenant_id: str) -> str:
    from src.infrastructure.storage.minio.bucket_manager import BucketManager

    env = get_test_env()
    from src.infrastructure.config.minio import MinIOConfig

    config = MinIOConfig(
        host=env.minio.endpoint.split(":")[0],
        port=int(env.minio.endpoint.split(":")[1]) if ":" in env.minio.endpoint else 9000,
        access_key=env.minio.access_key,
        secret_key=env.minio.secret_key,
        secure=env.minio.secure,
    )
    bm = BucketManager(config)
    return bm.build_bucket_name("raw-documents", minio_tenant_id)


@pytest.fixture
def minio_storage(minio_tenant_id: str, minio_bucket_name: str):
    """创建真实 MinIO 文档存储适配器，测试后清理整体 bucket"""
    from src.infrastructure.config.minio import MinIOConfig
    from src.infrastructure.storage.minio.bucket_manager import BucketManager
    from src.infrastructure.storage.minio.minio_adapter import MinIOAdapter
    from src.infrastructure.storage.minio.minio_document_storage import MinIODocumentStorage
    from src.infrastructure.storage.minio.minio_repository import MinIORepository
    from src.infrastructure.storage.minio.object_operations import ObjectOperations
    from src.infrastructure.storage.minio.worm_lifecycle import WORMManager

    env = get_test_env()
    endpoint_parts = env.minio.endpoint.split(":")
    host = endpoint_parts[0]
    port = int(endpoint_parts[1]) if len(endpoint_parts) > 1 else 9000

    config = MinIOConfig(
        host=host,
        port=port,
        access_key=env.minio.access_key,
        secret_key=env.minio.secret_key,
        secure=env.minio.secure,
    )

    # 验证 MinIO 连通性
    try:
        from src.infrastructure.storage.minio.minio_manager import MinioManager

        mgr = MinioManager.from_config(config)
        if not mgr.health_check():
            pytest.skip("MinIO not available")
    except Exception as e:
        pytest.skip(f"MinIO not available: {e}")

    bucket_manager = BucketManager(config)
    object_ops = ObjectOperations(config)
    worm_mgr = WORMManager(config)

    repository = MinIORepository(
        bucket_manager=bucket_manager,
        object_operations=object_ops,
        worm_manager=worm_mgr,
        tenant_id=minio_tenant_id,
    )

    adapter = MinIOAdapter(repository)

    # 确保 bucket 存在
    if not bucket_manager.bucket_exists(minio_bucket_name):
        bucket_manager.create_bucket(minio_bucket_name)

    # 使用 MinIODocumentStorage 实现 DocumentStoragePort
    storage = MinIODocumentStorage(adapter)

    yield storage

    # 清理：删除测试 bucket 及所有对象
    _cleanup_minio_bucket(bucket_manager, minio_bucket_name)


# ===================================================================
# 集成测试：元数据校验完整流程
# ===================================================================


class TestMetadataValidationRealService:
    """使用真实 PostgreSQL + MinIO 验证元数据校验完整流程"""

    def _make_upload_service(self, repo, storage, publisher=None):
        """创建 DocumentUploadService 实例，使用真实 repo + storage"""
        from src.application.services.document_upload_service import DocumentUploadService
        from src.domain.ports.event_publisher import EventPublisher

        publisher = publisher or AsyncMock(spec=EventPublisher)
        publisher.publish = AsyncMock()
        return DocumentUploadService(
            document_repository=repo,
            document_storage=storage,
            event_publisher=publisher,
        )

    @pytest.mark.asyncio
    async def test_1_complete_metadata_upload_success(
        self,
        pg_session: AsyncSession,
        repo,
        minio_storage,
    ) -> None:
        """测试 1: 完整 metadata 上传成功（真实 PG + MinIO）"""
        svc = self._make_upload_service(repo, minio_storage)
        pdf_path = _create_test_pdf("complete.pdf")
        try:
            metadata = {
                "creator": "test-user",
                "created_at": "2024-01-15T10:30:00Z",
                "source": "internal",
                "license": "confidential",
                "business_domain": "finance",
            }
            doc = await svc.upload(
                filename="complete.pdf",
                mime_type="application/pdf",
                file_size_bytes=os.path.getsize(pdf_path),
                tenant_id="tenant-1",
                uploaded_by="user-1",
                file_path=pdf_path,
                metadata=metadata,
            )
            assert doc is not None
            assert doc.metadata.get("source") == "internal"
            assert doc.metadata.get("license") == "confidential"

            # 验证 PG 持久化
            reloaded = await repo.find(DocumentQuery(tenant_id="tenant-1", document_id=doc.document_id))
            assert reloaded is not None, "文档应持久化到 PG"
            assert reloaded.metadata.get("source") == "internal"
        finally:
            _cleanup(pdf_path)

    @pytest.mark.asyncio
    async def test_2_partial_metadata_with_autofill(
        self,
        pg_session: AsyncSession,
        repo,
        minio_storage,
    ) -> None:
        """测试 2: 部分 metadata + 自动填充上传成功"""
        svc = self._make_upload_service(repo, minio_storage)
        pdf_path = _create_test_pdf("autofill.pdf")
        try:
            metadata = {
                "source": "internal",
                "license": "confidential",
                "business_domain": "finance",
            }
            doc = await svc.upload(
                filename="autofill.pdf",
                mime_type="application/pdf",
                file_size_bytes=os.path.getsize(pdf_path),
                tenant_id="tenant-1",
                uploaded_by="user-1",
                file_path=pdf_path,
                metadata=metadata,
            )
            assert doc is not None
            # 自动填充
            assert doc.metadata.get("creator") == "user-1"
            assert "created_at" in doc.metadata
            # 显式字段
            assert doc.metadata.get("source") == "internal"
        finally:
            _cleanup(pdf_path)

    @pytest.mark.asyncio
    async def test_3_missing_license_blocks_no_side_effects(
        self,
        pg_session: AsyncSession,
        repo,
        minio_storage,
    ) -> None:
        """测试 3: 缺失 license 字段阻断 + 无 MinIO/PG 残留"""
        from src.domain.exceptions.storage_exceptions import MetadataValidationError

        svc = self._make_upload_service(repo, minio_storage)
        pdf_path = _create_test_pdf("missing_license.pdf")
        try:
            metadata = {
                "creator": "test-user",
                "created_at": "2024-01-15T10:30:00Z",
                "source": "internal",
                "business_domain": "finance",
            }
            with pytest.raises(MetadataValidationError) as exc_info:
                await svc.upload(
                    filename="missing_license.pdf",
                    mime_type="application/pdf",
                    file_size_bytes=os.path.getsize(pdf_path),
                    tenant_id="tenant-1",
                    uploaded_by="user-1",
                    file_path=pdf_path,
                    metadata=metadata,
                )
            # 异常包含缺失字段
            assert "license" in exc_info.value.context["missing_fields"]

            # 验证 PG 无残留：查询所有文档，无此文档记录
            all_docs = await repo.list(DocumentQuery(tenant_id="tenant-1"))
            doc_ids_with_license = [d for d in all_docs if d.metadata.get("license") is None]
            assert len(doc_ids_with_license) == 0
        finally:
            _cleanup(pdf_path)

    @pytest.mark.asyncio
    async def test_4_empty_value_blocks(
        self,
        pg_session,
        repo,
        minio_storage,
    ) -> None:
        """测试 4: 空字符串值阻断"""
        from src.domain.exceptions.storage_exceptions import MetadataValidationError

        svc = self._make_upload_service(repo, minio_storage)
        pdf_path = _create_test_pdf("empty_source.pdf")
        try:
            metadata = {
                "creator": "test-user",
                "created_at": "2024-01-15T10:30:00Z",
                "source": "",
                "license": "confidential",
                "business_domain": "finance",
            }
            with pytest.raises(MetadataValidationError) as exc_info:
                await svc.upload(
                    filename="empty_source.pdf",
                    mime_type="application/pdf",
                    file_size_bytes=os.path.getsize(pdf_path),
                    tenant_id="tenant-1",
                    uploaded_by="user-1",
                    file_path=pdf_path,
                    metadata=metadata,
                )
            assert "source" in exc_info.value.context["missing_fields"]
        finally:
            _cleanup(pdf_path)

    @pytest.mark.asyncio
    async def test_5_invalid_created_at_blocks(
        self,
        pg_session,
        repo,
        minio_storage,
    ) -> None:
        """测试 5: created_at 非法格式阻断"""
        from src.domain.exceptions.storage_exceptions import MetadataValidationError

        svc = self._make_upload_service(repo, minio_storage)
        pdf_path = _create_test_pdf("bad_date.pdf")
        try:
            metadata = {
                "creator": "test-user",
                "created_at": "2024/01/01",
                "source": "internal",
                "license": "confidential",
                "business_domain": "finance",
            }
            with pytest.raises(MetadataValidationError) as exc_info:
                await svc.upload(
                    filename="bad_date.pdf",
                    mime_type="application/pdf",
                    file_size_bytes=os.path.getsize(pdf_path),
                    tenant_id="tenant-1",
                    uploaded_by="user-1",
                    file_path=pdf_path,
                    metadata=metadata,
                )
            assert "created_at" in exc_info.value.context["missing_fields"]
        finally:
            _cleanup(pdf_path)

    @pytest.mark.asyncio
    async def test_6_tenant_data_isolation(
        self,
        pg_session,
        repo,
        minio_storage,
    ) -> None:
        """测试 6: 跨租户数据隔离验证"""
        svc = self._make_upload_service(repo, minio_storage)

        pdf_a = _create_test_pdf("tenant_a.pdf")
        pdf_b = _create_test_pdf("tenant_b.pdf")
        try:
            meta_a = {
                "creator": "user-a",
                "created_at": "2024-01-15T10:30:00Z",
                "source": "internal",
                "license": "confidential",
                "business_domain": "finance",
            }
            meta_b = {
                "creator": "user-b",
                "created_at": "2024-01-16T11:00:00Z",
                "source": "external",
                "license": "public",
                "business_domain": "marketing",
            }

            doc_a = await svc.upload(
                filename="a.pdf",
                mime_type="application/pdf",
                file_size_bytes=os.path.getsize(pdf_a),
                tenant_id="tenant-a",
                uploaded_by="user-a",
                file_path=pdf_a,
                metadata=meta_a,
            )
            doc_b = await svc.upload(
                filename="b.pdf",
                mime_type="application/pdf",
                file_size_bytes=os.path.getsize(pdf_b),
                tenant_id="tenant-b",
                uploaded_by="user-b",
                file_path=pdf_b,
                metadata=meta_b,
            )

            assert doc_a.tenant_id == "tenant-a"
            assert doc_b.tenant_id == "tenant-b"
            assert doc_a.metadata["business_domain"] == "finance"
            assert doc_b.metadata["business_domain"] == "marketing"

            # 验证租户隔离：tenant-a 查不到 tenant-b 的文档
            found_a = await repo.find(DocumentQuery(tenant_id="tenant-a", document_id=doc_b.document_id))
            assert found_a is None, "租户 A 不应查到租户 B 的文档"
        finally:
            _cleanup(pdf_a)
            _cleanup(pdf_b)

    @pytest.mark.asyncio
    async def test_7_batch_upload_with_metadata(
        self,
        pg_session,
        repo,
        minio_storage,
    ) -> None:
        """测试 7: 批量上传 metadata 传递"""
        svc = self._make_upload_service(repo, minio_storage)

        pdf1 = _create_test_pdf("batch1.pdf")
        pdf2 = _create_test_pdf("batch2.pdf")
        try:
            files = [
                {"filename": "batch1.pdf", "mime_type": "application/pdf", "file_size_bytes": os.path.getsize(pdf1)},
                {"filename": "batch2.pdf", "mime_type": "application/pdf", "file_size_bytes": os.path.getsize(pdf2)},
            ]
            metadata_list = [
                {
                    "creator": "user1",
                    "created_at": "2024-01-15T10:30:00Z",
                    "source": "internal",
                    "license": "confidential",
                    "business_domain": "finance",
                },
                None,
            ]
            result = await svc.upload_batch(
                files=files,
                tenant_id="tenant-1",
                uploaded_by="user-1",
                file_paths=[pdf1, pdf2],
                metadata_list=metadata_list,
            )
            assert result["success"] == 1
            assert result["failed"] == 1
        finally:
            _cleanup(pdf1)
            _cleanup(pdf2)

    @pytest.mark.asyncio
    async def test_8_register_document_with_metadata(
        self,
        pg_session,
        repo,
        minio_storage,
    ) -> None:
        """测试 8: register_document 接收 metadata 参数"""
        svc = self._make_upload_service(repo, minio_storage)
        metadata = {
            "creator": "test-user",
            "created_at": "2024-01-15T10:30:00Z",
            "source": "internal",
            "license": "confidential",
            "business_domain": "finance",
        }
        doc = await svc.register_document(
            filename="chunked.pdf",
            mime_type="application/pdf",
            file_size_bytes=1024,
            tenant_id="tenant-1",
            uploaded_by="user-1",
            object_key="test-object-key",
            metadata=metadata,
        )
        assert doc is not None
        assert doc.metadata.get("source") == "internal"
        assert doc.metadata.get("license") == "confidential"

        # 验证 PG 持久化
        reloaded = await repo.find(DocumentQuery(tenant_id="tenant-1", document_id=doc.document_id))
        assert reloaded is not None
        assert reloaded.metadata.get("source") == "internal"
