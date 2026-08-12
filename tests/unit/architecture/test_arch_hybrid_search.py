"""Story 3-1b: SDD 架构约束验证测试

验证 BM25 稀疏检索 + RRF 融合的架构合规性：
- domain 层零外部依赖（rrf_fusion.py 仅 Python 标准库）
- 依赖方向：application → domain ✓，application → infrastructure ✗
- RRF 融合函数在 domain/services 中定义
- Bm25SparseSearchService 和 HybridSearchService 在 application/services 中定义
"""

from __future__ import annotations

import importlib
import inspect


class TestDomainLayerPurity:
    """验证领域层零外部依赖"""

    def test_rrf_fusion_no_external_deps(self) -> None:
        """rrf_fusion.py 仅使用 Python 标准库（collections.abc、typing、内置函数）"""
        mod = importlib.import_module("src.domain.services.rrf_fusion")

        # 获取模块中所有导入的外部模块名
        external_modules: set[str] = set()
        for name, obj in mod.__dict__.items():
            if inspect.ismodule(obj) and hasattr(obj, "__name__"):
                external_modules.add(obj.__name__)

        # Python 标准库白名单
        stdlib_whitelist = {
            "__future__",
            "collections",
            "typing",
            "builtins",
            "abc",
            "dataclasses",
            "math",
            "enum",
            "functools",
            "itertools",
            "operator",
            "os",
            "sys",
            "json",
            "logging",
        }

        # 领域层内部导入
        domain_imports = {"src.domain.ports.l3_vector", "src.domain.ports"}

        for mod_name in external_modules:
            # 标准库或领域层内部导入 → OK
            if mod_name in stdlib_whitelist or any(mod_name == d or mod_name.startswith(d + ".") for d in domain_imports):
                continue
            # 标准库前缀（如 collections.abc）
            if mod_name.split(".")[0] in stdlib_whitelist:
                continue

            assert False, f"domain/services/rrf_fusion.py 禁止依赖外部模块: {mod_name}"

    def test_rrf_fusion_no_third_party_imports(self) -> None:
        """rrrf_fusion.py 不存在第三方库导入"""
        import ast
        from pathlib import Path

        src_path = Path("src/domain/services/rrf_fusion.py")
        source = src_path.read_text()
        tree = ast.parse(source)

        blocked_prefixes = (
            "qdrant_client",
            "fastembed",
            "FlagEmbedding",
            "numpy",
            "fastapi",
            "sqlalchemy",
            "prefect",
            "redis",
            "pydantic",
            "neo4j",
            "minio",
            "torch",
            "sentence_transformers",
        )

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(blocked_prefixes), f"rrf_fusion.py 禁止导入 {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert not node.module.startswith(blocked_prefixes), f"rrf_fusion.py 禁止导入 {node.module}"


class TestServicePlacement:
    """验证服务在正确的架构层中"""

    def test_rrf_fusion_in_domain_services(self) -> None:
        """RRF 融合函数在 domain/services 中定义"""
        from src.domain.services.rrf_fusion import RRF_K_DEFAULT, fuse

        assert callable(fuse)
        assert isinstance(RRF_K_DEFAULT, int)
        assert RRF_K_DEFAULT == 60

    def test_sparse_search_service_in_application(self) -> None:
        """Bm25SparseSearchService 在 application/services 中定义"""
        from src.application.services.sparse_search_service import Bm25SparseSearchService

        assert hasattr(Bm25SparseSearchService, "search")

    def test_hybrid_search_service_in_application(self) -> None:
        """HybridSearchService 在 application/services 中定义"""
        from src.application.services.hybrid_search_service import HybridSearchService

        assert hasattr(HybridSearchService, "search")

    def test_graph_search_service_in_application(self) -> None:
        """GraphSearchService 在 application/services 中定义"""
        from src.application.services.graph_search_service import GraphSearchService

        assert hasattr(GraphSearchService, "search")

    def test_reranker_port_in_domain(self) -> None:
        """RerankerPort 在 domain/ports 中定义"""
        from src.domain.ports.reranker import RerankerPort

        assert hasattr(RerankerPort, "rerank")

    def test_litellm_reranker_client_in_infrastructure(self) -> None:
        """LiteLLMRerankerClient 在 infrastructure/external_services 中定义"""
        from src.infrastructure.external_services.reranker.litellm_reranker_client import (
            LiteLLMRerankerClient,
        )

        assert hasattr(LiteLLMRerankerClient, "rerank")


class TestRerankerPortDomainPurity:
    """验证 RerankerPort 领域层零外部依赖"""

    def test_reranker_port_no_external_deps(self) -> None:
        """reranker.py 仅使用 Python 标准库 + SearchResult"""
        import ast
        from pathlib import Path

        src_path = Path("src/domain/ports/reranker.py")
        source = src_path.read_text()
        tree = ast.parse(source)

        blocked_prefixes = (
            "pydantic",
            "litellm",
            "torch",
            "sentence_transformers",
            "transformers",
            "qdrant_client",
            "fastapi",
            "sqlalchemy",
            "prefect",
            "redis",
            "neo4j",
            "minio",
        )

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(blocked_prefixes), f"reranker.py 禁止导入 {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert not node.module.startswith(blocked_prefixes), f"reranker.py 禁止导入 {node.module}"


class TestDependencyDirection:
    """验证依赖方向：application → domain ✓，application → infrastructure ✗"""

    def test_sparse_service_imports_domain_only(self) -> None:
        """Bm25SparseSearchService 仅导入 domain 和标准库，不导入 infrastructure"""
        import ast
        from pathlib import Path

        src_path = Path("src/application/services/sparse_search_service.py")
        source = src_path.read_text()
        tree = ast.parse(source)

        blocked_prefixes = (
            "src.infrastructure",
            "qdrant_client",
            "fastapi",
            "sqlalchemy",
            "prefect",
            "redis",
        )

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    assert not node.module.startswith(blocked_prefixes), (
                        f"sparse_search_service.py 禁止导入 infrastructure: {node.module}"
                    )

    def test_hybrid_service_imports_application_and_domain(self) -> None:
        """HybridSearchService 仅导入 domain + application，不导入 infrastructure"""
        import ast
        from pathlib import Path

        src_path = Path("src/application/services/hybrid_search_service.py")
        source = src_path.read_text()
        tree = ast.parse(source)

        blocked_prefixes = (
            "src.infrastructure",
            "qdrant_client",
            "fastapi",
            "sqlalchemy",
            "prefect",
            "redis",
        )

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    assert not node.module.startswith(blocked_prefixes), (
                        f"hybrid_search_service.py 禁止导入 infrastructure: {node.module}"
                    )

    def test_graph_search_service_imports_domain_only(self) -> None:
        """GraphSearchService 仅导入 domain，不导入 infrastructure"""
        import ast
        from pathlib import Path

        src_path = Path("src/application/services/graph_search_service.py")
        source = src_path.read_text()
        tree = ast.parse(source)

        blocked_prefixes = (
            "src.infrastructure",
            "qdrant_client",
            "fastapi",
            "sqlalchemy",
            "prefect",
            "redis",
        )

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    assert not node.module.startswith(blocked_prefixes), (
                        f"graph_search_service.py 禁止导入 infrastructure: {node.module}"
                    )

    def test_litellm_reranker_client_imports_domain_only(self) -> None:
        """LiteLLMRerankerClient 仅导入 domain，不导入 application"""
        import ast
        from pathlib import Path

        src_path = Path("src/infrastructure/external_services/reranker/litellm_reranker_client.py")
        source = src_path.read_text()
        tree = ast.parse(source)

        blocked_prefixes = (
            "src.application",
            "src.interfaces",
        )

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    assert not node.module.startswith(blocked_prefixes), (
                        f"litellm_reranker_client.py 禁止导入 application/interfaces: {node.module}"
                    )


class TestPortDefinitions:
    """端口定义完整性验证"""

    def test_search_result_in_l3_vector(self) -> None:
        """SearchResult TypedDict 在 domain/ports/l3_vector.py 中定义"""
        from src.domain.ports.l3_vector import SearchResult

        # TypedDict 字段验证
        assert "id" in SearchResult.__annotations__
        assert "score" in SearchResult.__annotations__
        assert "payload" in SearchResult.__annotations__

    def test_sparse_embedding_in_embedding_service(self) -> None:
        """SparseEmbedding TypedDict 在 domain/ports/embedding_service.py 中定义"""
        from src.domain.ports.embedding_service import SparseEmbedding

        assert "indices" in SparseEmbedding.__annotations__
        assert "values" in SparseEmbedding.__annotations__
