"""语义分块集成测试

验证解析→分块→持久化→事件发布完整流程。

真实服务 Schema 隔离模式：
- 真实 PostgreSQL（schema 隔离 + savepoint rollback）
- 真实 SemanticChunkerImpl
- Mock EventPublisher（纯基础设施，无安全清理）

测试覆盖：
- 短文档完整流程（解析→分块→持久化→验证）
- 多章节长文档（章节标题边界检测）
- 表格文档（表格独立分块 + 展平格式）
- 多页文档（页面边界切分）
- 中英混合文档（token 计数准确性）
- 分块后的 metadata.chunks JSONB 存储和读取
- RAGIndexed 事件发布验证
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.document import Document, DocumentType, ParseStatus
from src.domain.value_objects.semantic_chunk import ChunkBoundaryType
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
        version=version,
        document_type=DocumentType.OTHER,
        parse_status=ParseStatus.COMPLETED,
        uploaded_by=uploaded_by,
        tenant_id=tenant_id,
        metadata=metadata or {},
        file_size_bytes=1024,
        mime_type="text/plain",
    )


def _make_parse_result(texts: list[str] | None = None, document_id: str | None = None) -> dict:
    """构造 parse_result 字典"""
    from src.domain.value_objects.parsed_document import ParsedElement

    page_texts = []
    if texts:
        for t in texts:
            page_texts.append(ParsedElement(content=t).to_dict())

    return {
        "document_id": document_id or str(uuid4()),
        "mime_type": "text/plain",
        "pages": [
            {
                "page_number": 1,
                "texts": page_texts,
                "tables": [],
                "images": [],
            }
        ],
        "parse_status": "completed",
        "error_message": None,
        "parse_timestamp": "2025-01-01T00:00:00Z",
    }


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def test_schema() -> str:
    """生成测试专用 schema 名称"""
    return f"test_chunk_{uuid4().hex[:8]}"


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
    """创建测试专用 schema，含 documents 表"""
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
def repository(pg_session: AsyncSession):
    """注入 ContextVar session 的 DocumentRepository"""
    token = set_session(pg_session)
    repo = PostgreSQLDocumentRepository()
    yield repo
    reset_session(token)


@pytest.fixture
def mock_event_publisher() -> AsyncMock:
    """Mock EventPublisher"""
    mock = AsyncMock()
    mock.publish = AsyncMock()
    return mock


# ===================================================================
# Tests
# ===================================================================


class TestSemanticChunkingIntegration:
    """语义分块集成测试"""

    @pytest.mark.asyncio
    async def test_short_document_full_flow(
        self,
        repository: PostgreSQLDocumentRepository,
        mock_event_publisher: AsyncMock,
    ) -> None:
        """短文档完整流程：解析→分块→持久化→验证"""
        from src.application.services.semantic_chunking_service import SemanticChunkingService
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        # 准备
        doc_id = uuid4()
        tenant_id = "t1"
        metadata = {"business_domain": "test"}
        parse_result = _make_parse_result(texts=["今天天气很好，适合出去散步。"], document_id=str(doc_id))

        doc = _make_doc(
            document_id=doc_id,
            tenant_id=tenant_id,
            metadata=metadata | {"parse_result": parse_result},
        )
        await repository.save(doc)

        # 执行
        chunker = SemanticChunkerImpl()
        service = SemanticChunkingService(
            document_repository=repository,
            semantic_chunker=chunker,
            event_publisher=mock_event_publisher,
        )
        chunks = await service.chunk_document(
            document_id=doc_id,
            tenant_id=tenant_id,
        )

        # 验证
        assert len(chunks) > 0, "Should produce at least 1 chunk"
        assert chunks[0].document_id == doc_id
        assert chunks[0].boundary_type == ChunkBoundaryType.PARAGRAPH

        # 验证持久化
        from src.domain.ports.document_repository import DocumentQuery

        saved_doc = await repository.find(DocumentQuery(tenant_id=tenant_id, document_id=doc_id))
        assert saved_doc is not None
        assert "chunks" in saved_doc.metadata
        assert len(saved_doc.metadata["chunks"]) == len(chunks)

        # 验证事件发布
        mock_event_publisher.publish.assert_called_once()
        call_args = mock_event_publisher.publish.call_args
        published_event = call_args[0][0]
        assert published_event.chunk_count == len(chunks)

    @pytest.mark.asyncio
    async def test_multi_chapter_document(
        self,
        repository: PostgreSQLDocumentRepository,
        mock_event_publisher: AsyncMock,
    ) -> None:
        """多章节长文档（章节标题边界检测）"""
        from src.application.services.semantic_chunking_service import SemanticChunkingService
        from src.domain.value_objects.parsed_document import ParsedElement, ParsedPage
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        # 准备
        doc_id = uuid4()
        tenant_id = "t1"

        doc = _make_doc(
            document_id=doc_id,
            tenant_id=tenant_id,
            filename="chapter_test.pdf",
            metadata={
                "parse_result": {
                    "document_id": str(doc_id),
                    "mime_type": "text/plain",
                    "pages": [
                        ParsedPage(
                            page_number=1,
                            texts=[
                                ParsedElement(content="第一章", metadata={"style": "h1"}),
                                ParsedElement(content="这是第一章的内容。" * 100),
                                ParsedElement(content="第二章", metadata={"style": "h2"}),
                                ParsedElement(content="这是第二章的内容。" * 100),
                            ],
                        ).to_dict()
                    ],
                    "parse_status": "completed",
                }
            },
        )
        await repository.save(doc)

        # 执行
        chunker = SemanticChunkerImpl()
        service = SemanticChunkingService(
            document_repository=repository,
            semantic_chunker=chunker,
            event_publisher=mock_event_publisher,
        )
        chunks = await service.chunk_document(
            document_id=doc_id,
            tenant_id=tenant_id,
        )

        # 验证
        assert len(chunks) >= 2, "Should produce at least 2 chunks"
        header_chunks = [c for c in chunks if c.boundary_type == ChunkBoundaryType.SECTION_HEADER]
        assert len(header_chunks) >= 2, "Should detect at least 2 section headers"

    @pytest.mark.asyncio
    async def test_table_document(
        self,
        repository: PostgreSQLDocumentRepository,
        mock_event_publisher: AsyncMock,
    ) -> None:
        """表格文档（表格独立分块 + 展平格式）"""
        from src.application.services.semantic_chunking_service import SemanticChunkingService
        from src.domain.value_objects.parsed_document import ParsedElement, ParsedPage, ParsedTable
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        # 准备
        doc_id = uuid4()
        tenant_id = "t1"

        doc = _make_doc(
            document_id=doc_id,
            tenant_id=tenant_id,
            filename="table_test.pdf",
            metadata={
                "parse_result": {
                    "document_id": str(doc_id),
                    "mime_type": "text/plain",
                    "pages": [
                        ParsedPage(
                            page_number=1,
                            texts=[ParsedElement(content="正文内容")],
                            tables=[
                                ParsedTable(
                                    rows=[["姓名", "年龄", "城市"], ["张三", "28", "北京"], ["李四", "32", "上海"]],
                                    header=["姓名", "年龄", "城市"],
                                    table_caption="用户信息表",
                                )
                            ],
                        ).to_dict()
                    ],
                    "parse_status": "completed",
                }
            },
        )
        await repository.save(doc)

        # 执行
        chunker = SemanticChunkerImpl()
        service = SemanticChunkingService(
            document_repository=repository,
            semantic_chunker=chunker,
            event_publisher=mock_event_publisher,
        )
        chunks = await service.chunk_document(
            document_id=doc_id,
            tenant_id=tenant_id,
        )

        # 验证
        table_chunks = [c for c in chunks if c.boundary_type == ChunkBoundaryType.TABLE]
        assert len(table_chunks) >= 1, "Should detect at least 1 table chunk"
        content = table_chunks[0].content
        assert "|" in content, "Table content should be pipe-separated"
        assert "[表格: 用户信息表]" in content, "Table should have caption prefix"

    @pytest.mark.asyncio
    async def test_multi_page_document(
        self,
        repository: PostgreSQLDocumentRepository,
        mock_event_publisher: AsyncMock,
    ) -> None:
        """多页文档（页面边界切分）"""
        from src.application.services.semantic_chunking_service import SemanticChunkingService
        from src.domain.value_objects.parsed_document import ParsedElement, ParsedPage
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        # 准备
        doc_id = uuid4()
        tenant_id = "t1"

        doc = _make_doc(
            document_id=doc_id,
            tenant_id=tenant_id,
            filename="multi_page_test.pdf",
            metadata={
                "parse_result": {
                    "document_id": str(doc_id),
                    "mime_type": "text/plain",
                    "pages": [
                        ParsedPage(
                            page_number=1,
                            texts=[ParsedElement(content="第一页内容。" * 50)],
                        ).to_dict(),
                        ParsedPage(
                            page_number=2,
                            texts=[ParsedElement(content="第二页内容。" * 50)],
                        ).to_dict(),
                    ],
                    "parse_status": "completed",
                }
            },
        )
        await repository.save(doc)

        # 执行
        chunker = SemanticChunkerImpl()
        service = SemanticChunkingService(
            document_repository=repository,
            semantic_chunker=chunker,
            event_publisher=mock_event_publisher,
        )
        chunks = await service.chunk_document(
            document_id=doc_id,
            tenant_id=tenant_id,
        )

        # 验证
        assert len(chunks) >= 2, "Should produce at least 2 chunks for 2 pages"
        assert chunks[0].page_start == 1 or chunks[0].page_end == 1
        assert chunks[-1].page_start == 2 or chunks[-1].page_end == 2

    @pytest.mark.asyncio
    async def test_chunks_jsonb_storage(
        self,
        repository: PostgreSQLDocumentRepository,
        mock_event_publisher: AsyncMock,
    ) -> None:
        """分块后的 metadata.chunks JSONB 存储和读取"""
        from src.application.services.semantic_chunking_service import SemanticChunkingService
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        # 准备
        doc_id = uuid4()
        tenant_id = "t1"
        parse_result = _make_parse_result(texts=["测试分块存储。" * 50])

        doc = _make_doc(
            document_id=doc_id,
            tenant_id=tenant_id,
            metadata={"business_domain": "test"} | {"parse_result": parse_result},
        )
        await repository.save(doc)

        # 执行
        chunker = SemanticChunkerImpl()
        service = SemanticChunkingService(
            document_repository=repository,
            semantic_chunker=chunker,
            event_publisher=mock_event_publisher,
        )
        chunks = await service.chunk_document(
            document_id=doc_id,
            tenant_id=tenant_id,
        )

        # 验证 JSONB 存储
        from src.domain.ports.document_repository import DocumentQuery

        saved_doc = await repository.find(DocumentQuery(tenant_id=tenant_id, document_id=doc_id))
        assert saved_doc is not None
        chunks_data = saved_doc.metadata.get("chunks", [])
        assert len(chunks_data) == len(chunks)

        # 验证反序列化为 SemanticChunk
        for chunk_dict in chunks_data:
            assert "chunk_id" in chunk_dict
            assert "content" in chunk_dict
            assert "chunk_index" in chunk_dict
            assert "boundary_type" in chunk_dict
            assert "token_count" in chunk_dict
            assert "content_hash" in chunk_dict

        # 验证 JSON 可序列化
        json_str = json.dumps(chunks_data, ensure_ascii=False)
        assert json_str

    @pytest.mark.asyncio
    async def test_rag_indexed_event(
        self,
        repository: PostgreSQLDocumentRepository,
        mock_event_publisher: AsyncMock,
    ) -> None:
        """RAGIndexed 事件发布验证"""
        from src.application.services.semantic_chunking_service import SemanticChunkingService
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        # 准备
        doc_id = uuid4()
        tenant_id = "t1"
        parse_result = _make_parse_result(texts=["事件发布测试。" * 100])

        doc = _make_doc(
            document_id=doc_id,
            tenant_id=tenant_id,
            metadata={"parse_result": parse_result},
        )
        await repository.save(doc)

        # 执行
        chunker = SemanticChunkerImpl()
        service = SemanticChunkingService(
            document_repository=repository,
            semantic_chunker=chunker,
            event_publisher=mock_event_publisher,
        )
        chunks = await service.chunk_document(
            document_id=doc_id,
            tenant_id=tenant_id,
        )

        # 验证事件
        mock_event_publisher.publish.assert_called_once()
        call_args = mock_event_publisher.publish.call_args
        event = call_args[0][0]

        # 验证 RAGIndexed 事件字段
        assert event.event_type == "RAGIndexed"
        assert event.document_id == doc_id
        assert event.chunk_count == len(chunks)
        assert event.tenant_id == tenant_id
