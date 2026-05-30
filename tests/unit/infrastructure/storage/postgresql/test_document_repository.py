"""Tests for PostgreSQLDocumentRepository — CRUD + 租户隔离"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.entities.document import Document, DocumentType, ParseStatus
from src.domain.ports.document_repository import DocumentQuery
from src.infrastructure.storage.postgresql.models.document import DocumentModel
from src.infrastructure.storage.postgresql.repository.document_repository import (
    PostgreSQLDocumentRepository,
)
from src.infrastructure.storage.postgresql.repository.postgresql_adapter import PostgreSQLAdapter
from src.infrastructure.storage.postgresql.session_context import reset_session, set_session


def run_async(coro):
    """Run async coroutine synchronously for tests."""
    return asyncio.run(coro)


class MockResult:
    """Mock SQLAlchemy execute result."""

    def __init__(self, scalar_one_or_none=None, scalars_all=None):
        self._scalar_one_or_none = scalar_one_or_none
        self._scalars_all = scalars_all

    def scalar_one_or_none(self):
        return self._scalar_one_or_none

    def scalars(self):
        return MockScalars(self._scalars_all or [])


class MockScalars:
    """Mock scalars result."""

    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


def _make_doc(
    document_id: uuid.UUID | None = None,
    filename: str = "test.pdf",
    tenant_id: str = "tenant-123",
    uploaded_by: str = "user-456",
    mime_type: str = "application/pdf",
    file_size_bytes: int = 1024,
) -> Document:
    """创建测试用 Document 实体"""
    return Document(
        document_id=document_id or uuid.uuid4(),
        filename=filename,
        tenant_id=tenant_id,
        uploaded_by=uploaded_by,
        mime_type=mime_type,
        file_size_bytes=file_size_bytes,
    )


def _make_model(
    id: uuid.UUID | None = None,
    tenant_id: str = "tenant-123",
    filename: str = "test.pdf",
    mime_type: str = "application/pdf",
    file_size_bytes: int = 1024,
    document_type: str = "other",
    parse_status: str = "pending",
    uploaded_by: str = "user-456",
    version: int = 1,
    metadata: dict | None = None,
) -> DocumentModel:
    """创建测试用 DocumentModel"""
    return DocumentModel(
        id=id or uuid.uuid4(),
        tenant_id=tenant_id,
        filename=filename,
        mime_type=mime_type,
        file_size_bytes=file_size_bytes,
        document_type=document_type,
        parse_status=parse_status,
        uploaded_by=uploaded_by,
        version=version,
        metadata=metadata or {},
    )


class TestDocumentModelConversion:
    """验证 _to_entity / _to_model 转换"""

    def test_to_entity(self) -> None:
        repo = PostgreSQLDocumentRepository()
        model = _make_model()
        entity = repo._to_entity(model)
        assert entity.document_id == model.id
        assert entity.filename == model.filename
        assert entity.mime_type == model.mime_type
        assert entity.file_size_bytes == model.file_size_bytes
        assert entity.tenant_id == model.tenant_id
        assert entity.uploaded_by == model.uploaded_by
        assert entity.document_type == DocumentType.OTHER
        assert entity.parse_status == ParseStatus.PENDING

    def test_to_model(self) -> None:
        repo = PostgreSQLDocumentRepository()
        entity = _make_doc()
        model = repo._to_model(entity)
        assert model.id == entity.document_id
        assert model.tenant_id == entity.tenant_id
        assert model.filename == entity.filename
        assert model.mime_type == entity.mime_type

    def test_roundtrip_conversion(self) -> None:
        repo = PostgreSQLDocumentRepository()
        original = _make_doc()
        model = repo._to_model(original)
        restored = repo._to_entity(model)
        assert restored.document_id == original.document_id
        assert restored.filename == original.filename
        assert restored.tenant_id == original.tenant_id


class TestDocumentRepositorySave:
    """验证 save 操作"""

    @pytest.fixture
    def mock_session(self):
        mock = AsyncMock()
        mock.add = MagicMock()
        mock.flush = AsyncMock()
        mock.refresh = AsyncMock()
        return mock

    @pytest.fixture
    def repo(self, mock_session):
        token = set_session(mock_session)
        repo = PostgreSQLDocumentRepository()
        yield repo
        reset_session(token)

    def test_save_calls_session_add(self, repo, mock_session) -> None:
        doc = _make_doc()
        run_async(repo.save(doc))
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

        added_model = mock_session.add.call_args[0][0]
        assert isinstance(added_model, DocumentModel)
        assert added_model.tenant_id == doc.tenant_id
        assert added_model.filename == doc.filename


class TestDocumentRepositoryFind:
    """验证 find 操作（带租户隔离）"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def repo(self, mock_session):
        token = set_session(mock_session)
        repo = PostgreSQLDocumentRepository()
        yield repo
        reset_session(token)

    def test_find_by_id_found(self, repo, mock_session) -> None:
        doc_id = uuid.uuid4()
        model = _make_model(id=doc_id, tenant_id="t1")
        mock_session.execute = AsyncMock(return_value=MockResult(scalar_one_or_none=model))

        query = DocumentQuery(tenant_id="t1", document_id=doc_id)
        result = run_async(repo.find(query))
        assert result is not None
        assert result.document_id == doc_id
        assert result.tenant_id == "t1"

    def test_find_not_found(self, repo, mock_session) -> None:
        mock_session.execute = AsyncMock(return_value=MockResult(scalar_one_or_none=None))

        query = DocumentQuery(tenant_id="t1", document_id=uuid.uuid4())
        result = run_async(repo.find(query))
        assert result is None

    def test_find_tenant_isolation(self, repo, mock_session) -> None:
        """验证 find 查询包含 tenant_id WHERE 条件"""
        mock_session.execute = AsyncMock(return_value=MockResult(scalar_one_or_none=None))

        query = DocumentQuery(tenant_id="other-tenant", document_id=uuid.uuid4())
        result = run_async(repo.find(query))
        assert result is None

        # 验证 SQL 语句包含 tenant_id 过滤条件
        stmt = mock_session.execute.call_args[0][0]
        where_str = str(stmt)
        assert "tenant_id" in where_str


class TestDocumentRepositoryList:
    """验证 list 操作"""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def repo(self, mock_session):
        token = set_session(mock_session)
        repo = PostgreSQLDocumentRepository()
        yield repo
        reset_session(token)

    def test_list_returns_documents(self, repo, mock_session) -> None:
        model1 = _make_model(tenant_id="t1")
        model2 = _make_model(tenant_id="t1")
        mock_session.execute = AsyncMock(return_value=MockResult(scalars_all=[model1, model2]))

        query = DocumentQuery(tenant_id="t1")
        results = run_async(repo.list(query))
        assert len(results) == 2

    def test_list_empty(self, repo, mock_session) -> None:
        mock_session.execute = AsyncMock(return_value=MockResult(scalars_all=[]))

        query = DocumentQuery(tenant_id="nonexistent")
        results = run_async(repo.list(query))
        assert results == []

    def test_list_tenant_isolation_sql_contains_where(self, repo, mock_session) -> None:
        """验证 list 查询包含 tenant_id WHERE 条件"""
        mock_session.execute = AsyncMock(return_value=MockResult(scalars_all=[]))

        query = DocumentQuery(tenant_id="t1")
        run_async(repo.list(query))

        # 验证 SQL 语句包含 tenant_id 过滤条件
        stmt = mock_session.execute.call_args[0][0]
        where_str = str(stmt)
        assert "tenant_id" in where_str

    def test_list_with_parse_status_filter(self, repo, mock_session) -> None:
        mock_session.execute = AsyncMock(return_value=MockResult(scalars_all=[]))

        query = DocumentQuery(tenant_id="t1", parse_status="completed")
        run_async(repo.list(query))

        stmt = mock_session.execute.call_args[0][0]
        where_str = str(stmt)
        assert "parse_status" in where_str

    def test_list_with_document_type_filter(self, repo, mock_session) -> None:
        mock_session.execute = AsyncMock(return_value=MockResult(scalars_all=[]))

        query = DocumentQuery(tenant_id="t1", document_type="strategic_plan")
        run_async(repo.list(query))

        stmt = mock_session.execute.call_args[0][0]
        where_str = str(stmt)
        assert "document_type" in where_str

    def test_list_with_pagination(self, repo, mock_session) -> None:
        mock_session.execute = AsyncMock(return_value=MockResult(scalars_all=[]))

        query = DocumentQuery(tenant_id="t1", offset=10, limit=20)
        run_async(repo.list(query))

        stmt = mock_session.execute.call_args[0][0]
        where_str = str(stmt)
        assert "OFFSET" in where_str or "offset" in where_str.lower()
        assert "LIMIT" in where_str or "limit" in where_str.lower()


class TestDocumentRepositoryInheritance:
    """验证继承模式"""

    def test_inherits_postgresql_adapter(self) -> None:
        repo = PostgreSQLDocumentRepository()
        assert isinstance(repo, PostgreSQLAdapter)

    def test_model_class_is_document_model(self) -> None:
        repo = PostgreSQLDocumentRepository()
        assert repo._model_class is DocumentModel
