"""文档版本冲突异常单元测试

测试 DocumentVersionConflictError 异常：
- 构造与属性
- to_dict() 序列化
- HTTP 映射
- 编码唯一性
"""

from __future__ import annotations

from uuid import uuid4

from src.domain.exceptions import DocumentVersionConflictError
from src.domain.exceptions._code_ranges import get_subdomain_for_class
from src.domain.exceptions.business_exceptions import ConflictError
from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP, _get_http_status


class TestDocumentVersionConflictErrorCreation:
    """测试异常构造"""

    def test_create_with_all_params(self) -> None:
        """使用所有参数创建异常"""
        doc_id = uuid4()
        exc = DocumentVersionConflictError(
            document_id=doc_id,
            expected_version=2,
            actual_version=3,
        )

        assert exc.code == "EXCEPTION_216"
        assert exc.document_id == doc_id
        assert exc.expected_version == 2
        assert exc.actual_version == 3
        assert str(doc_id) in str(exc)
        assert "2" in str(exc)
        assert "3" in str(exc)

    def test_default_message_contains_conflict_info(self) -> None:
        """默认消息应包含版本冲突信息"""
        doc_id = uuid4()
        exc = DocumentVersionConflictError(
            document_id=doc_id,
            expected_version=1,
            actual_version=2,
        )

        assert "文档版本冲突" in str(exc)
        assert str(doc_id) in str(exc)
        assert "expected=1" in str(exc) or "1" in str(exc)
        assert "actual=2" in str(exc) or "2" in str(exc)


class TestDocumentVersionConflictErrorInheritance:
    """测试继承关系"""

    def test_inherits_from_conflict_error(self) -> None:
        """应继承自 ConflictError"""
        exc = DocumentVersionConflictError(
            document_id=uuid4(),
            expected_version=1,
            actual_version=2,
        )

        assert isinstance(exc, ConflictError)

    def test_is_domain_error(self) -> None:
        """应属于 DomainError 层次"""
        exc = DocumentVersionConflictError(
            document_id=uuid4(),
            expected_version=1,
            actual_version=2,
        )

        from src.domain.exceptions import DomainError

        assert isinstance(exc, DomainError)


class TestDocumentVersionConflictErrorSerialization:
    """测试序列化"""

    def test_to_dict_contains_all_fields(self) -> None:
        """to_dict() 应包含代码、消息和上下文"""
        doc_id = uuid4()
        exc = DocumentVersionConflictError(
            document_id=doc_id,
            expected_version=1,
            actual_version=3,
            context={"extra": "info"},
        )

        result = exc.to_dict()

        assert result["code"] == "EXCEPTION_216"
        assert "文档版本冲突" in result["message"]
        assert result["context"]["document_id"] == str(doc_id)
        assert result["context"]["expected_version"] == 1
        assert result["context"]["actual_version"] == 3
        assert result["context"]["extra"] == "info"


class TestDocumentVersionConflictErrorHttpMapping:
    """测试 HTTP 映射"""

    def test_http_status_is_409(self) -> None:
        """HTTP 状态码应为 409 CONFLICT"""
        exc = DocumentVersionConflictError(
            document_id=uuid4(),
            expected_version=1,
            actual_version=2,
        )

        status = _get_http_status(exc)
        assert status == 409

    def test_mapped_in_exception_http_map(self) -> None:
        """应在 EXCEPTION_HTTP_MAP 中有映射"""
        assert DocumentVersionConflictError in EXCEPTION_HTTP_MAP
        assert EXCEPTION_HTTP_MAP[DocumentVersionConflictError] == 409


class TestDocumentVersionConflictErrorCodeRange:
    """测试编码范围"""

    def test_code_in_storage_range(self) -> None:
        """编码 216 应在 storage 子域范围 (211-219) 内"""
        subdomain = get_subdomain_for_class("DocumentVersionConflictError")
        assert subdomain == "storage"

    def test_code_is_216(self) -> None:
        """编码应为 EXCEPTION_216"""
        exc = DocumentVersionConflictError(
            document_id=uuid4(),
            expected_version=1,
            actual_version=2,
        )

        assert exc.code == "EXCEPTION_216"


class TestDocumentVersionConflictErrorCause:
    """测试异常链"""

    def test_cause_stored_correctly(self) -> None:
        """cause 应正确存储和获取"""
        cause = ValueError("underlying error")
        exc = DocumentVersionConflictError(
            document_id=uuid4(),
            expected_version=1,
            actual_version=2,
            cause=cause,
        )

        assert exc.cause is cause
