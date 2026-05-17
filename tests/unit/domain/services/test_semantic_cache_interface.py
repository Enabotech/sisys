"""SemanticCache Protocol type checking tests."""

from __future__ import annotations

import inspect

from src.application.ports.semantic_cache import SemanticCache


class TestSemanticCacheInterface:
    """SemanticCache Protocol 接口测试"""

    def test_protocol_has_required_methods(self) -> None:
        """SemanticCache 应定义所有必需的抽象方法"""
        assert hasattr(SemanticCache, "get")
        assert hasattr(SemanticCache, "set")
        assert hasattr(SemanticCache, "invalidate")

    def test_get_signature(self) -> None:
        """get 方法应有正确的签名"""
        sig = inspect.signature(SemanticCache.get)
        params = list(sig.parameters.keys())
        assert "query_embedding" in params
        assert "threshold" in params

    def test_set_signature(self) -> None:
        """set 方法应有正确的签名"""
        sig = inspect.signature(SemanticCache.set)
        params = list(sig.parameters.keys())
        assert "query_embedding" in params
        assert "result" in params
        assert "ttl" in params

    def test_invalidate_signature(self) -> None:
        """invalidate 方法应有正确的签名"""
        sig = inspect.signature(SemanticCache.invalidate)
        params = list(sig.parameters.keys())
        assert "cache_key" in params

    def test_protocol_is_protocol(self) -> None:
        """SemanticCache 应是 Protocol 类型"""
        # Protocol classes have _is_protocol flag
        assert getattr(SemanticCache, "_is_protocol", False) is True
