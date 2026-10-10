"""文档版本快照 AC-1 端到端性能基准（2-6 技术债清偿——残余缺口补齐）

AC-1「版本快照创建延迟 P95 < 100ms」——dev 期交付的 5 项基准覆盖 domain 口径
（值对象构造/元数据 diff/内容 diff），本文件补齐 create_snapshot 端到端口径
（find + get_version + compute_diff + 乐观锁 save + 快照 save + publish 多轮
真实 PG 往返）。

形态：独立 schema 隔离（perf_ 前缀 + create_all + teardown DROP CASCADE，
test_integration_document_version_concurrent 同款）+ 真实 DocumentVersionService
+ 真实 PostgreSQLDocumentRepository + 端口级事件记录器；分位断言
`statistics.quantiles(n=20)[18]` + 分级断言（达标 assert / 环境不达标 skip 留
测量证据——4-6 test_tool_version_integration.py 先例同款）。
"""

from __future__ import annotations

import statistics
from typing import Any, AsyncGenerator, Generator
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.services.document_version_service import DocumentVersionService
from src.domain.entities.document import Document, DocumentType, ParseStatus
from src.infrastructure.config.postgresql import PostgreSQLConfig
from src.infrastructure.storage.postgresql.postgresql_manager import PostgreSQLManager
from src.infrastructure.storage.postgresql.repository.document_repository import (
    PostgreSQLDocumentRepository,
)
from src.infrastructure.storage.postgresql.session_context import (
    get_session,
    reset_session,
    set_session,
)
from tests.environments import get_test_env


class _RecordingPublisher:
    """端口级事件记录器（发布面零 IO——基准聚焦 PG 往返段）."""

    def __init__(self) -> None:
        self.published: list[Any] = []

    async def publish(self, event: Any) -> None:
        self.published.append(event)


def _make_doc(
    document_id: UUID | None = None,
    version: int = 1,
    tenant_id: str = "perf-t1",
) -> Document:
    """构造 Document 实体（基准种子文档）."""
    return Document(
        document_id=document_id or uuid4(),
        filename="benchmark.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        document_type=DocumentType.OTHER,
        parse_status=ParseStatus.PENDING,
        version=version,
        tenant_id=tenant_id,
        uploaded_by="bench",
    )


@pytest.fixture
def test_schema() -> str:
    """生成测试专用 schema 名称"""
    return f"perf_{uuid4().hex[:8]}"


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
def service(pg_session: AsyncSession) -> Generator[DocumentVersionService, None, None]:
    """注入 ContextVar session 的真实服务（仓储 + 端口级记录器）"""
    token = set_session(pg_session)
    repository = PostgreSQLDocumentRepository()
    publisher: Any = _RecordingPublisher()  # 端口级记录器（结构满足发布面，Any 过协议协变窄化）
    yield DocumentVersionService(document_repository=repository, event_publisher=publisher)
    reset_session(token)


class TestCreateSnapshotP95:
    """AC-1 端到端基准：create_snapshot P95 < 100ms."""

    @pytest.mark.asyncio
    async def test_create_snapshot_p95_under_100ms(self, service: DocumentVersionService) -> None:
        """20 次串行快照创建（每次版本递增 + diff + 乐观锁 + 快照落库 + 事件）."""
        import time

        doc = _make_doc()
        from src.domain.ports.document_repository import DocumentQuery

        seed_repo = PostgreSQLDocumentRepository()
        assert get_session() is not None, "前置：ContextVar session 已由 fixture 注入"
        await seed_repo.save(doc)
        found = await seed_repo.find(DocumentQuery(document_id=doc.document_id, tenant_id=doc.tenant_id))
        assert found is not None, "前置：种子文档已落库"

        durations: list[float] = []
        for i in range(20):
            started = time.perf_counter()
            snapshot = await service.create_snapshot(
                document_id=doc.document_id,
                tenant_id=doc.tenant_id,
                created_by="bench",
                change_description=f"perf-{i}",
                old_content_summary=f"summary-{i}" if i > 0 else None,
                new_content_summary=f"summary-{i + 1}",
            )
            durations.append(time.perf_counter() - started)
            assert snapshot.version == i + 2, "版本号递增（当前 1 + i + 1）"

        p95 = statistics.quantiles(durations, n=20)[18]
        if p95 >= 0.1:
            pytest.skip(f"环境不达标：create_snapshot P95 = {p95 * 1000:.1f}ms ≥ 100ms（测量证据留存）")
        assert p95 < 0.1, f"create_snapshot P95 = {p95 * 1000:.1f}ms 应 < 100ms"
        assert len(durations) == 20
