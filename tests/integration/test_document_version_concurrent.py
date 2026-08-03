"""文档版本并发控制测试

验证 AC-3: 并发版本控制 ≥ 10 个并发操作。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.document import Document, DocumentType, ParseStatus
from src.domain.exceptions import DocumentVersionConflictError
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
# PostgreSQL Schema Isolation Fixtures
# ===================================================================


@pytest.fixture
def test_schema() -> str:
    """生成测试专用 schema 名称"""
    return f"concur_{uuid4().hex[:8]}"


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
# Test Helpers
# ===================================================================


async def _concurrent_save_with_version_check(
    repo,
    doc: Document,
    expected_version: int,
    results: list,
    index: int,
) -> None:
    """并发调用 save_with_version_check"""
    try:
        doc_copy = Document(
            document_id=doc.document_id,
            filename=doc.filename,
            version=doc.version,
            tenant_id=doc.tenant_id,
            uploaded_by=doc.uploaded_by,
        )
        result = await repo.save_with_version_check(doc_copy, expected_version=expected_version)
        results[index] = ("success", result.version)
    except DocumentVersionConflictError as e:
        results[index] = ("conflict", e.actual_version)
    except Exception as e:
        results[index] = ("error", str(e))


def _make_doc(
    document_id: UUID | None = None,
    version: int = 1,
    tenant_id: str = "t1",
    uploaded_by: str = "u1",
    filename: str = "test.pdf",
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
        metadata={},
        tenant_id=tenant_id,
        uploaded_by=uploaded_by,
    )


# ===================================================================
# Tests
# ===================================================================


class TestConcurrentVersionControl:
    """验证并发版本控制（AC-3: ≥10 并发操作）"""

    async def test_10_concurrent_saves_only_one_succeeds(
        self,
        repo,
    ) -> None:
        """10 个并发 save_with_version_check 只有 1 个成功"""
        doc = _make_doc(version=1, tenant_id="con-t1")
        await repo.save(doc)

        doc.version = 2
        results: list = [None] * 10

        await asyncio.gather(
            *[_concurrent_save_with_version_check(repo, doc, expected_version=1, results=results, index=i) for i in range(10)]
        )

        success_count = sum(1 for r in results if r is not None and r[0] == "success")
        conflict_count = sum(1 for r in results if r is not None and r[0] == "conflict")

        assert success_count == 1, f"应只有 1 个成功，实际 {success_count}"
        assert conflict_count >= 9, f"至少 9 个应冲突，实际 {conflict_count}"

    async def test_serial_10_saves_all_succeed(
        self,
        repo,
    ) -> None:
        """串行 10 次 save_with_version_check 全部成功"""
        doc = _make_doc(version=1, tenant_id="con-t2")
        await repo.save(doc)

        for i in range(10):
            doc.version = i + 2
            result = await repo.save_with_version_check(doc, expected_version=i + 1)
            assert result.version == i + 2

        from src.domain.ports.document_repository import DocumentQuery

        query = DocumentQuery(tenant_id="con-t2", document_id=doc.document_id)
        updated = await repo.find(query)
        assert updated is not None
        assert updated.version == 11  # 初始 1 + 10 次递增

    async def test_5_concurrent_initial_versions(
        self,
        repo,
    ) -> None:
        """5 个不同文档并发创建首次快照"""
        docs = [_make_doc(version=1, tenant_id=f"con-t{i}") for i in range(5)]
        for d in docs:
            await repo.save(d)

        async def create_first_snapshot(doc: Document) -> bool:
            doc.version = 2
            try:
                await repo.save_with_version_check(doc, expected_version=1)
                return True
            except DocumentVersionConflictError:
                return False

        results = await asyncio.gather(*[create_first_snapshot(d) for d in docs])
        assert all(results), "5 个并发首次快照应全部成功"
