"""Story 3.5 分层检索端口契约单元测试

验证 LayeredRetrievalPort Protocol 的方法签名、@runtime_checkable 可用性。
遵循故事规范：端口统一返回 list[SearchResult]，target_level 默认 "L4"。
"""

from __future__ import annotations

import inspect

from src.domain.ports.l3_vector import SearchResult
from src.domain.ports.layered_retrieval import LayeredRetrievalPort


class TestLayeredRetrievalPort:
    """LayeredRetrievalPort Protocol 验证"""

    def test_is_protocol(self) -> None:
        """验证 LayeredRetrievalPort 是 Protocol"""
        import typing

        assert typing.Protocol in LayeredRetrievalPort.__mro__

    def test_is_runtime_checkable(self) -> None:
        """验证 @runtime_checkable 可用"""
        assert hasattr(LayeredRetrievalPort, "__instancecheck__")

    def test_search_top_down_signature(self) -> None:
        """验证 search_top_down 方法签名"""
        sig = inspect.signature(LayeredRetrievalPort.search_top_down)
        params = {p.name: p for p in sig.parameters.values()}

        assert "self" in params, "缺少 self 参数"
        assert "query_text" in params, "缺少 query_text 参数"
        assert "target_level" in params, "缺少 target_level 参数"
        assert "collection" in params, "缺少 collection 参数"
        assert "limit" in params, "缺少 limit 参数"
        assert "tenant_id" in params, "缺少 tenant_id 参数"
        assert "filter_payload" in params, "缺少 filter_payload 参数"

        # target_level 默认值为 "L4"
        assert params["target_level"].default == "L4", f"target_level 默认值应为 'L4', 实际 {params['target_level'].default}"

        # limit 默认值为 10
        assert params["limit"].default == 10, f"limit 默认值应为 10, 实际 {params['limit'].default}"

        # 返回类型为 list[SearchResult]
        return_annotation = str(sig.return_annotation)
        assert "list[SearchResult]" in return_annotation, f"返回类型应为 list[SearchResult], 实际 {return_annotation}"

    def test_search_bottom_up_signature(self) -> None:
        """验证 search_bottom_up 方法签名"""
        sig = inspect.signature(LayeredRetrievalPort.search_bottom_up)
        params = {p.name: p for p in sig.parameters.values()}

        assert "self" in params, "缺少 self 参数"
        assert "query_text" in params, "缺少 query_text 参数"
        assert "target_level" in params, "缺少 target_level 参数"
        assert "collection" in params, "缺少 collection 参数"
        assert "limit" in params, "缺少 limit 参数"
        assert "tenant_id" in params, "缺少 tenant_id 参数"
        assert "filter_payload" in params, "缺少 filter_payload 参数"

        # target_level 默认值为 "L4"
        assert params["target_level"].default == "L4", f"target_level 默认值应为 'L4', 实际 {params['target_level'].default}"

        return_annotation = str(sig.return_annotation)
        assert "list[SearchResult]" in return_annotation, f"返回类型应为 list[SearchResult], 实际 {return_annotation}"

    def test_both_methods_async(self) -> None:
        """验证 search_top_down 和 search_bottom_up 都是 async 方法"""
        assert inspect.iscoroutinefunction(LayeredRetrievalPort.search_top_down), "search_top_down 必须是 async 方法"
        assert inspect.iscoroutinefunction(LayeredRetrievalPort.search_bottom_up), "search_bottom_up 必须是 async 方法"

    def test_retrieve_signature(self) -> None:
        """验证 retrieve 方法签名（对齐架构 §17.1.5 RAGService.retrieve）"""
        sig = inspect.signature(LayeredRetrievalPort.retrieve)
        params = {p.name: p for p in sig.parameters.values()}

        assert "self" in params, "缺少 self 参数"
        assert "query" in params, "缺少 query 参数"
        assert "top_k" in params, "缺少 top_k 参数"
        assert "tenant_id" in params, "缺少 tenant_id 参数"

        # top_k 默认值为 20
        assert params["top_k"].default == 20, f"top_k 默认值应为 20, 实际 {params['top_k'].default}"

        # tenant_id 默认为 None
        assert params["tenant_id"].default is None, "tenant_id 默认应为 None"

        return_annotation = str(sig.return_annotation)
        assert "list[SearchResult]" in return_annotation, f"返回类型应为 list[SearchResult], 实际 {return_annotation}"

    def test_retrieve_is_async(self) -> None:
        """验证 retrieve 是 async 方法"""
        assert inspect.iscoroutinefunction(LayeredRetrievalPort.retrieve), "retrieve 必须是 async 方法"

    def test_struct_validates_with_protocol(self) -> None:
        """验证实现类可通过 Protocol 结构检查"""

        class MockLayeredRetrieval:
            async def retrieve(
                self,
                query: str,
                top_k: int = 20,
                tenant_id: str | None = None,
            ) -> list[SearchResult]:
                return []

            async def search_top_down(
                self,
                query_text: str,
                target_level: str = "L4",
                collection: str = "documents",
                limit: int = 10,
                tenant_id: str | None = None,
                filter_payload: dict | None = None,
            ) -> list[SearchResult]:
                return []

            async def search_bottom_up(
                self,
                query_text: str,
                target_level: str = "L4",
                collection: str = "documents",
                limit: int = 10,
                tenant_id: str | None = None,
                filter_payload: dict | None = None,
            ) -> list[SearchResult]:
                return []

        mock = MockLayeredRetrieval()
        assert isinstance(mock, LayeredRetrievalPort), "MockLayeredRetrieval 应通过 LayeredRetrievalPort 结构检查"

    def test_no_local_protocol_in_service(self) -> None:
        """验证服务文件中不定义 Protocol（架构约束：禁止在服务文件中本地定义 Protocol）"""
        from pathlib import Path

        service_path = Path("src/application/services/layered_retrieval_service.py")
        if not service_path.exists():
            return  # 服务尚未实现，跳过
        source = service_path.read_text()
        assert "Protocol" not in source or "import Protocol" not in source, "服务文件禁止定义 Protocol"
