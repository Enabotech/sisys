"""RerankerPort 端口契约单元测试

验证 RerankerPort Protocol 的方法签名、@runtime_checkable 可用性。
遵循故事规范：端口统一返回 SearchResult，不定义 RerankResult 值对象。
"""

from __future__ import annotations

from src.domain.ports.l3_vector import SearchResult
from src.domain.ports.reranker import RerankerPort


class TestRerankerPort:
    """RerankerPort Protocol 验证"""

    def test_is_protocol(self) -> None:
        """验证 RerankerPort 是 Protocol"""
        # 通过 typing 模块判断是否为 Protocol 类
        import typing

        # Protocol 的子类会在 MRO 中包含 Protocol 和 Generic
        assert typing.Protocol in RerankerPort.__mro__

    def test_is_runtime_checkable(self) -> None:
        """验证 @runtime_checkable 可用"""
        assert hasattr(RerankerPort, "__instancecheck__")

    def test_rerank_method_signature(self) -> None:
        """验证 rerank 方法签名"""
        import inspect

        sig = inspect.signature(RerankerPort.rerank)
        params = list(sig.parameters.values())

        # 方法参数
        param_names = [p.name for p in params]
        assert "self" in param_names, "缺少 self 参数"
        assert "query" in param_names, "缺少 query 参数"
        assert "results" in param_names, "缺少 results 参数"
        assert "top_k" in param_names, "缺少 top_k 参数"

        # 参数类型注解（from __future__ import annotations 下为字符串）
        query_param = params[param_names.index("query")]
        query_annotation = query_param.annotation
        if isinstance(query_annotation, str):
            assert query_annotation == "str", f"query 类型应为 str, 实际 {query_annotation}"
        else:
            assert query_annotation is str, f"query 类型应为 str, 实际 {query_annotation}"

        results_param = params[param_names.index("results")]
        results_annotation = str(results_param.annotation)
        assert "list[SearchResult]" in results_annotation or "SearchResult" in results_annotation

        # 返回类型
        return_annotation = sig.return_annotation
        return_str = str(return_annotation)
        assert "list[SearchResult]" in return_str or "SearchResult" in return_str, (
            f"返回类型应为 list[SearchResult], 实际 {return_str}"
        )

    def test_rerank_method_async(self) -> None:
        """验证 rerank 是 async 方法"""
        import inspect

        assert inspect.iscoroutinefunction(RerankerPort.rerank), "rerank 必须是 async 方法"

    def test_top_k_default_value(self) -> None:
        """验证 top_k 默认值为 20"""
        import inspect

        sig = inspect.signature(RerankerPort.rerank)
        params = list(sig.parameters.values())
        top_k_param = params[[p.name for p in params].index("top_k")]
        assert top_k_param.default == 20, f"top_k 默认值应为 20, 实际 {top_k_param.default}"

    def test_no_rerank_result_value_object(self) -> None:
        """验证不导入 RerankResult 值对象"""
        # RerankResult 不应存在于 ports 模块中
        import src.domain.ports as ports_module

        assert not hasattr(ports_module, "RerankResult"), "RerankResult 值对象已删除，不应存在"

    def test_struct_validates_with_protocol(self) -> None:
        """验证实现类可通过 Protocol 结构检查"""

        class MockReranker:
            async def rerank(self, query: str, results: list[SearchResult], top_k: int = 20) -> list[SearchResult]:
                return results[:top_k]

        mock = MockReranker()
        assert isinstance(mock, RerankerPort), "MockReranker 应通过 RerankerPort 结构检查"
