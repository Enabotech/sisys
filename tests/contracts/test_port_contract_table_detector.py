"""TableDetectorPort 端口契约测试

验证 TableDetectorPort 的结构化子类型合规性。
"""

from __future__ import annotations

import inspect

from src.domain.ports.table_detector import TableDetectorPort
from src.domain.value_objects.parsed_document import ParsedTable


class TestTableDetectorPortContract:
    """测试 TableDetectorPort 端口契约"""

    def test_protocol_is_runtime_checkable(self) -> None:
        """验证 Protocol 使用 @runtime_checkable 装饰器"""
        assert hasattr(TableDetectorPort, "_is_runtime_protocol")
        assert TableDetectorPort._is_runtime_protocol is True  # type: ignore[attr-defined]

    def test_detect_method_exists(self) -> None:
        """验证 detect 方法存在"""
        assert hasattr(TableDetectorPort, "detect")
        method = getattr(TableDetectorPort, "detect")
        assert callable(method)

    def test_detect_method_signature(self) -> None:
        """验证 detect(file_path, mime_type) -> list[ParsedTable]"""
        method = getattr(TableDetectorPort, "detect")
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        assert params == ["self", "file_path", "mime_type"]
        assert sig.return_annotation == "list[ParsedTable]"

    def test_compliant_implementation(self) -> None:
        """验证合规实现可通过 isinstance 检查"""

        class MockDetector:
            def detect(self, file_path: str, mime_type: str) -> list[ParsedTable]:
                return []

        detector = MockDetector()
        assert isinstance(detector, TableDetectorPort)

    def test_noncompliant_implementation_fails(self) -> None:
        """验证不合规实现无法通过 isinstance 检查"""

        class BadDetector:
            pass

        assert not isinstance(BadDetector(), TableDetectorPort)


__all__ = ["TestTableDetectorPortContract"]
