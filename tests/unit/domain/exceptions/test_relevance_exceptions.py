"""Story 3.7 检索相关性评估异常单元测试

验证 RelevanceEvaluationError 和 RelevanceEvaluationBlockedError 的构造、序列化。
"""

from __future__ import annotations


class TestRelevanceEvaluationError:
    """RelevanceEvaluationError 异常测试"""

    def test_importable(self) -> None:
        """异常可以从 domain.exceptions 导入"""
        from src.domain.exceptions import RelevanceEvaluationError

        assert RelevanceEvaluationError is not None

    def test_code_is_360(self) -> None:
        """错误码为 EXCEPTION_360"""
        from src.domain.exceptions import RelevanceEvaluationError

        assert RelevanceEvaluationError.code == "EXCEPTION_360"

    def test_default_message(self) -> None:
        """默认消息正确"""
        from src.domain.exceptions import RelevanceEvaluationError

        exc = RelevanceEvaluationError(query_text="test", result_count=5)
        assert exc.message == "LLM 评估调用失败"

    def test_constructor_with_query_text(self) -> None:
        """构造器接受 query_text 和 result_count 参数"""
        from src.domain.exceptions import RelevanceEvaluationError

        exc = RelevanceEvaluationError(query_text="测试查询文本", result_count=5)
        assert exc.context["query_text"] == "测试查询文本"
        assert exc.context["result_count"] == 5

    def test_query_text_truncated_to_100(self) -> None:
        """query_text 截断至 100 字符"""
        from src.domain.exceptions import RelevanceEvaluationError

        long_text = "a" * 200
        exc = RelevanceEvaluationError(query_text=long_text, result_count=0)
        assert len(exc.context["query_text"]) == 100

    def test_to_dict_contains_code_message_context(self) -> None:
        """to_dict() 包含 code message context"""
        from src.domain.exceptions import RelevanceEvaluationError

        exc = RelevanceEvaluationError(query_text="test", result_count=3, message="LLM 调用超时")
        d = exc.to_dict()
        assert d["code"] == "EXCEPTION_360"
        assert "message" in d
        assert "context" in d
        assert d["context"]["query_text"] == "test"
        assert d["context"]["result_count"] == 3

    def test_cause_chain(self) -> None:
        """异常链正确"""
        from src.domain.exceptions import RelevanceEvaluationError

        cause = RuntimeError("LLM API 返回 500")
        exc = RelevanceEvaluationError(query_text="test", result_count=2, cause=cause)
        assert exc.cause is cause
        d = exc.to_dict()
        assert "cause" in d
        assert "LLM API 返回 500" in str(d["cause"])

    def test_custom_message(self) -> None:
        """自定义消息"""
        from src.domain.exceptions import RelevanceEvaluationError

        exc = RelevanceEvaluationError(query_text="test", result_count=1, message="自定义错误消息")
        assert exc.message == "自定义错误消息"

    def test_inherits_from_external_exception(self) -> None:
        """继承 ExternalException"""
        from src.domain.exceptions import ExternalException, RelevanceEvaluationError

        assert issubclass(RelevanceEvaluationError, ExternalException)


class TestRelevanceEvaluationBlockedError:
    """RelevanceEvaluationBlockedError 异常测试"""

    def test_importable(self) -> None:
        """异常可以从 domain.exceptions 导入"""
        from src.domain.exceptions import RelevanceEvaluationBlockedError

        assert RelevanceEvaluationBlockedError is not None

    def test_code_is_361(self) -> None:
        """错误码为 EXCEPTION_361"""
        from src.domain.exceptions import RelevanceEvaluationBlockedError

        assert RelevanceEvaluationBlockedError.code == "EXCEPTION_361"

    def test_default_message(self) -> None:
        """默认消息正确"""
        from src.domain.exceptions import RelevanceEvaluationBlockedError

        exc = RelevanceEvaluationBlockedError(query_text="test", overall_score=0.45, block_reason="数据不足")
        assert exc.message == "检索结果不足被阻断"

    def test_constructor_with_all_params(self) -> None:
        """构造器接受所有参数"""
        from src.domain.exceptions import RelevanceEvaluationBlockedError

        exc = RelevanceEvaluationBlockedError(
            query_text="测试查询",
            overall_score=0.45,
            block_reason="数据不足",
        )
        assert exc.context["query_text"] == "测试查询"
        assert exc.context["overall_score"] == 0.45
        assert exc.context["block_reason"] == "数据不足"

    def test_to_dict_contains_code_message_context(self) -> None:
        """to_dict() 包含 code message context"""
        from src.domain.exceptions import RelevanceEvaluationBlockedError

        exc = RelevanceEvaluationBlockedError(query_text="test", overall_score=0.3, block_reason="数据不足")
        d = exc.to_dict()
        assert d["code"] == "EXCEPTION_361"
        assert "message" in d
        assert "context" in d
        assert d["context"]["overall_score"] == 0.3
        assert d["context"]["block_reason"] == "数据不足"

    def test_cause_chain(self) -> None:
        """异常链正确"""
        from src.domain.exceptions import RelevanceEvaluationBlockedError

        cause = ValueError("score too low")
        exc = RelevanceEvaluationBlockedError(
            query_text="test",
            overall_score=0.4,
            block_reason="数据不足",
            cause=cause,
        )
        assert exc.cause is cause

    def test_inherits_from_business_exception(self) -> None:
        """继承 BusinessException"""
        from src.domain.exceptions import BusinessException, RelevanceEvaluationBlockedError

        assert issubclass(RelevanceEvaluationBlockedError, BusinessException)
