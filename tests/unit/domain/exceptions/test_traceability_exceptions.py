"""Story 3.8 溯源异常单元测试

验证 TraceabilityError 和 TraceabilityNotFoundError 的构造、序列化、编码和继承关系。
"""

from __future__ import annotations


class TestTraceabilityError:
    """TraceabilityError 异常测试"""

    def test_importable(self) -> None:
        """异常可以从 domain.exceptions 导入"""
        from src.domain.exceptions import TraceabilityError

        assert TraceabilityError is not None

    def test_code_is_370(self) -> None:
        """错误码为 EXCEPTION_370"""
        from src.domain.exceptions import TraceabilityError

        assert TraceabilityError.code == "EXCEPTION_370"

    def test_default_message(self) -> None:
        """默认消息正确"""
        from src.domain.exceptions import TraceabilityError

        exc = TraceabilityError(claim="测试结论", citation_count=3)
        assert exc.message == "溯源评估调用失败"

    def test_constructor_with_claim_and_count(self) -> None:
        """构造器接受 claim 和 citation_count 参数"""
        from src.domain.exceptions import TraceabilityError

        exc = TraceabilityError(claim="公司营收增长15%", citation_count=3)
        assert exc.context["claim"] == "公司营收增长15%"
        assert exc.context["citation_count"] == 3

    def test_claim_truncated_to_100(self) -> None:
        """claim 截断至 100 字符"""
        from src.domain.exceptions import TraceabilityError

        long_claim = "a" * 200
        exc = TraceabilityError(claim=long_claim, citation_count=0)
        assert len(exc.context["claim"]) == 100

    def test_to_dict_contains_code_message_context(self) -> None:
        """to_dict() 包含 code message context"""
        from src.domain.exceptions import TraceabilityError

        exc = TraceabilityError(claim="测试", citation_count=1, message="LLM 调用超时")
        d = exc.to_dict()
        assert d["code"] == "EXCEPTION_370"
        assert "message" in d
        assert "context" in d
        assert d["context"]["claim"] == "测试"
        assert d["context"]["citation_count"] == 1

    def test_cause_chain(self) -> None:
        """异常链正确"""
        from src.domain.exceptions import TraceabilityError

        cause = RuntimeError("LLM API 返回 500")
        exc = TraceabilityError(claim="测试", citation_count=1, cause=cause)
        assert exc.cause is cause

    def test_inherits_from_external_exception(self) -> None:
        """继承 ExternalException"""
        from src.domain.exceptions import ExternalException, TraceabilityError

        assert issubclass(TraceabilityError, ExternalException)


class TestTraceabilityNotFoundError:
    """TraceabilityNotFoundError 异常测试"""

    def test_importable(self) -> None:
        """异常可以从 domain.exceptions 导入"""
        from src.domain.exceptions import TraceabilityNotFoundError

        assert TraceabilityNotFoundError is not None

    def test_code_is_371(self) -> None:
        """错误码为 EXCEPTION_371"""
        from src.domain.exceptions import TraceabilityNotFoundError

        assert TraceabilityNotFoundError.code == "EXCEPTION_371"

    def test_default_message(self) -> None:
        """默认消息正确"""
        from src.domain.exceptions import TraceabilityNotFoundError

        exc = TraceabilityNotFoundError(claim="测试结论", min_confidence=0.7)
        assert exc.message == "未找到溯源引文"

    def test_constructor_with_claim_and_confidence(self) -> None:
        """构造器接受 claim 和 min_confidence 参数（向后兼容）"""
        from src.domain.exceptions import TraceabilityNotFoundError

        exc = TraceabilityNotFoundError(claim="测试", min_confidence=0.7)
        assert exc.context["claim"] == "测试"
        assert exc.context["min_confidence"] == 0.7

    def test_claim_truncated_to_100(self) -> None:
        """claim 截断至 100 字符"""
        from src.domain.exceptions import TraceabilityNotFoundError

        long_claim = "b" * 200
        exc = TraceabilityNotFoundError(claim=long_claim, min_confidence=0.5)
        assert len(exc.context["claim"]) == 100

    def test_to_dict_contains_code_message_context(self) -> None:
        """to_dict() 包含 code message context"""
        from src.domain.exceptions import TraceabilityNotFoundError

        exc = TraceabilityNotFoundError(claim="测试", min_confidence=0.7, message="引文不存在")
        d = exc.to_dict()
        assert d["code"] == "EXCEPTION_371"
        assert "message" in d
        assert "context" in d
        assert d["context"]["min_confidence"] == 0.7

    def test_inherits_from_business_exception(self) -> None:
        """继承 BusinessException"""
        from src.domain.exceptions import BusinessException, TraceabilityNotFoundError

        assert issubclass(TraceabilityNotFoundError, BusinessException)

    def test_constructor_with_citation_id(self) -> None:
        """构造器接受 citation_id 参数（get_citation_detail 场景）"""
        from src.domain.exceptions import TraceabilityNotFoundError

        exc = TraceabilityNotFoundError(citation_id="chunk-001-cit")
        assert exc.context["citation_id"] == "chunk-001-cit"
        assert "claim" not in exc.context
        assert "min_confidence" not in exc.context
        assert "document_id" not in exc.context

    def test_constructor_with_document_id(self) -> None:
        """构造器接受 document_id 参数（get_citation_by_document 场景）"""
        from src.domain.exceptions import TraceabilityNotFoundError

        exc = TraceabilityNotFoundError(document_id="12345678-1234-5678-1234-567812345678")
        assert exc.context["document_id"] == "12345678-1234-5678-1234-567812345678"
        assert "claim" not in exc.context
        assert "min_confidence" not in exc.context
        assert "citation_id" not in exc.context

    def test_constructor_with_citation_id_and_claim(self) -> None:
        """构造器可同时传入 citation_id 和 claim（组合场景）"""
        from src.domain.exceptions import TraceabilityNotFoundError

        exc = TraceabilityNotFoundError(citation_id="cit-1", claim="测试结论")
        assert exc.context["citation_id"] == "cit-1"
        assert exc.context["claim"] == "测试结论"

    def test_constructor_no_params_produces_empty_context(self) -> None:
        """无参数时 context 为空字典"""
        from src.domain.exceptions import TraceabilityNotFoundError

        exc = TraceabilityNotFoundError()
        assert exc.context == {}
