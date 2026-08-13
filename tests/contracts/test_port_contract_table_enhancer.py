"""TableSemanticEnhancerPort 端口契约测试

验证 TableSemanticEnhancerPort 的结构化子类型合规性。
"""

from __future__ import annotations

import inspect

from src.domain.ports.table_enhancer import TableSemanticEnhancerPort
from src.domain.value_objects.parsed_document import ParsedTable


class TestTableSemanticEnhancerPortContract:
    """测试 TableSemanticEnhancerPort 端口契约"""

    def test_protocol_is_runtime_checkable(self) -> None:
        """验证 Protocol 使用 @runtime_checkable 装饰器"""
        assert hasattr(TableSemanticEnhancerPort, "_is_runtime_protocol")
        assert TableSemanticEnhancerPort._is_runtime_protocol is True

    def test_enhance_method_exists(self) -> None:
        """验证 enhance 方法存在"""
        assert hasattr(TableSemanticEnhancerPort, "enhance")
        method = getattr(TableSemanticEnhancerPort, "enhance")
        assert callable(method)

    def test_enhance_method_signature(self) -> None:
        """验证 enhance(tables, mime_type) -> list[ParsedTable]"""
        method = getattr(TableSemanticEnhancerPort, "enhance")
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        assert params == ["self", "tables", "mime_type"]
        assert sig.return_annotation == "list[ParsedTable]"

    def test_enhance_is_sync(self) -> None:
        """enhance 是同步方法（非 async）"""
        method = getattr(TableSemanticEnhancerPort, "enhance")
        assert not inspect.iscoroutinefunction(method)

    def test_compliant_implementation(self) -> None:
        """验证合规实现可通过 isinstance 检查"""

        class MockEnhancer:
            def enhance(self, tables: list[ParsedTable], mime_type: str) -> list[ParsedTable]:
                return tables

        enhancer = MockEnhancer()
        assert isinstance(enhancer, TableSemanticEnhancerPort)

    def test_noncompliant_implementation_fails(self) -> None:
        """验证不合规实现无法通过 isinstance 检查"""

        class BadEnhancer:
            pass

        assert not isinstance(BadEnhancer(), TableSemanticEnhancerPort)


__all__ = ["TestTableSemanticEnhancerPortContract"]
