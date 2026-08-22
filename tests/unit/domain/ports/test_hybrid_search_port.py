"""R2 混合检索端口契约单元测试

验证 HybridSearchPort Protocol 的方法签名、@runtime_checkable 可用性。
遵循 R2：应用层端口组合领域层 SearchServicePort 三路检索。
"""

from __future__ import annotations

import inspect

from src.domain.ports.hybrid_search import HybridSearchPort
from src.domain.ports.l3_vector import SearchResult


class TestHybridSearchPort:
    """HybridSearchPort Protocol 验证"""

    def test_is_protocol(self) -> None:
        """验证 HybridSearchPort 是 Protocol"""
        import typing

        assert typing.Protocol in HybridSearchPort.__mro__

    def test_is_runtime_checkable(self) -> None:
        """验证 @runtime_checkable 可用"""
        assert hasattr(HybridSearchPort, "__instancecheck__")

    def test_search_signature(self) -> None:
        """验证 search 方法签名"""
        sig = inspect.signature(HybridSearchPort.search)
        params = {p.name: p for p in sig.parameters.values()}

        assert "self" in params, "缺少 self 参数"
        assert "collection" in params, "缺少 collection 参数"
        assert "query_text" in params, "缺少 query_text 参数"
        assert "limit" in params, "缺少 limit 参数"
        assert "tenant_id" in params, "缺少 tenant_id 参数"
        assert "filter_payload" in params, "缺少 filter_payload 参数"
        assert "weights" in params, "缺少 weights 参数（三路权重）"

        # limit 默认值为 10
        assert params["limit"].default == 10, f"limit 默认值应为 10, 实际 {params['limit'].default}"
        # tenant_id 默认值为 None
        assert params["tenant_id"].default is None, "tenant_id 默认应为 None"
        # weights 默认值为 None
        assert params["weights"].default is None, "weights 默认应为 None"

        # 返回类型为 list[SearchResult]
        return_annotation = str(sig.return_annotation)
        assert "list[SearchResult]" in return_annotation, f"返回类型应为 list[SearchResult], 实际 {return_annotation}"

    def test_search_is_async(self) -> None:
        """验证 search 是 async 方法"""
        assert inspect.iscoroutinefunction(HybridSearchPort.search), "search 必须是 async 方法"

    def test_struct_validates_with_protocol(self) -> None:
        """验证实现类可通过 HybridSearchPort 结构检查"""

        class MockHybridSearch:
            async def search(
                self,
                collection: str,
                query_text: str,
                limit: int = 10,
                tenant_id: str | None = None,
                filter_payload: dict | None = None,
                weights: list[float] | None = None,
            ) -> list[SearchResult]:
                return []

        mock = MockHybridSearch()
        assert isinstance(mock, HybridSearchPort), "MockHybridSearch 应通过 HybridSearchPort 结构检查"

    def test_protocol_method_ellipsis_body(self) -> None:
        """Protocol 方法体使用 ... 占位符"""
        source = inspect.getsource(HybridSearchPort.search)
        assert "..." in source

    def test_module_has_docstring(self) -> None:
        """模块有 docstring"""
        import src.domain.ports.hybrid_search as hybrid_module

        assert hybrid_module.__doc__ is not None
        assert len(hybrid_module.__doc__) > 10

    def test_class_has_docstring(self) -> None:
        """类有 docstring"""
        assert HybridSearchPort.__doc__ is not None
        assert len(HybridSearchPort.__doc__) > 10
