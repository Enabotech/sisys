"""Tests for DocumentRepositoryPort Protocol interface"""

import inspect

from src.domain.ports.document_repository import DocumentQuery, DocumentRepositoryPort


class TestDocumentRepositoryPortInterface:
    """验证端口 Protocol 接口签名"""

    def test_is_runtime_checkable(self) -> None:
        assert hasattr(DocumentRepositoryPort, "__protocol_attrs__") or hasattr(DocumentRepositoryPort, "_is_protocol")

    def test_has_save_method(self) -> None:
        assert hasattr(DocumentRepositoryPort, "save")
        sig = inspect.signature(DocumentRepositoryPort.save)
        params = list(sig.parameters.keys())
        assert "self" in params or "document" in params

    def test_has_find_method(self) -> None:
        assert hasattr(DocumentRepositoryPort, "find")
        sig = inspect.signature(DocumentRepositoryPort.find)
        params = list(sig.parameters.keys())
        assert "query" in params

    def test_has_list_method(self) -> None:
        assert hasattr(DocumentRepositoryPort, "list")
        sig = inspect.signature(DocumentRepositoryPort.list)
        params = list(sig.parameters.keys())
        assert "query" in params

    def test_find_accepts_document_query(self) -> None:
        """find 的 query 参数类型为 DocumentQuery"""
        sig = inspect.signature(DocumentRepositoryPort.find)
        assert "query" in sig.parameters

    def test_document_query_has_tenant_id(self) -> None:
        """DocumentQuery 必须包含 tenant_id"""
        sig = inspect.signature(DocumentQuery)
        assert "tenant_id" in sig.parameters

    def test_document_query_has_pagination(self) -> None:
        """DocumentQuery 包含 offset/limit 分页参数"""
        sig = inspect.signature(DocumentQuery)
        assert "offset" in sig.parameters
        assert "limit" in sig.parameters

    def test_save_returns_document(self) -> None:
        assert hasattr(DocumentRepositoryPort, "save")

    def test_find_returns_optional_document(self) -> None:
        assert hasattr(DocumentRepositoryPort, "find")

    def test_three_required_methods(self) -> None:
        """端口必须有 save、find、list 三个方法"""
        required = {"save", "find", "list"}
        actual = {
            name
            for name in dir(DocumentRepositoryPort)
            if not name.startswith("_") and callable(getattr(DocumentRepositoryPort, name))
        }
        assert required.issubset(actual)

    def test_protocol_is_runtime_checkable(self) -> None:
        """Protocol 应支持运行时检查"""
        assert hasattr(DocumentRepositoryPort, "_is_runtime_protocol")


class TestDocumentQuery:
    """DocumentQuery 值对象测试"""

    def test_minimal_query(self) -> None:
        """最小查询仅需 tenant_id"""
        q = DocumentQuery(tenant_id="tenant-1")
        assert q.tenant_id == "tenant-1"
        assert q.document_id is None
        assert q.offset == 0
        assert q.limit == 100

    def test_full_query(self) -> None:
        """完整查询包含所有过滤条件"""
        import uuid

        doc_id = uuid.uuid4()
        q = DocumentQuery(
            tenant_id="tenant-1",
            document_id=doc_id,
            parse_status="completed",
            document_type="pdf",
            uploaded_by="user-1",
            offset=10,
            limit=50,
        )
        assert q.document_id == doc_id
        assert q.parse_status == "completed"
        assert q.document_type == "pdf"
        assert q.uploaded_by == "user-1"
        assert q.offset == 10
        assert q.limit == 50

    def test_document_query_is_frozen(self) -> None:
        """DocumentQuery 是不可变数据类"""
        import pytest

        q = DocumentQuery(tenant_id="tenant-1")
        with pytest.raises(Exception):
            object.__setattr__(q, "tenant_id", "other-tenant")

    def test_document_query_default_pagination(self) -> None:
        """默认分页参数正确"""
        q = DocumentQuery(tenant_id="t")
        assert q.offset == 0
        assert q.limit == 100
