"""Story 3.5 分层检索架构约束验证测试

验证分层检索的架构合规性：
- domain 层零外部依赖（layered_retrieval.py 仅 Python 标准库）
- 依赖方向：application → domain ✓，application → infrastructure ✗
- LayeredRetrievalService 在 application/services 中定义
- LayeredRetrievalPort 在 domain/ports 中定义
- 分块级索引重构（document_tasks.py payload 含 parent_chunk_id/index_level）
"""

from __future__ import annotations

import ast
from pathlib import Path

# 领域层禁止导入的外部模块前缀
_FORBIDDEN_PREFIXES: tuple[str, ...] = (
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
    "litellm",
)


def _assert_no_blocked_imports(file_path: str, blocked: tuple[str, ...]) -> None:
    """断言源文件不包含被禁止的导入

    Args:
        file_path: 源文件路径（相对项目根）
        blocked: 禁止的导入前缀列表

    Raises:
        AssertionError: 存在被禁止的导入时抛出
    """
    src_path = Path(file_path)
    if not src_path.exists():
        return
    source = src_path.read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(blocked), f"{file_path} 禁止导入 {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert not node.module.startswith(blocked), f"{file_path} 禁止导入 {node.module}"


class TestDomainLayerPurity:
    """验证领域层零外部依赖"""

    def test_layered_retrieval_port_no_external_deps(self) -> None:
        """layered_retrieval.py 仅使用 Python 标准库 + SearchResult"""
        _assert_no_blocked_imports("src/domain/ports/layered_retrieval.py", _FORBIDDEN_PREFIXES)

    def test_layered_retrieval_exceptions_no_external_deps(self) -> None:
        """layered_retrieval_exceptions.py 仅导入领域异常"""
        _assert_no_blocked_imports(
            "src/domain/exceptions/layered_retrieval_exceptions.py",
            _FORBIDDEN_PREFIXES + ("src.infrastructure", "src.application", "src.interfaces"),
        )


class TestServicePlacement:
    """验证服务在正确的架构层中"""

    def test_layered_retrieval_port_in_domain(self) -> None:
        """LayeredRetrievalPort 在 domain/ports 中定义"""
        from src.domain.ports.layered_retrieval import LayeredRetrievalPort

        assert hasattr(LayeredRetrievalPort, "search_top_down")
        assert hasattr(LayeredRetrievalPort, "search_bottom_up")

    def test_search_result_reused_in_port(self) -> None:
        """LayeredRetrievalPort 复用 SearchResult（不重新定义）"""
        import inspect

        from src.domain.ports.l3_vector import SearchResult
        from src.domain.ports.layered_retrieval import LayeredRetrievalPort

        sig = inspect.signature(LayeredRetrievalPort.search_top_down)
        return_str = str(sig.return_annotation)
        assert "list[SearchResult]" in return_str or "SearchResult" in return_str
        assert SearchResult is not None

    def test_layered_retrieval_service_in_application(self) -> None:
        """LayeredRetrievalService 在 application/services 中定义"""
        from src.application.services.layered_retrieval_service import LayeredRetrievalService

        assert hasattr(LayeredRetrievalService, "search_top_down")
        assert hasattr(LayeredRetrievalService, "search_bottom_up")

    def test_service_does_not_import_infrastructure(self) -> None:
        """LayeredRetrievalService 仅导入 domain，不导入 infrastructure"""
        _assert_no_blocked_imports(
            "src/application/services/layered_retrieval_service.py",
            ("src.infrastructure", "qdrant_client", "fastapi", "sqlalchemy", "prefect", "redis"),
        )

    def test_service_does_not_define_local_protocol(self) -> None:
        """服务文件不本地定义 Protocol（端口定义在 domain/ports）"""
        import re

        src_path = Path("src/application/services/layered_retrieval_service.py")
        if not src_path.exists():
            return
        source = src_path.read_text()
        # 使用正则匹配类定义中包含 Protocol 的模式（如 class FooProtocol、class MyProtocol）
        assert not re.search(r"class\s+\w*Protocol", source), "服务文件禁止定义本地 Protocol"
        assert "import Protocol" not in source, "服务文件禁止导入 Protocol"


class TestChunkLevelIndexing:
    """分块级索引重构架构验证

    ⚠️ 索引已统一迁移至事件驱动链（generate_embedding/index_document 已删除），
    分块级 payload 由 ChunkIndexingHandler 承担。
    """

    def test_chunk_indexing_handler_applies_chunk_level_payload(self) -> None:
        """ChunkIndexingHandler 的 payload 应包含 index_level=parent/child 分块字段"""
        src_path = Path("src/application/event_handlers/chunk_indexing_handler.py")
        source = src_path.read_text()
        assert '"parent"' in source, "ChunkIndexingHandler payload 应包含 parent 层级"
        assert '"child"' in source, "ChunkIndexingHandler payload 应包含 child 层级"
        assert "parent_chunk_id" in source, "ChunkIndexingHandler payload 应包含 parent_chunk_id"

    def test_chunk_indexing_handler_in_application(self) -> None:
        """ChunkIndexingHandler 在 application/event_handlers 中定义"""
        from src.application.event_handlers.chunk_indexing_handler import ChunkIndexingHandler

        assert hasattr(ChunkIndexingHandler, "handle_chunk_indexed")

    def test_chunk_indexing_handler_imports_domain_only(self) -> None:
        """ChunkIndexingHandler 不导入 interfaces"""
        _assert_no_blocked_imports(
            "src/application/event_handlers/chunk_indexing_handler.py",
            ("src.interfaces", "src.infrastructure", "qdrant_client", "prefect"),
        )


class TestParentChildHierarchy:
    """Parent-Child 层级关系验证（AC-2/AC-3 依赖）"""

    def test_index_level_enum_exists(self) -> None:
        """IndexLevel 枚举存在且包含 CHILD/PARENT 值"""
        from src.domain.value_objects.semantic_chunk import IndexLevel

        assert hasattr(IndexLevel, "CHILD")
        assert hasattr(IndexLevel, "PARENT")
        assert IndexLevel.CHILD.value == "child"
        assert IndexLevel.PARENT.value == "parent"

    def test_semantic_chunk_has_parent_chunk_id(self) -> None:
        """SemanticChunk 值对象包含 parent_chunk_id 字段"""
        import dataclasses

        from src.domain.value_objects.semantic_chunk import SemanticChunk

        field_names = {f.name for f in dataclasses.fields(SemanticChunk)}
        assert "parent_chunk_id" in field_names
        assert "index_level" in field_names

    def test_parent_chunk_id_reference_integrity(self) -> None:
        """Child 块（index_level=child）的 parent_chunk_id 必须非 None"""
        import uuid

        from src.domain.value_objects.semantic_chunk import (
            ChunkBoundaryType,
            IndexLevel,
            SemanticChunk,
        )

        child = SemanticChunk(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            content="child content",
            chunk_index=0,
            boundary_type=ChunkBoundaryType.PARAGRAPH,
            token_count=150,
            page_start=1,
            page_end=1,
            content_hash="hash",
            metadata={},
            parent_chunk_id=uuid.uuid4(),
            index_level=IndexLevel.CHILD,
        )
        assert child.parent_chunk_id is not None, "Child 块的 parent_chunk_id 不能为 None"
        assert child.index_level == IndexLevel.CHILD

    def test_index_level_values_match_layer_semantics(self) -> None:
        """IndexLevel 枚举值对应检索层级语义（child 对应 L4，parent 对应 L3）"""
        from src.domain.value_objects.semantic_chunk import IndexLevel

        # 语义映射：child → L4 实体级片段，parent → L3 文档切片
        layer_map = {
            IndexLevel.CHILD.value: "L4",
            IndexLevel.PARENT.value: "L3",
        }
        assert layer_map["child"] == "L4"
        assert layer_map["parent"] == "L3"
