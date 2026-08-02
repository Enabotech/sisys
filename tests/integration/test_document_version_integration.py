"""文档版本快照集成测试

验证完整版本快照流程：Service → Repository → 持久化 → EventPublish

真实服务 Schema 隔离模式：
- 真实 PostgreSQL（schema 隔离 + savepoint rollback）
- 真实 DocumentRepository（ContextVar session）
- Mock EventPublisher（纯基础设施，无安全清理）

测试覆盖：
- 版本快照 CRUD 完整流程
- 差异摘要计算准确性
- 乐观锁版本冲突检测
- 版本历史列表查询 + 排序
- 跨租户隔离验证
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.document import Document, DocumentType, ParseStatus
from src.domain.exceptions import DocumentVersionConflictError
from src.domain.services.document_version_diff_service import compute_diff
from src.domain.value_objects.document_version import (
    DocumentVersionSnapshot,
)
from src.infrastructure.config.postgresql import PostgreSQLConfig
from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
from src.infrastructure.storage.postgresql.repository.document_repository import (
    PostgreSQLDocumentRepository,
)
from src.infrastructure.storage.postgresql.session_context import (
    reset_session,
    set_session,
)
from tests.environments import get_test_env

# ===================================================================
# Helpers
# ===================================================================


def _make_doc(
    document_id: UUID | None = None,
    version: int = 1,
    tenant_id: str = "t1",
    uploaded_by: str = "u1",
    filename: str = "test.pdf",
    metadata: dict | None = None,
) -> Document:
    """构造 Document 实体"""
    return Document(
        document_id=document_id or uuid4(),
        filename=filename,
        mime_type="application/pdf",
        file_size_bytes=1024,
        document_type=DocumentType.OTHER,
        parse_status=ParseStatus.PENDING,
        version=version,
        metadata=metadata or {},
        tenant_id=tenant_id,
        uploaded_by=uploaded_by,
    )


def _make_snapshot(document_id: UUID, version: int = 1) -> DocumentVersionSnapshot:
    """构造 DocumentVersionSnapshot 值对象"""
    return DocumentVersionSnapshot(
        document_id=document_id,
        version=version,
        snapshot_id=uuid4(),
        created_at=datetime.now(UTC),
        created_by="system",
        change_description="文档上传",
        diff_summary="initial version" if version == 1 else "content changed",
        diff_json={"changed_fields": [], "is_initial": version == 1},
    )


# ===================================================================
# PostgreSQL Schema Isolation Fixtures
# ===================================================================


@pytest.fixture
def test_schema() -> str:
    """生成测试专用 schema 名称"""
    return f"test_ver_{uuid4().hex[:8]}"


@pytest.fixture
def pg_config() -> PostgreSQLConfig:
    """测试环境 PostgreSQL 配置"""
    env = get_test_env()
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
def db_engine(pg_config: PostgreSQLConfig) -> PostgreSQLManager:
    """创建 PostgreSQL 引擎管理实例"""
    return PostgreSQLManager(pg_config)


@pytest.fixture
def ensure_schema(
    db_engine: PostgreSQLManager,
    pg_config: PostgreSQLConfig,
    test_schema: str,
):
    """创建测试专用 schema，含 documents 和 document_version_snapshots 表"""
    sync_url = (
        f"postgresql+psycopg2://{pg_config.username}:{pg_config.password}"
        f"@{pg_config.host}:{pg_config.port}/{pg_config.database}"
    )
    from sqlalchemy import create_engine

    sync_engine = create_engine(sync_url)

    try:
        with sync_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        sync_engine.dispose()
        pytest.skip(f"PostgreSQL not available: {e}")

    # 创建 schema 并建表
    with sync_engine.connect() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{test_schema}" CASCADE'))
        conn.commit()

    from src.infrastructure.storage.postgresql.models import Base

    with sync_engine.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA "{test_schema}"'))
        conn.execute(text(f'SET search_path TO "{test_schema}"'))
        Base.metadata.create_all(conn)
        conn.commit()

    sync_engine.dispose()

    yield test_schema

    # 清理 schema
    sync_engine = create_engine(sync_url)
    try:
        with sync_engine.connect() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{test_schema}" CASCADE'))
            conn.commit()
    except Exception:
        pass
    sync_engine.dispose()


@pytest.fixture
async def pg_session(
    db_engine: PostgreSQLManager,
    ensure_schema: str,
) -> AsyncGenerator[AsyncSession, None]:
    """创建带 schema 隔离的 PostgreSQL 会话（savepoint rollback）"""
    async_engine = db_engine.get_async_engine()
    session = AsyncSession(async_engine, expire_on_commit=False)

    await session.execute(text(f'SET search_path TO "{ensure_schema}"'))

    async with session.begin_nested():
        yield session

    await session.rollback()
    await session.close()


@pytest.fixture
def repo(pg_session: AsyncSession):
    """注入 ContextVar session 的 DocumentRepository"""
    token = set_session(pg_session)
    repository = PostgreSQLDocumentRepository()
    yield repository
    reset_session(token)


# ===================================================================
# 真实 EventPublisher Mock（纯基础设施，无安全清理场景）
# ===================================================================


@pytest.fixture
def event_publisher() -> AsyncMock:
    """Mock EventPublisher（纯基础设施端口）"""
    return AsyncMock()


# ===================================================================
# Tests: 版本快照 CRUD
# ===================================================================


class TestVersionSnapshotCRUD:
    """验证版本快照完整 CRUD 流程（真实 PostgreSQL）"""

    async def test_save_and_retrieve_snapshot(self, repo: PostgreSQLDocumentRepository) -> None:
        """保存版本快照并查询"""
        # 先创建 Document
        doc = _make_doc(tenant_id="t1")
        await repo.save(doc)

        # 保存版本快照
        snapshot = _make_snapshot(document_id=doc.document_id, version=1)
        saved = await repo.save_version_snapshot(snapshot)

        assert saved.document_id == doc.document_id
        assert saved.version == 1
        assert saved.diff_summary == "initial version"

        # 按版本号查询
        fetched = await repo.get_version(doc.document_id, 1, "t1")
        assert fetched is not None
        assert fetched.snapshot_id == snapshot.snapshot_id
        assert fetched.diff_summary == "initial version"

    async def test_list_versions_ordered_desc(self, repo: PostgreSQLDocumentRepository) -> None:
        """版本历史按版本号降序排列"""
        doc = _make_doc(tenant_id="t2")
        await repo.save(doc)

        # 创建 3 个版本快照
        for ver in (1, 2, 3):
            snap = _make_snapshot(document_id=doc.document_id, version=ver)
            await repo.save_version_snapshot(snap)

        result = await repo.list_versions(doc.document_id, "t2")
        assert len(result) == 3
        # 验证降序
        assert result[0].version == 3
        assert result[1].version == 2
        assert result[2].version == 1

    async def test_list_versions_empty(self, repo: PostgreSQLDocumentRepository) -> None:
        """无版本快照时返回空列表"""
        doc = _make_doc(tenant_id="t3")
        await repo.save(doc)

        result = await repo.list_versions(doc.document_id, "t3")
        assert result == []

    async def test_get_version_not_found(self, repo: PostgreSQLDocumentRepository) -> None:
        """不存在的版本返回 None"""
        doc = _make_doc(tenant_id="t4")
        await repo.save(doc)

        result = await repo.get_version(doc.document_id, 99, "t4")
        assert result is None


class TestVersionConflictDetection:
    """验证乐观锁版本冲突检测（真实 PostgreSQL）"""

    async def test_save_with_version_check_success(self, repo: PostgreSQLDocumentRepository) -> None:
        """版本匹配时成功保存"""
        doc = _make_doc(version=1, tenant_id="t5")
        await repo.save(doc)

        doc.version = 2
        saved = await repo.save_with_version_check(doc, expected_version=1)
        assert saved.version == 2

    async def test_save_with_version_check_conflict(self, repo: PostgreSQLDocumentRepository) -> None:
        """版本不匹配时抛出 DocumentVersionConflictError"""
        doc = _make_doc(version=3, tenant_id="t6")
        await repo.save(doc)

        doc.version = 4
        with pytest.raises(DocumentVersionConflictError) as exc_info:
            await repo.save_with_version_check(doc, expected_version=1)

        assert exc_info.value.document_id == doc.document_id
        assert exc_info.value.expected_version == 1
        assert exc_info.value.actual_version == 3


class TestTenantIsolation:
    """验证跨租户隔离（真实 PostgreSQL）"""

    async def test_list_versions_tenant_isolation(self, repo: PostgreSQLDocumentRepository) -> None:
        """租户 B 无法查询租户 A 的版本历史"""
        # 租户 A 创建文档和快照
        doc_a = _make_doc(tenant_id="tenant-A")
        await repo.save(doc_a)
        await repo.save_version_snapshot(_make_snapshot(document_id=doc_a.document_id, version=1))

        # 租户 B 查询应返回空列表
        result = await repo.list_versions(doc_a.document_id, "tenant-B")
        assert result == []

    async def test_get_version_tenant_isolation(self, repo: PostgreSQLDocumentRepository) -> None:
        """租户 B 无法获取租户 A 的指定版本"""
        doc_a = _make_doc(tenant_id="tenant-AA")
        await repo.save(doc_a)
        await repo.save_version_snapshot(_make_snapshot(document_id=doc_a.document_id, version=1))

        result = await repo.get_version(doc_a.document_id, 1, "tenant-BB")
        assert result is None


# ===================================================================
# Tests: 差异摘要计算
# ===================================================================


class TestDiffCalculation:
    """验证差异摘要计算（领域层纯函数）"""

    def test_metadata_diff_detected(self) -> None:
        """元数据变更应生成正确的 diff"""
        diff = compute_diff(
            old_metadata={"parse_status": "pending"},
            new_metadata={"parse_status": "completed", "filename": "new.pdf"},
            old_content_summary="old",
            new_content_summary="new",
        )
        assert "parse_status" in diff.changed_fields
        assert "filename" in diff.changed_fields
        assert diff.is_initial is False
        assert diff.diff_summary != "no changes"

    def test_initial_version_marked(self) -> None:
        """首次版本标记为 initial"""
        diff = compute_diff(
            old_metadata={},
            new_metadata={"key": "value"},
            old_content_summary="",
            new_content_summary="content",
            is_initial=True,
        )
        assert diff.is_initial is True
        assert diff.diff_summary == "initial version"
        assert diff.changed_fields == []

    def test_no_changes_detected(self) -> None:
        """无变更时返回 no changes"""
        diff = compute_diff(
            old_metadata={"a": "1"},
            new_metadata={"a": "1"},
            old_content_summary="same",
            new_content_summary="same",
        )
        assert diff.changed_fields == []
        assert diff.diff_summary == "no changes"


# ===================================================================
# Tests: 应用层服务编排（Mock EventPublisher）
# ===================================================================


class TestApplicationService:
    """验证应用层服务编排（真实 Repository + Mock Publisher）"""

    async def test_create_snapshot_flow(
        self,
        repo: PostgreSQLDocumentRepository,
        event_publisher: AsyncMock,
    ) -> None:
        """创建快照完整流程：查询 → diff → 持久化 → 事件"""
        from src.application.services.document_version_service import DocumentVersionService

        doc = _make_doc(version=1, tenant_id="t7")
        await repo.save(doc)

        service = DocumentVersionService(
            document_repository=repo,
            event_publisher=event_publisher,
        )

        snapshot = await service.create_snapshot(
            document_id=doc.document_id,
            tenant_id=doc.tenant_id,
            created_by="user-1",
            change_description="初始上传",
        )

        assert snapshot.document_id == doc.document_id
        assert snapshot.version == 1
        assert snapshot.change_description == "初始上传"
        assert snapshot.diff_summary == "initial version"

        # 验证事件发布
        event_publisher.publish.assert_called_once()
        event = event_publisher.publish.call_args[0][0]
        assert event.event_type == "DocumentVersionSnapshotCreated"
        assert event.document_id == doc.document_id

    async def test_list_versions_after_creation(
        self,
        repo: PostgreSQLDocumentRepository,
        event_publisher: AsyncMock,
    ) -> None:
        """创建多个快照后查询列表"""
        from src.application.services.document_version_service import DocumentVersionService

        doc = _make_doc(version=1, tenant_id="t8")
        await repo.save(doc)

        service = DocumentVersionService(
            document_repository=repo,
            event_publisher=event_publisher,
        )

        # 创建快照
        await service.create_snapshot(
            document_id=doc.document_id,
            tenant_id=doc.tenant_id,
            created_by="user-1",
            change_description="上传",
        )

        result = await service.list_versions(doc.document_id, "t8")
        assert len(result) >= 1
        assert result[0].version == 1
