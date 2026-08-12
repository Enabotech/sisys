"""词典异常单元测试

测试 DictionaryNotFoundError、DictionaryEntryConflictError、
DictionaryVersionConflictError 的构造、to_dict()、HTTP 映射。
"""

from __future__ import annotations

from src.domain.exceptions import (
    ConflictError,
    DictionaryEntryConflictError,
    DictionaryNotFoundError,
    DictionaryVersionConflictError,
    NotFoundError,
)


class TestDictionaryNotFoundError:
    """DictionaryNotFoundError 异常测试"""

    def test_inherits_not_found(self):
        """继承 NotFoundError"""
        assert issubclass(DictionaryNotFoundError, NotFoundError)

    def test_code(self):
        """编码为 EXCEPTION_270"""
        assert DictionaryNotFoundError.code == "EXCEPTION_270"

    def test_construct_with_message(self):
        """带消息构造"""
        exc = DictionaryNotFoundError(message="词条不存在")
        assert "词条不存在" in str(exc)

    def test_construct_with_term(self):
        """带 term 上下文构造"""
        exc = DictionaryNotFoundError(term="BLM")
        assert exc.term == "BLM"
        assert exc.context["term"] == "BLM"

    def test_to_dict_contains_code(self):
        """to_dict() 包含 code"""
        exc = DictionaryNotFoundError(term="BLM")
        data = exc.to_dict()
        assert data["code"] == "EXCEPTION_270"

    def test_to_dict_contains_context(self):
        """to_dict() 包含 term 上下文"""
        exc = DictionaryNotFoundError(term="BLM")
        data = exc.to_dict()
        assert data["context"]["term"] == "BLM"


class TestDictionaryEntryConflictError:
    """DictionaryEntryConflictError 异常测试"""

    def test_inherits_conflict(self):
        """继承 ConflictError"""
        assert issubclass(DictionaryEntryConflictError, ConflictError)

    def test_code(self):
        """编码为 EXCEPTION_271"""
        assert DictionaryEntryConflictError.code == "EXCEPTION_271"

    def test_construct_with_term(self):
        """带 term 上下文构造"""
        exc = DictionaryEntryConflictError(term="BLM")
        assert exc.term == "BLM"
        assert exc.context["term"] == "BLM"

    def test_to_dict_contains_code(self):
        """to_dict() 包含 code"""
        exc = DictionaryEntryConflictError(term="BLM")
        data = exc.to_dict()
        assert data["code"] == "EXCEPTION_271"

    def test_to_dict_contains_context(self):
        """to_dict() 包含 term 上下文"""
        exc = DictionaryEntryConflictError(term="BLM")
        data = exc.to_dict()
        assert data["context"]["term"] == "BLM"


class TestDictionaryVersionConflictError:
    """DictionaryVersionConflictError 异常测试"""

    def test_inherits_conflict(self):
        """继承 ConflictError"""
        assert issubclass(DictionaryVersionConflictError, ConflictError)

    def test_code(self):
        """编码为 EXCEPTION_272"""
        assert DictionaryVersionConflictError.code == "EXCEPTION_272"

    def test_construct_with_versions(self):
        """带版本上下文构造"""
        exc = DictionaryVersionConflictError(expected_version=1, actual_version=2)
        assert exc.expected_version == 1
        assert exc.actual_version == 2
        assert exc.context["expected_version"] == 1
        assert exc.context["actual_version"] == 2

    def test_to_dict_contains_versions(self):
        """to_dict() 包含版本上下文"""
        exc = DictionaryVersionConflictError(expected_version=1, actual_version=2)
        data = exc.to_dict()
        assert data["context"]["expected_version"] == 1
        assert data["context"]["actual_version"] == 2

    def test_to_dict_contains_code(self):
        """to_dict() 包含 code"""
        exc = DictionaryVersionConflictError(expected_version=1, actual_version=2)
        data = exc.to_dict()
        assert data["code"] == "EXCEPTION_272"


class TestExceptionChain:
    """异常链测试"""

    def test_cause_chain(self):
        """cause 链正确序列化"""
        cause = ValueError("underlying error")
        exc = DictionaryNotFoundError(term="BLM", cause=cause)
        data = exc.to_dict()
        assert data["cause"]["type"] == "ValueError"
        assert data["cause"]["message"] == "underlying error"

    def test_http_mapping_via_base(self):
        """通过基类映射 HTTP 状态码"""
        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        # DictionaryNotFoundError -> NotFoundError -> 404
        assert EXCEPTION_HTTP_MAP[NotFoundError] == 404
        # DictionaryEntryConflictError -> ConflictError -> 409
        assert EXCEPTION_HTTP_MAP[ConflictError] == 409
