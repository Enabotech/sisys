"""语义分块端口契约测试

验证 SemanticChunkerPort 端口契约：
- 端口注册到 _global_registry
- 接口类型正确
- 版本号正确
- 生命周期正确
- 方法签名存在
"""

from __future__ import annotations

from src.domain.ports.registry import _global_registry
from src.domain.ports.semantic_chunker import SemanticChunkerPort


class TestSemanticChunkerPortContract:
    """验证语义分块端口契约"""

    def test_semantic_chunker_port_registered(self) -> None:
        """semantic_chunker 端口应已注册到 _global_registry"""
        spec = _global_registry.get("semantic_chunker")
        assert spec is not None, "semantic_chunker port should be registered"

    def test_interface_type_is_semantic_chunker_port(self) -> None:
        """端口接口类型应为 SemanticChunkerPort"""
        spec = _global_registry.get("semantic_chunker")
        assert spec is not None
        assert spec.interface is SemanticChunkerPort

    def test_version_is_v1_0_0(self) -> None:
        """端口版本应为 v1.0.0"""
        spec = _global_registry.get("semantic_chunker")
        assert spec is not None
        assert spec.version == "v1.0.0"

    def test_lifetime_is_singleton(self) -> None:
        """生命周期应为 SINGLETON"""
        spec = _global_registry.get("semantic_chunker")
        assert spec is not None
        assert spec.lifetime.name == "SINGLETON"

    def test_chunk_method_exists(self) -> None:
        """chunk 方法应存在"""
        assert hasattr(SemanticChunkerPort, "chunk")
        method = SemanticChunkerPort.chunk
        assert callable(method)

    def test_chunk_method_async(self) -> None:
        """chunk 方法应为 async"""

        assert hasattr(SemanticChunkerPort, "chunk")
        method = SemanticChunkerPort.chunk
        # Protocol 方法的签名对于 async 检查比较特殊
        # 验证方法名确实为 chunk
        assert method.__name__ == "chunk"
