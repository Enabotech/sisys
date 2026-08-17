"""Story 3.7 检索相关性评估端口契约单元测试

验证 RelevanceEvaluationPort Protocol 的方法签名、参数默认值和 runtime_checkable。
"""

from __future__ import annotations

import inspect

from src.domain.ports.l3_vector import SearchResult
from src.domain.ports.llm_client import LLMConfig


class TestRelevanceEvaluationPortProtocol:
    """RelevanceEvaluationPort Protocol 验证"""

    def test_is_protocol(self) -> None:
        """RelevanceEvaluationPort 是 Protocol"""
        import typing

        from src.domain.ports.relevance_evaluation import RelevanceEvaluationPort

        assert typing.Protocol in RelevanceEvaluationPort.__mro__

    def test_is_runtime_checkable(self) -> None:
        """RelevanceEvaluationPort 是 @runtime_checkable"""
        from src.domain.ports.relevance_evaluation import RelevanceEvaluationPort

        assert hasattr(RelevanceEvaluationPort, "__instancecheck__")

    def test_evaluate_method_exists(self) -> None:
        """evaluate 方法存在"""
        from src.domain.ports.relevance_evaluation import RelevanceEvaluationPort

        assert hasattr(RelevanceEvaluationPort, "evaluate")

    def test_evaluate_is_async(self) -> None:
        """evaluate 是异步方法"""
        from src.domain.ports.relevance_evaluation import RelevanceEvaluationPort

        assert inspect.iscoroutinefunction(RelevanceEvaluationPort.evaluate)

    def test_evaluate_signature(self) -> None:
        """evaluate 方法签名正确"""
        from src.domain.ports.relevance_evaluation import RelevanceEvaluationPort

        sig = inspect.signature(RelevanceEvaluationPort.evaluate)
        params = sig.parameters
        assert "self" in params
        assert "query_text" in params
        assert "search_results" in params
        assert "config" in params

    def test_evaluate_query_text_type(self) -> None:
        """query_text 参数类型为 str"""
        from src.domain.ports.relevance_evaluation import RelevanceEvaluationPort

        sig = inspect.signature(RelevanceEvaluationPort.evaluate)
        query_annotation = sig.parameters["query_text"].annotation
        if isinstance(query_annotation, str):
            assert query_annotation == "str"
        else:
            assert query_annotation is str

    def test_evaluate_search_results_type(self) -> None:
        """search_results 参数类型为 list[SearchResult]"""
        from src.domain.ports.relevance_evaluation import RelevanceEvaluationPort

        sig = inspect.signature(RelevanceEvaluationPort.evaluate)
        sr_annotation = str(sig.parameters["search_results"].annotation)
        assert "SearchResult" in sr_annotation

    def test_evaluate_config_default_none(self) -> None:
        """config 参数默认值为 None"""
        from src.domain.ports.relevance_evaluation import RelevanceEvaluationPort

        sig = inspect.signature(RelevanceEvaluationPort.evaluate)
        assert sig.parameters["config"].default is None

    def test_evaluate_return_type(self) -> None:
        """evaluate 返回类型为 RelevanceEvaluationResult"""
        from src.domain.ports.relevance_evaluation import RelevanceEvaluationPort

        sig = inspect.signature(RelevanceEvaluationPort.evaluate)
        return_annotation = str(sig.return_annotation)
        assert "RelevanceEvaluationResult" in return_annotation

    def test_quick_rule_check_method_exists(self) -> None:
        """quick_rule_check 方法存在"""
        from src.domain.ports.relevance_evaluation import RelevanceEvaluationPort

        assert hasattr(RelevanceEvaluationPort, "quick_rule_check")

    def test_quick_rule_check_is_async(self) -> None:
        """quick_rule_check 是异步方法"""
        from src.domain.ports.relevance_evaluation import RelevanceEvaluationPort

        assert inspect.iscoroutinefunction(RelevanceEvaluationPort.quick_rule_check)

    def test_quick_rule_check_signature(self) -> None:
        """quick_rule_check 方法签名正确"""
        from src.domain.ports.relevance_evaluation import RelevanceEvaluationPort

        sig = inspect.signature(RelevanceEvaluationPort.quick_rule_check)
        params = sig.parameters
        assert "self" in params
        assert "query_text" in params
        assert "search_results" in params

    def test_quick_rule_check_return_type(self) -> None:
        """quick_rule_check 返回类型为 RuleBasedResult"""
        from src.domain.ports.relevance_evaluation import RelevanceEvaluationPort

        sig = inspect.signature(RelevanceEvaluationPort.quick_rule_check)
        return_annotation = str(sig.return_annotation)
        assert "RuleBasedResult" in return_annotation

    def test_result_types_are_typed_dict(self) -> None:
        """RelevanceEvaluationResult 和 RuleBasedResult 是 TypedDict"""

        from src.domain.ports.relevance_evaluation import RelevanceEvaluationResult, RuleBasedResult

        # TypedDict 的起源是 dict
        assert issubclass(RelevanceEvaluationResult, dict)
        assert issubclass(RuleBasedResult, dict)

    def test_relevance_evaluation_result_fields(self) -> None:
        """RelevanceEvaluationResult 包含所有字段"""
        from src.domain.ports.relevance_evaluation import RelevanceEvaluationResult

        hints = RelevanceEvaluationResult.__annotations__
        assert "context_relevance" in hints
        assert "context_relevance_reason" in hints
        assert "completeness" in hints
        assert "completeness_reason" in hints
        assert "timeliness" in hints
        assert "timeliness_reason" in hints
        assert "overall_score" in hints
        assert "should_block" in hints
        assert "block_reason" in hints

    def test_rule_based_result_fields(self) -> None:
        """RuleBasedResult 包含所有字段"""
        from src.domain.ports.relevance_evaluation import RuleBasedResult

        hints = RuleBasedResult.__annotations__
        assert "has_valid_results" in hints
        assert "min_score" in hints
        assert "max_score" in hints
        assert "avg_score" in hints
        assert "result_count" in hints
        assert "quick_block" in hints

    def test_port_imports_search_result(self) -> None:
        """端口从 l3_vector 导入 SearchResult"""
        from src.domain.ports import relevance_evaluation as re_module

        source = inspect.getsource(re_module)
        assert "from src.domain.ports.l3_vector import SearchResult" in source

    def test_port_imports_llm_config(self) -> None:
        """端口从 llm_client 导入 LLMConfig"""
        from src.domain.ports import relevance_evaluation as re_module

        source = inspect.getsource(re_module)
        assert "from src.domain.ports.llm_client import LLMConfig" in source

    def test_protocol_method_ellipsis_body(self) -> None:
        """Protocol 方法体使用 ... 占位符"""
        from src.domain.ports.relevance_evaluation import RelevanceEvaluationPort

        source = inspect.getsource(RelevanceEvaluationPort.evaluate)
        assert "..." in source

    def test_struct_validates_with_protocol(self) -> None:
        """验证实现类可通过 Protocol 结构检查"""
        from src.domain.ports.relevance_evaluation import RelevanceEvaluationPort, RelevanceEvaluationResult, RuleBasedResult

        class MockEvaluator:
            async def evaluate(
                self,
                query_text: str,
                search_results: list[SearchResult],
                config: LLMConfig | None = None,
            ) -> RelevanceEvaluationResult:
                return RelevanceEvaluationResult(
                    context_relevance=0.8,
                    context_relevance_reason="test",
                    completeness=0.7,
                    completeness_reason="test",
                    timeliness=0.9,
                    timeliness_reason="test",
                    overall_score=0.8,
                    should_block=False,
                    block_reason=None,
                )

            async def quick_rule_check(
                self,
                query_text: str,
                search_results: list[SearchResult],
            ) -> RuleBasedResult:
                return RuleBasedResult(
                    has_valid_results=True,
                    min_score=0.5,
                    max_score=0.9,
                    avg_score=0.7,
                    result_count=5,
                    quick_block=False,
                )

        mock = MockEvaluator()
        assert isinstance(mock, RelevanceEvaluationPort), "MockEvaluator 应通过 RelevanceEvaluationPort 结构检查"


class TestRelevanceEvaluationPortDocstring:
    """RelevanceEvaluationPort docstring 验证"""

    def test_module_has_docstring(self) -> None:
        """模块有 docstring"""
        from src.domain.ports import relevance_evaluation as re_module

        assert re_module.__doc__ is not None
        assert len(re_module.__doc__) > 10

    def test_class_has_docstring(self) -> None:
        """类有 docstring"""
        from src.domain.ports.relevance_evaluation import RelevanceEvaluationPort

        assert RelevanceEvaluationPort.__doc__ is not None
        assert len(RelevanceEvaluationPort.__doc__) > 10

    def test_method_has_docstring(self) -> None:
        """方法有 docstring"""
        from src.domain.ports.relevance_evaluation import RelevanceEvaluationPort

        assert RelevanceEvaluationPort.evaluate.__doc__ is not None
        assert len(RelevanceEvaluationPort.evaluate.__doc__) > 10

    def test_method_docstring_has_args(self) -> None:
        """方法 docstring 包含 Args 说明"""
        from src.domain.ports.relevance_evaluation import RelevanceEvaluationPort

        doc = RelevanceEvaluationPort.evaluate.__doc__
        assert doc is not None
        assert "Args:" in doc

    def test_method_docstring_has_returns(self) -> None:
        """方法 docstring 包含 Returns 说明"""
        from src.domain.ports.relevance_evaluation import RelevanceEvaluationPort

        doc = RelevanceEvaluationPort.evaluate.__doc__
        assert doc is not None
        assert "Returns:" in doc

    def test_method_docstring_has_raises(self) -> None:
        """方法 docstring 包含 Raises 说明"""
        from src.domain.ports.relevance_evaluation import RelevanceEvaluationPort

        doc = RelevanceEvaluationPort.evaluate.__doc__
        assert doc is not None
        assert "Raises:" in doc
