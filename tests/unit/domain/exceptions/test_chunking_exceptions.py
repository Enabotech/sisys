"""ChunkingError 领域异常测试

测试 ChunkingError 的构造、to_dict() 序列化、HTTP 422 映射。
"""

from __future__ import annotations

from uuid import UUID, uuid4

from src.domain.exceptions import BusinessRuleViolationError, ChunkingError


class TestChunkingError:
    """测试 ChunkingError 异常"""

    def test_has_correct_code(self) -> None:
        """验证异常编码为 EXCEPTION_218"""
        doc_id = uuid4()
        exc = ChunkingError(document_id=doc_id)
        assert exc.code == "EXCEPTION_218"

    def test_inherits_from_business_rule_violation(self) -> None:
        """验证继承自 BusinessRuleViolationError"""
        doc_id = uuid4()
        exc = ChunkingError(document_id=doc_id)
        assert isinstance(exc, BusinessRuleViolationError)

    def test_constructor_with_minimal_args(self) -> None:
        """验证最小参数构造"""
        doc_id = uuid4()
        exc = ChunkingError(document_id=doc_id)
        assert exc.document_id == doc_id
        assert exc.reason == ""
        assert "语义分块失败" in str(exc.message) if hasattr(exc, "message") else "语义分块失败" in str(exc)

    def test_constructor_with_all_args(self) -> None:
        """验证全参数构造"""
        doc_id = uuid4()
        cause = ValueError("原始错误")
        exc = ChunkingError(
            document_id=doc_id,
            reason="序列化失败",
            message="自定义消息",
            cause=cause,
            context={"extra": "info"},
        )
        assert exc.document_id == doc_id
        assert exc.reason == "序列化失败"
        assert exc.cause is cause

    def test_to_dict_contains_required_fields(self) -> None:
        """验证 to_dict 包含必需字段"""
        doc_id = uuid4()
        exc = ChunkingError(document_id=doc_id, reason="测试失败")
        d = exc.to_dict()
        assert d["code"] == "EXCEPTION_218"
        assert "语义分块失败" in d["message"]
        assert d["context"]["document_id"] == str(doc_id)
        assert d["context"]["reason"] == "测试失败"

    def test_to_dict_no_cause(self) -> None:
        """验证无 cause 时 to_dict 不包含 cause 字段"""
        doc_id = uuid4()
        exc = ChunkingError(document_id=doc_id)
        d = exc.to_dict()
        assert "cause" not in d

    def test_to_dict_with_cause(self) -> None:
        """验证含 cause 时 to_dict 包含 cause 字段"""
        doc_id = uuid4()
        cause = ValueError("原始错误")
        exc = ChunkingError(document_id=doc_id, cause=cause)
        d = exc.to_dict()
        assert d.get("cause") is not None
        assert d["cause"]["type"] == "ValueError"

    def test_http_status_422(self) -> None:
        """验证 HTTP 映射为 422 Unprocessable Entity"""
        from src.interfaces.api.exception_handlers import EXCEPTION_HTTP_MAP

        assert ChunkingError in EXCEPTION_HTTP_MAP
        from fastapi import status

        assert EXCEPTION_HTTP_MAP[ChunkingError] == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_document_id_type(self) -> None:
        """验证 document_id 类型为 UUID"""
        doc_id = uuid4()
        exc = ChunkingError(document_id=doc_id)
        assert isinstance(exc.document_id, UUID)
