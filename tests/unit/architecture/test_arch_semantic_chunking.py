"""语义分块架构约束验证测试

验证六边形架构约束：
- 领域层零外部依赖
- 异常继承链正确
- SemanticChunkerPort 是 runtime_checkable Protocol
- SemanticChunk 为 frozen=True dataclass
- SemanticChunkerImpl 在基础设施层
- 运行时兼容性检查
"""

from __future__ import annotations

import dataclasses

from src.domain.ports.registry import _global_registry
from src.domain.ports.semantic_chunker import SemanticChunkerPort
from src.domain.value_objects.semantic_chunk import ChunkBoundaryType, ChunkingConfig, SemanticChunk


class TestArchSemanticChunking:
    """验证语义分块架构约束"""

    def test_domain_value_object_no_external_deps(self) -> None:
        """领域层值对象仅使用标准库"""
        import ast

        file_path = "src/domain/value_objects/semantic_chunk.py"
        with open(file_path) as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.startswith("__future__") or alias.name in (
                        "dataclasses",
                        "uuid",
                        "enum",
                        "typing",
                        "hashlib",
                    ), f"领域层禁止导入外部依赖: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module is not None:
                    assert node.module.startswith("__future__") or node.module in (
                        "dataclasses",
                        "uuid",
                        "enum",
                        "typing",
                        "hashlib",
                    ), f"领域层禁止导入外部依赖: {node.module}"

    def test_domain_port_no_external_deps(self) -> None:
        """领域层端口仅使用标准库"""
        import ast

        file_path = "src/domain/ports/semantic_chunker.py"
        with open(file_path) as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.startswith("__future__") or alias.name in ("typing",), (
                        f"领域层端口禁止导入外部依赖: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module is not None:
                    allowed = (
                        "__future__",
                        "typing",
                        "src.domain.value_objects.semantic_chunk",
                        "src.domain.value_objects.parsed_document",
                    )
                    assert node.module in allowed, f"领域层端口禁止导入: {node.module}"

    def test_chunking_error_inheritance_chain(self) -> None:
        """ChunkingError 继承链正确"""
        from src.domain.exceptions import BusinessException, BusinessRuleViolationError, ChunkingError

        assert issubclass(ChunkingError, BusinessRuleViolationError)
        assert issubclass(BusinessRuleViolationError, BusinessException)
        # 验证编码
        assert ChunkingError.code == "EXCEPTION_218"

    def test_semantic_chunker_port_is_runtime_checkable(self) -> None:
        """SemanticChunkerPort 是 runtime_checkable Protocol"""
        # 验证是 Protocol：_is_protocol 标志存在
        assert hasattr(SemanticChunkerPort, "_is_protocol"), "Protocol 应包含 _is_protocol 标志"
        # 验证 runtime_checkable：_is_runtime_protocol 标志存在
        assert hasattr(SemanticChunkerPort, "_is_runtime_protocol"), (
            "runtime_checkable Protocol 应包含 _is_runtime_protocol 标志"
        )
        assert SemanticChunkerPort._is_runtime_protocol, "runtime_checkable Protocol 的 _is_runtime_protocol 应为 True"  # type: ignore[attr-defined]
        # 验证是类
        assert isinstance(SemanticChunkerPort, type)

    def test_semantic_chunk_is_frozen_dataclass(self) -> None:
        """SemanticChunk 是 frozen=True dataclass"""
        assert dataclasses.is_dataclass(SemanticChunk)
        assert SemanticChunk.__dataclass_params__.frozen  # type: ignore[attr-defined]

    def test_chunking_config_is_frozen_dataclass(self) -> None:
        """ChunkingConfig 是 frozen=True dataclass"""
        assert dataclasses.is_dataclass(ChunkingConfig)
        assert ChunkingConfig.__dataclass_params__.frozen  # type: ignore[attr-defined]

    def test_chunk_boundary_type_is_str_enum(self) -> None:
        """ChunkBoundaryType 是 str 枚举"""
        assert issubclass(ChunkBoundaryType, str)
        assert issubclass(ChunkBoundaryType, object)

    def test_semantic_chunker_impl_in_infrastructure(self) -> None:
        """SemanticChunkerImpl 在基础设施层"""
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        module = SemanticChunkerImpl.__module__
        assert "infrastructure" in module, f"预期在 infrastructure 层，实际: {module}"

    def test_semantic_chunker_impl_isinstance_port(self) -> None:
        """SemanticChunkerImpl 通过运行时兼容性检查"""
        from src.infrastructure.document_parsing.semantic_chunker_impl import SemanticChunkerImpl

        # 验证 isinstance 检查通过（runtime_checkable）
        instance = SemanticChunkerImpl()
        # Protocol 的 isinstance 检查在运行时通过 duck typing 验证
        assert isinstance(instance, SemanticChunkerPort)

    def test_semantic_chunker_port_registered(self) -> None:
        """semantic_chunker 端口已注册"""
        spec = _global_registry.get("semantic_chunker")
        assert spec is not None
        assert spec.name == "semantic_chunker"
        assert spec.version == "v1.0.0"

    def test_semantic_chunking_handler_registered(self) -> None:
        """semantic_chunking_handler 端口已注册"""
        spec = _global_registry.get("semantic_chunking_handler")
        assert spec is not None
        assert spec.name == "semantic_chunking_handler"

    def test_semantic_chunking_service_registered(self) -> None:
        """semantic_chunking_service 端口已注册"""
        spec = _global_registry.get("semantic_chunking_service")
        assert spec is not None
        assert spec.name == "semantic_chunking_service"
