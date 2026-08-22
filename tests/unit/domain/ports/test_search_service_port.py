"""Story 3.1a/3.1b/3.4 检索端口契约单元测试

验证 SearchServicePort / DenseSearchPort / SparseSearchPort / GraphSearchPort
Protocol 的方法签名、@runtime_checkable 可用性。
遵循故事规范：端口统一返回 list[SearchResult]。
"""

from __future__ import annotations

import inspect

from src.domain.ports.l3_vector import SearchResult
from src.domain.ports.search_service import (
    DenseSearchPort,
    GraphSearchPort,
    SearchServicePort,
    SparseSearchPort,
)


class TestSearchServicePort:
    """SearchServicePort Protocol 验证"""

    def test_is_protocol(self) -> None:
        """验证 SearchServicePort 是 Protocol"""
        assert inspect.isclass(SearchServicePort)
        import typing

        assert typing.Protocol in SearchServicePort.__mro__

    def test_is_runtime_checkable(self) -> None:
        """验证 @runtime_checkable 可用"""
        assert hasattr(SearchServicePort, "__instancecheck__")

    def test_search_signature(self) -> None:
        """验证 search 方法签名"""
        sig = inspect.signature(SearchServicePort.search)
        params = {p.name: p for p in sig.parameters.values()}

        assert "self" in params, "缺少 self 参数"
        assert "collection" in params, "缺少 collection 参数"
        assert "query_text" in params, "缺少 query_text 参数"
        assert "limit" in params, "缺少 limit 参数"
        assert "tenant_id" in params, "缺少 tenant_id 参数"
        assert "filter_payload" in params, "缺少 filter_payload 参数"

        # limit 默认值为 10
        assert params["limit"].default == 10, f"limit 默认值应为 10, 实际 {params['limit'].default}"
        # tenant_id 默认值为 None
        assert params["tenant_id"].default is None, "tenant_id 默认应为 None"
        # filter_payload 默认值为 None
        assert params["filter_payload"].default is None, "filter_payload 默认应为 None"

        # 返回类型为 list[SearchResult]
        return_annotation = str(sig.return_annotation)
        assert "list[SearchResult]" in return_annotation, f"返回类型应为 list[SearchResult], 实际 {return_annotation}"

    def test_search_is_async(self) -> None:
        """验证 search 是 async 方法"""
        assert inspect.iscoroutinefunction(SearchServicePort.search), "search 必须是 async 方法"

    def test_struct_validates_with_protocol(self) -> None:
        """验证实现类可通过 Protocol 结构检查"""

        class MockSearchService:
            async def search(
                self,
                collection: str,
                query_text: str,
                limit: int = 10,
                tenant_id: str | None = None,
                filter_payload: dict | None = None,
            ) -> list[SearchResult]:
                return []

        mock = MockSearchService()
        assert isinstance(mock, SearchServicePort), "MockSearchService 应通过 SearchServicePort 结构检查"

    def test_protocol_method_ellipsis_body(self) -> None:
        """Protocol 方法体使用 ... 占位符"""
        source = inspect.getsource(SearchServicePort.search)
        assert "..." in source


class TestDenseSearchPort:
    """DenseSearchPort Protocol 验证"""

    def test_inherits_search_service_port(self) -> None:
        """DenseSearchPort 继承 SearchServicePort"""
        assert issubclass(DenseSearchPort, SearchServicePort), "DenseSearchPort 应继承 SearchServicePort"

    def test_is_runtime_checkable(self) -> None:
        """验证 @runtime_checkable 可用"""
        assert hasattr(DenseSearchPort, "__instancecheck__")

    def test_struct_validates_with_protocol(self) -> None:
        """验证实现类可通过 DenseSearchPort 结构检查"""

        class MockDenseSearch:
            async def search(
                self,
                collection: str,
                query_text: str,
                limit: int = 10,
                tenant_id: str | None = None,
                filter_payload: dict | None = None,
            ) -> list[SearchResult]:
                return []

        mock = MockDenseSearch()
        assert isinstance(mock, DenseSearchPort), "MockDenseSearch 应通过 DenseSearchPort 结构检查"


class TestSparseSearchPort:
    """SparseSearchPort Protocol 验证"""

    def test_inherits_search_service_port(self) -> None:
        """SparseSearchPort 继承 SearchServicePort"""
        assert issubclass(SparseSearchPort, SearchServicePort), "SparseSearchPort 应继承 SearchServicePort"

    def test_is_runtime_checkable(self) -> None:
        """验证 @runtime_checkable 可用"""
        assert hasattr(SparseSearchPort, "__instancecheck__")

    def test_struct_validates_with_protocol(self) -> None:
        """验证实现类可通过 SparseSearchPort 结构检查"""

        class MockSparseSearch:
            async def search(
                self,
                collection: str,
                query_text: str,
                limit: int = 10,
                tenant_id: str | None = None,
                filter_payload: dict | None = None,
            ) -> list[SearchResult]:
                return []

        mock = MockSparseSearch()
        assert isinstance(mock, SparseSearchPort), "MockSparseSearch 应通过 SparseSearchPort 结构检查"


class TestGraphSearchPort:
    """GraphSearchPort Protocol 验证"""

    def test_inherits_search_service_port(self) -> None:
        """GraphSearchPort 继承 SearchServicePort"""
        assert issubclass(GraphSearchPort, SearchServicePort), "GraphSearchPort 应继承 SearchServicePort"

    def test_is_runtime_checkable(self) -> None:
        """验证 @runtime_checkable 可用"""
        assert hasattr(GraphSearchPort, "__instancecheck__")

    def test_struct_validates_with_protocol(self) -> None:
        """验证实现类可通过 GraphSearchPort 结构检查"""

        class MockGraphSearch:
            async def search(
                self,
                collection: str,
                query_text: str,
                limit: int = 10,
                tenant_id: str | None = None,
                filter_payload: dict | None = None,
            ) -> list[SearchResult]:
                return []

        mock = MockGraphSearch()
        assert isinstance(mock, GraphSearchPort), "MockGraphSearch 应通过 GraphSearchPort 结构检查"


class TestSearchPortDocstring:
    """检索端口 docstring 验证"""

    def test_module_has_docstring(self) -> None:
        """模块有 docstring"""
        import src.domain.ports.search_service as search_module

        assert search_module.__doc__ is not None
        assert len(search_module.__doc__) > 10

    def test_search_service_port_has_docstring(self) -> None:
        """SearchServicePort 类有 docstring"""
        assert SearchServicePort.__doc__ is not None
        assert len(SearchServicePort.__doc__) > 10

    def test_dense_search_port_has_docstring(self) -> None:
        """DenseSearchPort 类有 docstring"""
        assert DenseSearchPort.__doc__ is not None
        assert len(DenseSearchPort.__doc__) > 10

    def test_sparse_search_port_has_docstring(self) -> None:
        """SparseSearchPort 类有 docstring"""
        assert SparseSearchPort.__doc__ is not None
        assert len(SparseSearchPort.__doc__) > 10

    def test_graph_search_port_has_docstring(self) -> None:
        """GraphSearchPort 类有 docstring"""
        assert GraphSearchPort.__doc__ is not None
        assert len(GraphSearchPort.__doc__) > 10
